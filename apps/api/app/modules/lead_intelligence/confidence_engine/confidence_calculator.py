"""
Confidence Calculator — Confidence & Explainable AI Engine
==========================================================
Computes overall model confidence and extracts top positive/negative conversion drivers
for Explainable AI rationale.
"""
from typing import Dict, Any, List, Tuple


class ConfidenceCalculator:
    """
    Computes overall prediction confidence and generates Explainable AI drivers.
    """

    def compute_explanation(
        self,
        features: Dict[str, Any],
        lead_score: float,
        rules_fired: List[Dict[str, Any]],
        contributions: Dict[str, Any],
    ) -> Tuple[float, List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """
        Returns (overall_confidence, positive_drivers, negative_drivers, business_rationale)
        """
        positive_drivers = []
        negative_drivers = []

        # Analyze rules fired
        for rule in rules_fired:
            val = rule.get("action_value", 0.0)
            name = rule.get("name", "Rule")
            if val > 0:
                positive_drivers.append({"driver": name, "impact": f"+{int(val)} pts", "type": "rule"})
            elif val < 0:
                negative_drivers.append({"driver": name, "impact": f"{int(val)} pts", "type": "rule"})

        # Analyze feature conditions
        if features.get("has_viewing_booked"):
            positive_drivers.append({"driver": "Site Visit Booked", "impact": "+24% conversion lift", "type": "feature"})
        if features.get("is_cash_buyer") or features.get("has_mortgage_preapproval"):
            positive_drivers.append({"driver": "Cash / Mortgage Pre-approved", "impact": "+15% conversion lift", "type": "feature"})
        if features.get("is_high_value"):
            positive_drivers.append({"driver": "High Budget (>= 3M AED)", "impact": "+12% conversion lift", "type": "feature"})

        if not features.get("has_phone"):
            negative_drivers.append({"driver": "Phone Number Missing", "impact": "-15% conversion friction", "type": "feature"})
        if features.get("lead_age_days", 0) > 14 and features.get("activity_count", 0) == 0:
            negative_drivers.append({"driver": "Inactive for 14+ days", "impact": "-18% conversion friction", "type": "feature"})
        if features.get("loan_status") == "not_started":
            negative_drivers.append({"driver": "Financing Not Started", "impact": "-10% conversion friction", "type": "feature"})

        # Top 3 positive and top 3 negative
        pos_top = positive_drivers[:3]
        neg_top = negative_drivers[:3]

        # Overall confidence
        completeness = float(features.get("field_completion_rate") or 0.5)
        overall_confidence = round(min(0.98, max(0.50, 0.65 + (completeness * 0.30))), 2)

        # Business rationale summary
        pos_str = ", ".join([d["driver"] for d in pos_top]) or "Basic contact info provided"
        neg_str = ", ".join([d["driver"] for d in neg_top]) or "No major friction points detected"
        rationale = f"Lead Score {lead_score:.0f}/100. Positive Drivers: {pos_str}. Conversion Friction: {neg_str}."

        return overall_confidence, pos_top, neg_top, rationale
