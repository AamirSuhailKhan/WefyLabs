"""
Build 07 — Stale Lead & Opportunity Stall Detection Service
===========================================================
Enforces the Revenue Continuity Invariant:
    "AN ACTIVE LEAD MUST ALWAYS HAVE A VALID NEXT-BEST-ACTION OR WORK ITEM."

Leads decaying silently without scheduled actions represent uncaptured revenue.
This service continuously monitors:
  1. Lead inactivity against FollowUpPolicy.stale_lead_days.
  2. The absence of pending/scheduled WorkItems for active leads.
  3. Opportunity stage stagnation and deal momentum decay.
  4. Automatic generation of explainable re-engagement WorkItems via WorkItemService.

Tenancy: Multi-tenant fail-closed with organization_id enforcement.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.models.lead import Lead
from app.models.crm_models import Task
from app.models.follow_up_models import FollowUpPolicy
from app.modules.follow_up.work_item_service import WorkItemService

logger = logging.getLogger(__name__)

ACTIVE_PIPELINE_STAGES = {
    "new", "pending", "contacted", "engaged", "qualified",
    "in_progress", "follow_up", "site_visit_scheduled", "offer_made", "negotiation"
}
TERMINAL_STAGES = {"won", "lost", "closed", "dropped", "archived", "unqualified"}


@dataclass
class StaleLeadItem:
    lead_id: str
    organization_id: str
    lead_name: Optional[str]
    days_inactive: int
    threshold_days: int
    classification: str  # "STALE_NO_ACTION" | "STALE_OVERDUE_ACTION" | "ACTIVE_HEALTHY"
    has_active_work_item: bool
    pending_work_item_count: int
    reason: str
    recommended_action: str
    revenue_at_risk_aed: float = 0.0


@dataclass
class StaleLeadScanReport:
    organization_id: str
    scanned_at: datetime
    total_active_leads: int
    stale_leads_count: int
    leads_without_next_action: int
    reengagement_items_created: int
    stale_leads: List[StaleLeadItem] = field(default_factory=list)


def _parse_uuid(val: Any) -> Optional[Any]:
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return val


class StaleLeadService:
    """
    Canonical detector for lead stagnation, missing next-best-actions, and revenue decay.
    """

    def __init__(self, db: AsyncSession, work_item_service: Optional[WorkItemService] = None):
        self.db = db
        self.work_item_service = work_item_service or WorkItemService(db)

    async def get_org_policy(self, organization_id: str) -> Optional[FollowUpPolicy]:
        """Fetch organization follow-up policy or return None."""
        stmt = select(FollowUpPolicy).where(FollowUpPolicy.organization_id == organization_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def evaluate_lead(
        self,
        lead_id: str,
        organization_id: str,
        stale_threshold_days: Optional[int] = None,
    ) -> StaleLeadItem:
        """
        Evaluate a single lead for staleness and missing next actions.
        """
        now = datetime.now(timezone.utc)
        parsed_lid = _parse_uuid(lead_id)

        # 1. Fetch Lead
        stmt = select(Lead).where(
            and_(
                Lead.id == parsed_lid,
                Lead.deleted_at.is_(None),
            )
        )
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()

        if not lead:
            raise ValueError(f"Lead {lead_id} not found or deleted")

        # Multi-tenancy check
        lead_org = str(lead.organization_id) if lead.organization_id else str(lead.broker_id)
        if lead_org != str(organization_id):
            raise PermissionError(f"Lead {lead_id} does not belong to organization {organization_id}")

        # 2. Determine threshold
        if stale_threshold_days is None:
            policy = await self.get_org_policy(organization_id)
            stale_threshold_days = policy.stale_lead_days if policy else 7

        # 3. Calculate inactivity
        last_activity = lead.last_message_at or lead.updated_at or lead.created_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        days_inactive = max(0, (now - last_activity).days)

        # 4. Check active WorkItems
        stmt_tasks = select(Task).where(
            and_(
                Task.lead_id == lead.id,
                Task.organization_id == organization_id,
                Task.status.in_(["pending", "scheduled", "ready", "in_progress"]),
            )
        )
        res_tasks = await self.db.execute(stmt_tasks)
        active_tasks = list(res_tasks.scalars().all())

        is_terminal = (
            (lead.pipeline_stage and lead.pipeline_stage.lower() in TERMINAL_STAGES) or
            (lead.status and lead.status.lower() in TERMINAL_STAGES)
        )

        # 5. Classify
        if is_terminal:
            return StaleLeadItem(
                lead_id=str(lead.id),
                organization_id=organization_id,
                lead_name=lead.name,
                days_inactive=days_inactive,
                threshold_days=stale_threshold_days,
                classification="TERMINAL_STAGE",
                has_active_work_item=len(active_tasks) > 0,
                pending_work_item_count=len(active_tasks),
                reason=f"Lead is in terminal stage ({lead.pipeline_stage or lead.status}).",
                recommended_action="NO_ACTION",
            )

        if not active_tasks:
            if days_inactive >= stale_threshold_days:
                classification = "STALE_NO_ACTION"
                reason = (
                    f"Lead has been inactive for {days_inactive} days (exceeds {stale_threshold_days}d threshold) "
                    f"and has NO pending or scheduled next-best-action."
                )
                rec_action = "REENGAGE_IMMEDIATELY"
            else:
                classification = "HEALTHY_BUT_NO_ACTION"
                reason = (
                    f"Lead active within threshold ({days_inactive}/{stale_threshold_days}d) "
                    f"but lacks a scheduled next-best-action."
                )
                rec_action = "SCHEDULE_NEXT_ACTION"
        else:
            # Check if any active task is overdue
            overdue_tasks = [
                t for t in active_tasks
                if t.due_at and (t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)) < now
            ]
            if overdue_tasks:
                classification = "STALE_OVERDUE_ACTION"
                reason = (
                    f"Lead has {len(overdue_tasks)} overdue action(s). "
                    f"Last activity was {days_inactive} days ago."
                )
                rec_action = "ESCALATE_OVERDUE_ACTION"
            else:
                classification = "ACTIVE_HEALTHY"
                reason = f"Lead has {len(active_tasks)} active scheduled work item(s)."
                rec_action = "MAINTAIN_SCHEDULE"

        budget = float(lead.budget_max or 0.0)
        return StaleLeadItem(
            lead_id=str(lead.id),
            organization_id=organization_id,
            lead_name=lead.name,
            days_inactive=days_inactive,
            threshold_days=stale_threshold_days,
            classification=classification,
            has_active_work_item=len(active_tasks) > 0,
            pending_work_item_count=len(active_tasks),
            reason=reason,
            recommended_action=rec_action,
            revenue_at_risk_aed=budget,
        )

    async def scan_organization(
        self,
        organization_id: str,
        stale_threshold_days: Optional[int] = None,
        auto_reengage: bool = False,
        limit: int = 200,
    ) -> StaleLeadScanReport:
        """
        Scan all active leads in an organization for stagnation and missing next actions.
        Optionally creates reengagement work items.
        """
        now = datetime.now(timezone.utc)
        parsed_oid = _parse_uuid(organization_id)
        if stale_threshold_days is None:
            policy = await self.get_org_policy(organization_id)
            stale_threshold_days = policy.stale_lead_days if policy else 7

        threshold_dt = now - timedelta(days=stale_threshold_days)

        # Find active leads for org
        stmt = select(Lead).where(
            and_(
                or_(
                    Lead.organization_id == parsed_oid,
                    and_(Lead.organization_id.is_(None), Lead.broker_id == parsed_oid),
                ),
                Lead.deleted_at.is_(None),
                Lead.status.notin_(list(TERMINAL_STAGES)),
                or_(Lead.pipeline_stage.is_(None), Lead.pipeline_stage.notin_(list(TERMINAL_STAGES))),
            )
        ).limit(limit)

        res = await self.db.execute(stmt)
        leads = list(res.scalars().all())

        stale_items: List[StaleLeadItem] = []
        created_count = 0

        for lead in leads:
            item = await self.evaluate_lead(
                str(lead.id),
                organization_id,
                stale_threshold_days=stale_threshold_days,
            )
            if item.classification in ("STALE_NO_ACTION", "STALE_OVERDUE_ACTION"):
                stale_items.append(item)

                if auto_reengage and item.classification == "STALE_NO_ACTION":
                    idemp_key = f"stale_reengage:{organization_id}:{lead.id}:{now.strftime('%Y-W%W')}"
                    try:
                        await self.work_item_service.create(
                            organization_id=organization_id,
                            broker_id=str(lead.broker_id),
                            task_type="REENGAGEMENT",
                            source="SYSTEM_SLA",
                            title=f"Re-engage Stale Lead: {lead.name or lead.phone}",
                            lead_id=str(lead.id),
                            description=f"Auto-generated re-engagement. Lead inactive for {item.days_inactive} days.",
                            reason=item.reason,
                            priority="high" if item.days_inactive >= stale_threshold_days * 2 else "normal",
                            due_at=now + timedelta(hours=4),
                            idempotency_key=idemp_key,
                        )
                        created_count += 1
                    except Exception as exc:
                        logger.warning(f"[StaleLeadService] Could not create re-engagement task: {exc}")

        leads_without_action = sum(1 for it in stale_items if not it.has_active_work_item)

        return StaleLeadScanReport(
            organization_id=organization_id,
            scanned_at=now,
            total_active_leads=len(leads),
            stale_leads_count=len(stale_items),
            leads_without_next_action=leads_without_action,
            reengagement_items_created=created_count,
            stale_leads=stale_items,
        )
