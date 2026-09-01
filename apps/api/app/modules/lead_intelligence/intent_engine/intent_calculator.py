"""
Intent Calculator — Buyer Intent Engine
=======================================
Infers buyer intent phase (Research -> Comparison -> Decision -> Negotiation -> Purchase Ready -> Post Purchase)
and computes a 0-100 Intent Score based on engagement signals, financing status, and property definition.
"""
from typing import Dict, Any, Tuple


class IntentCalculator:
    """
    Computes Buyer Intent Score (0-100) and Buyer Intent Phase.
    """

    def calculate(self, features: Dict[str, Any]) -> Tuple[float, str]:
        """
        Returns (intent_score, intent_phase)
        """
        score = 20.0  # Baseline intent

        # Specification specificity (+25 max)
        if features.get("property_type") and features["property_type"] != "unknown":
            score += 15.0
        if features.get("budget_aed", 0) > 0:
            score += 10.0

        # Financing & purchasing power (+25 max)
        if features.get("is_cash_buyer") or features.get("has_mortgage_preapproval"):
            score += 25.0
        elif features.get("loan_status") == "in_process":
            score += 15.0

        # Engagement & active commitment (+30 max)
        if features.get("has_viewing_booked") or features.get("meeting_count", 0) > 0:
            score += 30.0
        elif features.get("activity_count", 0) >= 3:
            score += 15.0

        # Timeline urgency (+20 max)
        if features.get("is_immediate"):
            score += 20.0
        elif features.get("timeline") == "3_months":
            score += 10.0

        intent_score = min(100.0, round(score, 1))

        # Infer Intent Phase
        if intent_score >= 85.0 and (features.get("has_viewing_booked") or features.get("is_cash_buyer")):
            phase = "purchase_ready"
        elif intent_score >= 70.0 and features.get("has_viewing_booked"):
            phase = "negotiation"
        elif intent_score >= 55.0:
            phase = "decision"
        elif intent_score >= 35.0:
            phase = "comparison"
        else:
            phase = "research"

        return intent_score, phase
