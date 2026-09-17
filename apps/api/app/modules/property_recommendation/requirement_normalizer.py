import re
import logging
from typing import Optional, Dict, Any, List, Tuple

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

# Unit multipliers to canonical sqft
AREA_UNIT_CONVERSIONS_TO_SQFT = {
    "sqft": 1.0,
    "sq ft": 1.0,
    "square feet": 1.0,
    "sq.ft": 1.0,
    "sqm": 10.7639,
    "sq m": 10.7639,
    "sq.m": 10.7639,
    "square meter": 10.7639,
    "square meters": 10.7639,
    "acre": 43560.0,
    "acres": 43560.0,
    "cent": 435.6,
    "cents": 435.6,
    "guntas": 1089.0,
    "guntha": 1089.0,
}


def parse_indian_budget(raw_val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses Indian real estate pricing language into canonical numeric values in INR.
    Handles '1 crore', '1.2 crore', '₹1.2 Cr', '1.2 cr', '120 lakh', '1.2L', '₹80 lakhs', '80L', etc.
    Returns (numeric_amount, currency_code).
    """
    if raw_val is None:
        return None, None
    if isinstance(raw_val, (int, float)):
        return float(raw_val), "INR"

    text = str(raw_val).strip()
    if not text:
        return None, None

    cleaned = re.sub(r"[₹,]|rs\.?|inr", "", text, flags=re.IGNORECASE).strip()

    # Match Crore / Cr pattern
    cr_match = re.search(r"^([\d.]+)\s*(?:cr|crore|crores)$", cleaned, re.IGNORECASE)
    if cr_match:
        try:
            return float(cr_match.group(1)) * 10_000_000.0, "INR"
        except ValueError:
            pass

    # Match Lakh / Lac / L pattern
    l_match = re.search(r"^([\d.]+)\s*(?:l|lac|lacs|lakh|lakhs)$", cleaned, re.IGNORECASE)
    if l_match:
        try:
            return float(l_match.group(1)) * 100_000.0, "INR"
        except ValueError:
            pass

    # Match Thousand / K pattern
    k_match = re.search(r"^([\d.]+)\s*(?:k|thousand)$", cleaned, re.IGNORECASE)
    if k_match:
        try:
            return float(k_match.group(1)) * 1_000.0, "INR"
        except ValueError:
            pass

    # Pure numeric representation
    try:
        val = float(cleaned)
        return val, "INR"
    except ValueError:
        return None, None


def normalize_area_value(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    """
    Converts given area into canonical square feet (sqft).
    """
    if value is None:
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None

    if not unit:
        return val

    norm_unit = unit.strip().lower()
    multiplier = AREA_UNIT_CONVERSIONS_TO_SQFT.get(norm_unit, 1.0)
    return round(val * multiplier, 2)


def extract_negative_preferences(text: str) -> Dict[str, Any]:
    """
    Extracts explicit negative constraints and exclusions from unstructured notes or requirements.
    Never ignores negative statements.
    """
    neg: Dict[str, Any] = {
        "exclude_ground_floor": False,
        "require_furnished": False,
        "exclude_unfurnished": False,
        "parking_mandatory": False,
        "excluded_locations": [],
        "hard_budget_ceiling": None,
    }
    if not text:
        return neg

    low = text.lower()

    # Ground floor exclusion
    if "no ground floor" in low or "not ground floor" in low or "don't show me ground floor" in low or "avoid ground floor" in low:
        neg["exclude_ground_floor"] = True

    # Furnishing constraints
    if "no unfurnished" in low or "don't show unfurnished" in low or "fully furnished only" in low:
        neg["require_furnished"] = True
        neg["exclude_unfurnished"] = True

    # Parking mandate
    if "parking is mandatory" in low or "parking mandatory" in low or "parking required" in low or "must have parking" in low:
        neg["parking_mandatory"] = True

    # Location exclusions ("strictly avoid X", "not interested in X", "no properties in X")
    avoid_loc_matches = re.findall(r"(?:strictly avoid|not interested in|avoid|exclude|no properties in)\s+([a-zA-Z\s]+?)(?:,|\.|$|and)", low)
    for loc_cand in avoid_loc_matches:
        cleaned_loc = loc_cand.strip().title()
        if cleaned_loc and len(cleaned_loc) > 2 and cleaned_loc not in neg["excluded_locations"]:
            neg["excluded_locations"].append(cleaned_loc)

    # Budget hard ceiling ("no properties above X", "must be under X")
    cap_match = re.search(r"(?:no properties above|must be under|budget strictly under|under)\s+(?:₹|rs\.?|inr)?\s*([\d.]+\s*(?:cr|crore|l|lakh|lacs)?)", low)
    if cap_match:
        cap_val, _ = parse_indian_budget(cap_match.group(1))
        if cap_val:
            neg["hard_budget_ceiling"] = cap_val

    return neg


def generate_clarification_questions(lead: Lead, req: Optional[NormalizedRequirementsDTO] = None) -> List[str]:
    """
    Generates tailored, professional clarification questions to improve match quality for incomplete leads.
    """
    questions: List[str] = []

    has_budget = bool(lead.budget_max or lead.budget_min or (req and req.max_budget))
    has_location = bool((lead.preferred_locations and len(lead.preferred_locations) > 0) or (req and req.location))
    has_bhk = bool(lead.property_type and any(k in lead.property_type.lower() for k in ("bhk", "bedroom", "bed")))

    if not has_budget:
        questions.append("What is your target budget or maximum price comfort range?")
    if not has_location:
        questions.append("Which localities or neighborhoods do you prefer to live in or invest?")
    if not has_bhk:
        questions.append("How many bedrooms (BHK) do you require?")

    # Additional high-value soft parameters
    tx_type = (lead.transaction_type or (req.transaction_intent if req else "")).lower()
    if not tx_type or tx_type in ("unknown", ""):
        questions.append("Are you looking to buy, rent, or invest in real estate?")

    timeline = (lead.timeline or (req.possession_timeline if req else "")).lower()
    if not timeline or timeline in ("unknown", ""):
        questions.append("Do you need a ready-to-move property or are you open to under-construction projects?")

    return questions


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
    Separates explicit CRM data from AI-inferred preferences and preserves provenance.
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

        # 2. Budget & Currency with Indian Notation Support
        curr = override_currency or budget_info.get("currency") or getattr(lead, "budget_currency", None) or "INR"
        if not curr or curr == "UNKNOWN":
            curr = "INR"

        raw_b_min = budget_info.get("budget_min") or lead.budget_min or 0.0
        raw_b_max = budget_info.get("budget_max") or lead.budget_max or 0.0

        b_min, _ = parse_indian_budget(raw_b_min)
        b_max, _ = parse_indian_budget(raw_b_max)
        b_min = b_min or 0.0
        b_max = b_max or 0.0

        if override_budget is not None:
            parsed_override, _ = parse_indian_budget(override_budget)
            b_max = parsed_override or float(override_budget)

        # 3. Location & Communities
        loc = prop_reqs.get("location")
        pref_areas: List[str] = list(prop_reqs.get("preferred_areas") or [])
        if not pref_areas and lead.preferred_locations:
            pref_areas = list(lead.preferred_locations)

        # 4. Negative Preferences from Lead Notes
        notes_str = " ".join([str(n.get("content", "")) if isinstance(n, dict) else str(n) for n in (lead.notes or [])])
        neg_prefs = extract_negative_preferences(notes_str)
        excluded_areas = list(neg_prefs.get("excluded_locations", []))

        # 5. Transaction Intent
        intent = "BUY"
        if intelligence and intelligence.transaction_intent and intelligence.transaction_intent != "UNKNOWN":
            intent = intelligence.transaction_intent
        elif lead.transaction_type:
            lt = lead.transaction_type.upper()
            if lt in ("BUY", "SELL", "RENT", "LEASE", "INVEST"):
                intent = lt

        # 6. Purpose
        purpose = "end_user"
        if intelligence and intelligence.purpose and intelligence.purpose != "UNKNOWN":
            purpose = "investment" if intelligence.purpose in ("INVESTMENT", "RENTAL_YIELD") else "end_user"
        elif intent == "INVEST":
            purpose = "investment"

        # 7. Timeline & Financing
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

        # Field-level Provenance Tracking
        provenance = {
            "budget": "explicit_crm" if (lead.budget_max or lead.budget_min) else "ai_inferred" if intelligence else "missing",
            "property_type": "explicit_crm" if lead.property_type else "ai_inferred" if prop_reqs.get("property_type") else "missing",
            "location": "explicit_crm" if lead.preferred_locations else "ai_inferred" if loc else "missing",
            "negative_preferences": "extracted_from_notes" if neg_prefs.get("exclude_ground_floor") or excluded_areas else "none",
        }

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
            excluded_areas=excluded_areas,
            preferred_developers=[],
            excluded_developers=[],
            amenities=amenities,
            transaction_intent=intent,
            purchase_purpose=purpose,
            possession_timeline=timeline,
            financing_required=financing_req,
            urgency=intelligence.urgency if intelligence and intelligence.urgency != "UNKNOWN" else "MEDIUM",
        )

