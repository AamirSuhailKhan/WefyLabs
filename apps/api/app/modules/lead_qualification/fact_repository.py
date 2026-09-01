"""
Part 21.4.1 — Qualification Fact Repository & Persistence Layer
==============================================================
Strict tenant-scoped persistence for facts, conflicts, policies, snapshots, and audit events.
Guarantees tenant isolation at the database query level.
"""
import logging
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, and_, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qualification_models import (
    QualificationFact,
    QualificationConflict,
    QualificationRequirementPolicy,
    QualificationAuditEvent,
    QualificationSnapshotRecord,
    FactStatus,
    ConflictStatus,
    QualificationAuditActorType,
    QualificationAuditEventType,
)
from app.modules.lead_qualification.dto import (
    QualificationFactCreateDTO,
    QualificationConflictResolveDTO,
    QualificationSnapshotDTO,
)

logger = logging.getLogger(__name__)


class QualificationFactRepository:
    """Repository handling tenant-isolated persistence for lead qualification."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_facts(self, organization_id: str, lead_id: str) -> List[QualificationFact]:
        """Fetch all active qualification facts for a tenant-scoped lead."""
        stmt = (
            select(QualificationFact)
            .where(
                and_(
                    QualificationFact.organization_id == organization_id,
                    QualificationFact.lead_id == lead_id,
                    QualificationFact.status == FactStatus.ACTIVE.value,
                )
            )
            .order_by(QualificationFact.created_at.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_all_facts(self, organization_id: str, lead_id: str) -> List[QualificationFact]:
        """Fetch complete history of qualification facts for a tenant-scoped lead."""
        stmt = (
            select(QualificationFact)
            .where(
                and_(
                    QualificationFact.organization_id == organization_id,
                    QualificationFact.lead_id == lead_id,
                )
            )
            .order_by(QualificationFact.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_open_conflicts(self, organization_id: str, lead_id: str) -> List[QualificationConflict]:
        """Fetch open conflicts for a tenant-scoped lead."""
        stmt = (
            select(QualificationConflict)
            .where(
                and_(
                    QualificationConflict.organization_id == organization_id,
                    QualificationConflict.lead_id == lead_id,
                    QualificationConflict.status == ConflictStatus.OPEN.value,
                )
            )
            .order_by(QualificationConflict.created_at.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_all_conflicts(self, organization_id: str, lead_id: str) -> List[QualificationConflict]:
        """Fetch all conflicts (open, resolved, superseded) for a lead."""
        stmt = (
            select(QualificationConflict)
            .where(
                and_(
                    QualificationConflict.organization_id == organization_id,
                    QualificationConflict.lead_id == lead_id,
                )
            )
            .order_by(QualificationConflict.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_audit_history(
        self, organization_id: str, lead_id: str, limit: int = 50
    ) -> List[QualificationAuditEvent]:
        """Fetch chronological audit trail of qualification actions for a lead."""
        stmt = (
            select(QualificationAuditEvent)
            .where(
                and_(
                    QualificationAuditEvent.organization_id == organization_id,
                    QualificationAuditEvent.lead_id == lead_id,
                )
            )
            .order_by(QualificationAuditEvent.created_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_matching_policy(
        self,
        organization_id: str,
        country_code: Optional[str] = None,
        market_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
    ) -> Optional[QualificationRequirementPolicy]:
        """Retrieve most specific active policy for tenant, or fallback to system policy."""
        # 1. Organization-specific match
        stmt = (
            select(QualificationRequirementPolicy)
            .where(
                and_(
                    QualificationRequirementPolicy.organization_id == organization_id,
                    QualificationRequirementPolicy.is_active == True,
                )
            )
            .order_by(QualificationRequirementPolicy.created_at.desc())
        )
        res = await self.db.execute(stmt)
        policies = list(res.scalars().all())
        if policies:
            # Filter by matching context
            for p in policies:
                if (
                    (not p.country_code or p.country_code == country_code)
                    and (not p.market_id or p.market_id == market_id)
                    and (not p.transaction_type or p.transaction_type == transaction_type)
                ):
                    return p
            return policies[0]

        # 2. System default policy (organization_id is None)
        stmt_default = (
            select(QualificationRequirementPolicy)
            .where(
                and_(
                    QualificationRequirementPolicy.organization_id.is_(None),
                    QualificationRequirementPolicy.is_active == True,
                )
            )
            .order_by(QualificationRequirementPolicy.created_at.desc())
        )
        res_default = await self.db.execute(stmt_default)
        return res_default.scalars().first()

    async def record_fact(
        self,
        organization_id: str,
        lead_id: str,
        dto: QualificationFactCreateDTO,
        actor_type: QualificationAuditActorType = QualificationAuditActorType.SYSTEM,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[QualificationFact, Optional[QualificationConflict]]:
        """
        Records a qualification fact with provenance.
        Detects contradictions:
        - If new value replaces an older fact from the same source or confirmed update: supersedes old fact.
        - If conflicting values exist without confirmation: creates an explicit QualificationConflict.
        """
        # Find existing active fact for this field
        stmt_existing = select(QualificationFact).where(
            and_(
                QualificationFact.organization_id == organization_id,
                QualificationFact.lead_id == lead_id,
                QualificationFact.field_name == dto.field_name,
                QualificationFact.status == FactStatus.ACTIVE.value,
            )
        )
        existing_fact = (await self.db.execute(stmt_existing)).scalars().first()

        supersedes_id = None
        conflict_created = None

        if existing_fact:
            # Check if values differ
            is_different = (
                str(existing_fact.raw_value or "").strip().lower()
                != str(dto.raw_value or "").strip().lower()
            )

            if is_different:
                # If incoming fact is from CUSTOMER_MESSAGE or HUMAN_VERIFICATION with higher/equal confidence:
                # The latest statement supersedes the older statement, retaining history
                if (
                    dto.source_type in ("CUSTOMER_MESSAGE", "HUMAN_VERIFICATION")
                    or dto.confidence >= existing_fact.confidence
                ):
                    existing_fact.status = FactStatus.SUPERSEDED.value
                    supersedes_id = existing_fact.id
                    await self.record_audit_event(
                        organization_id=organization_id,
                        lead_id=lead_id,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        event_type=QualificationAuditEventType.FACT_SUPERSEDED,
                        reason=f"Fact for '{dto.field_name}' superseded: '{existing_fact.raw_value}' -> '{dto.raw_value}'",
                        correlation_id=correlation_id,
                        details_json={"old_fact_id": existing_fact.id, "new_value": dto.raw_value},
                    )
                else:
                    # Ambiguous contradiction -> Mark conflict
                    conflict_created = QualificationConflict(
                        organization_id=organization_id,
                        lead_id=lead_id,
                        field_name=dto.field_name,
                        existing_fact_id=existing_fact.id,
                        status=ConflictStatus.OPEN.value,
                    )
                    self.db.add(conflict_created)
                    await self.db.flush()

                    await self.record_audit_event(
                        organization_id=organization_id,
                        lead_id=lead_id,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        event_type=QualificationAuditEventType.CONFLICT_DETECTED,
                        reason=f"Conflicting fact observed for '{dto.field_name}': existing='{existing_fact.raw_value}', new='{dto.raw_value}'",
                        correlation_id=correlation_id,
                        details_json={
                            "conflict_id": conflict_created.id,
                            "existing_fact_id": existing_fact.id,
                            "attempted_value": dto.raw_value,
                        },
                    )

        # Create new fact entity
        new_fact = QualificationFact(
            organization_id=organization_id,
            lead_id=lead_id,
            field_name=dto.field_name,
            raw_value=dto.raw_value,
            normalized_value=dto.normalized_value,
            value_category=dto.value_category.value,
            value_type=dto.value_type,
            source_type=dto.source_type.value,
            source_id=dto.source_id,
            confidence=dto.confidence,
            extracted_by=dto.extracted_by,
            model_version=dto.model_version,
            evidence_text_reference=dto.evidence_text_reference,
            status=FactStatus.CONFLICTED.value if conflict_created else FactStatus.ACTIVE.value,
            supersedes_fact_id=supersedes_id,
            observed_at=datetime.now(timezone.utc),
        )
        self.db.add(new_fact)
        await self.db.flush()

        if conflict_created:
            conflict_created.conflicting_fact_id = new_fact.id

        # Audit event for fact addition
        await self.record_audit_event(
            organization_id=organization_id,
            lead_id=lead_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=QualificationAuditEventType.FACT_RECORDED,
            reason=reason or f"Recorded fact '{dto.field_name}' = '{dto.raw_value}'",
            correlation_id=correlation_id,
            details_json={
                "fact_id": new_fact.id,
                "field_name": dto.field_name,
                "source_type": dto.source_type.value,
                "confidence": dto.confidence,
            },
        )

        return new_fact, conflict_created

    async def resolve_conflict(
        self,
        organization_id: str,
        lead_id: str,
        conflict_id: str,
        dto: QualificationConflictResolveDTO,
        actor_id: str,
    ) -> QualificationConflict:
        """Resolves an open qualification conflict by designating a winning fact."""
        stmt = select(QualificationConflict).where(
            and_(
                QualificationConflict.id == conflict_id,
                QualificationConflict.organization_id == organization_id,
                QualificationConflict.lead_id == lead_id,
            )
        )
        conflict = (await self.db.execute(stmt)).scalars().first()
        if not conflict:
            raise ValueError(f"Qualification conflict '{conflict_id}' not found for lead '{lead_id}'.")

        conflict.status = ConflictStatus.RESOLVED.value
        conflict.resolved_by = actor_id
        conflict.resolution_reason = dto.resolution_reason
        conflict.resolved_at = datetime.now(timezone.utc)
        conflict.resolved_fact_id = dto.selected_fact_id

        # If a specific fact was chosen as authoritative, set its status to ACTIVE and others to SUPERSEDED
        if dto.selected_fact_id:
            # Activate selected fact
            await self.db.execute(
                update(QualificationFact)
                .where(
                    and_(
                        QualificationFact.id == dto.selected_fact_id,
                        QualificationFact.organization_id == organization_id,
                    )
                )
                .values(status=FactStatus.ACTIVE.value)
            )
            # Supersede other fact
            other_id = conflict.conflicting_fact_id if dto.selected_fact_id == conflict.existing_fact_id else conflict.existing_fact_id
            if other_id:
                await self.db.execute(
                    update(QualificationFact)
                    .where(
                        and_(
                            QualificationFact.id == other_id,
                            QualificationFact.organization_id == organization_id,
                        )
                    )
                    .values(status=FactStatus.SUPERSEDED.value)
                )

        await self.record_audit_event(
            organization_id=organization_id,
            lead_id=lead_id,
            actor_type=QualificationAuditActorType.HUMAN,
            actor_id=actor_id,
            event_type=QualificationAuditEventType.CONFLICT_RESOLVED,
            reason=f"Resolved conflict on field '{conflict.field_name}': {dto.resolution_reason}",
            details_json={
                "conflict_id": conflict.id,
                "selected_fact_id": dto.selected_fact_id,
                "reason": dto.resolution_reason,
            },
        )
        return conflict

    async def save_snapshot(
        self, organization_id: str, lead_id: str, snapshot_dto: QualificationSnapshotDTO
    ) -> QualificationSnapshotRecord:
        """Persists a new latest qualification snapshot record, marking previous snapshots non-latest."""
        # Mark existing snapshots as non-latest
        await self.db.execute(
            update(QualificationSnapshotRecord)
            .where(
                and_(
                    QualificationSnapshotRecord.organization_id == organization_id,
                    QualificationSnapshotRecord.lead_id == lead_id,
                    QualificationSnapshotRecord.is_latest == True,
                )
            )
            .values(is_latest=False)
        )

        record = QualificationSnapshotRecord(
            organization_id=organization_id,
            lead_id=lead_id,
            state=snapshot_dto.state,
            intent=snapshot_dto.intent,
            buyer_type=snapshot_dto.buyer_type,
            budget_min=snapshot_dto.budget_min,
            budget_max=snapshot_dto.budget_max,
            budget_currency=snapshot_dto.budget_currency,
            location=snapshot_dto.location,
            property_type=snapshot_dto.property_type,
            bedrooms=snapshot_dto.bedrooms,
            timeline=snapshot_dto.timeline,
            financing=snapshot_dto.financing,
            completeness_score=snapshot_dto.completeness_score,
            confidence_score=snapshot_dto.confidence_score,
            missing_fields=snapshot_dto.missing_fields,
            conflicting_fields=snapshot_dto.conflicting_fields,
            policy_version=snapshot_dto.policy_version,
            summary_notes=snapshot_dto.summary_notes,
            is_latest=True,
            generated_at=snapshot_dto.generated_at,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_latest_snapshot_record(
        self, organization_id: str, lead_id: str
    ) -> Optional[QualificationSnapshotRecord]:
        """Fetches the latest persisted qualification snapshot record for a lead."""
        stmt = (
            select(QualificationSnapshotRecord)
            .where(
                and_(
                    QualificationSnapshotRecord.organization_id == organization_id,
                    QualificationSnapshotRecord.lead_id == lead_id,
                    QualificationSnapshotRecord.is_latest == True,
                )
            )
            .order_by(QualificationSnapshotRecord.generated_at.desc())
        )
        return (await self.db.execute(stmt)).scalars().first()


    async def record_audit_event(
        self,
        organization_id: str,
        lead_id: str,
        actor_type: QualificationAuditActorType,
        actor_id: Optional[str],
        event_type: QualificationAuditEventType,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        details_json: Optional[dict] = None,
    ) -> QualificationAuditEvent:
        """Records an immutable qualification audit event."""
        event = QualificationAuditEvent(
            organization_id=organization_id,
            lead_id=lead_id,
            actor_type=actor_type.value,
            actor_id=actor_id,
            event_type=event_type.value,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            correlation_id=correlation_id,
            details_json=details_json or {},
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(event)
        return event
