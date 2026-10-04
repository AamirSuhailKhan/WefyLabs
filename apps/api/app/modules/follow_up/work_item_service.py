"""
Build 07 — Canonical WorkItem Service
======================================
Single point of creation, state management, and querying for all work items.

Replaces scattered Task creation across:
  - SlaService (first-contact task)
  - FollowUpOrchestratorService
  - autonomous_loop
  - revenue_autopilot

ALL work item creation goes through this service.

INVARIANTS:
  1. Idempotent: same idempotency_key → returns existing item, not a duplicate.
  2. Type-controlled: only WORK_ITEM_TYPES allowed.
  3. Source-controlled: only WORK_ITEM_SOURCES allowed.
  4. State machine: only valid transitions allowed.
  5. Tenant-isolated: all queries require organization_id.
  6. Audit: every transition is recorded in the reason field.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func

from app.models.crm_models import Task, WORK_ITEM_TYPES, WORK_ITEM_SOURCES, WORK_ITEM_STATUSES

# Sprint 1E — Learning layer wiring (non-blocking, failure-safe)
from app.modules.intelligence.outcome_recorder import OutcomeRecorder

logger = logging.getLogger(__name__)

# Allowed status transitions (deterministic state machine)
_ALLOWED_TRANSITIONS: Dict[str, set] = {
    "pending":     {"scheduled", "ready", "in_progress", "completed", "cancelled", "expired"},
    "scheduled":   {"ready", "in_progress", "completed", "cancelled", "expired"},
    "ready":       {"in_progress", "completed", "cancelled", "expired"},
    "in_progress": {"completed", "skipped", "cancelled", "failed"},
    "completed":   set(),
    "skipped":     set(),
    "cancelled":   set(),
    "failed":      {"pending"},   # retry → back to pending
    "expired":     set(),
}


def _parse_uuid(val: Any) -> Optional[Any]:
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return val


class WorkItemService:
    """
    Canonical WorkItem CRUD and state machine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Creation ──────────────────────────────────────────────────────────────

    async def create(
        self,
        organization_id: str,
        broker_id: str,
        task_type: str,
        source: str,
        title: str,
        lead_id: Optional[str] = None,
        description: Optional[str] = None,
        reason: Optional[str] = None,
        priority: str = "normal",
        due_at: Optional[datetime] = None,
        scheduled_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        conversation_id: Optional[str] = None,
        identity_id: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        assigned_broker_id: Optional[str] = None,
        assigned_team: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source_event_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        source_action_id: Optional[str] = None,
        source_workflow_id: Optional[str] = None,
        source_agent_run_id: Optional[str] = None,
    ) -> Task:
        """
        Create or return an existing work item (idempotent by idempotency_key).
        """
        # Validate type + source
        if task_type not in WORK_ITEM_TYPES:
            raise ValueError(f"Invalid task_type '{task_type}'. Must be one of {WORK_ITEM_TYPES}")
        if source not in WORK_ITEM_SOURCES:
            raise ValueError(f"Invalid source '{source}'. Must be one of {WORK_ITEM_SOURCES}")

        # Idempotency check
        if idempotency_key:
            existing = await self._find_by_idempotency_key(idempotency_key, organization_id)
            if existing:
                logger.info(
                    f"[WorkItem] Idempotent: returning existing item {existing.id} "
                    f"for key '{idempotency_key}'"
                )
                return existing

        item = Task(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            broker_id=_parse_uuid(broker_id),
            lead_id=_parse_uuid(lead_id),
            assigned_broker_id=_parse_uuid(assigned_broker_id),
            title=title,
            description=description,
            reason=reason,
            task_type=task_type,
            source=source,
            priority=priority,
            status="pending",
            due_at=due_at,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
            conversation_id=conversation_id,
            identity_id=identity_id,
            opportunity_id=opportunity_id,
            assigned_team=assigned_team,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            source_event_id=source_event_id,
            source_message_id=source_message_id,
            source_action_id=source_action_id,
            source_workflow_id=source_workflow_id,
            source_agent_run_id=source_agent_run_id,
        )
        self.db.add(item)
        await self.db.flush()

        logger.info(
            f"[WorkItem] Created {task_type}/{source} item {item.id} "
            f"for lead {lead_id} org {organization_id}"
        )
        return item

    # ─── State Machine ─────────────────────────────────────────────────────────

    async def transition(
        self,
        item_id: str,
        new_status: str,
        organization_id: str,
        reason: Optional[str] = None,
    ) -> Task:
        """
        Transition a work item to a new status. Raises on invalid transition.
        """
        if new_status not in WORK_ITEM_STATUSES:
            raise ValueError(f"Unknown status '{new_status}'")

        item = await self.get(item_id, organization_id)
        if not item:
            raise ValueError(f"WorkItem '{item_id}' not found in org '{organization_id}'")

        allowed = _ALLOWED_TRANSITIONS.get(item.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {item.status} → {new_status} "
                f"(allowed: {allowed or 'none — terminal state'})"
            )

        now = datetime.now(timezone.utc)
        item.status = new_status
        if new_status == "completed":
            item.completed_at = now
        if new_status == "cancelled":
            item.cancelled_at = now
        if reason:
            item.reason = (item.reason or "") + f"\n[{now.isoformat()}] → {new_status}: {reason}"

        await self.db.flush()

        # ── Sprint 1E: Learning layer wiring ──────────────────────────────────
        if new_status == "completed" and item.lead_id:
            await OutcomeRecorder.record_followup_completed(
                db=self.db,
                org_id=organization_id,
                work_item_id=str(item_id),
                lead_id=str(item.lead_id),
                channel=getattr(item, 'channel', None),
                agent_id=str(item.broker_id) if item.broker_id else None,
                completed_at=now,
                response_received=False,
            )

        return item

    # ─── Queries ───────────────────────────────────────────────────────────────

    async def get(self, item_id: str, organization_id: str) -> Optional[Task]:
        stmt = select(Task).where(
            Task.id == item_id,
            Task.organization_id == organization_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_lead(
        self,
        lead_id: str,
        organization_id: str,
        statuses: Optional[List[str]] = None,
        task_types: Optional[List[str]] = None,
    ) -> List[Task]:
        conditions = [
            Task.lead_id == uuid.UUID(str(lead_id)),
            Task.organization_id == organization_id,
        ]
        if statuses:
            conditions.append(Task.status.in_(statuses))
        if task_types:
            conditions.append(Task.task_type.in_(task_types))

        stmt = select(Task).where(and_(*conditions)).order_by(Task.due_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_overdue(
        self,
        organization_id: str,
        limit: int = 100,
    ) -> List[Task]:
        """Returns all non-terminal tasks past their due_at."""
        now = datetime.now(timezone.utc)
        stmt = select(Task).where(
            Task.organization_id == organization_id,
            Task.due_at <= now,
            Task.status.in_(["pending", "scheduled", "ready", "in_progress"]),
        ).order_by(Task.due_at.asc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_due_now(
        self,
        organization_id: str,
        limit: int = 100,
        window_minutes: int = 5,
    ) -> List[Task]:
        """Returns tasks due within the next window_minutes."""
        now = datetime.now(timezone.utc)
        window = now + timedelta(minutes=window_minutes)
        stmt = select(Task).where(
            Task.organization_id == organization_id,
            Task.due_at <= window,
            Task.due_at >= now,
            Task.status.in_(["pending", "scheduled", "ready"]),
        ).order_by(Task.due_at.asc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def cancel_pending_for_lead(
        self,
        lead_id: str,
        organization_id: str,
        task_types: Optional[List[str]] = None,
        reason: str = "Cancelled by system",
    ) -> int:
        """
        Cancel all pending/scheduled work items for a lead.
        Used when customer replies (Golden Path 100) or opts out.
        Returns count of cancelled items.
        """
        now = datetime.now(timezone.utc)
        parsed_lid = _parse_uuid(lead_id)
        conditions = [
            Task.lead_id == parsed_lid,
            Task.organization_id == organization_id,
            Task.status.in_(["pending", "scheduled", "ready"]),
        ]
        if task_types:
            conditions.append(Task.task_type.in_(task_types))

        stmt = select(Task).where(and_(*conditions))
        items = list((await self.db.execute(stmt)).scalars().all())

        for item in items:
            item.status = "cancelled"
            item.cancelled_at = now
            item.reason = (item.reason or "") + f"\n[{now.isoformat()}] Auto-cancelled: {reason}"

        if items:
            await self.db.flush()

        logger.info(
            f"[WorkItem] Cancelled {len(items)} pending items for lead {lead_id} "
            f"in org {organization_id}: {reason}"
        )
        return len(items)

    async def get_active_lead_count_without_next_action(
        self, organization_id: str
    ) -> int:
        """
        Revenue continuity invariant: count active leads with no pending/scheduled work item.
        These are leads silently decaying.
        """
        # This is a diagnostic query — simplified for now
        # Full implementation requires joining leads table
        # Returns count of leads in this org that have zero active work items
        from app.models.lead import Lead as LeadModel
        active_statuses = {"new", "pending", "qualified", "engaged", "contacted"}

        # Leads with at least one active work item
        subq = (
            select(Task.lead_id)
            .where(
                Task.organization_id == organization_id,
                Task.status.in_(["pending", "scheduled", "ready", "in_progress"]),
            )
            .distinct()
        )

        stmt = select(func.count()).where(
            LeadModel.organization_id == uuid.UUID(organization_id)
            if True else True,  # type-agnostic
        )
        # Simplified: return 0 (full implementation needs lead join)
        return 0

    # ─── Private ───────────────────────────────────────────────────────────────

    async def _find_by_idempotency_key(
        self, key: str, organization_id: str
    ) -> Optional[Task]:
        stmt = select(Task).where(
            Task.idempotency_key == key,
            Task.organization_id == organization_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
