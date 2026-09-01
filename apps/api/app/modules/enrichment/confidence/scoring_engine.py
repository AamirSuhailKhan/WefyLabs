"""
Volume 2 PART 2 — Confidence Scoring Engine
"""
from typing import Dict, Any, List


class ScoringEngine:
    """
    Computes overall profile confidence score and field completion rate.
    """
    TOTAL_CANONICAL_FIELDS = [
        "name", "email", "phone", "country", "state", "city",
        "timezone", "language", "nationality", "occupation", "company",
        "budget_min", "budget_max", "budget_canonical_aed", "property_type",
        "bedrooms", "bathrooms", "preferred_locations", "purpose",
        "timeline", "financing_required", "urgency", "intent"
    ]

    @classmethod
    def calculate_field_completion(cls, enriched_dict: Dict[str, Any]) -> float:
        present_count = 0
        for field in cls.TOTAL_CANONICAL_FIELDS:
            val = enriched_dict.get(field)
            if val is not None and val != "" and val != []:
                present_count += 1

        return round(present_count / len(cls.TOTAL_CANONICAL_FIELDS), 2)

    @classmethod
    def calculate_overall_confidence(cls, field_confidence_scores: List[float]) -> float:
        if not field_confidence_scores:
            return 0.0
        avg = sum(field_confidence_scores) / len(field_confidence_scores)
        return round(avg, 2)
