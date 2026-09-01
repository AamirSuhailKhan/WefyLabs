"""
Volume 2 PART 2 — Budget Classifier
"""
from typing import Dict, Any, Optional

# Average starting prices in AED for Dubai Real Estate
MIN_FEASIBLE_BUDGET_AED = {
    "1bhk": 700000,
    "2bhk": 1200000,
    "3bhk": 2000000,
    "villa": 3000000,
    "plot": 1500000,
}


class BudgetClassifier:
    @staticmethod
    def classify(budget_aed: Optional[float], property_type: Optional[str]) -> Dict[str, Any]:
        if not budget_aed or budget_aed <= 0:
            return {
                "budget_tier": "unknown",
                "is_realistic": None,
                "budget_confidence": 0.2
            }

        # Determine tier
        if budget_aed >= 5000000:
            tier = "ultra_luxury"
        elif budget_aed >= 2500000:
            tier = "luxury"
        elif budget_aed >= 1200000:
            tier = "mid_tier"
        else:
            tier = "entry_level"

        # Check market feasibility
        is_realistic = True
        if property_type and property_type in MIN_FEASIBLE_BUDGET_AED:
            min_req = MIN_FEASIBLE_BUDGET_AED[property_type]
            if budget_aed < (min_req * 0.7):
                is_realistic = False

        confidence = 0.90 if is_realistic else 0.65

        return {
            "budget_tier": tier,
            "is_realistic": is_realistic,
            "budget_confidence": confidence
        }
