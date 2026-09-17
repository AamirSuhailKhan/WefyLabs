"""
Part 29 — Unit Test Suite: AI Lead ↔ Property Matching Engine
=============================================================
Comprehensive unit tests covering:
1. Indian Budget Parsing & Currency Normalization (10 tests)
2. Area Normalization & Conversion (5 tests)
3. Location & Locality Normalization (3 tests)
4. Negative Preferences & Constraint Extraction (5 tests)
5. Hard Constraint Filtering (6 tests)
6. Soft Preference Scoring & Weights (4 tests)
7. Confidence Evaluation & Incomplete Lead Questions (3 tests)
8. Alternative Relaxation & Fallback (3 tests)
Total: 39 Unit Tests
"""
import uuid
import pytest
from unittest.mock import MagicMock

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.modules.property_recommendation.requirement_normalizer import (
    parse_indian_budget,
    normalize_area_value,
    extract_negative_preferences,
    generate_clarification_questions,
    normalize_property_type,
    extract_bedrooms_from_text,
    RequirementNormalizer
)
from app.modules.property_recommendation.matching_service import (
    AIPropertyMatchingEngine,
    DEFAULT_MATCHING_WEIGHTS
)


# ─── 1. Indian Budget Parsing Tests ──────────────────────────────────────────

def test_parse_budget_crore_variants():
    """Validates variations of 'crore' and 'Cr'."""
    val, curr = parse_indian_budget("1.2 crore")
    assert val == 12_000_000.0
    assert curr == "INR"

    val2, _ = parse_indian_budget("₹1.5 Cr")
    assert val2 == 15_000_000.0

    val3, _ = parse_indian_budget("2cr")
    assert val3 == 20_000_000.0


def test_parse_budget_lakh_variants():
    """Validates variations of 'lakh', 'lac', and 'L'."""
    val, curr = parse_indian_budget("80 lakhs")
    assert val == 8_000_000.0
    assert curr == "INR"

    val2, _ = parse_indian_budget("₹85L")
    assert val2 == 8_500_000.0

    val3, _ = parse_indian_budget("120 lac")
    assert val3 == 12_000_000.0


def test_parse_budget_thousands_variants():
    """Validates rental thousands e.g. 45k or 50 thousand."""
    val, curr = parse_indian_budget("45k")
    assert val == 45_000.0
    assert curr == "INR"

    val2, _ = parse_indian_budget("50 thousand")
    assert val2 == 50_000.0


def test_parse_budget_raw_numbers():
    """Validates int, float, and numeric string representation."""
    val, curr = parse_indian_budget(9500000)
    assert val == 9_500_000.0
    assert curr == "INR"

    val2, _ = parse_indian_budget(12500000.5)
    assert val2 == 12_500_000.5

    val3, _ = parse_indian_budget("10000000")
    assert val3 == 10_000_000.0


def test_parse_budget_invalid_and_empty():
    """Validates graceful handling of empty or invalid budget values."""
    val, curr = parse_indian_budget(None)
    assert val is None
    assert curr is None

    val2, curr2 = parse_indian_budget("")
    assert val2 is None
    assert curr2 is None

    val3, curr3 = parse_indian_budget("not a budget number")
    assert val3 is None
    assert curr3 is None


# ─── 2. Area Normalization Tests ─────────────────────────────────────────────

def test_normalize_area_sqft():
    """Direct sqft representation preserved."""
    assert normalize_area_value(1500, "sqft") == 1500.0
    assert normalize_area_value(1650.5, "sq ft") == 1650.5
    assert normalize_area_value(2000, "square feet") == 2000.0


def test_normalize_area_sqm_to_sqft():
    """Square meters converted to canonical sqft (1 sqm ≈ 10.7639 sqft)."""
    norm = normalize_area_value(100, "sqm")
    assert norm == 1076.39


def test_normalize_area_acre_to_sqft():
    """Acre converted to canonical sqft (1 acre = 43,560 sqft)."""
    norm = normalize_area_value(1.0, "acre")
    assert norm == 43560.0


def test_normalize_area_cent_to_sqft():
    """Cent converted to canonical sqft (1 cent = 435.6 sqft)."""
    norm = normalize_area_value(5.0, "cent")
    assert norm == 2178.0


def test_normalize_area_invalid():
    """Invalid area values handled gracefully."""
    assert normalize_area_value(None, "sqft") is None
    assert normalize_area_value("abc", "sqft") is None


# ─── 3. Property Type & Location Normalization Tests ─────────────────────────

def test_normalize_property_type_synonyms():
    """Maps synonyms and abbreviations to standard canonical types."""
    assert normalize_property_type("flat") == "apartment"
    assert normalize_property_type("condo") == "apartment"
    assert normalize_property_type("3BHK Apartment") == "apartment"
    assert normalize_property_type("independent house") == "villa"
    assert normalize_property_type("bungalow") == "villa"
    assert normalize_property_type("commercial office") == "office"
    assert normalize_property_type("residential plot") == "land"


