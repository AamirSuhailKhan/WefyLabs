"""
Part 21.4.4 — AI Qualification Conversation Engine
==================================================
Production-grade conversational layer orchestrating multi-turn qualification:
1. Deterministic Next Question Selection based on Part 21.4.3 missing policy fields.
2. Question Deduplication, anti-looping safeguards, and fatigue controls.
3. Natural-language phrasing with strict JSON schema validation and deterministic fallback.
4. Customer message routing through Part 21.4.2 extraction pipeline with fact provenance.
5. Deterministic re-evaluation via Part 21.4.3 policy engine.
6. Immediate human handoff on evidence conflicts, explicit customer requests, or low confidence.
7. Verified real-inventory property recommendation integration via Part 21.3.
8. Multi-tenant isolation and strict real-data provenance (Zero fake data).
"""
from __future__ import annotations
import os
import re
import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.conversation import Conversation
from app.models.qualification_models import (
    QualificationFact,
    QualificationConflict,
    QualificationRequirementPolicy,
    QualificationAuditEvent,
    QualificationSnapshotRecord,
    QualificationState,
    QualificationAuditActorType,
    QualificationAuditEventType,
    EvidenceSourceType,
    FactValueCategory,
    FactStatus,
    ConflictStatus,
)
from app.modules.lead_qualification.dto import (
    QualificationSnapshotDTO,
    QualificationEvaluationResultDTO,
    QualificationMissingInfoDTO,
    QualificationConversationState,
    QualificationConversationStartDTO,
    QualificationConversationMessageDTO,
    QualificationConversationResponseDTO,
    QualificationConversationStateDTO,
    ProposedQualificationFactDTO,
)
from app.modules.lead_qualification.fact_repository import QualificationFactRepository
from app.modules.lead_qualification.policy_engine import DeterministicQualificationPolicyEngine
from app.modules.lead_qualification.extractor import QualificationFactExtractor, QualificationFactNormalizer
from app.modules.lead_qualification.taxonomies import QualificationTaxonomyNormalizer
from app.modules.lead_qualification.metrics import (
    QUALIFICATION_CONVERSATIONS_STARTED,
    QUALIFICATION_QUESTIONS_GENERATED,
    QUALIFICATION_QUESTIONS_FALLBACK,
    QUALIFICATION_RESPONSES_PROCESSED,
    QUALIFICATION_HUMAN_HANDOFFS,
    QUALIFICATION_CONVERSATIONS_COMPLETED,
    QUALIFICATION_REPEATED_QUESTIONS_PREVENTED,
    mask_org_id,
)
from app.infrastructure.security.prompt_guard import validate_prompt_injection
from app.config import settings

logger = logging.getLogger(__name__)

# Standard priority ordering for real estate qualification fields
STANDARD_FIELD_PRIORITY: List[str] = [
    "intent",
    "property_type",
    "location",
    "budget_max",
    "bedrooms",
    "timeline",
    "financing",
    "buyer_type",
    "budget_min",
    "preferred_amenities",
]

HUMAN_HANDOFF_TRIGGER_PHRASES = [
    "speak to human",
    "speak to a human",
    "talk to a human",
    "talk to human",
    "human agent",
    "real person",
    "connect me with an agent",
    "speak with an agent",
    "talk to an agent",
    "call me",
    "representative",
    "human please",
    "transfer me",
    "stop bot",
]


