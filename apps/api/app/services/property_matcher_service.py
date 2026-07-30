from typing import List, Dict, Any, Optional

class PropertyMatcherService:
    """
    AI Real Estate Inventory Matcher matching qualified lead parameters
    (budget, location, property_type, transaction_type) against listing inventory.
    """

    @classmethod
    def match_lead_to_listings(
        cls,
        lead_criteria: Dict[str, Any],
        available_listings: List[Dict[str, Any]],
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        budget_max = lead_criteria.get("budget_max") or 9999999999
        budget_min = lead_criteria.get("budget_min") or 0
        prop_type = (lead_criteria.get("property_type") or "").lower().strip()
        locations = [loc.lower().strip() for loc in (lead_criteria.get("preferred_locations") or [])]

        matched_listings = []

        for listing in available_listings:
            price = listing.get("price", 0)
            l_type = (listing.get("property_type") or "").lower().strip()
            l_loc = (listing.get("location") or "").lower().strip()

            # Budget match
            if not (budget_min * 0.8 <= price <= budget_max * 1.2):
                continue

            score = 50.0

            # Property type match bonus
            if prop_type and prop_type in l_type:
                score += 30.0

            # Location match bonus
            if locations and any(loc in l_loc for loc in locations):
                score += 20.0

            matched_listings.append({
                "listing": listing,
                "match_score": min(score, 100.0)
            })

        # Sort by highest match score
        matched_listings.sort(key=lambda x: x["match_score"], reverse=True)
        return matched_listings[:max_results]
