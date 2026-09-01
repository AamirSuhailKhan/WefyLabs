"""
Part 21.3 — Hard Constraint Engine
===================================
Applies deterministic pre-filtering to eliminate non-compliant properties.
Enforces:
- Active availability
- Hard budget ceiling with Decimal-safe Money comparisons
- Bedroom count thresholds
- Excluded developers/locations
"""
from decimal import Decimal
import logging
from typing import List, Dict, Any, Tuple, Optional

from app.models.property_models import PropertyListing
from app.modules.property_recommendation.dto import NormalizedRequirementsDTO
from app.modules.property_recommendation.currency_converter import DecimalCurrencyConverter
from app.modules.global_.currencies.money import Money

logger = logging.getLogger(__name__)


class HardConstraintEngine:
    """
    Evaluates hard safety and eligibility constraints.
    """

    def __init__(self, fx_service: Optional[DecimalCurrencyConverter] = None):
        self.fx_service = fx_service or DecimalCurrencyConverter()

    def filter_candidates(
        self,
        candidates: List[PropertyListing],
        requirements: NormalizedRequirementsDTO,
        flexibility_pct: float = 10.0,
    ) -> Tuple[List[PropertyListing], List[Dict[str, Any]]]:
        """
        Filters out non-compliant listings.
        Returns: (valid_candidates, rejected_log)
        """
        valid_candidates: List[PropertyListing] = []
        rejected_log: List[Dict[str, Any]] = []

        max_budget = requirements.max_budget
        target_currency = requirements.currency.upper()

        # Hard budget ceiling using Decimal
        hard_ceiling_decimal = Decimal(str(max_budget)) * Decimal(str(1.0 + (flexibility_pct / 100.0))) if max_budget > 0 else Decimal("0")

        for prop in candidates:
            reasons = []

            # 1. Availability Status Check
            prop_status = (prop.status or "").lower()
            if prop_status not in ("available", "active", "ready"):
                reasons.append(f"Status is '{prop.status}', expected active/available")

            # 2. Decimal-safe Budget Ceiling Check
            if hard_ceiling_decimal > Decimal("0") and prop.price:
                try:
                    prop_curr = (getattr(prop, "currency_code", None) or getattr(prop, "currency", "AED")).upper()
                    prop_money = Money.of(prop.price, prop_curr)

                    # Convert property price into target currency if different
                    if prop_curr != target_currency:
                        conv = self.fx_service.convert(prop_money, target_currency)
                        converted_price = conv.amount
                    else:
                        converted_price = prop_money.amount

                    if converted_price > hard_ceiling_decimal:
                        reasons.append(
                            f"Price ({prop.price:,.0f} {prop_curr} ~ {converted_price:,.0f} {target_currency}) "
                            f"exceeds budget ceiling ({hard_ceiling_decimal:,.0f} {target_currency})"
                        )
                except Exception as fx_err:
                    logger.warning(f"[HARD_FILTER] FX conversion check failed for property {prop.id}: {fx_err}")
                    # Direct comparison fallback
                    if prop.price > float(hard_ceiling_decimal):
                        reasons.append(f"Price exceeds stated budget ceiling ({hard_ceiling_decimal:,.0f})")

            # 3. Bedroom Threshold Check
            if requirements.min_bedrooms and getattr(prop, "bedrooms", None) is not None:
                if prop.bedrooms < requirements.min_bedrooms:
                    reasons.append(f"Bedrooms ({prop.bedrooms}) below required minimum ({requirements.min_bedrooms})")
                if prop.bedrooms > requirements.max_bedrooms + 2:
                    reasons.append(f"Bedrooms ({prop.bedrooms}) far exceeds required range ({requirements.max_bedrooms})")

            # 4. Excluded Locations / Developers Check
            if prop.locality and any(exc.lower() in prop.locality.lower() for exc in requirements.excluded_areas):
                reasons.append(f"Locality '{prop.locality}' is explicitly excluded by prospect")
            if prop.project_name and any(exc.lower() in prop.project_name.lower() for exc in requirements.excluded_developers):
                reasons.append(f"Developer/Project '{prop.project_name}' is explicitly excluded")

            if reasons:
                rejected_log.append({
                    "property_id": str(prop.id),
                    "title": prop.title,
                    "reasons": reasons,
                })
            else:
                valid_candidates.append(prop)

        logger.info(
            f"[HARD_CONSTRAINTS] Evaluated {len(candidates)} candidates → "
            f"{len(valid_candidates)} passed, {len(rejected_log)} rejected."
        )

        return valid_candidates, rejected_log