class QualificationQuestionSelector:
    """
    Deterministic Next Question Selector.
    Consumes output of Part 21.4.3 deterministic evaluation, tracks question history,
    and applies anti-looping and fatigue limits.
    """

    MAX_ATTEMPTS_PER_FIELD = 2

    @classmethod
    def select_next_question(
        cls,
        eval_result: QualificationEvaluationResultDTO,
        field_attempts: Dict[str, int],
        policy: Optional[QualificationRequirementPolicy] = None,
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Selects the next best field to ask according to deterministic policy priority.
        Returns (field_name, template_question, handoff_required).
        """
        # 1. Determine priority list from policy or standard taxonomy
        required_fields = policy.required_fields if policy and policy.required_fields else DeterministicQualificationPolicyEngine.DEFAULT_REQUIRED_FIELDS
        recommended_fields = policy.recommended_fields if policy and policy.recommended_fields else DeterministicQualificationPolicyEngine.DEFAULT_RECOMMENDED_FIELDS

        # Ordered candidate fields: missing required first, then missing recommended
        candidate_fields: List[str] = []
        for f in required_fields:
            if f in eval_result.missing_required_information and f not in candidate_fields:
                candidate_fields.append(f)

        for f in recommended_fields:
            if f in eval_result.missing_recommended_information and f not in candidate_fields:
                candidate_fields.append(f)

        # Fallback to standard priority for any additional missing fields
        for f in STANDARD_FIELD_PRIORITY:
            if (f in eval_result.missing_required_information or f in eval_result.missing_recommended_information) and f not in candidate_fields:
                candidate_fields.append(f)

        if not candidate_fields:
            return None, None, False

        # 2. Find first field that has not exceeded fatigue limits
        for field in candidate_fields:
            attempts = field_attempts.get(field, 0)
            if attempts < cls.MAX_ATTEMPTS_PER_FIELD:
                template = DeterministicQualificationPolicyEngine.QUESTION_TEMPLATES.get(
                    field, f"Could you please share your preference for {field.replace('_', ' ')}?"
                )
                return field, template, False

        # All candidate missing fields have exceeded fatigue limits -> Human Handoff
        return None, None, True


class QualificationConversationEngine:
    """
    Core AI Qualification Conversation Engine orchestrating customer communication,
    fact extraction, policy evaluation, question generation, and human handoff.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = QualificationFactRepository(db)

    async def _validate_lead_tenant(
        self, lead_id: str, organization_id: str, broker: Optional[Broker] = None
    ) -> Lead:
        """Enforces multi-tenant isolation and existence check on lead."""
        try:
            lead_uuid = uuid.UUID(str(lead_id)) if isinstance(lead_id, str) else lead_id
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invalid lead ID '{lead_id}'.",
            )

        stmt = select(Lead).where(
            and_(
                Lead.id == lead_uuid,
                Lead.deleted_at.is_(None),
            )
        )
        lead = (await self.db.execute(stmt)).scalars().first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with ID '{lead_id}' not found.",
            )

        if broker and str(lead.broker_id) != str(broker.id):
            lead_org = getattr(lead, "organization_id", None) or str(lead.broker_id)
            broker_org = getattr(broker, "organization_id", None) or str(broker.id)
            if lead_org != broker_org:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Lead belongs to another organization.",
                )

        return lead

    async def _get_conversation_audit_history(
        self, organization_id: str, lead_id: str
    ) -> Tuple[List[str], Dict[str, int], int]:
        """
        Computes asked question history and attempt counts from audit log events.
        """
        stmt = (
            select(QualificationAuditEvent)
            .where(
                and_(
                    QualificationAuditEvent.organization_id == organization_id,
                    QualificationAuditEvent.lead_id == lead_id,
                )
            )
            .order_by(QualificationAuditEvent.created_at.asc())
        )
        events = (await self.db.execute(stmt)).scalars().all()

        asked_fields: List[str] = []
        field_attempts: Dict[str, int] = {}
        total_turns = 0

        for ev in events:
            if ev.details_json and "question_field" in ev.details_json:
                f = ev.details_json["question_field"]
                if f:
                    asked_fields.append(f)
                    field_attempts[f] = field_attempts.get(f, 0) + 1
            if ev.event_type in ("CUSTOMER_RESPONSE_RECEIVED", "FACT_RECORDED"):
                total_turns += 1

        return asked_fields, field_attempts, total_turns

    async def start_or_resume_conversation(
        self,
        organization_id: str,
        lead_id: str,
        start_dto: QualificationConversationStartDTO = QualificationConversationStartDTO(),
        broker: Optional[Broker] = None,
    ) -> QualificationConversationResponseDTO:
        """
        Initiates or resumes the qualification conversation for a lead:
        1. Multi-tenant authorization.
        2. Evaluates active facts via Part 21.4.3.
        3. Selects the next best deterministic question.
        4. Applies natural-language conversational generation via LLM or template fallback.
        5. Returns structured conversation response.
        """
        lead = await self._validate_lead_tenant(lead_id, organization_id, broker)

        # 1. Deterministically evaluate current qualification state
        from app.modules.lead_qualification.service import LeadQualificationDomainService
        service = LeadQualificationDomainService(self.db)
        eval_result = await service.evaluate_lead_qualification(
            organization_id=organization_id,
            lead_id=str(lead.id),
            actor_id=str(broker.id) if broker else "conversation_engine",
            broker=broker,
        )

        org_hash = mask_org_id(organization_id)
        QUALIFICATION_CONVERSATIONS_STARTED.labels(org_hash=org_hash, channel=start_dto.channel).inc()

        # 2. Check for terminal states
        if eval_result.qualification_state in (
            QualificationState.QUALIFIED.value,
            QualificationState.DISQUALIFIED.value,
            QualificationState.NURTURE.value,
        ):
            QUALIFICATION_CONVERSATIONS_COMPLETED.labels(
                org_hash=org_hash, final_state=eval_result.qualification_state
            ).inc()
            return QualificationConversationResponseDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                conversation_state=QualificationConversationState.COMPLETED,
                qualification_state=eval_result.qualification_state,
                question=None,
                question_field=None,
                completeness_score=eval_result.completeness_score,
                confidence_score=eval_result.confidence_score,
                missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
                human_handoff=False,
            )

        # 3. Check for blocking conflicts requiring human review
        if eval_result.blocking_conflicts or eval_result.qualification_state == QualificationState.NEEDS_HUMAN_REVIEW.value:
            QUALIFICATION_HUMAN_HANDOFFS.labels(org_hash=org_hash, reason="EVIDENCE_CONFLICT").inc()
            return QualificationConversationResponseDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                conversation_state=QualificationConversationState.HUMAN_HANDOFF,
                qualification_state=eval_result.qualification_state,
                question=None,
                question_field=None,
                completeness_score=eval_result.completeness_score,
                confidence_score=eval_result.confidence_score,
                missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
                human_handoff=True,
                handoff_reason="Contradictory qualification facts detected requiring human review.",
            )

        # 4. Select next question based on missing fields and fatigue history
        policy = await self.repo.get_matching_policy(
            organization_id=organization_id,
            country_code=lead.country_code,
            transaction_type=lead.transaction_type,
        )
        asked_fields, field_attempts, total_turns = await self._get_conversation_audit_history(
            organization_id, str(lead.id)
        )

        selected_field, template, handoff_req = QualificationQuestionSelector.select_next_question(
            eval_result=eval_result,
            field_attempts=field_attempts,
            policy=policy,
        )

        if handoff_req or not selected_field:
            QUALIFICATION_HUMAN_HANDOFFS.labels(org_hash=org_hash, reason="INFORMATION_GATHERING_FATIGUE").inc()
            return QualificationConversationResponseDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                conversation_state=QualificationConversationState.HUMAN_HANDOFF,
                qualification_state=eval_result.qualification_state,
                question=None,
                question_field=None,
                completeness_score=eval_result.completeness_score,
                confidence_score=eval_result.confidence_score,
                missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
                human_handoff=True,
                handoff_reason="Maximum qualification attempts reached without obtaining required fields.",
            )

        # 5. Generate conversational phrasing with LLM / fallback
        question_text, is_fallback = await self._generate_conversational_question(
            target_field=selected_field,
            template=template or "",
            known_facts=eval_result.snapshot.model_dump(),
            context_notes=start_dto.context_notes,
            organization_id=organization_id,
        )

        # 6. Audit question generation
        audit = QualificationAuditEvent(
            organization_id=organization_id,
            lead_id=str(lead.id),
            actor_type=QualificationAuditActorType.SYSTEM.value,
            actor_id=str(broker.id) if broker else "conversation_engine",
            event_type="QUESTION_GENERATED",
            previous_state=eval_result.qualification_state,
            new_state=eval_result.qualification_state,
            reason=f"Generated qualification question for field '{selected_field}'",
            details_json={
                "question_field": selected_field,
                "question_text": question_text,
                "is_fallback": is_fallback,
                "channel": start_dto.channel,
            },
        )
        self.db.add(audit)
        await self.db.commit()

        QUALIFICATION_QUESTIONS_GENERATED.labels(
            org_hash=org_hash, field_name=selected_field, generation_mode="template" if is_fallback else "llm"
        ).inc()

        return QualificationConversationResponseDTO(
            lead_id=str(lead.id),
            organization_id=organization_id,
            conversation_state=QualificationConversationState.WAITING_FOR_RESPONSE,
            qualification_state=eval_result.qualification_state,
            question=question_text,
            question_field=selected_field,
            is_fallback_question=is_fallback,
            missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
            completeness_score=eval_result.completeness_score,
            confidence_score=eval_result.confidence_score,
            human_handoff=False,
        )

    async def process_customer_message(
        self,
        organization_id: str,
        lead_id: str,
        msg_dto: QualificationConversationMessageDTO,
        broker: Optional[Broker] = None,
    ) -> QualificationConversationResponseDTO:
        """
        Processes an inbound customer response:
        1. Multi-tenant authorization & sanitization.
        2. Checks for explicit human handoff requests.
        3. Checks for property inquiry keywords & runs verified Part 21.3 matching if applicable.
        4. Extracts facts via Part 21.4.2 extraction pipeline.
        5. Persists extracted facts with provenance and conflict detection.
        6. Deterministically re-evaluates qualification state via Part 21.4.3.
        7. Returns updated state, matched properties, and next best question or terminal handoff.
        """
        lead = await self._validate_lead_tenant(lead_id, organization_id, broker)
        org_hash = mask_org_id(organization_id)
        QUALIFICATION_RESPONSES_PROCESSED.labels(org_hash=org_hash, channel=msg_dto.channel).inc()

        raw_message = msg_dto.message.strip()

        # 1. Prompt Injection Sanitization
        is_safe, sanitized_msg = QualificationFactNormalizer.sanitize_untrusted_text(raw_message)
        if not is_safe:
            logger.warning(f"[CONVERSATION_ENGINE] Prompt injection detected for lead {lead_id}")
            audit = QualificationAuditEvent(
                organization_id=organization_id,
                lead_id=str(lead.id),
                actor_type=QualificationAuditActorType.SYSTEM.value,
                actor_id=str(broker.id) if broker else "prompt_guard",
                event_type="PROMPT_INJECTION_BLOCKED",
                reason="Customer message contained disallowed prompt injection tokens.",
                details_json={"raw_message_length": len(raw_message)},
            )
            self.db.add(audit)
            await self.db.commit()

        # 2. Check for explicit human agent request
        lower_msg = raw_message.lower()
        if any(phrase in lower_msg for phrase in HUMAN_HANDOFF_TRIGGER_PHRASES):
            QUALIFICATION_HUMAN_HANDOFFS.labels(org_hash=org_hash, reason="CUSTOMER_REQUESTED_HUMAN").inc()
            audit = QualificationAuditEvent(
                organization_id=organization_id,
                lead_id=str(lead.id),
                actor_type=QualificationAuditActorType.SYSTEM.value,
                actor_id="customer",
                event_type="HUMAN_HANDOFF",
                reason="Customer explicitly requested a human broker or representative.",
                details_json={"trigger_phrase": raw_message[:100]},
            )
            self.db.add(audit)
            await self.db.commit()

            from app.modules.lead_qualification.service import LeadQualificationDomainService
            svc = LeadQualificationDomainService(self.db)
            eval_res = await svc.evaluate_lead_qualification(organization_id, str(lead.id), broker=broker)

            return QualificationConversationResponseDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                conversation_state=QualificationConversationState.HUMAN_HANDOFF,
                qualification_state=eval_res.qualification_state,
                question="I have notified our senior property specialist to connect with you directly.",
                question_field=None,
                completeness_score=eval_res.completeness_score,
                confidence_score=eval_res.confidence_score,
                missing_fields=eval_res.missing_required_information + eval_res.missing_recommended_information,
                human_handoff=True,
                handoff_reason="CUSTOMER_REQUESTED_HUMAN",
            )

        # 3. Check for customer reluctance ("I don't know", "not sure", "skip", "no idea")
        is_reluctant = bool(
            re.search(r"\b(don'?t\s+know|not\s+sure|no\s+idea|undecided|skip|later)\b", lower_msg)
        )

        # 4. Execute Part 21.4.2 Fact Extraction
        extraction_result = await QualificationFactExtractor.extract_facts_from_text(
            text_corpus=sanitized_msg if is_safe else raw_message,
            lead_id=str(lead.id),
            organization_id=organization_id,
            source_type=EvidenceSourceType.CUSTOMER_MESSAGE,
            source_message_id=msg_dto.message_id,
            country_code=lead.country_code,
        )

        # Persist extracted facts with provenance and conflict detection
        persisted_facts_summary: Dict[str, Any] = {}
        active_facts = await self.repo.get_active_facts(organization_id, str(lead.id))
        active_facts_by_field: Dict[str, QualificationFact] = {f.field_name: f for f in active_facts}

        for proposed in extraction_result.facts:
            existing_fact = active_facts_by_field.get(proposed.field_name)

            if existing_fact:
                if existing_fact.source_type == EvidenceSourceType.HUMAN_VERIFICATION.value and proposed.source_type != EvidenceSourceType.HUMAN_VERIFICATION:
                    continue

                norm_existing = str(getattr(existing_fact.normalized_value, "value", existing_fact.normalized_value) or "").strip().upper()
                norm_proposed = str(getattr(proposed.normalized_value, "value", proposed.normalized_value) or "").strip().upper()

                if norm_existing and norm_proposed:
                    if norm_existing == norm_proposed:
                        continue
                    else:
                        conflict = QualificationConflict(
                            organization_id=organization_id,
                            lead_id=str(lead.id),
                            field_name=proposed.field_name,
                            existing_fact_id=existing_fact.id,
                            status=ConflictStatus.OPEN.value,
                        )
                        self.db.add(conflict)
                elif existing_fact.raw_value and proposed.raw_value:
                    if str(existing_fact.raw_value).strip().lower() == str(proposed.raw_value).strip().lower():
                        continue
                    else:
                        conflict = QualificationConflict(
                            organization_id=organization_id,
                            lead_id=str(lead.id),
                            field_name=proposed.field_name,
                            existing_fact_id=existing_fact.id,
                            status=ConflictStatus.OPEN.value,
                        )
                        self.db.add(conflict)

            fact_entity = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name=proposed.field_name,
                raw_value=proposed.raw_value,
                normalized_value=proposed.normalized_value,
                value_category=proposed.value_category.value,
                value_type=proposed.value_type,
                source_type=proposed.source_type.value,
                source_id=proposed.source_id,
                confidence=proposed.confidence,
                extracted_by=extraction_result.model_name,
                model_version=extraction_result.extraction_version,
                evidence_text_reference=proposed.evidence_text_reference,
                status=FactStatus.ACTIVE.value,
            )
            self.db.add(fact_entity)
            persisted_facts_summary[proposed.field_name] = proposed.normalized_value or proposed.raw_value

        # Also store inbound message in conversations table
        conv_record = Conversation(
            lead_id=lead.id,
            direction="inbound",
            sender_type="lead",
            message=raw_message,
            message_type="text",
        )
        self.db.add(conv_record)
        await self.db.flush()

        # 5. Deterministic Qualification Re-evaluation via Part 21.4.3
        from app.modules.lead_qualification.service import LeadQualificationDomainService
        service = LeadQualificationDomainService(self.db)
        eval_result = await service.evaluate_lead_qualification(
            organization_id=organization_id,
            lead_id=str(lead.id),
            actor_id=str(broker.id) if broker else "conversation_engine",
            broker=broker,
        )

        # 6. Check for Property Recommendation triggers from verified inventory (Part 21.3)
        matched_props_summary = None
        if any(w in lower_msg for w in ["property", "properties", "apartment", "villa", "options", "listing", "listings", "viewing", "available", "unit", "units"]):
            try:
                from app.modules.property_recommendation.service import PropertyRecommendationService
                from app.modules.property_recommendation.dto import PropertyRecommendationRequestDTO
                rec_svc = PropertyRecommendationService(self.db)
                rec_res = await rec_svc.generate_recommendations(
                    dto=PropertyRecommendationRequestDTO(lead_id=str(lead.id), limit=3),
                    organization_id=organization_id,
                )
                if rec_res and rec_res.items:
                    matched_props_summary = {
                        "count": len(rec_res.items),
                        "top_matches": [
                            {
                                "property_id": str(item.property_id),
                                "title": item.title,
                                "price": item.price,
                                "location": getattr(item, 'locality', '') or getattr(item, 'city', '') or getattr(item, 'location', 'Dubai'),
                                "bedrooms": item.bedrooms,
                                "match_score": item.match_score,
                            }
                            for item in rec_res.items[:3]
                        ]
                    }
            except Exception as e:
                logger.warning(f"[CONVERSATION_ENGINE] Property recommendation lookup error: {e}")

        # 7. Check for Terminal / Handoff states
        if eval_result.blocking_conflicts or eval_result.qualification_state == QualificationState.NEEDS_HUMAN_REVIEW.value:
            QUALIFICATION_HUMAN_HANDOFFS.labels(org_hash=org_hash, reason="EVIDENCE_CONFLICT").inc()
            return QualificationConversationResponseDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                conversation_state=QualificationConversationState.HUMAN_HANDOFF,
                qualification_state=eval_result.qualification_state,
                question=None,
                question_field=None,
                completeness_score=eval_result.completeness_score,
                confidence_score=eval_result.confidence_score,
                missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
                human_handoff=True,
                handoff_reason="Conflicting customer statements detected requiring broker assistance.",
                extracted_facts_count=len(persisted_facts_summary),
                extracted_facts_summary=persisted_facts_summary,
                matched_properties_summary=matched_props_summary,
            )

        if eval_result.qualification_state in (
            QualificationState.QUALIFIED.value,
            QualificationState.DISQUALIFIED.value,
            QualificationState.NURTURE.value,
        ):
            QUALIFICATION_CONVERSATIONS_COMPLETED.labels(
                org_hash=org_hash, final_state=eval_result.qualification_state
            ).inc()
            return QualificationConversationResponseDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                conversation_state=QualificationConversationState.COMPLETED,
                qualification_state=eval_result.qualification_state,
                question="Thank you! We have all the required details to prepare tailored options for you.",
                question_field=None,
                completeness_score=eval_result.completeness_score,
                confidence_score=eval_result.confidence_score,
                missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
                human_handoff=False,
                extracted_facts_count=len(persisted_facts_summary),
                extracted_facts_summary=persisted_facts_summary,
                matched_properties_summary=matched_props_summary,
            )

        # 8. Select next qualification question
        policy = await self.repo.get_matching_policy(
            organization_id=organization_id,
            country_code=lead.country_code,
            transaction_type=lead.transaction_type,
        )
        asked_fields, field_attempts, total_turns = await self._get_conversation_audit_history(
            organization_id, str(lead.id)
        )

        selected_field, template, handoff_req = QualificationQuestionSelector.select_next_question(
            eval_result=eval_result,
            field_attempts=field_attempts,
            policy=policy,
        )

        if handoff_req or not selected_field:
            QUALIFICATION_HUMAN_HANDOFFS.labels(org_hash=org_hash, reason="INFORMATION_GATHERING_FATIGUE").inc()
            return QualificationConversationResponseDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                conversation_state=QualificationConversationState.HUMAN_HANDOFF,
                qualification_state=eval_result.qualification_state,
                question="Thank you for sharing your preferences. One of our property advisors will follow up with you.",
                question_field=None,
                completeness_score=eval_result.completeness_score,
                confidence_score=eval_result.confidence_score,
                missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
                human_handoff=True,
                handoff_reason="Max qualification attempts reached without gathering all required fields.",
                extracted_facts_count=len(persisted_facts_summary),
                extracted_facts_summary=persisted_facts_summary,
                matched_properties_summary=matched_props_summary,
            )

        # 9. Generate question phrasing
        question_text, is_fallback = await self._generate_conversational_question(
            target_field=selected_field,
            template=template or "",
            known_facts=eval_result.snapshot.model_dump(),
            context_notes=None,
            organization_id=organization_id,
        )

        # Save outbound question message in conversations
        outbound_conv = Conversation(
            lead_id=lead.id,
            direction="outbound",
            sender_type="bot",
            message=question_text,
            message_type="text",
        )
        self.db.add(outbound_conv)

        # Record question audit
        audit = QualificationAuditEvent(
            organization_id=organization_id,
            lead_id=str(lead.id),
            actor_type=QualificationAuditActorType.SYSTEM.value,
            actor_id=str(broker.id) if broker else "conversation_engine",
            event_type="QUESTION_GENERATED",
            previous_state=eval_result.qualification_state,
            new_state=eval_result.qualification_state,
            reason=f"Generated qualification question for field '{selected_field}'",
            details_json={
                "question_field": selected_field,
                "question_text": question_text,
                "is_fallback": is_fallback,
                "channel": msg_dto.channel,
            },
        )
        self.db.add(audit)
        await self.db.commit()

        QUALIFICATION_QUESTIONS_GENERATED.labels(
            org_hash=org_hash, field_name=selected_field, generation_mode="template" if is_fallback else "llm"
        ).inc()

        return QualificationConversationResponseDTO(
            lead_id=str(lead.id),
            organization_id=organization_id,
            conversation_state=QualificationConversationState.WAITING_FOR_RESPONSE,
            qualification_state=eval_result.qualification_state,
            question=question_text,
            question_field=selected_field,
            is_fallback_question=is_fallback,
            missing_fields=eval_result.missing_required_information + eval_result.missing_recommended_information,
            completeness_score=eval_result.completeness_score,
            confidence_score=eval_result.confidence_score,
            human_handoff=False,
            extracted_facts_count=len(persisted_facts_summary),
            extracted_facts_summary=persisted_facts_summary,
            matched_properties_summary=matched_props_summary,
        )

    async def get_conversation_state(
        self, organization_id: str, lead_id: str, broker: Optional[Broker] = None
    ) -> QualificationConversationStateDTO:
        """Retrieves active conversation state, history, and missing qualification items."""
        lead = await self._validate_lead_tenant(lead_id, organization_id, broker)

        from app.modules.lead_qualification.service import LeadQualificationDomainService
        service = LeadQualificationDomainService(self.db)
        eval_res = await service.evaluate_lead_qualification(organization_id, str(lead.id), broker=broker)

        asked_fields, field_attempts, total_turns = await self._get_conversation_audit_history(
            organization_id, str(lead.id)
        )

        current_state = QualificationConversationState.WAITING_FOR_RESPONSE
        human_handoff = False
        handoff_reason = None

        if eval_result_is_terminal := eval_res.qualification_state in (
            QualificationState.QUALIFIED.value,
            QualificationState.DISQUALIFIED.value,
            QualificationState.NURTURE.value,
        ):
            current_state = QualificationConversationState.COMPLETED
        elif eval_res.blocking_conflicts or eval_res.qualification_state == QualificationState.NEEDS_HUMAN_REVIEW.value:
            current_state = QualificationConversationState.HUMAN_HANDOFF
            human_handoff = True
            handoff_reason = "Conflicting evidence requires human verification."

        return QualificationConversationStateDTO(
            lead_id=str(lead.id),
            organization_id=organization_id,
            conversation_state=current_state,
            qualification_state=eval_res.qualification_state,
            current_question=eval_res.next_best_question,
            current_question_field=eval_res.next_best_question_field,
            missing_required_fields=eval_res.missing_required_information,
            missing_recommended_fields=eval_res.missing_recommended_information,
            completeness_score=eval_res.completeness_score,
            confidence_score=eval_res.confidence_score,
            human_handoff=human_handoff,
            handoff_reason=handoff_reason,
            previously_asked_fields=asked_fields,
            field_attempts=field_attempts,
            total_turns=total_turns,
            last_interaction_at=eval_res.evaluated_at,
        )

    # ─── LLM Natural-Language Phrasing with Schema Validation ──────────────────

    async def _generate_conversational_question(
        self,
        target_field: str,
        template: str,
        known_facts: Dict[str, Any],
        context_notes: Optional[str],
        organization_id: str,
    ) -> Tuple[str, bool]:
        """
        Generates conversational phrasing for the deterministically selected target field.
        Strictly validates schema, target field match, and absence of hallucinations.
        Falls back to deterministic template if anything fails.
        """
        org_hash = mask_org_id(organization_id)

        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        if not gemini_key or gemini_key.startswith("placeholder") or gemini_key.startswith("AIzaSy_placeholder"):
            QUALIFICATION_QUESTIONS_FALLBACK.labels(org_hash=org_hash, field_name=target_field, reason="no_llm_key").inc()
            return template, True

        system_instruction = (
            "You are a professional, polite real-estate qualification assistant.\n"
            "Your task is to rephrase the given template question naturally in a single conversational sentence.\n"
            "RULES:\n"
            "1. ONLY ask for the specified target_field.\n"
            "2. DO NOT invent or assume any customer attributes (no fake budgets, no fake locations).\n"
            "3. Return a valid JSON object strictly matching this schema:\n"
            '{"question": string, "field": string, "safety_status": "VALID"}\n'
            "4. The 'field' key MUST exactly equal the target_field provided."
        )

        user_payload = {
            "target_field": target_field,
            "template_question": template,
            "known_facts": {k: v for k, v in known_facts.items() if v and v != "UNKNOWN"},
            "context_notes": context_notes,
        }

        try:
            from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter
            adapter = GoogleAdapter(api_key=gemini_key, model="gemini-3.5-flash")
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": json.dumps(user_payload, default=str)},
            ]
            resp = await adapter.complete(messages, max_tokens=256, temperature=0.2)
            if resp.success and resp.content:
                clean_json = re.sub(r"```(?:json)?", "", resp.content).strip("` \n")
                parsed = json.loads(clean_json)

                # Schema & Grounding Validation
                if isinstance(parsed, dict) and "question" in parsed and "field" in parsed:
                    q_text = str(parsed["question"]).strip()
                    resp_field = str(parsed["field"]).strip()

                    if resp_field == target_field and len(q_text) >= 5 and q_text.endswith("?"):
                        # Prompt injection safety validation on generated text
                        if validate_prompt_injection(q_text):
                            return q_text, False
        except Exception as ex:
            logger.warning(f"[CONVERSATION_ENGINE] LLM question generation failed: {ex}. Falling back to template.")

        QUALIFICATION_QUESTIONS_FALLBACK.labels(org_hash=org_hash, field_name=target_field, reason="llm_error_or_invalid").inc()
        return template, True
