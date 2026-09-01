"""
Urgency Calculator — Urgency Engine
===================================
Calculates 0-100 Urgency Score based on buyer timeline, financing readiness,
viewing activity, and response delays.
"""
from typing import Dict, Any


class UrgencyCalculator:
    """
    Computes Urgency Score (0.0 - 100.0).
    """

    def calculate(self, features: Dict[str, Any]) -> float:
        score = 10.0

        # Timeline factor (Max 40 pts)
        timeline = features.get("timeline")
        if timeline == "immediate":
            score += 40.0
        elif timeline == "1_month":
            score += 25.0
        elif timeline == "3_months":
            score += 15.0

        # Financing factor (Max 30 pts)
        if features.get("is_cash_buyer"):
            score += 30.0
        elif features.get("has_mortgage_preapproval"):
            score += 25.0
        elif features.get("loan_status") == "in_process":
            score += 15.0

        # Action / Commitment factor (Max 30 pts)
        if features.get("has_viewing_booked"):
            score += 30.0
        elif features.get("meeting_count", 0) > 0:
            score += 20.0

        # Inactivity decay penalty
        age_days = float(features.get("lead_age_days") or 0.0)
        activity = int(features.get("activity_count") or 0)
        if age_days > 14 and activity == 0:
            score -= 15.0
        elif age_days > 30 and activity <= 1:
            score -= 25.0

        return max(0.0, min(100.0, round(score, 1)))
