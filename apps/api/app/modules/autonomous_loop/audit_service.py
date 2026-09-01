"""
Part 21.8 — Autonomous Sales Loop Audit Service
================================================
Persists immutable audit entries for every autonomous decision.
Supports the 'Why did BeetleLabs do this?' explainability requirement.

INVARIANTS:
  - Every entry is written AFTER the decision, never before.
  - No raw customer message text or PII is stored in audit entries.
  - No provider credentials or tokens are stored.
  - All data comes from verified CRM state, not from AI inference.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autonomous_loop.models import SalesLoopAuditEntry
from app.modules.autonomous_loop.dto import ExplainabilityDTO, TimelineEntryDTO, OrchestratorResultDTO
from app.modules.autonomous_loop.taxonomies import ActorType

logger = logging.getLogger(__name__)


class SalesLoopAuditService:
    """Persists and retrieves audit entries for the autonomous sales loop."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        result: OrchestratorResultDTO,
        event_type: str,
        policy_version: str = "v1.0",
    ) -> SalesLoopAuditEntry:
        """
        Persists a full orchestration audit entry from an OrchestratorResultDTO.
        """
        guard_results_serialized = []
        if result.guard_chain:
            for g in result.guard_chain.guard_results:
                guard_results_serialized.append({
                    "guard_name": g.guard_name.value,
                    "passed": g.passed,
                    "reason": g.reason,
                    "details": g.details,
                    "evaluated_at": g.evaluated_at.isoformat(),
                })

        entry = SalesLoopAuditEntry(
            event_id=result.event_id,
            correlation_id=result.correlation_id,
            causation_id=result.causation_id,
            tenant_id=result.tenant_id,
            lead_id=result.lead_id or "",
            event_type=event_type,
            lifecycle_state_before=(
                result.lifecycle_state_before.value if result.lifecycle_state_before else None
            ),
            lifecycle_state_after=(
                result.lifecycle_state_after.value if result.lifecycle_state_after else None
            ),
            qualification_completeness=(
                result.intelligence.qualification_completeness if result.intelligence else None
            ),
            qualification_state=(
                result.intelligence.qualification_state if result.intelligence else None
            ),
            matched_properties_count=(
                result.intelligence.matched_properties_count if result.intelligence else 0
            ),
            buying_signal_level=(
                result.intelligence.buying_signal_level if result.intelligence else None
            ),
            action_type=result.action_type,
            automation_permission=(
                result.automation_permission.value if result.automation_permission else None
            ),
            guard_results=guard_results_serialized,
            provider_name=result.provider_name,
            provider_status=result.provider_status,
            provider_message_id=result.provider_message_id,
            decision_reason=result.decision_reason,
            policy_version=policy_version,
            actor_type=ActorType.SYSTEM.value,
            occurred_at=result.processed_at,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(entry)
        await self.db.flush()
        logger.info(
            f"[AUDIT_SERVICE] Recorded audit entry {entry.id} "
            f"for lead={result.lead_id} event_type={event_type}"
        )
        return entry

    async def get_timeline(
        self,
        lead_id: str,
        tenant_id: str,
        limit: int = 50,
    ) -> List[TimelineEntryDTO]:
        """Retrieves the autonomous sales timeline for a lead."""
        stmt = (
            select(SalesLoopAuditEntry)
            .where(
                and_(
                    SalesLoopAuditEntry.lead_id == lead_id,
                    SalesLoopAuditEntry.tenant_id == tenant_id,
                )
            )
            .order_by(desc(SalesLoopAuditEntry.occurred_at))
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        entries = list(res.scalars().all())

        timeline = []
        for e in entries:
            blocking_guard = None
            blocking_reason = None

            # Find first failing guard
            for g in (e.guard_results or []):
                if not g.get("passed"):
                    blocking_guard = g.get("guard_name")
                    blocking_reason = g.get("reason")
                    break

            all_guards_passed = all(g.get("passed") for g in (e.guard_results or []))

            timeline.append(TimelineEntryDTO(
                audit_id=e.id,
                event_type=e.event_type,
                action_type=e.action_type,
                automation_permission=e.automation_permission,
                lifecycle_state_before=e.lifecycle_state_before,
                lifecycle_state_after=e.lifecycle_state_after,
                guard_passed=all_guards_passed,
                blocking_guard=blocking_guard,
                blocking_reason=blocking_reason,
                provider_status=e.provider_status,
                decision_reason=e.decision_reason or "",
                occurred_at=e.occurred_at,
                actor_type=e.actor_type or "SYSTEM",
            ))

        return timeline

    async def explain(
        self,
        audit_id: str,
        lead_id: str,
        tenant_id: str,
    ) -> Optional[ExplainabilityDTO]:
        """Returns the explainability record for a specific audit entry."""
        stmt = select(SalesLoopAuditEntry).where(
            and_(
                SalesLoopAuditEntry.id == audit_id,
                SalesLoopAuditEntry.lead_id == lead_id,
                SalesLoopAuditEntry.tenant_id == tenant_id,
            )
        )
        res = await self.db.execute(stmt)
        e = res.scalars().first()
        if not e:
            return None

        return ExplainabilityDTO(
            audit_id=e.id,
            lead_id=e.lead_id,
            tenant_id=e.tenant_id,
            event_type=e.event_type,
            occurred_at=e.occurred_at,
            correlation_id=e.correlation_id,
            causation_id=e.causation_id,
            qualification_state=e.qualification_state or "UNKNOWN",
            qualification_completeness=e.qualification_completeness or 0.0,
            matched_properties_count=e.matched_properties_count or 0,
            buying_signal_level=e.buying_signal_level or "UNKNOWN",
            action_type=e.action_type,
            automation_permission=e.automation_permission,
            guard_results=e.guard_results or [],
            provider_name=e.provider_name,
            provider_status=e.provider_status,
            decision_reason=e.decision_reason or "",
            policy_version=e.policy_version or "v1.0",
            lifecycle_state_before=e.lifecycle_state_before,
            lifecycle_state_after=e.lifecycle_state_after,
            actor_type=e.actor_type or "SYSTEM",
        )
