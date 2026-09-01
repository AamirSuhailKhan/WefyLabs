"""
Hard Constraint Engine
======================
Applies deterministic pre-filtering on candidate properties.
Properties violating hard constraints are eliminated before scoring.
"""

import logging
from typing import List, Dict, Any, Tuple
from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile
from app.modules.recommendation.scoring.FX_converter import FXConverter

logger = logging.getLogger(__name__)

class HardConstraintEngine:
    """
    Evaluates hard safety and eligibility constraints.
    """

    def __init__(self, fx_converter: Optional[FXConverter] = None):
        self.fx_converter = fx_converter or FXConverter()

    def filter_candidates(
        self,
        candidates: List[PropertyListing],
        buyer_profile: BuyerProfile,
        override_budget: Optional[float] = None
    ) -> Tuple[List[PropertyListing], List[Dict[str, Any]]]:
        """
        Filters out non-compliant listings.
        Returns: (valid_candidates, rejected_log)
        """
        valid_candidates: List[PropertyListing] = []
        rejected_log: List[Dict[str, Any]] = []

        target_max_budget = override_budget if override_budget is not None else buyer_profile.max_budget
        budget_flexibility_pct = buyer_profile.budget_flexibility_pct / 100.0
        # Hard ceiling includes flexibility range (e.g. +10%)
        hard_max_budget = target_max_budget * (1.0 + budget_flexibility_pct)

        # Normalize hard budget ceiling into AED
        hard_max_budget_aed, _ = self.fx_converter.convert_to_aed(hard_max_budget, buyer_profile.currency)

        for prop in candidates:
            reasons = []

            # 1. Availability Status Check
            if prop.status.lower() != "available":
                reasons.append(f"Status is '{prop.status}', expected 'available'")

            # 2. Budget Ceiling Check (using FX converted AED value)
            prop_price_aed, _ = self.fx_converter.convert_to_aed(prop.price, prop.currency)
            if hard_max_budget_aed > 0 and prop_price_aed > hard_max_budget_aed:
                reasons.append(
                    f"Price ({prop.price} {prop.currency} ~ {prop_price_aed:.0f} AED) "
                    f"exceeds hard budget ceiling ({hard_max_budget_aed:.0f} AED)"
                )

            # 3. Bedroom Constraint Check
            if prop.bedrooms < buyer_profile.min_bedrooms:
                reasons.append(f"Bedrooms ({prop.bedrooms}) below required minimum ({buyer_profile.min_bedrooms})")
            if prop.bedrooms > buyer_profile.max_bedrooms + 1:
                reasons.append(f"Bedrooms ({prop.bedrooms}) exceeds maximum acceptable ({buyer_profile.max_bedrooms + 1})")

            # 4. Excluded Developer / Location Check
            if prop.project_name and prop.project_name in buyer_profile.excluded_developers:
                reasons.append(f"Project '{prop.project_name}' is in excluded developers list")
            if prop.locality and prop.locality in buyer_profile.excluded_locations:
                reasons.append(f"Locality '{prop.locality}' is in excluded locations list")

            if reasons:
                rejected_log.append({
                    "property_id": str(prop.id),
                    "title": prop.title,
                    "reasons": reasons
                })
            else:
                valid_candidates.append(prop)

        logger.info(
            f"[HARD_CONSTRAINTS] Evaluated {len(candidates)} candidates → "
            f"{len(valid_candidates)} passed, {len(rejected_log)} rejected."
        )

        return valid_candidates, rejected_log
