"""
8-Dimensional Compatibility Scorer Engine
===========================================
Calculates a 0.0 to 100.0 suitability score across 8 distinct dimensions:
1. Budget Fit
2. Location Fit
3. Property Spec Fit
4. Preference / Amenity Fit
5. Investment Fit (Yield & ROI)
6. Timeline & Possession Fit
7. Payment Plan Fit
8. Behavioral Fit

Weights are dynamic and configurable by organization / market / purchase purpose.
"""

import math
import logging
from typing import Dict, Any, Tuple
from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile
from app.modules.recommendation.dto.recommendation_schemas import ScoreBreakdownDTO
from app.modules.recommendation.scoring.FX_converter import FXConverter

logger = logging.getLogger(__name__)

# Default Org Scoring Weight Distribution (Sum = 1.0)
DEFAULT_WEIGHTS_END_USER = {
    "budget_fit": 0.25,
    "location_fit": 0.20,
    "property_fit": 0.20,
    "preference_fit": 0.10,
    "investment_fit": 0.05,
    "timeline_fit": 0.10,
    "payment_plan_fit": 0.05,
    "behavioral_fit": 0.05
}

DEFAULT_WEIGHTS_INVESTOR = {
    "budget_fit": 0.20,
    "location_fit": 0.15,
    "property_fit": 0.10,
    "preference_fit": 0.05,
    "investment_fit": 0.30,
    "timeline_fit": 0.05,
    "payment_plan_fit": 0.10,
    "behavioral_fit": 0.05
}


