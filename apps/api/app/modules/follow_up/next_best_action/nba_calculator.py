"""
Next Best Action (NBA) Engine
=============================
Calculates the optimal revenue-generating next step for a lead.
Outputs (recommended_action, action_reason, priority_score, confidence, expected_outcome).
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.follow_up_models import NextBestAction, FollowUpPolicy

logger = logging.getLogger(__name__)

class NextBestActionEngine:
    """
    Evaluates lead momentum, stage, and fatigue to compute the Next Best Action.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_next_best_action(
        self,
        lead: Lead,
        policy: Optional[FollowUpPolicy] = None,
        target_property_id: Optional[str] = None
    ) -> NextBestAction:
        """
        Computes and persists the optimal next step for the lead.
        """
        stage = (lead.pipeline_stage or "new").upper()
        lead_id = str(lead.id)
        org_id = str(policy.organization_id if policy else "default_org")

        action = "Send WhatsApp Follow-Up"
        reason = "Lead is active in pipeline; prompt with relevant inventory."
        priority = 60.0
        confidence = 0.90
        outcome = "Customer reply / interest confirmation"

        if stage == "NEW":
            action = "Send Initial WhatsApp Greeting & Discovery"
            reason = "New inbound inquiry requires immediate sub-5-minute contact."
            priority = 95.0
            outcome = "Lead qualification & budget discovery"

        elif stage == "QUALIFIED":
            action = "Send AI Property Recommendations"
            reason = "Lead criteria is qualified; present top 3 verified matches."
            priority = 85.0
            outcome = "Viewing request / shortlist"

        elif stage == "VIEWING_BOOKED":
            action = "Send Viewing Reminder & Location Pin"
            reason = "Viewing slot is scheduled; confirm attendance 24h/2h prior."
            priority = 90.0
            outcome = "Viewing attendance"

        elif stage == "VIEWING_COMPLETED":
            action = "Call for Site Visit Feedback & Next Steps"
            reason = "Viewing completed; capture buyer feedback and gauge offer intent."
            priority = 80.0
            outcome = "Offer submission / alternative property search"

        elif stage == "HUMAN_HANDOFF":
            action = "Broker Direct Phone Call"
            reason = "Customer requested human interaction or has high-value inquiry."
            priority = 90.0
            outcome = "Direct broker consultation"

        elif stage == "UNRESPONSIVE":
            action = "Enroll in Long-Term Nurture Sequence"
            reason = "Multiple unanswered attempts; transition to low-frequency nurture."
            priority = 40.0
            outcome = "Re-activation upon market/inventory change"

        elif stage in ("DO_NOT_CONTACT", "CONVERTED", "LOST", "CLOSED"):
            action = "No Action (Terminal State)"
            reason = f"Lead is in terminal state '{stage}'."
            priority = 0.0
            confidence = 1.0
            outcome = "None"

        nba = NextBestAction(
            lead_id=lead_id,
            organization_id=org_id,
            recommended_action=action,
            action_reason=reason,
            priority_score=priority,
            confidence=confidence,
            expected_outcome=outcome,
            target_property_id=target_property_id,
            calculated_at=datetime.now(timezone.utc)
        )
        return nba
