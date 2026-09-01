"""
Priority Calculator — Lead Temperature & Momentum Engine
=========================================================
Determines lead temperature classification, dynamic lead momentum (velocity),
and agent follow-up priorities (1-100).
"""
from typing import Dict, Any, Tuple


class PriorityCalculator:
    """
    Computes Lead Temperature, Momentum, and Agent Priorities.
    """

    def calculate(
        self,
        lead_score: float,
        score_yesterday: float,
        intent_phase: str,
        features: Dict[str, Any],
    ) -> Tuple[str, float, int, int]:
        """
        Returns (temperature, momentum, follow_up_priority, agent_priority)
        """
        # Dynamic Momentum
        momentum = round(lead_score - score_yesterday, 1)

        # Lead Temperature Classification
        if intent_phase == "purchase_ready" or (lead_score >= 85.0 and features.get("has_viewing_booked")):
            temperature = "purchase_ready"
        elif lead_score >= 75.0 or momentum >= 15.0:
            temperature = "very_hot"
        elif lead_score >= 55.0 or momentum >= 8.0:
            temperature = "hot"
        elif lead_score >= 35.0:
            temperature = "warm"
        else:
            temperature = "cold"

        # Priorities (1 - 100)
        base_priority = int(lead_score)

        # Boost follow-up priority if momentum is high or viewing is booked
        follow_up_priority = base_priority
        if momentum > 10.0:
            follow_up_priority += 15
        if features.get("has_viewing_booked"):
            follow_up_priority += 20
        follow_up_priority = max(1, min(100, follow_up_priority))

        # Agent priority (experienced agents assigned to high-value / luxury leads)
        agent_priority = base_priority
        if features.get("is_luxury"):
            agent_priority += 25
        elif features.get("is_high_value"):
            agent_priority += 15
        agent_priority = max(1, min(100, agent_priority))

        return temperature, momentum, follow_up_priority, agent_priority
