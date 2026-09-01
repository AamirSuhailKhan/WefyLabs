"""
Part 21.5 — Human Approval & Escalation Guard
=============================================
Identifies situations requiring mandatory human broker review before execution:
- Customer complaints, legal/compliance questions
- Price disputes, aggressive negotiation
- High-value luxury leads (e.g. >= 5M AED)
- Explicit agent requests or unresolved qualification conflicts
- Low autonomy policy settings
"""
import re
import logging
from typing import Tuple, Optional, List, Dict, Any

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy
from app.modules.sales_action.taxonomies import HandoffReason

logger = logging.getLogger(__name__)

COMPLAINT_PATTERNS = [
    r"\b(complaint|complain|scam|fraud|sue|lawyer|legal|illegal|police|court|unacceptable|terrible|horrible|angry|cheat|cheated)\b",
]

NEGOTIATION_PATTERNS = [
    r"\b(discount|negotiate|cheaper|lowest price|best price|reduce price|last price|commission cut|cash rebate|waiver)\b",
]

AGENT_REQUEST_PATTERNS = [
    r"\b(human|agent|broker|manager|managing|director|person|representative|executive|consultant|advisor|call me|talk to someone|speak to someone|speak to|talk to|speak directly|real person|not a bot|stop bot)\b",
]


class HumanApprovalGuard:
    """
    Evaluates whether an action must be gated behind human broker review or escalated.
    """

    @classmethod
    def check_message_triggers(cls, latest_message: Optional[str]) -> Tuple[bool, Optional[HandoffReason], Optional[str]]:
        """
        Scans latest customer text for urgent human triggers.
        Returns (requires_handoff, handoff_reason, explanation).
        """
        if not latest_message:
            return False, None, None

        msg_lower = latest_message.lower()

        # 1. Complaint / Legal Risk
        for pat in COMPLAINT_PATTERNS:
            if re.search(pat, msg_lower):
                return True, HandoffReason.COMPLAINT, "Customer message indicates complaint, dispute, or legal concern."

        # 2. Explicit Human Agent Request
        for pat in AGENT_REQUEST_PATTERNS:
            if re.search(pat, msg_lower):
                return True, HandoffReason.CUSTOMER_REQUESTED_AGENT, "Customer explicitly requested to speak with a human agent/broker."

        # 3. Price Negotiation / Discounts
        for pat in NEGOTIATION_PATTERNS:
            if re.search(pat, msg_lower):
                return True, HandoffReason.PRICE_NEGOTIATION, "Customer requested custom price negotiation or discount."

        return False, None, None

    @classmethod
    def evaluate_approval_requirement(
        cls,
        lead: Lead,
        policy: Optional[FollowUpPolicy] = None,
        has_blocking_conflicts: bool = False,
        latest_message: Optional[str] = None,
        confidence_score: float = 0.85,
    ) -> Tuple[bool, Optional[str], Optional[HandoffReason]]:
        """
        Determines whether manual broker approval is required.
        Returns (requires_human_approval, reason_text, handoff_reason).
        """
        # 1. Message-based triggers
        req_msg, msg_reason, msg_exp = cls.check_message_triggers(latest_message)
        if req_msg:
            return True, msg_exp, msg_reason

        # 2. Open qualification / property conflicts
        if has_blocking_conflicts:
            return True, "Lead has unresolved qualification facts or data conflicts requiring review.", HandoffReason.QUALIFICATION_CONFLICT

        # 3. Low confidence evaluation
        if confidence_score < 0.60:
            return True, f"Confidence score ({confidence_score:.2f}) is below safe automation threshold (0.60).", HandoffReason.LOW_CONFIDENCE

        # 4. High-value luxury lead threshold
        budget_max = float(lead.budget_max or 0.0)
        high_value_thresh = float(policy.high_value_threshold_aed) if (policy and policy.high_value_threshold_aed) else 5000000.0
        require_high_val = policy.require_approval_high_value if policy else True

        if require_high_val and budget_max >= high_value_thresh:
            return True, f"Lead budget ({budget_max:,.0f} AED) meets or exceeds high-value threshold ({high_value_thresh:,.0f} AED).", HandoffReason.HIGH_VALUE_OPPORTUNITY

        # 5. Low autonomy policy level
        autonomy = (policy.autonomy_level if policy else "LEVEL_3").upper()
        if autonomy in ("LEVEL_0", "LEVEL_1", "LEVEL_2"):
            return True, f"Organization autonomy level '{autonomy}' mandates human broker approval prior to dispatch.", None

        return False, None, None
