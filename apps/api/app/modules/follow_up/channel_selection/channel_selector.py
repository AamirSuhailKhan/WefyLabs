"""
Channel Selection & Scoring Engine
==================================
Selects the most appropriate permitted communication channel based on customer preferences,
channel consent, organization policy, and message urgency.
"""

import logging
from typing import Tuple, List
from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy

logger = logging.getLogger(__name__)

class ChannelSelector:
    """
    Evaluates channel suitability scores and determines optimal dispatch channel.
    """

    def select_channel(
        self,
        lead: Lead,
        policy: FollowUpPolicy,
        preferred_step_channel: str = "WHATSAPP",
        reason_type: str = "UNANSWERED_INQUIRY"
    ) -> Tuple[str, float]:
        """
        Determines the best channel and returns (channel_name, suitability_score).
        """
        allowed = [c.upper() for c in (policy.allowed_channels or ["WHATSAPP", "EMAIL"])]

        # 1. Document requests or heavy info prefer Email if allowed
        if reason_type in ("DOCUMENT_REQUEST", "PAYMENT_PLAN_UPDATE") and "EMAIL" in allowed:
            return "EMAIL", 0.95

        # 2. Preferred step channel if allowed
        step_ch = preferred_step_channel.upper()
        if step_ch in allowed:
            return step_ch, 0.90

        # 3. Fallback to first allowed channel
        if allowed:
            return allowed[0], 0.75

        return "WHATSAPP", 0.50
