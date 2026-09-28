"""
Build 07 — Re-engagement Eligibility Gate
=========================================
Prevents unlawful, fatigued, or conflicting automated re-engagement outreach.

A lead is ONLY eligible for re-engagement if:
  1. Tenant isolation passes (lead belongs to organization).
  2. Consent is ACTIVE and lead has NOT opted out / marked DNC.
  3. Lead has been inactive for at least `reengagement_days` (default: 14d, min: 7d).
  4. Human agent is NOT actively conversing (no human takeover).
  5. Lead is NOT in a terminal state (CONVERTED, LOST, CLOSED, DO_NOT_CONTACT).
  6. Fatigue limits and minimum message intervals are respected.
  7. Lifetime re-engagement attempts have not been exhausted.

INVARIANT:
  No draft or message is generated without passing this gate first.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy, FollowUpExecution
from app.models.crm_models import Task
from app.modules.follow_up.suppression.suppression_engine import SuppressionEngine
from app.modules.follow_up.ai_reengagement.reengagement_service import ReengagementService

logger = logging.getLogger(__name__)

TERMINAL_STATES = {"CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED", "ARCHIVED", "UNQUALIFIED"}
MAX_LIFETIME_REENGAGEMENTS = 3


@dataclass
class ReengagementEligibilityResult:
    eligible: bool
    lead_id: str
    organization_id: str
    reason: str
    days_inactive: int
    required_inactivity_days: int
    rules_evaluated: Dict[str, Any] = field(default_factory=dict)
    reengagement_attempts: int = 0


class ReengagementEligibilityGate:
    """
    Pre-execution guard for any automated re-engagement action.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.suppression_engine = SuppressionEngine(db)

    async def evaluate_eligibility(
        self,
        lead: Lead,
        organization_id: str,
        policy: Optional[FollowUpPolicy] = None,
        channel: str = "WHATSAPP",
    ) -> ReengagementEligibilityResult:
        """
        Comprehensive check before drafting or sending re-engagement.
        """
        now = datetime.now(timezone.utc)
        lead_id = str(lead.id)
        rules: Dict[str, Any] = {}

        # 1. Multi-tenant check
        lead_org = str(lead.organization_id) if lead.organization_id else str(lead.broker_id)
        if lead_org != str(organization_id):
            return ReengagementEligibilityResult(
                eligible=False,
                lead_id=lead_id,
                organization_id=organization_id,
                reason=f"Multi-tenant violation: lead belongs to {lead_org}, not {organization_id}",
                days_inactive=0,
                required_inactivity_days=14,
                rules_evaluated={"tenant_isolation": False},
            )
        rules["tenant_isolation"] = True

        # 2. Policy retrieval
        if not policy:
            stmt = select(FollowUpPolicy).where(FollowUpPolicy.organization_id == organization_id)
            res = await self.db.execute(stmt)
            policy = res.scalar_one_or_none()

        req_days = policy.reengagement_days if policy else 14

        # 3. Terminal state check
        stage = (lead.pipeline_stage or lead.status or "new").upper()
        if stage in TERMINAL_STATES:
            rules["lifecycle_state"] = False
            return ReengagementEligibilityResult(
                eligible=False,
                lead_id=lead_id,
                organization_id=organization_id,
                reason=f"Lead is in terminal state '{stage}'",
                days_inactive=0,
                required_inactivity_days=req_days,
                rules_evaluated=rules,
            )
        rules["lifecycle_state"] = True

        # 4. Human takeover check
        is_human_active = getattr(lead, "human_takeover", False) or stage == "HUMAN_HANDOFF"
        if is_human_active:
            rules["human_takeover"] = False
            return ReengagementEligibilityResult(
                eligible=False,
                lead_id=lead_id,
                organization_id=organization_id,
                reason="Human broker has active control; automated re-engagement prohibited.",
                days_inactive=0,
                required_inactivity_days=req_days,
                rules_evaluated=rules,
            )
        rules["human_takeover"] = True

        # 5. Inactivity threshold check
        last_activity = lead.last_message_at or lead.updated_at or lead.created_at
        if last_activity and last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        days_inactive = max(0, (now - last_activity).days) if last_activity else 999

        if days_inactive < req_days:
            rules["inactivity_period"] = False
            return ReengagementEligibilityResult(
                eligible=False,
                lead_id=lead_id,
                organization_id=organization_id,
                reason=f"Lead inactive for only {days_inactive}d; policy requires at least {req_days}d.",
                days_inactive=days_inactive,
                required_inactivity_days=req_days,
                rules_evaluated=rules,
            )
        rules["inactivity_period"] = True

        # 6. Prior Re-engagement Attempt Count
        stmt_prev = select(Task).where(
            and_(
                Task.lead_id == lead.id,
                Task.organization_id == organization_id,
                Task.task_type.in_(["REENGAGEMENT", "reengagement"]),
                Task.status.in_(["completed", "pending", "scheduled"]),
            )
        )
        res_prev = await self.db.execute(stmt_prev)
        prev_attempts = len(list(res_prev.scalars().all()))

        if prev_attempts >= MAX_LIFETIME_REENGAGEMENTS:
            rules["max_attempts"] = False
            return ReengagementEligibilityResult(
                eligible=False,
                lead_id=lead_id,
                organization_id=organization_id,
                reason=f"Exhausted maximum re-engagement attempts ({prev_attempts}/{MAX_LIFETIME_REENGAGEMENTS}).",
                days_inactive=days_inactive,
                required_inactivity_days=req_days,
                rules_evaluated=rules,
                reengagement_attempts=prev_attempts,
            )
        rules["max_attempts"] = True

        # 7. Suppression Engine Evaluation (consent, fatigue, interval)
        if policy:
            is_suppressed, supp_reason, rules_list = await self.suppression_engine.evaluate_suppression(
                lead=lead,
                channel=channel,
                policy=policy,
                purpose="MARKETING_AND_FOLLOWUP",
            )
            if is_suppressed:
                rules["suppression_check"] = False
                rules["suppression_reason"] = supp_reason
                return ReengagementEligibilityResult(
                    eligible=False,
                    lead_id=lead_id,
                    organization_id=organization_id,
                    reason=f"Suppressed by governance policy: {supp_reason}",
                    days_inactive=days_inactive,
                    required_inactivity_days=req_days,
                    rules_evaluated=rules,
                    reengagement_attempts=prev_attempts,
                )
        rules["suppression_check"] = True

        return ReengagementEligibilityResult(
            eligible=True,
            lead_id=lead_id,
            organization_id=organization_id,
            reason="Lead meets all eligibility, consent, and cooldown criteria for re-engagement.",
            days_inactive=days_inactive,
            required_inactivity_days=req_days,
            rules_evaluated=rules,
            reengagement_attempts=prev_attempts,
        )

    async def generate_safe_reengagement(
        self,
        lead: Lead,
        organization_id: str,
        policy: Optional[FollowUpPolicy] = None,
        broker_name: str = "your advisor",
    ) -> Dict[str, Any]:
        """
        Safe gated execution: Checks eligibility first, only drafts if approved.
        """
        eligibility = await self.evaluate_eligibility(lead, organization_id, policy)
        if not eligibility.eligible:
            return {
                "eligible": False,
                "lead_id": str(lead.id),
                "reason": eligibility.reason,
                "rules_evaluated": eligibility.rules_evaluated,
                "draft": None,
            }

        draft = await ReengagementService.generate_reengagement_draft(
            lead=lead,
            days_inactive=eligibility.days_inactive,
            broker_name=broker_name,
        )

        return {
            "eligible": True,
            "lead_id": str(lead.id),
            "reason": eligibility.reason,
            "rules_evaluated": eligibility.rules_evaluated,
            "draft": draft,
        }