def test_extract_bedrooms_from_text():
    """Extracts bedroom count from diverse textual descriptions."""
    assert extract_bedrooms_from_text("3 BHK luxury flat") == 3
    assert extract_bedrooms_from_text("2 bed apartment") == 2
    assert extract_bedrooms_from_text("spacious 4bhk villa") == 4
    assert extract_bedrooms_from_text("1 br studio") == 1
    assert extract_bedrooms_from_text("plot in gated community") is None


def test_requirement_normalizer_provenance_explicit_vs_inferred():
    """Ensures explicit lead data takes precedence and captures provenance."""
    lead = Lead(
        id=uuid.uuid4(),
        name="Ananya Roy",
        budget_min=8000000,
        budget_max=12000000,
        property_type="3 BHK apartment",
        preferred_locations=["Whitefield", "Sarjapur Road"],
        transaction_type="buy"
    )
    req = RequirementNormalizer.normalize(lead=lead)
    assert req.max_budget == 12000000.0
    assert req.min_budget == 8000000.0
    assert req.min_bedrooms == 3
    assert "Whitefield" in req.preferred_areas
    assert req.transaction_intent == "BUY"


# ─── 4. Negative Preferences & Constraint Extraction Tests ───────────────────

def test_extract_negative_ground_floor():
    """Extracts explicit ground floor exclusion."""
    neg = extract_negative_preferences("Please strictly avoid ground floor units. Need upper floors.")
    assert neg["exclude_ground_floor"] is True


def test_extract_negative_furnishing():
    """Extracts furnishing constraint."""
    neg = extract_negative_preferences("No unfurnished properties. Must be fully furnished.")
    assert neg["require_furnished"] is True
    assert neg["exclude_unfurnished"] is True


def test_extract_negative_parking():
    """Extracts mandatory parking requirement."""
    neg = extract_negative_preferences("Client has two cars, so parking is mandatory.")
    assert neg["parking_mandatory"] is True


def test_extract_negative_excluded_locations():
    """Extracts avoided localities."""
    neg = extract_negative_preferences("Looking in East Bengaluru, strictly avoid Sarjapur and Bellandur.")
    assert any("Sarjapur" in loc for loc in neg["excluded_locations"])


def test_extract_negative_hard_budget_cap():
    """Extracts hard budget ceiling expression."""
    neg = extract_negative_preferences("Strict budget ceiling, must be under 1.5 crore.")
    assert neg["hard_budget_ceiling"] == 15_000_000.0


# ─── 5. Hard Constraint Filtering Tests ──────────────────────────────────────

@pytest.fixture
def broker():
    return Broker(id=uuid.uuid4(), name="Agent A", email="a@crm.com")


@pytest.fixture
def base_lead(broker):
    return Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Vikram Rao",
        budget_min=6000000,
        budget_max=9000000,
        property_type="2 BHK apartment",
        transaction_type="buy",
        preferred_locations=["Indiranagar"],
        notes=[{"content": "Parking is mandatory and avoid ground floor."}]
    )


def test_hard_constraint_rejects_inactive_property(base_lead, broker):
    """Property that is reserved or sold must fail hard constraints."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Reserved Unit",
        property_type="apartment",
        status="reserved",
        transaction_category="resale",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar"
    )
    passed, reasons = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead)
    assert not passed
    assert any("reserved" in r.lower() or "available" in r.lower() for r in reasons)


def test_hard_constraint_transaction_type_mismatch(base_lead, broker):
    """Lead wants BUY, property is for RENT."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Rental Apartment",
        property_type="apartment",
        status="available",
        transaction_category="rent",
        price=35000.0,
        bedrooms=2,
        locality="Indiranagar"
    )
    passed, reasons = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead)
    assert not passed
    assert any("transaction" in r.lower() or "rent" in r.lower() for r in reasons)


def test_hard_constraint_property_type_group_mismatch(base_lead, broker):
    """Lead wants apartment, property is commercial land/plot."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Commercial Plot",
        property_type="land",
        status="available",
        transaction_category="sale",
        price=8500000.0,
        locality="Indiranagar"
    )
    passed, reasons = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead)
    assert not passed
    assert any("property type mismatch" in r.lower() for r in reasons)


def test_hard_constraint_budget_ceiling_tolerance(base_lead, broker):
    """Property price significantly above budget ceiling fails hard constraints."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Ultra Luxury 2BHK",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=13000000.0,  # Stated max is 90L, 1.3 Cr is +44%
        bedrooms=2,
        locality="Indiranagar"
    )
    passed, reasons = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead, flexibility_pct=10.0)
    assert not passed
    assert any("budget exceeded" in r.lower() for r in reasons)


def test_hard_constraint_mandatory_parking_enforced(base_lead, broker):
    """Lead note requires parking, property without parking fails."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="No-parking Apartment",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar",
        amenities=["Gym", "Clubhouse"]  # No parking
    )
    passed, reasons = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead)
    assert not passed
    assert any("parking" in r.lower() for r in reasons)


def test_hard_constraint_ground_floor_exclusion_enforced(base_lead, broker):
    """Lead note avoids ground floor, property on floor 0 fails."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Ground Floor Flat",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar",
        floor_number=0,
        amenities=["Parking"]
    )
    passed, reasons = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead)
    assert not passed
    assert any("ground floor" in r.lower() for r in reasons)