class CompatibilityScorer:
    """
    Evaluates 8-dimension suitability for a candidate property against a buyer profile.
    """

    def __init__(self, fx_converter: Optional[FXConverter] = None):
        self.fx_converter = fx_converter or FXConverter()

    def calculate_score(
        self,
        property_listing: PropertyListing,
        buyer_profile: BuyerProfile,
        weights_override: Optional[Dict[str, float]] = None
    ) -> Tuple[float, ScoreBreakdownDTO]:
        """
        Computes composite match score (0-100) and breakdown DTO.
        """
        weights = weights_override or (
            DEFAULT_WEIGHTS_INVESTOR if buyer_profile.purchase_purpose == "investment" else DEFAULT_WEIGHTS_END_USER
        )

        # ── 1. Budget Fit (0 - 100) ──────────────────────────────────────────
        s_budget = self._score_budget(property_listing, buyer_profile)

        # ── 2. Location Fit (0 - 100) ────────────────────────────────────────
        s_location = self._score_location(property_listing, buyer_profile)

        # ── 3. Property Spec Fit (0 - 100) ───────────────────────────────────
        s_property = self._score_property_specs(property_listing, buyer_profile)

        # ── 4. Preference & Amenity Fit (0 - 100) ────────────────────────────
        s_preference = self._score_preferences(property_listing, buyer_profile)

        # ── 5. Investment Fit (0 - 100) ───────────────────────────────────────
        s_investment = self._score_investment(property_listing, buyer_profile)

        # ── 6. Timeline Fit (0 - 100) ─────────────────────────────────────────
        s_timeline = self._score_timeline(property_listing, buyer_profile)

        # ── 7. Payment Plan Fit (0 - 100) ─────────────────────────────────────
        s_payment = self._score_payment_plan(property_listing, buyer_profile)

        # ── 8. Behavioral Fit (0 - 100) ───────────────────────────────────────
        s_behavioral = 85.0  # Baseline behavioral match score

        # Composite Weighted Sum
        total_score = (
            s_budget * weights.get("budget_fit", 0.25) +
            s_location * weights.get("location_fit", 0.20) +
            s_property * weights.get("property_fit", 0.20) +
            s_preference * weights.get("preference_fit", 0.10) +
            s_investment * weights.get("investment_fit", 0.05) +
            s_timeline * weights.get("timeline_fit", 0.10) +
            s_payment * weights.get("payment_plan_fit", 0.05) +
            s_behavioral * weights.get("behavioral_fit", 0.05)
        )

        breakdown = ScoreBreakdownDTO(
            budget_fit=round(s_budget, 1),
            location_fit=round(s_location, 1),
            property_fit=round(s_property, 1),
            preference_fit=round(s_preference, 1),
            investment_fit=round(s_investment, 1),
            timeline_fit=round(s_timeline, 1),
            payment_plan_fit=round(s_payment, 1),
            behavioral_fit=round(s_behavioral, 1)
        )

        return round(total_score, 1), breakdown

    def _score_budget(self, prop: PropertyListing, buyer: BuyerProfile) -> float:
        """Scores budget alignment in normalized FX AED."""
        prop_aed, _ = self.fx_converter.convert_to_aed(prop.price, prop.currency)
        max_b_aed, _ = self.fx_converter.convert_to_aed(buyer.max_budget, buyer.currency)
        min_b_aed, _ = self.fx_converter.convert_to_aed(buyer.min_budget, buyer.currency)

        if max_b_aed <= 0:
            return 80.0

        if prop_aed <= max_b_aed:
            if min_b_aed > 0 and prop_aed < min_b_aed * 0.85:
                # Under budget (below preferred min) -> slight drop
                return 85.0
            # Perfect budget alignment
            return 100.0

        # Over budget within flexibility range -> exponential decay
        flex_pct = buyer.budget_flexibility_pct / 100.0
        over_ratio = (prop_aed - max_b_aed) / (max_b_aed * flex_pct + 1.0)
        score = 100.0 * math.exp(-2.0 * over_ratio)
        return max(0.0, score)

    def _score_location(self, prop: PropertyListing, buyer: BuyerProfile) -> float:
        """Scores locality, city, and developer alignment."""
        if not buyer.preferred_locations:
            return 85.0

        loc_lower = [l.lower() for l in buyer.preferred_locations]
        prop_loc = prop.locality.lower() if prop.locality else ""
        prop_city = prop.city.lower() if prop.city else ""

        if any(req in prop_loc for req in loc_lower):
            return 100.0
        if any(req in prop_city for req in loc_lower):
            return 75.0

        return 50.0

    def _score_property_specs(self, prop: PropertyListing, buyer: BuyerProfile) -> float:
        """Scores bedrooms, bathrooms, and area."""
        score = 80.0

        min_beds = buyer.min_bedrooms or 1
        max_beds = buyer.max_bedrooms or 4

        # Bedroom alignment
        if min_beds <= prop.bedrooms <= max_beds:
            score += 10.0
        elif prop.bedrooms < min_beds:
            score -= 25.0

        # Area alignment
        min_area = buyer.min_area_sqft or 0.0
        if min_area > 0 and prop.built_up_area_sqft and prop.built_up_area_sqft >= min_area:
            score += 10.0

        return max(0.0, min(100.0, score))

    def _score_preferences(self, prop: PropertyListing, buyer: BuyerProfile) -> float:
        """Scores amenity match ratio."""
        if not buyer.amenities or not prop.amenities:
            return 80.0

        b_amenities = set(a.lower() for a in buyer.amenities)
        p_amenities = set(a.lower() for a in (prop.amenities or []))

        overlap = b_amenities.intersection(p_amenities)
        ratio = len(overlap) / float(len(b_amenities))
        return min(100.0, 50.0 + (ratio * 50.0))

    def _score_investment(self, prop: PropertyListing, buyer: BuyerProfile) -> float:
        """Scores rental yield and capital appreciation estimates."""
        if buyer.purchase_purpose != "investment":
            return 80.0

        target_yield = buyer.target_rental_yield_pct or 6.0
        actual_yield = prop.estimated_annual_roi_yield_pct or 6.5

        if actual_yield >= target_yield:
            return 100.0

        return max(40.0, (actual_yield / target_yield) * 100.0)

    def _score_timeline(self, prop: PropertyListing, buyer: BuyerProfile) -> float:
        """Scores possession timeline alignment."""
        category = prop.transaction_category.lower() if prop.transaction_category else "resale"
        req = (buyer.possession_timeline or "immediate").lower()

        if req == "immediate" and category == "resale":
            return 100.0
        if "offplan" in req and "offplan" in category:
            return 100.0

        return 70.0

    def _score_payment_plan(self, prop: PropertyListing, buyer: BuyerProfile) -> float:
        """Scores financing / payment structure suitability."""
        if buyer.financing_required:
            return 90.0
        return 85.0
