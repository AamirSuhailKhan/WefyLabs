"""
Part 21.3 — Diversity & Ranking Engine
=======================================
Orders candidates deterministically and classifies recommendations into actionable types:
- BEST_OVERALL
- BEST_VALUE
- BEST_LOCATION
- BEST_INVESTMENT
- BEST_PREMIUM
- ALTERNATIVE
"""
from typing import List, Dict, Any
from app.models.property_models import PropertyListing


class RankingEngine:
    """
    Reranks scored candidates with deterministic tie-breaking and role tagging.
    """

    def rerank_and_tag(
        self,
        scored_items: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Sorts candidates by match_score descending, resolves ties deterministically,
        and assigns recommendation types.
        """
        if not scored_items:
            return []

        # Deterministic sorting: match_score DESC, price ASC, id ASC
        sorted_items = sorted(
            scored_items,
            key=lambda x: (
                -x["match_score"],
                float(x["property"].price or 0.0),
                str(x["property"].id),
            ),
        )

        ranked_results: List[Dict[str, Any]] = []
        assigned_types = set()

        for idx, item in enumerate(sorted_items[:top_k], start=1):
            prop: PropertyListing = item["property"]
            score = item["match_score"]
            breakdown = item["breakdown"]

            rec_type = "ALTERNATIVE"
            if idx == 1:
                rec_type = "BEST_OVERALL"
            elif breakdown.investment_fit >= 90.0 and "BEST_INVESTMENT" not in assigned_types:
                rec_type = "BEST_INVESTMENT"
            elif breakdown.location_fit >= 95.0 and "BEST_LOCATION" not in assigned_types:
                rec_type = "BEST_LOCATION"
            elif breakdown.budget_fit >= 95.0 and "BEST_VALUE" not in assigned_types:
                rec_type = "BEST_VALUE"
            elif prop.price >= 3000000.0 and "BEST_PREMIUM" not in assigned_types:
                rec_type = "BEST_PREMIUM"

            assigned_types.add(rec_type)

            ranked_results.append({
                **item,
                "rank_position": idx,
                "recommendation_type": rec_type,
            })

        return ranked_results