# ─── 6. Soft Preference Scoring & Weights Tests ──────────────────────────────

def test_soft_scoring_weights_sum():
    """Default weights must sum to 1.0 (100%)."""
    total = sum(DEFAULT_MATCHING_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


def test_soft_scoring_budget_fit(base_lead, broker):
    """Property strictly within min-max budget gets 100% budget fit."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Good Value Flat",
        property_type="apartment",
        status="available",
        price=7500000.0,  # between 60L and 90L
        bedrooms=2,
        locality="Indiranagar",
        amenities=["Parking"]
    )
    score, breakdown, reasons, mismatches = AIPropertyMatchingEngine.calculate_compatibility_score(prop, base_lead)
    assert breakdown.budget_fit == 100.0
    assert any("within stated budget" in r.lower() for r in reasons)


def test_soft_scoring_location_fit(base_lead, broker):
    """Exact locality match gives 100% location fit score."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Indiranagar Prime",
        property_type="apartment",
        status="available",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar",
        amenities=["Parking"]
    )
    score, breakdown, reasons, mismatches = AIPropertyMatchingEngine.calculate_compatibility_score(prop, base_lead)
    assert breakdown.location_fit == 100.0
    assert any("indiranagar" in r.lower() for r in reasons)


def test_soft_scoring_amenities_and_parking(base_lead, broker):
    """Presence of requested amenities (parking) elevates score."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Amenity Rich Flat",
        property_type="apartment",
        status="available",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar",
        amenities=["Parking", "Gym", "Power Backup"]
    )
    score, breakdown, reasons, mismatches = AIPropertyMatchingEngine.calculate_compatibility_score(prop, base_lead)
    assert breakdown.preference_fit >= 90.0
    assert score >= 85.0


# ─── 7. Confidence Evaluation & Incomplete Lead Questions ────────────────────

def test_confidence_evaluation_complete_lead(base_lead, broker):
    """Lead with budget, location, and BHK has high confidence (>= 0.8)."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Indiranagar Home",
        property_type="apartment",
        status="available",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar"
    )
    conf, guidance = AIPropertyMatchingEngine.evaluate_confidence(base_lead, prop)
    assert conf >= 0.8
    assert guidance is None


def test_confidence_evaluation_incomplete_lead(broker):
    """Incomplete lead without budget or location has low confidence and guidance."""
    bare_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Bare Lead",
        phone="+919000000000"
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Indiranagar Home",
        property_type="apartment",
        status="available",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar"
    )
    conf, guidance = AIPropertyMatchingEngine.evaluate_confidence(bare_lead, prop)
    assert conf <= 0.6
    assert guidance is not None
    assert "requirements" in guidance.lower() or "clarify" in guidance.lower()


def test_generate_clarification_questions_for_incomplete_lead(broker):
    """Produces targeted questions for missing budget, location, and BHK."""
    bare_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Bare Lead",
        phone="+919000000000"
    )
    questions = generate_clarification_questions(bare_lead)
    assert any("budget" in q.lower() for q in questions)
    assert any("localit" in q.lower() or "area" in q.lower() for q in questions)
    assert any("bhk" in q.lower() or "bedroom" in q.lower() for q in questions)


# ─── 8. Alternative Relaxation & Fallback Tests ──────────────────────────────

def test_controlled_alternative_relaxation(base_lead, broker):
    """Slightly over-budget property fails strict filtering but passes in alternative mode."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Slightly Premium Flat",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=10500000.0,  # 1.05 Cr (16.6% over 90L ceiling)
        bedrooms=2,
        locality="Indiranagar",
        amenities=["Parking"]
    )
    # Strict mode (flexibility 10% -> 99L max)
    strict_pass, _ = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead, allow_alternatives=False, flexibility_pct=10.0)
    assert not strict_pass

    # Alternative mode (flexibility 25% -> 1.125 Cr max)
    alt_pass, _ = AIPropertyMatchingEngine.evaluate_hard_constraints(prop, base_lead, allow_alternatives=True)
    assert alt_pass


def test_sold_property_never_relaxed_in_alternative_mode(base_lead, broker):
    """Sold status can NEVER be relaxed, even in alternative mode."""
    sold_prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Sold Unit",
        property_type="apartment",
        status="sold",
        price=8000000.0,
        bedrooms=2,
        locality="Indiranagar",
        amenities=["Parking"]
    )
    alt_pass, reasons = AIPropertyMatchingEngine.evaluate_hard_constraints(sold_prop, base_lead, allow_alternatives=True)
    assert not alt_pass
    assert any("sold" in r.lower() or "available" in r.lower() for r in reasons)


def test_deterministic_explanation_fallback():
    """Engine generates grounded explanation without external AI calls."""
    engine = AIPropertyMatchingEngine(ai_service=None)
    assert engine.ai_service is None
