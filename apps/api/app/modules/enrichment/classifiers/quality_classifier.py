"""
Volume 2 PART 2 — Quality Classifier (0-100 Score & Quality Tiering)
"""
from typing import Dict, Any, Optional


class QualityClassifier:
    @staticmethod
    def evaluate(
        has_phone: bool,
        has_email: bool,
        budget_aed: Optional[float],
        timeline: Optional[str],
        urgency: Optional[str],
        property_type: Optional[str],
        intent_score: float = 0.5,
        field_completion_rate: float = 0.5
    ) -> Dict[str, Any]:
        score = 0.0

        # Contactability (Max 30 pts)
        if has_phone:
            score += 20.0
        if has_email:
            score += 10.0

        # Financial Capacity (Max 30 pts)
        if budget_aed:
            if budget_aed >= 2500000:
                score += 30.0
            elif budget_aed >= 1000000:
                score += 22.0
            else:
                score += 15.0

        # Buying Urgency & Intent (Max 25 pts)
        if urgency == "high" or timeline == "immediate":
            score += 25.0
        elif timeline == "1_month":
            score += 18.0
        elif timeline == "3_months":
            score += 10.0
        else:
            score += 5.0

        # Property Definition (Max 15 pts)
        if property_type:
            score += 15.0

        final_score = min(100.0, round(score, 1))

        # Assign Quality Tier
        if final_score >= 75.0:
            tier = "hot"
        elif final_score >= 50.0:
            tier = "warm"
        elif final_score >= 25.0:
            tier = "cold"
        else:
            tier = "unqualified"

        return {
            "overall_quality_score": final_score,
            "quality_tier": tier
        }
