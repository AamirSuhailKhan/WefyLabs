"""
Part 21.7 — AI Customer Response & Conversation Intelligence Domain Service
============================================================================
Unified domain orchestrator coordinating:
- Inbound communication normalization & deduplication
- Language detection & prompt injection defense
- Multi-intent classification
- Buying signal and objection detection
- Negotiation and appointment intent detection
- Part 21.4 Qualification fact updating with provenance
- Part 21.3 Property recommendation refreshing
- Part 21.5 Next Best Action recalculation
- Grounded AI response generation
- Automated human handoff escalation
- Strict multi-tenant isolation & PII-safe metrics
"""
from __future__ import annotations

import time
import uuid
import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.conversation import Conversation
from app.models.communication_models import (
    OmnichannelConversation,
    ChannelMessage,
)
from app.models.follow_up_models import CommunicationConsent, ContactFatigue
from app.models.qualification_models import (
    FactValueCategory,
    EvidenceSourceType,
    QualificationAuditActorType,
)
from app.modules.lead_qualification.dto import QualificationFactCreateDTO
from app.modules.lead_qualification.fact_repository import QualificationFactRepository
from app.modules.lead_qualification.extractor import QualificationFactExtractor
from app.modules.sales_action.service import SalesActionDomainService
from app.modules.sales_action.guards.consent_guard import ConsentGuard
from app.modules.sales_action.guards.fatigue_guard import FatigueGuard
from app.modules.property_recommendation.service import PropertyRecommendationService
from app.modules.property_recommendation.dto import PropertyRecommendationRequestDTO
from app.modules.conversation_intelligence.taxonomies import (
    CustomerIntent,
    BuyingSignalLevel,
    HandoffTrigger,
)
from app.modules.conversation_intelligence.dto import (
    InboundCustomerMessage,
    ResponseAnalysisResultDTO,
    ExtractedIntentDTO,
    BuyingSignalDTO,
    ObjectionDTO,
    NegotiationSignalDTO,
    AppointmentIntentDTO,
    ExtractedQualificationUpdateDTO,
    PropertyRequirementUpdateDTO,
    HumanHandoffBriefDTO,
    DraftReplyResponseDTO,
)
from app.modules.conversation_intelligence.language_detector import LanguageDetector
from app.modules.conversation_intelligence.intent_extractor import IntentExtractor
from app.modules.conversation_intelligence.buying_signal_detector import BuyingSignalDetector
from app.modules.conversation_intelligence.objection_detector import ObjectionDetector
from app.modules.conversation_intelligence.negotiation_detector import NegotiationDetector
from app.modules.conversation_intelligence.appointment_detector import AppointmentDetector
from app.modules.conversation_intelligence.handoff_service import HumanHandoffService
from app.modules.conversation_intelligence.response_generator import GroundedResponseGenerator
from app.modules.conversation_intelligence.metrics import (
    RESPONSE_INTELLIGENCE_TOTAL,
    RESPONSE_INTELLIGENCE_SUCCESS_TOTAL,
    RESPONSE_INTELLIGENCE_FAILURE_TOTAL,
    INTENT_DETECTED_TOTAL,
    OBJECTION_DETECTED_TOTAL,
    QUALIFICATION_UPDATE_TOTAL,
    PROPERTY_MATCH_REFRESH_TOTAL,
    HUMAN_HANDOFF_TOTAL,
    OPT_OUT_DETECTED_TOTAL,
    RESPONSE_GENERATION_TOTAL,
    PROCESSING_LATENCY_HISTOGRAM,
    mask_org_id,
)

logger = logging.getLogger(__name__)


