"""
Multi-Rule Suppression Engine
=============================
Evaluates whether an outbound follow-up must be suppressed due to opt-out,
human active takeover, contact fatigue, frequency caps, or recent replies.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy, FollowUpExecution
from app.modules.follow_up.consent.consent_manager import ConsentManager
from app.modules.follow_up.fatigue.fatigue_detector import FatigueDetector

logger = logging.getLogger(__name__)

class SuppressionEngine:
    """
    Evaluates multi-rule suppression criteria before scheduling or sending messages.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.consent_manager = ConsentManager(db)
        self.fatigue_detector = FatigueDetector(db)

    async def evaluate_suppression(
        self,
        lead: Lead,
        channel: str,
        policy: FollowUpPolicy,
        purpose: str = "MARKETING_AND_FOLLOWUP"
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """
        Runs comprehensive suppression checks.
        Returns (is_suppressed, primary_reason, evaluated_rules_list).
        """
        lead_id = str(lead.id)
        org_id = policy.organization_id
        rules_evaluated: List[Dict[str, Any]] = []

        # ── 1. Terminal State Check ──────────────────────────────────────────
        stage = (lead.pipeline_stage or "new").upper()
        if stage in ("CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED"):
            reason = f"Lead is in terminal lifecycle state '{stage}'"
            rules_evaluated.append({"rule": "terminal_state", "passed": False, "reason": reason})
            return True, reason, rules_evaluated
        rules_evaluated.append({"rule": "terminal_state", "passed": True})

        # ── 2. Human Active Takeover Check ───────────────────────────────────
        if stage == "HUMAN_HANDOFF":
            reason = "Human agent has active ownership of conversation"
            rules_evaluated.append({"rule": "human_handoff", "passed": False, "reason": reason})
            return True, reason, rules_evaluated
        rules_evaluated.append({"rule": "human_handoff", "passed": True})

        # ── 3. Consent & Opt-Out Check ───────────────────────────────────────
        has_consent = await self.consent_manager.verify_consent(lead_id, channel, purpose)
        if not has_consent:
            reason = f"No valid consent or customer opted out for channel '{channel}'"
            rules_evaluated.append({"rule": "consent_check", "passed": False, "reason": reason})
            return True, reason, rules_evaluated
        rules_evaluated.append({"rule": "consent_check", "passed": True})

        # ── 4. Contact Fatigue & Unanswered Cap ──────────────────────────────
        is_fatigued, fatigue_score, fatigue_reason = await self.fatigue_detector.evaluate_fatigue(lead_id, org_id, policy)
        if is_fatigued:
            rules_evaluated.append({
                "rule": "contact_fatigue",
                "passed": False,
                "fatigue_score": fatigue_score,
                "reason": fatigue_reason
            })
            return True, fatigue_reason, rules_evaluated
        rules_evaluated.append({"rule": "contact_fatigue", "passed": True, "fatigue_score": fatigue_score})

        # ── 5. Minimum Interval Between Outbound Messages ────────────────────
        stmt_last = (
            select(FollowUpExecution)
            .where(
                FollowUpExecution.lead_id == lead_id,
                FollowUpExecution.status.in_(["DISPATCHED", "DELIVERED", "READ"])
            )
            .order_by(desc(FollowUpExecution.executed_at))
            .limit(1)
        )
        res_last = await self.db.execute(stmt_last)
        last_exec = res_last.scalar_one_or_none()

        if last_exec and last_exec.executed_at:
            min_hours = policy.min_hours_between_msgs or 18
            delta = datetime.now(timezone.utc) - last_exec.executed_at
            if delta < timedelta(hours=min_hours):
                reason = f"Minimum interval between messages not met ({delta.total_seconds() / 3600:.1f}h < {min_hours}h)"
                rules_evaluated.append({"rule": "min_interval", "passed": False, "reason": reason})
                return True, reason, rules_evaluated

        rules_evaluated.append({"rule": "min_interval", "passed": True})

        return False, None, rules_evaluated
