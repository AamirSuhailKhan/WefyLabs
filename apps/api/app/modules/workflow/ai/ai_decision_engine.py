"""
Structured AI Decision Node Engine & Confidence Gates
======================================================
Executes AI-assisted qualification, next-action evaluation, and routing.
Enforces strict confidence tiers:
- Confidence >= 0.85 -> Autonomous Execution Allowed
- 0.60 <= Confidence < 0.85 -> Routes to Human Approval Gate
- Confidence < 0.60 -> Routes to Deterministic Fallback Branch
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AIDecisionResult:
    decision: str
    confidence: float
    reason_codes: List[str]
    autonomous_allowed: bool
    requires_approval: bool
    requires_fallback: bool
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": round(self.confidence, 4),
            "reason_codes": self.reason_codes,
            "autonomous_allowed": self.autonomous_allowed,
            "requires_approval": self.requires_approval,
            "requires_fallback": self.requires_fallback,
            "explanation": self.explanation
        }


class AIDecisionEngine:
    """
    Evaluates structured AI decisions within workflow execution graphs.
    """

    @classmethod
    def evaluate_ai_decision(
        cls,
        decision_prompt: str,
        context: Dict[str, Any],
        confidence_threshold_auto: float = 0.85,
        confidence_threshold_approval: float = 0.60
    ) -> AIDecisionResult:
        """
        Executes controlled decision assessment over context variables (e.g. lead score, intent, budget).
        """
        lead_score = float(context.get("lead_score", context.get("lead", {}).get("score", 70.0)) or 70.0)
        has_budget = bool(context.get("has_budget", True))
        intent = str(context.get("intent_phase", "active_search")).lower()

        # Deterministic feature-weighted decision evaluation
        if "viewing" in decision_prompt.lower():
            if lead_score >= 75.0 and has_budget:
                decision = "BOOK_VIEWING"
                confidence = 0.88
                reasons = ["HIGH_BUYER_INTENT", "VERIFIED_BUDGET", "MATCHING_PROPERTY_AVAILABLE"]
                explanation = "Lead has high intent and verified purchasing capacity for immediate viewing."
            elif lead_score >= 50.0:
                decision = "REQUEST_MORE_DETAILS"
                confidence = 0.72
                reasons = ["WARM_LEAD", "UNRESOLVED_TIMELINE"]
                explanation = "Lead is interested but timeline requires agent confirmation."
            else:
                decision = "NURTURE"
                confidence = 0.55
                reasons = ["COLD_LEAD_SCORE", "LOW_RESPONSE_VELOCITY"]
                explanation = "Lead not yet qualified for high-touch viewing."
        else:
            # General qualification decision
            if lead_score >= 70.0:
                decision = "QUALIFIED"
                confidence = 0.90
                reasons = ["HIGH_ENGAGEMENT_SCORE"]
                explanation = "Qualified lead meeting score threshold."
            else:
                decision = "NURTURE"
                confidence = 0.65
                reasons = ["BELOW_SCORE_THRESHOLD"]
                explanation = "Lead routed to long-term automated nurturing."

        is_auto = confidence >= confidence_threshold_auto
        is_approval = confidence_threshold_approval <= confidence < confidence_threshold_auto
        is_fallback = confidence < confidence_threshold_approval

        return AIDecisionResult(
            decision=decision,
            confidence=confidence,
            reason_codes=reasons,
            autonomous_allowed=is_auto,
            requires_approval=is_approval,
            requires_fallback=is_fallback,
            explanation=explanation
        )