class ResponseIntelligenceService:
    """Core domain service for Part 21.7 AI Conversation Intelligence."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fact_repo = QualificationFactRepository(db)
        self.consent_guard = ConsentGuard(db)
        self.fatigue_guard = FatigueGuard(db)
        self.sales_action_service = SalesActionDomainService(db)
        self.recommendation_service = PropertyRecommendationService(db)

    async def _validate_lead_tenant(
        self, lead_id: str, organization_id: str, broker: Optional[Broker] = None
    ) -> Lead:
        """Enforces tenant isolation for lead access."""
        try:
            lead_uuid = uuid.UUID(str(lead_id))
        except Exception:
            lead_uuid = lead_id

        stmt = select(Lead).where(Lead.id == lead_uuid)
        res = await self.db.execute(stmt)
        lead = res.scalars().first()

        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead '{lead_id}' not found.",
            )

        org_matches = False
        if hasattr(lead, "organization_id") and lead.organization_id:
            org_matches = str(lead.organization_id) == str(organization_id)
        elif lead.broker_id:
            org_matches = (str(lead.broker_id) == str(organization_id))

        if not org_matches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cross-tenant lead intelligence is prohibited.",
            )

        return lead

    async def analyze_customer_response(
        self,
        lead_id: str,
        organization_id: str,
        text: str,
        channel: str = "whatsapp",
        message_id: Optional[str] = None,
        broker: Optional[Broker] = None,
    ) -> ResponseAnalysisResultDTO:
        """
        Main intelligence analysis pipeline for an inbound customer message.
        """
        start_time = time.time()
        org_hash = mask_org_id(organization_id)

        # 1. Tenant & Lead verification
        lead = await self._validate_lead_tenant(lead_id, organization_id, broker)

        # 2. Language Detection
        detected_lang = LanguageDetector.detect_language(text)
        RESPONSE_INTELLIGENCE_TOTAL.labels(
            org_hash=org_hash, channel=channel, language=detected_lang
        ).inc()

        try:
            # 3. Multi-Intent Extraction & Injection Defense
            intents = IntentExtractor.extract_intents(text)
            for item in intents:
                INTENT_DETECTED_TOTAL.labels(
                    org_hash=org_hash, intent_type=item.intent.value
                ).inc()

            # 4. Buying Signal Detection
            buying_signal = BuyingSignalDetector.detect_signals(text)

            # 5. Objection Detection
            objections = ObjectionDetector.detect_objections(text, source_message_id=message_id)
            for obj in objections:
                OBJECTION_DETECTED_TOTAL.labels(
                    org_hash=org_hash,
                    category=obj.category.value,
                    severity=obj.severity.value,
                ).inc()

            # 6. Negotiation Detection
            negotiation = NegotiationDetector.detect_negotiation(text)

            # 7. Appointment / Viewing Intent Detection
            appointment = AppointmentDetector.detect_appointment_intent(text)

            # 8. Opt-Out / Consent Handling
            intent_types = [i.intent for i in intents]
            opt_out_detected = (
                CustomerIntent.OPT_OUT in intent_types
                or CustomerIntent.STOP_COMMUNICATION in intent_types
            )
            if opt_out_detected:
                OPT_OUT_DETECTED_TOTAL.labels(org_hash=org_hash, channel=channel).inc()
                # Immediately revoke channel consent
                stmt_c = select(CommunicationConsent).where(
                    CommunicationConsent.lead_id == str(lead.id),
                    CommunicationConsent.organization_id == organization_id,
                    CommunicationConsent.channel == channel.upper(),
                )
                existing_consent = (await self.db.execute(stmt_c)).scalars().first()
                if existing_consent:
                    existing_consent.status = "REVOKED"
                    existing_consent.revoked_at = datetime.now(timezone.utc)
                else:
                    new_consent = CommunicationConsent(
                        lead_id=str(lead.id),
                        organization_id=organization_id,
                        channel=channel.upper(),
                        status="REVOKED",
                        revoked_at=datetime.now(timezone.utc),
                    )
                    self.db.add(new_consent)

            # 9. Contact Fatigue inbound response registration
            await self.fatigue_guard.record_inbound_response(str(lead.id), organization_id)

            # 10. Extract Qualification Updates
            qual_extraction = await QualificationFactExtractor.extract_facts_from_text(
                organization_id=organization_id,
                lead_id=str(lead.id),
                text_corpus=text,
                source_message_id=message_id,
            )

            qual_update = ExtractedQualificationUpdateDTO()
            req_update = PropertyRequirementUpdateDTO()

            if qual_extraction and qual_extraction.facts:
                for proposed in qual_extraction.facts:
                    # Persist fact with provenance
                    fact_dto = QualificationFactCreateDTO(
                        field_name=proposed.field_name,
                        raw_value=proposed.raw_value,
                        normalized_value=proposed.normalized_value,
                        value_category=FactValueCategory(proposed.value_category),
                        value_type=proposed.value_type,
                        source_type=EvidenceSourceType.CUSTOMER_MESSAGE,
                        source_id=message_id,
                        confidence=proposed.confidence,
                        extracted_by="conversation_intelligence_v1",
                        model_version="v1.0-gemini-grounded",
                        evidence_text_reference=proposed.evidence_text_reference,
                    )
                    await self.fact_repo.record_fact(
                        organization_id=organization_id,
                        lead_id=str(lead.id),
                        dto=fact_dto,
                        actor_type=QualificationAuditActorType.AI,
                        reason=f"Customer statement: '{text[:100]}'",
                    )
                    QUALIFICATION_UPDATE_TOTAL.labels(
                        org_hash=org_hash, field_name=proposed.field_name
                    ).inc()

                    # Check for property requirement updates
                    if proposed.field_name == "budget_max" and proposed.normalized_value:
                        try:
                            qual_update.budget_max = Decimal(str(proposed.normalized_value))
                            req_update.budget_max = qual_update.budget_max
                            req_update.has_changes = True
                        except Exception:
                            pass
                    elif proposed.field_name == "location" and proposed.normalized_value:
                        qual_update.location = str(proposed.normalized_value)
                        req_update.location = qual_update.location
                        req_update.has_changes = True
                    elif proposed.field_name == "bedrooms" and proposed.normalized_value:
                        try:
                            qual_update.bedrooms = int(proposed.normalized_value)
                            req_update.bedrooms = qual_update.bedrooms
                            req_update.has_changes = True
                        except Exception:
                            pass
                    elif proposed.field_name == "property_type" and proposed.normalized_value:
                        qual_update.property_type = str(proposed.normalized_value)
                        req_update.property_type = qual_update.property_type
                        req_update.has_changes = True

            # 11. Refresh Property Recommendations if requirements changed
            matched_props_list: List[Dict[str, Any]] = []
            if req_update.has_changes and not opt_out_detected:
                try:
                    PROPERTY_MATCH_REFRESH_TOTAL.labels(org_hash=org_hash).inc()
                    rec_req = PropertyRecommendationRequestDTO(
                        lead_id=str(lead.id),
                        limit=3,
                        force_refresh=True,
                    )
                    rec_res = await self.recommendation_service.generate_recommendations(
                        organization_id=organization_id,
                        request=rec_req,
                    )
                    if rec_res and rec_res.recommendations:
                        for r in rec_res.recommendations:
                            matched_props_list.append({
                                "property_id": str(r.property_id),
                                "title": r.title,
                                "price": float(r.price),
                                "currency": r.currency,
                                "location": r.location,
                            })
                except Exception as e:
                    logger.warning(f"[ResponseIntelligence] Property match refresh error: {e}")

            # 12. Recalculate Next Best Action (Part 21.5)
            nba_action_name = None
            if not opt_out_detected:
                try:
                    nba_dec = await self.sales_action_service.evaluate_next_sales_action(
                        lead_id=str(lead.id),
                        organization_id=organization_id,
                        broker=broker,
                        trigger_event="CUSTOMER_RESPONSE",
                    )
                    if nba_dec:
                        nba_action_name = nba_dec.action_type.value
                except Exception as e:
                    logger.warning(f"[ResponseIntelligence] NBA recalculation error: {e}")

            # 13. Evaluate Human Handoff Escalation
            is_high_value = False
            if hasattr(lead, "estimated_budget") and lead.estimated_budget:
                is_high_value = float(lead.estimated_budget) >= 5_000_000.0

            requires_handoff, handoff_trigger, handoff_reason = HumanHandoffService.evaluate_escalation(
                intents=intents,
                objections=objections,
                negotiation=negotiation,
                is_luxury_or_high_value=is_high_value,
            )

            handoff_brief = None
            if requires_handoff:
                HUMAN_HANDOFF_TOTAL.labels(
                    org_hash=org_hash,
                    trigger_type=handoff_trigger.value,
                    urgency="URGENT" if handoff_trigger in (HandoffTrigger.LEGAL_RISK, HandoffTrigger.COMPLAINT) else "HIGH",
                ).inc()
                handoff_brief = HumanHandoffService.build_brief(
                    lead_id=str(lead.id),
                    organization_id=organization_id,
                    trigger=handoff_trigger,
                    customer_message=text,
                    intents=intents,
                    buying_signal=buying_signal,
                    objections=objections,
                    negotiation=negotiation,
                    qualification_update=qual_update,
                    recommended_action=nba_action_name or "REVIEW_CUSTOMER_RESPONSE",
                    reason=handoff_reason,
                )

            # 14. Generate Grounded AI Draft Reply
            lead_name = getattr(lead, "name", "Valued Client") or "Valued Client"
            draft_reply = GroundedResponseGenerator.generate_draft(
                lead_id=str(lead.id),
                lead_name=lead_name,
                channel=channel,
                language=detected_lang,
                intents=intents,
                buying_signal=buying_signal,
                objections=objections,
                negotiation=negotiation,
                appointment=appointment,
                matched_properties=matched_props_list,
            )
            RESPONSE_GENERATION_TOTAL.labels(
                org_hash=org_hash, channel=channel, language=detected_lang
            ).inc()

            # 15. Update Omnichannel Conversation Record if present
            stmt_conv = select(OmnichannelConversation).where(
                and_(
                    OmnichannelConversation.lead_id == str(lead.id),
                    OmnichannelConversation.organization_id == organization_id,
                )
            )
            conv_res = await self.db.execute(stmt_conv)
            conv = conv_res.scalars().first()
            if conv:
                if requires_handoff:
                    conv.control_mode = "human"
                if opt_out_detected:
                    conv.status = "archived"
                conv.ai_sentiment = "negative" if objections or CustomerIntent.COMPLAINT in intent_types else "positive" if buying_signal.level.value in ("VERY_HIGH", "HIGH") else "neutral"
                conv.ai_urgency_score = 1.0 if requires_handoff else 0.8 if buying_signal.level.value == "VERY_HIGH" else 0.5
                conv.ai_summary = f"Language: {detected_lang.upper()} | Intent: {', '.join([i.intent.value for i in intents[:2]])}"
                if nba_action_name:
                    conv.ai_next_best_action = nba_action_name
                await self.db.flush()

            latency_ms = int((time.time() - start_time) * 1000)
            PROCESSING_LATENCY_HISTOGRAM.labels(org_hash=org_hash).observe(time.time() - start_time)
            RESPONSE_INTELLIGENCE_SUCCESS_TOTAL.labels(org_hash=org_hash, channel=channel).inc()

            await self.db.commit()

            return ResponseAnalysisResultDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                message_id=message_id,
                detected_language=detected_lang,
                intents=intents,
                buying_signal=buying_signal,
                objections=objections,
                negotiation=negotiation,
                appointment=appointment,
                qualification_update=qual_update,
                property_requirement_update=req_update,
                opt_out_detected=opt_out_detected,
                requires_human_handoff=requires_handoff,
                handoff_brief=handoff_brief,
                next_best_action_suggested=nba_action_name,
                draft_response=draft_reply.draft_body,
                processing_latency_ms=latency_ms,
            )

        except Exception as exc:
            RESPONSE_INTELLIGENCE_FAILURE_TOTAL.labels(
                org_hash=org_hash, channel=channel, error_type=type(exc).__name__
            ).inc()
            logger.error(f"[ResponseIntelligence] Pipeline failure: {exc}", exc_info=True)
            raise

    async def ingest_inbound_message(
        self, msg: InboundCustomerMessage, broker: Optional[Broker] = None
    ) -> ResponseAnalysisResultDTO:
        """
        Full inbound ingestion:
        1. Checks idempotency key to prevent duplicate processing
        2. Persists to ChannelMessage and Conversation models
        3. Executes ResponseIntelligence analysis
        """
        # Deduplication check
        stmt = select(ChannelMessage).where(
            ChannelMessage.idempotency_key == msg.idempotency_key
        )
        existing = (await self.db.execute(stmt)).scalars().first()
        if existing:
            logger.info(f"[InboundIngestion] Duplicate message ignored: {msg.idempotency_key}")
            return await self.analyze_customer_response(
                lead_id=msg.lead_id,
                organization_id=msg.tenant_id,
                text=msg.text,
                channel=msg.channel,
                message_id=str(existing.id),
                broker=broker,
            )

        # Persist ChannelMessage
        channel_msg = ChannelMessage(
            conversation_id=msg.conversation_id or str(uuid.uuid4()),
            organization_id=msg.tenant_id,
            lead_id=msg.lead_id,
            channel=msg.channel,
            provider_name=getattr(msg, "provider_name", "webhook"),
            provider_message_id=msg.provider_message_id,
            direction="inbound",
            message_type=msg.message_type,
            content=msg.text,
            sender_name=msg.sender_name or "Customer",
            sender_identifier=msg.sender_identifier,
            idempotency_key=msg.idempotency_key,
            delivery_status="delivered",
            sent_at=msg.received_at,
            sent_by_ai=False,
        )
        self.db.add(channel_msg)

        # Relational timeline persistence to Conversation model
        try:
            lead_uuid = uuid.UUID(str(msg.lead_id))
            timeline_conv = Conversation(
                lead_id=lead_uuid,
                direction="inbound",
                sender_type="lead",
                message=msg.text,
                message_type="text",
                whatsapp_message_id=msg.provider_message_id,
            )
            self.db.add(timeline_conv)
        except Exception as e:
            logger.debug(f"[InboundIngestion] Timeline conversation note: {e}")

        await self.db.flush()

        return await self.analyze_customer_response(
            lead_id=msg.lead_id,
            organization_id=msg.tenant_id,
            text=msg.text,
            channel=msg.channel,
            message_id=str(channel_msg.id),
            broker=broker,
        )
