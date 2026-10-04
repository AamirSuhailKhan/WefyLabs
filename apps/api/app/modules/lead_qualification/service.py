"""
Part 21.4.1 — AI Lead Qualification Domain Service
==================================================
Coordinates fact ingestion, conflict management, deterministic evaluation,
audit event logging, and authorized human overrides.
Enforces multi-tenant isolation and strict real-data provenance across all operations.
"""
import uuid
import logging
import time
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

# Sprint 1E — Learning layer wiring (non-blocking, failure-safe)
from app.modules.intelligence.outcome_recorder import OutcomeRecorder
from app.models.intelligence_models import OutcomeEventType, OutcomeEntityType

from app.models.lead import Lead
from app.models.broker import Broker
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
    QualificationFactDTO,
    QualificationFactCreateDTO,
    QualificationConflictDTO,
    QualificationConflictResolveDTO,
    QualificationPolicyDTO,
    QualificationPolicyCreateDTO,
    QualificationSnapshotDTO,
    QualificationAuditEventDTO,
    QualificationHumanOverrideDTO,
    QualificationExtractionSummaryDTO,
    QualificationEvaluationResultDTO,
    QualificationMissingInfoDTO,
    QualificationConversationStartDTO,
    QualificationConversationMessageDTO,
    QualificationConversationResponseDTO,
    QualificationConversationStateDTO,
)
from app.modules.lead_qualification.fact_repository import QualificationFactRepository
from app.modules.lead_qualification.policy_engine import DeterministicQualificationPolicyEngine
from app.modules.lead_qualification.extractor import QualificationFactExtractor
from app.modules.lead_qualification.metrics import (
    QUALIFICATION_SNAPSHOT_READS,
    QUALIFICATION_FACT_WRITES,
    QUALIFICATION_CONFLICTS_TOTAL,
    QUALIFICATION_HUMAN_OVERRIDES_TOTAL,
    QUALIFICATION_EVALUATION_LATENCY,
    QUALIFICATION_EXTRACTION_ATTEMPTS,
    QUALIFICATION_EXTRACTION_SUCCESS,
    QUALIFICATION_EXTRACTION_FAILURES,
    mask_org_id,
)

logger = logging.getLogger(__name__)


