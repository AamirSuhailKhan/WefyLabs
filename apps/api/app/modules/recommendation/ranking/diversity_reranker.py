"""
Diversity Reranker & Choice Optimization Engine
================================================
Reranks candidate property matches using Maximal Marginal Relevance (MMR) and category diversity
to ensure recommendations present a rich range of valid choices (Best Overall, Best Value,
Best Location, Best Investment, Best Premium).
"""

import logging
from typing import List, Dict, Any
from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile
from app.modules.recommendation.dto.recommendation_schemas import ScoreBreakdownDTO

logger = logging.getLogger(__name__)

class DiversityReranker:
    """
    Reranks scored candidates to maximize utility and choice diversity.
    """

    def rerank_and_tag(
        self,
        scored_items: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Takes scored items (each dict contains prop, score, breakdown) and tags diverse options.
        """
        if not scored_items:
            return []

        # Sort strictly by match_score descending initially
        sorted_candidates = sorted(scored_items, key=lambda x: x["match_score"], reverse=True)

        selected: List[Dict[str, Any]] = []
        seen_projects = set()

        # 1. Best Overall (Rank 1)
        top_item = sorted_candidates[0]
        top_item["recommendation_type"] = "BEST_OVERALL"
        selected.append(top_item)
        if top_item["property"].project_name:
            seen_projects.add(top_item["property"].project_name)

        # 2. Select Diverse Candidates for remaining positions
        remaining = sorted_candidates[1:]

        for item in remaining:
            if len(selected) >= top_k:
                break

            prop = item["property"]
            proj = prop.project_name

            # Assign specific specialized tags
            if "recommendation_type" not in item:
                if getattr(prop, "is_overpriced", False) is False and item["breakdown"].budget_fit >= 95.0:
                    item["recommendation_type"] = "BEST_VALUE"
                elif item["breakdown"].investment_fit >= 90.0:
                    item["recommendation_type"] = "BEST_INVESTMENT"
                elif item["breakdown"].location_fit >= 95.0:
                    item["recommendation_type"] = "BEST_LOCATION"
                elif prop.price > sorted_candidates[0]["property"].price:
                    item["recommendation_type"] = "BEST_PREMIUM"
                else:
                    item["recommendation_type"] = "ALTERNATIVE"

            # Avoid back-to-back duplicate projects if possible
            if proj and proj in seen_projects and len(remaining) > top_k:
                # Deprioritize duplicate project to bottom of list
                continue

            if proj:
                seen_projects.add(proj)

            selected.append(item)

        # Fill up to top_k if diversity filtering reduced candidates below top_k
        if len(selected) < top_k and len(sorted_candidates) > len(selected):
            selected_ids = set(x["property"].id for x in selected)
            for item in sorted_candidates:
                if len(selected) >= top_k:
                    break
                if item["property"].id not in selected_ids:
                    if "recommendation_type" not in item:
                        item["recommendation_type"] = "ALTERNATIVE"
                    selected.append(item)

        # Re-assign sequential rank positions
        for idx, item in enumerate(selected, start=1):
            item["rank_position"] = idx

        return selected
