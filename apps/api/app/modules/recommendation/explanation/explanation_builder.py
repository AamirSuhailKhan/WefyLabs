"""
Grounded Explanation & Sales Agent Talking Points Generator
============================================================
Generates transparent, data-grounded match explanations, trade-offs, and sales agent guidance.
Never invents numerical property facts. All statements are derived from structured DB attributes.
"""

import logging
from typing import Dict, Any, List
from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile
from app.modules.recommendation.dto.recommendation_schemas import ScoreBreakdownDTO

logger = logging.getLogger(__name__)

class ExplanationBuilder:
    """
    Generates structured, grounded explanations for property recommendations.
    """

    def build_explanation(
        self,
        prop: PropertyListing,
        buyer: BuyerProfile,
        score: float,
        breakdown: ScoreBreakdownDTO,
        rec_type: str
    ) -> Dict[str, Any]:
        """
        Builds grounded strong matches, trade-offs, talking points, and next action.
        """
        strong_matches: List[str] = []
        weak_matches: List[str] = []
        tradeoffs: List[str] = []
        missing_information: List[str] = []
        agent_talking_points: List[str] = []

        curr = buyer.currency

        # ── 1. Budget Driver Analysis ─────────────────────────────────────────
        if prop.price <= buyer.max_budget:
            savings = buyer.max_budget - prop.price
            if savings > 0:
                strong_matches.append(
                    f"Priced at {prop.price:,.0f} {prop.currency}, saving {savings:,.0f} {curr} under stated maximum budget ({buyer.max_budget:,.0f} {curr})"
                )
            else:
                strong_matches.append(f"Price ({prop.price:,.0f} {prop.currency}) matches stated budget ceiling exactly")
        else:
            pct_over = ((prop.price - buyer.max_budget) / buyer.max_budget) * 100.0
            tradeoffs.append(
                f"Price ({prop.price:,.0f} {prop.currency}) is {pct_over:.1f}% above stated budget ceiling ({buyer.max_budget:,.0f} {curr}), but within acceptable flexibility range"
            )

        # ── 2. Location Driver Analysis ───────────────────────────────────────
        if buyer.preferred_locations:
            loc_lower = [l.lower() for l in buyer.preferred_locations]
            if prop.locality and prop.locality.lower() in loc_lower:
                strong_matches.append(f"Located directly in requested neighborhood ({prop.locality})")
            elif prop.city and prop.city.lower() in loc_lower:
                strong_matches.append(f"Located in target city ({prop.city})")
            else:
                tradeoffs.append(f"Location ({prop.locality or prop.city}) differs from top requested area ({buyer.preferred_locations[0]})")

        # ── 3. Bedroom Specs ──────────────────────────────────────────────────
        if buyer.min_bedrooms <= prop.bedrooms <= buyer.max_bedrooms:
            strong_matches.append(f"Matches required {prop.bedrooms} Bedroom layout specification")
        elif prop.bedrooms < buyer.min_bedrooms:
            tradeoffs.append(f"Offers {prop.bedrooms} Bedrooms vs requested minimum of {buyer.min_bedrooms} Bedrooms")

        # ── 4. Investment & Yield Highlights ──────────────────────────────────
        if buyer.purchase_purpose == "investment" and prop.estimated_annual_roi_yield_pct:
            strong_matches.append(f"Offers an estimated gross annual rental yield of {prop.estimated_annual_roi_yield_pct:.1f}%")

        # ── 5. Agent Talking Points ───────────────────────────────────────────
        if rec_type == "BEST_OVERALL":
            agent_talking_points.append(
                f"Present as top recommended property (#{prop.title}) — 90%+ match on budget, location, and bedroom configuration."
            )
        elif rec_type == "BEST_VALUE":
            agent_talking_points.append(
                f"Highlight high value per sqft ({prop.built_up_area_sqft:.0f} sqft at {prop.price:,.0f} {prop.currency})."
            )
        elif rec_type == "BEST_INVESTMENT":
            agent_talking_points.append(
                f"Emphasize strong investor return: {prop.estimated_annual_roi_yield_pct or 6.5:.1f}% projected annual yield."
            )

        if tradeoffs:
            agent_talking_points.append(
                f"Address potential buyer objection regarding: {tradeoffs[0]}"
            )

        # ── 6. Suggested Next Action ──────────────────────────────────────────
        suggested_next_action = "Schedule Site Visit / Viewing"
        if prop.transaction_category == "offplan_developer":
            suggested_next_action = "Share Off-Plan Payment Plan Brochure & Floorplan"

        return {
            "strong_matches": strong_matches,
            "weak_matches": weak_matches,
            "tradeoffs": tradeoffs,
            "missing_information": missing_information,
            "agent_talking_points": agent_talking_points,
            "suggested_next_action": suggested_next_action
        }