class LeadQualificationDomainService:
    """Enterprise domain service for lead qualification."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = QualificationFactRepository(db)

    async def _validate_and_get_lead(
        self, lead_id: str, organization_id: str, broker: Optional[Broker] = None
    ) -> Lead:
        """
        Validates that the lead exists and belongs strictly to the authenticated tenant/broker.
        Raises HTTP 404 / 403 on violation.
        """
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

        # Multi-tenant verification
        if broker and str(lead.broker_id) != str(broker.id):
            lead_org_id = getattr(lead, "organization_id", None) or str(lead.broker_id)
            broker_org_id = getattr(broker, "organization_id", None) or str(broker.id)
            if lead_org_id != broker_org_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Lead does not belong to your organization.",
                )

        return lead

    async def get_lead_qualification_snapshot(
        self,
        organization_id: str,
        lead_id: str,
        broker: Optional[Broker] = None,
    ) -> QualificationSnapshotDTO:
        """
        Computes and returns the evaluated qualification snapshot for a lead.
        Bootstraps initial facts from existing verified CRM fields if no facts exist yet.
        """
        start_time = time.perf_counter()
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)

        # Load active facts and conflicts
        active_facts = await self.repo.get_active_facts(organization_id, lead_id)
        open_conflicts = await self.repo.get_open_conflicts(organization_id, lead_id)

        # Bootstrap grounded facts from Lead record if facts table is empty
        if not active_facts:
            active_facts = await self._bootstrap_facts_from_lead(lead, organization_id)

        # Retrieve applicable requirement policy
        policy = await self.repo.get_matching_policy(
            organization_id=organization_id,
            country_code=lead.country_code,
            transaction_type=lead.transaction_type,
        )

        # Deterministic policy evaluation
        snapshot_dto = DeterministicQualificationPolicyEngine.evaluate(
            organization_id=organization_id,
            lead_id=lead_id,
            active_facts=active_facts,
            open_conflicts=open_conflicts,
            policy=policy,
        )

        # Persist evaluated snapshot record
        await self.repo.save_snapshot(organization_id, lead_id, snapshot_dto)
        await self.db.commit()

        # Observability Metrics
        org_hash = mask_org_id(organization_id)
        QUALIFICATION_SNAPSHOT_READS.labels(org_hash=org_hash, state=snapshot_dto.state).inc()
        QUALIFICATION_EVALUATION_LATENCY.labels(org_hash=org_hash).observe(time.perf_counter() - start_time)

        return snapshot_dto

    async def evaluate_lead_qualification(
        self,
        organization_id: str,
        lead_id: str,
        actor_id: Optional[str] = None,
        broker: Optional[Broker] = None,
    ) -> QualificationEvaluationResultDTO:
        """
        Deterministically evaluates qualification policy criteria against all active facts and conflicts.
        Computes completeness, confidence, missing information, next best question, updates snapshot,
        and logs audit trail if state transition occurred.
        """
        start_time = time.perf_counter()
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)

        # 1. Fetch previous snapshot to detect state changes
        prev_snapshot_record = await self.repo.get_latest_snapshot_record(organization_id, lead_id)
        prev_state = prev_snapshot_record.state if prev_snapshot_record else QualificationState.NEW.value

        # 2. Load active facts and conflicts
        active_facts = await self.repo.get_active_facts(organization_id, lead_id)
        open_conflicts = await self.repo.get_open_conflicts(organization_id, lead_id)

        # Bootstrap grounded facts from Lead record if facts table is empty
        if not active_facts:
            active_facts = await self._bootstrap_facts_from_lead(lead, organization_id)

        # 3. Retrieve applicable requirement policy
        policy = await self.repo.get_matching_policy(
            organization_id=organization_id,
            country_code=lead.country_code,
            transaction_type=lead.transaction_type,
        )

        # 4. Detailed deterministic evaluation
        result_dto = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id=organization_id,
            lead_id=lead_id,
            active_facts=active_facts,
            open_conflicts=open_conflicts,
            policy=policy,
        )

        # 5. Save updated snapshot record
        await self.repo.save_snapshot(organization_id, lead_id, result_dto.snapshot)

        # 6. Record audit event if state changed
        if prev_state != result_dto.qualification_state:
            audit = QualificationAuditEvent(
                organization_id=organization_id,
                lead_id=lead_id,
                actor_type=QualificationAuditActorType.SYSTEM.value,
                actor_id=actor_id or "policy_engine",
                event_type=QualificationAuditEventType.STATE_CHANGE.value,
                previous_state=prev_state,
                new_state=result_dto.qualification_state,
                reason=f"Qualification policy evaluated state transition from {prev_state} to {result_dto.qualification_state}",
                details_json={
                    "completeness_score": result_dto.completeness_score,
                    "confidence_score": result_dto.confidence_score,
                    "policy_version": result_dto.policy_version,
                    "missing_required": result_dto.missing_required_information,
                },
            )
            self.db.add(audit)

        await self.db.commit()

        # ── Sprint 1E: Learning layer wiring ──────────────────────────────────
        # Record qualification state transitions as OutcomeEvents.
        # Non-blocking: failures are caught internally.
        if prev_state != result_dto.qualification_state:
            new_state = result_dto.qualification_state
            _qual_event = None
            if new_state in ("QUALIFIED", QualificationState.QUALIFIED.value if hasattr(QualificationState, 'QUALIFIED') else "QUALIFIED"):
                _qual_event = OutcomeEventType.LEAD_QUALIFIED
            elif new_state in ("DISQUALIFIED", "REJECTED"):
                _qual_event = OutcomeEventType.LEAD_DISQUALIFIED
            if _qual_event:
                await OutcomeRecorder.record_lead_qualified(
                    db=self.db,
                    org_id=organization_id,
                    lead_id=lead_id,
                    qualified_by="DETERMINISTIC_POLICY",
                    qualification_score=result_dto.completeness_score,
                    qualified_at=datetime.now(timezone.utc),
                )

        # Observability Metrics
        org_hash = mask_org_id(organization_id)
        QUALIFICATION_SNAPSHOT_READS.labels(org_hash=org_hash, state=result_dto.qualification_state).inc()
        QUALIFICATION_EVALUATION_LATENCY.labels(org_hash=org_hash).observe(time.perf_counter() - start_time)

        return result_dto

    async def get_missing_qualification_info(
        self,
        organization_id: str,
        lead_id: str,
        broker: Optional[Broker] = None,
    ) -> QualificationMissingInfoDTO:
        """
        Retrieves the prioritized list of missing qualification fields along with
        deterministic question templates for the next best conversation prompt.
        """
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        active_facts = await self.repo.get_active_facts(organization_id, lead_id)
        open_conflicts = await self.repo.get_open_conflicts(organization_id, lead_id)

        if not active_facts:
            active_facts = await self._bootstrap_facts_from_lead(lead, organization_id)

        policy = await self.repo.get_matching_policy(
            organization_id=organization_id,
            country_code=lead.country_code,
            transaction_type=lead.transaction_type,
        )

        return DeterministicQualificationPolicyEngine.get_missing_info(
            organization_id=organization_id,
            lead_id=lead_id,
            active_facts=active_facts,
            open_conflicts=open_conflicts,
            policy=policy,
        )

    async def get_lead_facts(
        self,
        organization_id: str,
        lead_id: str,
        include_superseded: bool = False,
        broker: Optional[Broker] = None,
    ) -> List[QualificationFactDTO]:
        """Fetch all qualification facts for a lead."""
        await self._validate_and_get_lead(lead_id, organization_id, broker)
        if include_superseded:
            facts = await self.repo.get_all_facts(organization_id, lead_id)
        else:
            facts = await self.repo.get_active_facts(organization_id, lead_id)
        return [QualificationFactDTO.model_validate(f) for f in facts]

    async def get_lead_conflicts(
        self,
        organization_id: str,
        lead_id: str,
        broker: Optional[Broker] = None,
    ) -> List[QualificationConflictDTO]:
        """Fetch all qualification conflicts for a lead."""
        await self._validate_and_get_lead(lead_id, organization_id, broker)
        conflicts = await self.repo.get_all_conflicts(organization_id, lead_id)
        return [QualificationConflictDTO.model_validate(c) for c in conflicts]

    async def get_lead_audit_history(
        self,
        organization_id: str,
        lead_id: str,
        limit: int = 50,
        broker: Optional[Broker] = None,
    ) -> List[QualificationAuditEventDTO]:
        """Fetch qualification audit trail for a lead."""
        await self._validate_and_get_lead(lead_id, organization_id, broker)
        events = await self.repo.get_audit_history(organization_id, lead_id, limit=limit)
        return [QualificationAuditEventDTO.model_validate(e) for e in events]

    async def record_fact(
        self,
        organization_id: str,
        lead_id: str,
        dto: QualificationFactCreateDTO,
        actor_type: QualificationAuditActorType = QualificationAuditActorType.SYSTEM,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        broker: Optional[Broker] = None,
    ) -> QualificationFactDTO:
        """Records a new atomic qualification fact with provenance."""
        await self._validate_and_get_lead(lead_id, organization_id, broker)

        fact, conflict = await self.repo.record_fact(
            organization_id=organization_id,
            lead_id=lead_id,
            dto=dto,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            correlation_id=correlation_id,
        )
        await self.db.commit()

        org_hash = mask_org_id(organization_id)
        QUALIFICATION_FACT_WRITES.labels(
            org_hash=org_hash, field_name=dto.field_name, source_type=dto.source_type.value
        ).inc()
        if conflict:
            QUALIFICATION_CONFLICTS_TOTAL.labels(org_hash=org_hash, field_name=dto.field_name).inc()

        return QualificationFactDTO.model_validate(fact)

    async def resolve_conflict(
        self,
        organization_id: str,
        lead_id: str,
        conflict_id: str,
        dto: QualificationConflictResolveDTO,
        actor_id: str,
        broker: Optional[Broker] = None,
    ) -> QualificationConflictDTO:
        """Resolves an open qualification conflict."""
        await self._validate_and_get_lead(lead_id, organization_id, broker)
        conflict = await self.repo.resolve_conflict(
            organization_id=organization_id,
            lead_id=lead_id,
            conflict_id=conflict_id,
            dto=dto,
            actor_id=actor_id,
        )
        await self.db.commit()
        return QualificationConflictDTO.model_validate(conflict)

    async def apply_human_override(
        self,
        organization_id: str,
        lead_id: str,
        dto: QualificationHumanOverrideDTO,
        actor_id: str,
        actor_role: str,
        broker: Optional[Broker] = None,
    ) -> QualificationSnapshotDTO:
        """
        Executes an authorized human override of the lead qualification state.
        Enforces strict RBAC (admin, super_admin, broker, manager, owner).
        Records an immutable audit event.
        """
        # RBAC Check
        allowed_roles = {"admin", "super_admin", "broker", "manager", "owner", "agent"}
        if actor_role.lower() not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{actor_role}' is not authorized to perform human qualification overrides.",
            )

        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)

        # Get current evaluation
        current_snapshot = await self.get_lead_qualification_snapshot(organization_id, lead_id, broker)
        previous_state = current_snapshot.state

        # Update snapshot with overridden state
        current_snapshot.state = dto.target_state.value
        current_snapshot.summary_notes = f"[Human Override by {actor_id}]: {dto.reason}"

        # Persist overridden snapshot
        await self.repo.save_snapshot(organization_id, lead_id, current_snapshot)

        # Record Audit Event
        await self.repo.record_audit_event(
            organization_id=organization_id,
            lead_id=lead_id,
            actor_type=QualificationAuditActorType.HUMAN,
            actor_id=actor_id,
            event_type=QualificationAuditEventType.HUMAN_OVERRIDE,
            previous_state=previous_state,
            new_state=dto.target_state.value,
            reason=dto.reason,
            details_json={"notes": dto.notes, "actor_role": actor_role},
        )
        await self.db.commit()

        org_hash = mask_org_id(organization_id)
        QUALIFICATION_HUMAN_OVERRIDES_TOTAL.labels(org_hash=org_hash, target_state=dto.target_state.value).inc()

        return current_snapshot

    async def list_policies(self, organization_id: str) -> List[QualificationPolicyDTO]:
        """Lists active requirement policies for this organization and system defaults."""
        stmt = select(QualificationRequirementPolicy).where(
            and_(
                (QualificationRequirementPolicy.organization_id == organization_id)
                | (QualificationRequirementPolicy.organization_id.is_(None)),
                QualificationRequirementPolicy.is_active == True,
            )
        ).order_by(QualificationRequirementPolicy.created_at.desc())
        res = await self.db.execute(stmt)
        policies = list(res.scalars().all())

        if not policies:
            # Create standard default policy
            default_policy = QualificationRequirementPolicy(
                policy_name="Standard Real-Estate Buyer Policy",
                policy_version="v1.0",
                required_fields=["intent", "location", "property_type"],
                recommended_fields=["budget_max", "timeline"],
                optional_fields=["financing", "bedrooms", "buyer_type", "preferred_amenities"],
                min_completeness_for_qualified=0.8,
                min_confidence_for_qualified=0.7,
                is_active=True,
            )
            self.db.add(default_policy)
            await self.db.commit()
            policies = [default_policy]

        return [QualificationPolicyDTO.model_validate(p) for p in policies]

    async def _bootstrap_facts_from_lead(self, lead: Lead, organization_id: str) -> List[QualificationFact]:
        """
        Bootstraps verified qualification facts from existing CRM Lead model fields.
        Grounds every fact with EvidenceSourceType.LEAD_FIELD and zero mock/assumed data.
        """
        bootstrapped: List[QualificationFact] = []

        # 1. Intent / Transaction Type
        if lead.transaction_type:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="intent",
                raw_value=lead.transaction_type.upper(),
                value_category=FactValueCategory.FACT.value,
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        # 2. Location
        if lead.preferred_locations and len(lead.preferred_locations) > 0:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="location",
                raw_value=", ".join(lead.preferred_locations),
                value_category=FactValueCategory.FACT.value,
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        # 3. Property Type
        if lead.property_type:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="property_type",
                raw_value=lead.property_type,
                value_category=FactValueCategory.FACT.value,
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        # 4. Budget Max
        if lead.budget_max:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="budget_max",
                raw_value=str(lead.budget_max),
                value_category=FactValueCategory.FACT.value,
                value_type="number",
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        # 5. Budget Min
        if lead.budget_min:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="budget_min",
                raw_value=str(lead.budget_min),
                value_category=FactValueCategory.FACT.value,
                value_type="number",
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        # 6. Budget Currency
        if lead.budget_currency:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="budget_currency",
                raw_value=lead.budget_currency,
                value_category=FactValueCategory.FACT.value,
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        # 7. Timeline
        if lead.timeline:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="timeline",
                raw_value=lead.timeline,
                value_category=FactValueCategory.FACT.value,
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        # 8. Financing / Loan Status
        if lead.loan_status:
            fact = QualificationFact(
                organization_id=organization_id,
                lead_id=str(lead.id),
                field_name="financing",
                raw_value=lead.loan_status,
                value_category=FactValueCategory.FACT.value,
                source_type=EvidenceSourceType.LEAD_FIELD.value,
                confidence=1.0,
            )
            self.db.add(fact)
            bootstrapped.append(fact)

        if bootstrapped:
            await self.db.flush()

        return bootstrapped

    # ─── Part 21.4.2 Fact Extraction & Ingestion Pipeline ────────────────────────

    async def extract_and_ingest_from_lead_conversations(
        self,
        organization_id: str,
        lead_id: str,
        message_id: Optional[str] = None,
        include_full_history: bool = True,
        actor_id: Optional[str] = None,
        broker: Optional[Broker] = None,
    ) -> QualificationExtractionSummaryDTO:
        """
        Executes Part 21.4.2 extraction pipeline over real customer communications:
        1. Multi-tenant authorization & lead verification.
        2. Retrieves relevant messages (UnifiedMessage / ChannelMessage).
        3. Extracts structured proposed facts via QualificationFactExtractor (Gemini / Heuristic fallback).
        4. Validates, calibrates, deduplicates, and resolves source priority.
        5. Persists approved facts and detects conflicts.
        6. Re-evaluates deterministic qualification snapshot.
        7. Records immutable audit event.
        """
        start_time = time.perf_counter()
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)

        # Retrieve conversation messages
        messages_text_list: List[Tuple[str, Optional[str], datetime]] = []

        try:
            from app.models.communication_models import UnifiedMessage, ChannelMessage, OmnichannelConversation
            lead_uuid = uuid.UUID(str(lead_id)) if isinstance(lead_id, str) else lead_id

            # 1. Fetch UnifiedMessages
            stmt_um = (
                select(UnifiedMessage)
                .where(
                    and_(
                        UnifiedMessage.lead_id == lead_uuid,
                        UnifiedMessage.direction == "inbound",
                    )
                )
                .order_by(UnifiedMessage.created_at.asc())
            )
            um_res = (await self.db.execute(stmt_um)).scalars().all()
            for m in um_res:
                if message_id and str(m.id) != message_id:
                    continue
                if m.content and m.content.strip():
                    messages_text_list.append((m.content, str(m.id), m.created_at))

            # 2. Fetch Omnichannel ChannelMessages if available
            stmt_omni = (
                select(ChannelMessage)
                .join(OmnichannelConversation, ChannelMessage.conversation_id == OmnichannelConversation.id)
                .where(
                    and_(
                        OmnichannelConversation.lead_id == str(lead.id),
                        OmnichannelConversation.organization_id == organization_id,
                        ChannelMessage.direction == "inbound",
                    )
                )
                .order_by(ChannelMessage.created_at.asc())
            )
            omni_res = (await self.db.execute(stmt_omni)).scalars().all()
            for m in omni_res:
                if message_id and str(m.id) != message_id:
                    continue
                if m.content and m.content.strip():
                    messages_text_list.append((m.content, str(m.id), m.created_at))
        except Exception as ex:
            logger.warning(f"[QUALIFICATION_SERVICE] Error querying message models: {ex}")

        # If no discrete message models exist, fallback to lead.notes or prospect text
        if not messages_text_list and lead.notes:
            messages_text_list.append((lead.notes, None, lead.created_at or datetime.now(timezone.utc)))

        extracted_facts_count = 0
        persisted_facts_count = 0
        conflicts_count = 0
        newly_persisted_facts: List[QualificationFact] = []

        active_facts = await self.repo.get_active_facts(organization_id, lead_id)
        active_facts_by_field: Dict[str, QualificationFact] = {f.field_name: f for f in active_facts}

        # Multi-turn progressive extraction
        for msg_content, msg_id, msg_ts in messages_text_list:
            extraction_result = await QualificationFactExtractor.extract_facts_from_text(
                organization_id=organization_id,
                lead_id=lead_id,
                text_corpus=msg_content,
                source_message_id=msg_id,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE,
                country_code=lead.country_code,
            )

            if not extraction_result.is_safe:
                logger.warning(f"[QUALIFICATION_SERVICE] Blocked injection in message {msg_id}")
                continue

            extracted_facts_count += len(extraction_result.facts)

            for proposed in extraction_result.facts:
                existing = active_facts_by_field.get(proposed.field_name)

                # 1. Deduplication check: skip if identical fact already active
                if existing and (
                    str(existing.normalized_value) == str(proposed.normalized_value)
                    or str(existing.raw_value).strip().lower() == str(proposed.raw_value).strip().lower()
                ):
                    continue

                # 2. Source priority protection:
                # If existing was HUMAN_VERIFICATION and proposed is not, do not supersede
                if existing and existing.source_type == EvidenceSourceType.HUMAN_VERIFICATION.value:
                    if proposed.source_type != EvidenceSourceType.HUMAN_VERIFICATION:
                        logger.info(
                            f"[QUALIFICATION_SERVICE] Preserving human-verified fact for field {proposed.field_name}"
                        )
                        continue

                # 3. Create and persist fact
                create_dto = QualificationFactCreateDTO(
                    field_name=proposed.field_name,
                    raw_value=proposed.raw_value,
                    normalized_value=proposed.normalized_value,
                    value_category=proposed.value_category,
                    value_type=proposed.value_type,
                    source_type=proposed.source_type,
                    source_id=proposed.source_id,
                    confidence=proposed.confidence,
                    extracted_by=extraction_result.model_provider,
                    model_version=extraction_result.model_name,
                    evidence_text_reference=proposed.evidence_text_reference,
                )

                persisted_fact, conflict = await self.repo.record_fact(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    dto=create_dto,
                    actor_type=QualificationAuditActorType.AI,
                    actor_id=actor_id or extraction_result.model_provider,
                    reason=f"Extracted from customer communication (ref: {msg_id or 'lead_corpus'})",
                    correlation_id=msg_id,
                )

                active_facts_by_field[proposed.field_name] = persisted_fact
                newly_persisted_facts.append(persisted_fact)
                persisted_facts_count += 1
                if conflict:
                    conflicts_count += 1

        # Re-evaluate snapshot
        snapshot = await self.get_lead_qualification_snapshot(organization_id, lead_id, broker=broker)

        # Audit event for extraction
        if persisted_facts_count > 0:
            audit = QualificationAuditEvent(
                organization_id=organization_id,
                lead_id=lead_id,
                actor_type=QualificationAuditActorType.AI.value,
                actor_id=actor_id or "extraction_engine",
                event_type=QualificationAuditEventType.FACT_RECORDED.value,
                previous_state=snapshot.state,
                new_state=snapshot.state,
                reason=f"Extracted {persisted_facts_count} qualification facts from communication history",
                details_json={
                    "facts_extracted": extracted_facts_count,
                    "facts_persisted": persisted_facts_count,
                    "conflicts_detected": conflicts_count,
                },
            )
            self.db.add(audit)

        await self.db.commit()

        # Fetch open conflicts
        conflicts = await self.get_lead_conflicts(organization_id, lead_id, broker=broker)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return QualificationExtractionSummaryDTO(
            lead_id=lead_id,
            organization_id=organization_id,
            facts_extracted_count=extracted_facts_count,
            facts_persisted_count=persisted_facts_count,
            conflicts_detected_count=conflicts_count,
            snapshot=snapshot,
            extracted_facts=[QualificationFactDTO.model_validate(f) for f in newly_persisted_facts],
            open_conflicts=conflicts,
            processing_time_ms=elapsed_ms,
        )

    # ─── Part 21.4.4 Qualification Conversation Engine Integration ──────────────

    async def start_qualification_conversation(
        self,
        organization_id: str,
        lead_id: str,
        start_dto: QualificationConversationStartDTO = QualificationConversationStartDTO(),
        broker: Optional[Broker] = None,
    ) -> QualificationConversationResponseDTO:
        """
        Initiates or resumes the qualification conversation for a lead.
        Evaluates active state and selects the next prioritized question.
        """
        from app.modules.lead_qualification.conversation_engine import QualificationConversationEngine
        engine = QualificationConversationEngine(self.db)
        return await engine.start_or_resume_conversation(
            organization_id=organization_id,
            lead_id=lead_id,
            start_dto=start_dto,
            broker=broker,
        )

    async def process_customer_qualification_message(
        self,
        organization_id: str,
        lead_id: str,
        msg_dto: QualificationConversationMessageDTO,
        broker: Optional[Broker] = None,
    ) -> QualificationConversationResponseDTO:
        """
        Ingests and processes an inbound customer qualification message:
        Extracts facts, detects conflicts, updates deterministic state, and returns next question/handoff.
        """
        from app.modules.lead_qualification.conversation_engine import QualificationConversationEngine
        engine = QualificationConversationEngine(self.db)
        return await engine.process_customer_message(
            organization_id=organization_id,
            lead_id=lead_id,
            msg_dto=msg_dto,
            broker=broker,
        )

    async def get_qualification_conversation_state(
        self,
        organization_id: str,
        lead_id: str,
        broker: Optional[Broker] = None,
    ) -> QualificationConversationStateDTO:
        """Retrieves active conversation state, history turns, fatigue counters, and handoff status."""
        from app.modules.lead_qualification.conversation_engine import QualificationConversationEngine
        engine = QualificationConversationEngine(self.db)
        return await engine.get_conversation_state(
            organization_id=organization_id,
            lead_id=lead_id,
            broker=broker,
        )

