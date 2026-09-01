"""
Revenue Calculator — Revenue Intelligence & What-If Simulator
===============================================================
Computes expected deal revenue, probability-weighted pipeline revenue, estimated commission,
and runs 'What-If' revenue impact simulations.
"""
from typing import Dict, Any


class RevenueCalculator:
    """
    Computes Revenue Intelligence metrics and What-If scenarios.
    """

    COMMISSION_RATE = 0.02  # 2% standard Dubai real estate agency commission

    def calculate_revenue(
        self,
        features: Dict[str, Any],
        conversion_probability: float,
    ) -> Dict[str, float]:
        budget = float(features.get("budget_aed") or 1_500_000.0)
        # Default property value assumption if budget is zero
        if budget <= 0:
            budget = 1_500_000.0

        estimated_revenue = budget
        estimated_commission = estimated_revenue * self.COMMISSION_RATE
        prob_weighted_revenue = estimated_revenue * conversion_probability
        prob_weighted_commission = estimated_commission * conversion_probability

        ltv_estimate = estimated_revenue * 1.2 if features.get("is_repeat_buyer") else estimated_revenue

        return {
            "estimated_revenue_aed": round(estimated_revenue, 2),
            "estimated_commission_aed": round(estimated_commission, 2),
            "probability_weighted_revenue_aed": round(prob_weighted_revenue, 2),
            "probability_weighted_commission_aed": round(prob_weighted_commission, 2),
            "ltv_estimate_aed": round(ltv_estimate, 2),
        }

    def simulate_what_if(
        self,
        current_pipeline: Dict[str, Any],
        response_time_improvement_pct: float = 50.0,  # e.g. 50% faster responses
        viewing_booking_increase_pct: float = 20.0,    # e.g. 20% more viewings
    ) -> Dict[str, Any]:
        """
        Runs 'What-If' revenue impact simulation for managers.
        Returns baseline vs simulated revenue lift.
        """
        base_revenue = current_pipeline.get("probability_weighted_revenue_aed", 10_000_000.0)
        base_commission = current_pipeline.get("expected_commission_aed", 200_000.0)

        # Response time impact (+0.2% revenue per 1% response time speedup)
        response_lift_multiplier = 1.0 + (response_time_improvement_pct * 0.002)

        # Viewing impact (+0.3% revenue per 1% viewing increase)
        viewing_lift_multiplier = 1.0 + (viewing_booking_increase_pct * 0.003)

        simulated_revenue = base_revenue * response_lift_multiplier * viewing_lift_multiplier
        simulated_commission = base_commission * response_lift_multiplier * viewing_lift_multiplier

        revenue_lift = simulated_revenue - base_revenue
        commission_lift = simulated_commission - base_commission

        return {
            "baseline_weighted_revenue_aed": round(base_revenue, 2),
            "simulated_weighted_revenue_aed": round(simulated_revenue, 2),
            "revenue_lift_aed": round(revenue_lift, 2),
            "revenue_lift_pct": round(((simulated_revenue / base_revenue) - 1.0) * 100.0, 1) if base_revenue > 0 else 0.0,
            "baseline_commission_aed": round(base_commission, 2),
            "simulated_commission_aed": round(simulated_commission, 2),
            "commission_lift_aed": round(commission_lift, 2),
            "scenarios_applied": {
                "response_time_improvement_pct": response_time_improvement_pct,
                "viewing_booking_increase_pct": viewing_booking_increase_pct,
            },
        }
