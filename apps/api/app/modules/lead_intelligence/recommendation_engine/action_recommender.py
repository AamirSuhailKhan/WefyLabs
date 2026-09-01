"""
Action Recommender — Next Best Action Recommendation Engine
============================================================
Generates ranked Next Best Actions for sales agents with estimated conversion lift (%)
and business reasoning.
"""
from typing import Dict, Any, List


class ActionRecommender:
    """
    Generates ranked Next Best Action recommendations.
    """

    def generate_recommendations(
        self,
        features: Dict[str, Any],
        lead_score: float,
        temperature: str,
    ) -> List[Dict[str, Any]]:
        recs = []

        # 1. Rapid Call Recommendation
        if features.get("lead_age_days", 0) < 1.0 and features.get("has_phone"):
            recs.append({
                "rank": 1,
                "action_type": "call_30m",
                "action_title": "Call lead within 30 minutes",
                "estimated_conversion_lift": 18.0,
                "reasoning": "Fresh leads called within 30 minutes have an 18% higher conversion rate.",
            })

        # 2. Site Visit Recommendation
        if not features.get("has_viewing_booked") and lead_score >= 50.0:
            recs.append({
                "rank": 2 if recs else 1,
                "action_type": "schedule_visit",
                "action_title": "Schedule a Property Site Visit",
                "estimated_conversion_lift": 24.0,
                "reasoning": "Site visits increase deal conversion probability by 24% for qualified leads.",
            })

        # 3. Financing Recommendation
        if features.get("loan_status") == "not_started" and features.get("budget_aed", 0) > 1000000:
            recs.append({
                "rank": len(recs) + 1,
                "action_type": "offer_financing",
                "action_title": "Share Mortgage Pre-Approval Options",
                "estimated_conversion_lift": 12.0,
                "reasoning": "Offering pre-approval assistance resolves buyer financing hesitation.",
            })

        # 4. Senior Agent Assignment for Luxury
        if features.get("is_luxury") or features.get("is_high_value"):
            recs.append({
                "rank": len(recs) + 1,
                "action_type": "assign_senior",
                "action_title": "Assign Senior Luxury Broker",
                "estimated_conversion_lift": 15.0,
                "reasoning": "Luxury leads (>= 3M AED) close 15% faster when assigned to experienced brokers.",
            })

        # Fallback default recommendation
        if not recs:
            recs.append({
                "rank": 1,
                "action_type": "share_brochure",
                "action_title": "Share Project Portfolio & Brochure",
                "estimated_conversion_lift": 8.0,
                "reasoning": "Nurture lead with curated property options.",
            })

        # Re-index ranks 1..N
        for idx, rec in enumerate(recs, start=1):
            rec["rank"] = idx

        return recs
