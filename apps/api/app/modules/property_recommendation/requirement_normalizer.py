"""
Part 21.3 — Requirement Normalizer
===================================
Normalizes lead preferences and structured prospect intelligence into a canonical
NormalizedRequirementsDTO without ever fabricating missing information.
"""
import logging
from typing import Optional, Dict, Any, List

from app.models.lead import Lead
from app.models.prospect_intelligence_models import ProspectIntelligence
from app.modules.property_recommendation.dto import NormalizedRequirementsDTO

logger = logging.getLogger(__name__)

# Property type normalization synonyms
PROPERTY_TYPE_SYNONYMS = {
    "flat": "apartment",
    "apt": "apartment",
    "flat/apartment": "apartment",
    "condo": "apartment",
    "residential apartment": "apartment",
    "independent house": "villa",
    "bungalow": "villa",
    "row house": "townhouse",
    "duplex": "penthouse",
    "commercial office": "office",
    "retail shop": "retail",
    "plot": "land",
}


def normalize_property_type(raw_type: Optional[str]) -> Optional[str]:
    """Deterministically normalizes raw property type strings."""
    if not raw_type:
        return None
    cleaned = raw_type.lower().strip()
    # Check for direct synonym
    if cleaned in PROPERTY_TYPE_SYNONYMS:
        return PROPERTY_TYPE_SYNONYMS[cleaned]
    # Check sub-patterns
    if "apartment" in cleaned or "bhk" in cleaned:
        return "apartment"
    if "villa" in cleaned:
        return "villa"
    if "townhouse" in cleaned:
        return "townhouse"
    if "penthouse" in cleaned:
        return "penthouse"
    if "office" in cleaned:
        return "office"
    if "retail" in cleaned or "shop" in cleaned:
        return "retail"
    if "land" in cleaned or "plot" in cleaned:
        return "land"
    return cleaned


def extract_bedrooms_from_text(raw_text: Optional[str]) -> Optional[int]:
    """Extracts explicit bedroom counts from strings like '3 BHK' or '2 bed'."""
    if not raw_text:
        return None
    low = raw_text.lower()
    for num in range(1, 10):
        if f"{num}bhk" in low or f"{num} bhk" in low or f"{num}bed" in low or f"{num} bed" in low or f"{num} br" in low:
            return num
    return None


class RequirementNormalizer:
    """
    Synthesizes and normalizes explicit requirements from Lead and ProspectIntelligence.
    """

    @classmethod
    def normalize(
        cls,
        lead: Lead,
        intelligence: Optional[ProspectIntelligence] = None,
        override_budget: Optional[float] = None,
        override_currency: Optional[str] = None,
    ) -> NormalizedRequirementsDTO:
        """
        Builds canonical NormalizedRequirementsDTO.
        Gives precedence to structured ProspectIntelligence, falling back to Lead entity attributes.
        """
        prop_reqs = intelligence.property_requirements if intelligence else {}
        budget_info = intelligence.budget if intelligence else {}

        # 1. Property Type & Bedrooms
        raw_pt = prop_reqs.get("property_type") or lead.property_type
        norm_pt = normalize_property_type(raw_pt)

        beds = prop_reqs.get("bedrooms")
        if beds is None and lead.property_type:
            beds = extract_bedrooms_from_text(lead.property_type)

        min_beds = beds if beds is not None else 1
        max_beds = beds if beds is not None else 4
        baths = prop_reqs.get("bathrooms") or 1

        # 2. Budget & Currency
        curr = override_currency or budget_info.get("currency") or getattr(lead, "budget_currency", None) or "AED"
        if not curr or curr == "UNKNOWN":
            curr = "AED"

        b_min = float(budget_info.get("budget_min") or lead.budget_min or 0.0)
        b_max = float(budget_info.get("budget_max") or lead.budget_max or 0.0)

        if override_budget is not None:
            b_max = float(override_budget)

        # 3. Location & Communities
        loc = prop_reqs.get("location")
        pref_areas: List[str] = list(prop_reqs.get("preferred_areas") or [])
        if not pref_areas and lead.preferred_locations:
            pref_areas = list(lead.preferred_locations)

        # 4. Transaction Intent
        intent = "BUY"
        if intelligence and intelligence.transaction_intent and intelligence.transaction_intent != "UNKNOWN":
            intent = intelligence.transaction_intent
        elif lead.transaction_type:
            lt = lead.transaction_type.upper()
            if lt in ("BUY", "SELL", "RENT", "LEASE", "INVEST"):
                intent = lt

        # 5. Purpose
        purpose = "end_user"
        if intelligence and intelligence.purpose and intelligence.purpose != "UNKNOWN":
            purpose = "investment" if intelligence.purpose in ("INVESTMENT", "RENTAL_YIELD") else "end_user"
        elif intent == "INVEST":
            purpose = "investment"

        # 6. Timeline & Financing
        timeline = "immediate"
        if intelligence and intelligence.timeline and intelligence.timeline != "UNKNOWN":
            timeline = intelligence.timeline.lower()
        elif lead.timeline:
            timeline = lead.timeline.lower()

        financing_req = False
        if intelligence and intelligence.financing:
            financing_req = intelligence.financing in ("MORTGAGE", "FINANCING_REQUIRED")
        elif lead.loan_status in ("in_process", "needed"):
            financing_req = True

        amenities = list(prop_reqs.get("amenities") or [])

        return NormalizedRequirementsDTO(
            property_type=norm_pt,
            category="residential",
            min_bedrooms=min_beds,
            max_bedrooms=max_beds,
            min_bathrooms=baths,
            min_budget=b_min,
            max_budget=b_max,
            currency=curr,
            location=loc,
            preferred_areas=pref_areas,
            excluded_areas=[],
            preferred_developers=[],
            excluded_developers=[],
            amenities=amenities,
            transaction_intent=intent,
            purchase_purpose=purpose,
            possession_timeline=timeline,
            financing_required=financing_req,
            urgency=intelligence.urgency if intelligence and intelligence.urgency != "UNKNOWN" else "MEDIUM",
        )
