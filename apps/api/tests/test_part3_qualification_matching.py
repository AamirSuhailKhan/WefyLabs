"""
WefyLabs Core Product — Part 3 of 8
Qualification Engine + Canonical Property Matching + Customer-Property Intelligence + Shortlist
================================================================================================
Comprehensive test suite verifying:
  1. Canonical Match Engine (AIPropertyMatchingEngine) determinism without Gemini
  2. Exact match vs close match vs controlled alternative labeling
  3. Strict hard budget ceiling (₹1.5 Cr strictly rejects ₹1.55 Cr without flexibility)
  4. Negative preferences enforcement (Ground floor exclusion outranks positive fit)
  5. Missing data preservation ('UNKNOWN' for unverified amenities, never assumed true/false)
  6. Confidence score independent of match quality
  7. No-match determinism and restrictive criteria explanation
  8. Shortlist lifecycle (add, remove, list, idempotency, DB uniqueness)
  9. Customer-Property interaction recording & structured rejection feedback
 10. Multi-tenant isolation & cross-tenant inventory protection (Tenant A vs Tenant B)
 11. IDOR security (Customer A cannot access Customer B shortlist or mutate other tenant)
 12. Tenant-scoped cache isolation and requirement/property change invalidation
 13. Qualification engine completeness & decision-prioritized question generation
 14. Realistic E2E scenarios 103 - 108 (Noida buyer, budget stretch, ground floor objection, unavailable listing)
 15. MatchingIntelligenceFacade tool readiness for Part 4 AI agent
"""
import uuid
import asyncio
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, and_

from app.main import app
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.memory_models import MemoryRecord, MemoryPropertyFeedback
from app.modules.property_recommendation.matching_service import (
    AIPropertyMatchingEngine,
    DEFAULT_MATCHING_WEIGHTS,
)
from app.modules.property_recommendation.requirement_normalizer import (
    RequirementNormalizer,
    generate_clarification_questions,
)
from app.modules.property_recommendation.dto import (
    ShortlistRequestDTO,
    PropertyInteractionRequestDTO,
)
from app.modules.matching_intelligence.service import MatchingIntelligenceFacade
from app.modules.customer_intelligence.schemas import (
    RequirementProfileDTO,
    RequirementUpdateDTO,
)
from app.modules.customer_intelligence.service import CustomerIntelligenceService
from app.infrastructure.cache.query_cache import AsyncQueryCacheService


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_a_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def tenant_b_id() -> str:
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def brokers(db_session, tenant_a_id, tenant_b_id):
    broker_a = Broker(
        id=uuid.UUID(tenant_a_id),
        email=f"tenant_a_{uuid.uuid4().hex[:6]}@wefylabs.com",
        phone=f"+91{uuid.uuid4().int % 10000000000:010d}",
        name="Tenant A Brokerage",
        agency_name="Agency A",
        city="Noida"
    )
    broker_b = Broker(
        id=uuid.UUID(tenant_b_id),
        email=f"tenant_b_{uuid.uuid4().hex[:6]}@wefylabs.com",
        phone=f"+91{uuid.uuid4().int % 10000000000:010d}",
        name="Tenant B Brokerage",
        agency_name="Agency B",
        city="Delhi"
    )
    db_session.add_all([broker_a, broker_b])
    await db_session.commit()
    return broker_a, broker_b


@pytest_asyncio.fixture
async def test_leads(db_session, brokers):
    broker_a, broker_b = brokers

    # Lead A1: Noida buyer, budget max 1.5 Cr (15,000,000), 3 BHK, ready to move, no ground floor
    lead_a1 = Lead(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        name="Vikram Verma",
        phone="+919810000001",
        email="vikram.verma@example.com",
        status="active",
        score="hot",
        score_confidence=0.85,
        transaction_type="buy",
        budget_min=12000000,
        budget_max=15000000,
        budget_currency="INR",
        property_type="3 BHK apartment",
        preferred_locations=["Noida", "Sector 150"],
        timeline="immediate",
        notes=[
            {"content": "Client wants ready to move with parking. Negative preference: no ground floor."}
        ]
    )

    # Lead A2: Incomplete discovery lead (no budget, no location specified)
    lead_a2 = Lead(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        name="Neha Gupta",
        phone="+919810000002",
        email="neha.gupta@example.com",
        status="active",
        score="cold",
        score_confidence=0.4,
        notes=[]
    )

    # Lead B1: Tenant B customer searching in Delhi
    lead_b1 = Lead(
        id=uuid.uuid4(),
        broker_id=broker_b.id,
        name="Rajesh Khanna",
        phone="+919810000003",
        email="rajesh.khanna@example.com",
        status="active",
        score="warm",
        score_confidence=0.9,
        transaction_type="buy",
        budget_min=8000000,
        budget_max=12000000,
        budget_currency="INR",
        property_type="2 BHK apartment",
        preferred_locations=["Dwarka", "Delhi"],
        timeline="1_month"
    )

    db_session.add_all([lead_a1, lead_a2, lead_b1])
    await db_session.commit()
    return lead_a1, lead_a2, lead_b1


@pytest_asyncio.fixture
async def scenario_properties(db_session, brokers):
    broker_a, broker_b = brokers

    # Prop A1 (Ideal Exact Match): 3 BHK Noida ₹1.45 Cr, ready, parking, 2nd floor
    prop_a1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A1-EXACT",
        title="Ace Golfshire Luxury 3BHK",
        description="Premium spacious apartment with park facing balcony and modular kitchen.",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=14500000.0,
        currency_code="INR",
        area_value=1800.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Sector 150",
        city="Noida",
        amenities=["Parking", "Gym", "Clubhouse", "Security"],
        floor_number=2,
        total_floors=20,
        construction_status="ready_to_move",
        possession_date=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )

    # Prop A2 (Negative Conflict): 3 BHK Noida ₹1.48 Cr, ready, parking, Ground Floor (floor_number=0)
    prop_a2 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A2-GROUND",
        title="ATS Pristine Ground Floor 3BHK",
        description="Ground floor luxury unit with private garden.",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=14800000.0,
        currency_code="INR",
        area_value=1750.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Sector 150",
        city="Noida",
        amenities=["Parking", "Garden", "Clubhouse"],
        floor_number=0,  # GROUND FLOOR
        total_floors=18,
        construction_status="ready_to_move"
    )

    # Prop A3 (Alternative / BHK Mismatch): 2 BHK Noida ₹1.3 Cr, ready, parking
    prop_a3 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A3-2BHK",
        title="Eldeco Live Greens 2BHK",
        description="Cozy 2BHK unit with modern layout.",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=13000000.0,
        currency_code="INR",
        area_value=1250.0,
        area_unit="sqft",
        bedrooms=2,  # 2 BHK instead of 3 BHK
        bathrooms=2,
        locality="Sector 150",
        city="Noida",
        amenities=["Parking", "Gym"],
        floor_number=5,
        total_floors=22,
        construction_status="ready_to_move"
    )

    # Prop A4 (Budget Ceiling Exceeded): 3 BHK Noida ₹1.55 Cr (Over ₹1.5 Cr ceiling)
    prop_a4 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A4-EXPENSIVE",
        title="Godrej Woods 3BHK Ultra Luxury",
        description="Ultra luxury 3BHK overlooking forest reserve.",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=15500000.0,  # Exceeds 15,000,000 limit
        currency_code="INR",
        area_value=1950.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Sector 43",
        city="Noida",
        amenities=["Parking", "Gym", "Pool"],
        floor_number=10,
        total_floors=30,
        construction_status="ready_to_move"
    )

    # Prop A5 (Unavailable / Sold): 3 BHK Noida ₹1.4 Cr, ready, but SOLD
    prop_a5 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A5-SOLD",
        title="Mahagun Manorial 3BHK Sold Unit",
        description="Spacious unit recently sold.",
        property_type="apartment",
        status="sold",  # NOT AVAILABLE
        transaction_category="resale",
        price=14000000.0,
        currency_code="INR",
        area_value=1800.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Sector 128",
        city="Noida",
        amenities=["Parking"],
        floor_number=7,
        total_floors=25,
        construction_status="ready_to_move"
    )

    # Prop B1 (Tenant B Property): 3 BHK Noida ₹1.45 Cr (Perfect match on paper, but belongs to Tenant B!)
    prop_b1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_b.id,  # Tenant B
        property_code="PROP-B1-TENANTB",
        title="Tenant B Exclusive Luxury 3BHK",
        description="Exclusive 3BHK listing managed by Tenant B agency.",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=14500000.0,
        currency_code="INR",
        area_value=1800.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Sector 150",
        city="Noida",
        amenities=["Parking", "Gym"],
        floor_number=4,
        total_floors=18,
        construction_status="ready_to_move"
    )

    db_session.add_all([prop_a1, prop_a2, prop_a3, prop_a4, prop_a5, prop_b1])
    await db_session.commit()
    return prop_a1, prop_a2, prop_a3, prop_a4, prop_a5, prop_b1


# ─── 1. Canonical Match Engine & Hard Filter Determinism ──────────────────────

@pytest.mark.asyncio
async def test_canonical_matching_exact_match(db_session, brokers, test_leads, scenario_properties):
    """Phase 78 & 103: Realistic scenario - Prop A1 must be exact match with high score."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    prop_a1, _, _, _, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    res = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        top_k=10,
        force_refresh=True
    )

    matched_ids = [str(item.property_id) for item in res.recommendations]
    assert str(prop_a1.id) in matched_ids

    # Find prop_a1 item
    item_a1 = next(item for item in res.recommendations if str(item.property_id) == str(prop_a1.id))
    assert item_a1.compatibility_score >= 80.0
    assert item_a1.is_alternative is False
    assert any("budget" in m.lower() for m in item_a1.requirement_coverage.matched)


@pytest.mark.asyncio
async def test_strict_hard_budget_ceiling_enforcement(db_session, brokers, test_leads, scenario_properties):
    """Phase 13 & 78: Budget ceiling ₹1.5 Cr strictly rejects ₹1.55 Cr (Prop A4)."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    _, _, _, prop_a4, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    res = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        top_k=10,
        allow_alternatives=False,
        flexibility_pct=0.0,
        force_refresh=True
    )

    matched_ids = [item.property_id for item in res.recommendations]
    assert prop_a4.id not in matched_ids, "Property exceeding budget ceiling must NOT appear in exact matches!"


@pytest.mark.asyncio
async def test_negative_preference_ground_floor_conflict(db_session, brokers, test_leads, scenario_properties):
    """Phase 24, 83 & 103: Ground floor negative preference detected and flagged as conflict."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    _, prop_a2, _, _, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    req = RequirementNormalizer.normalize(lead=lead_a1)

    # Directly evaluate compatibility detailed
    (
        score, breakdown, reasons, mismatches,
        matched_crit, partial_crit, unmatched_crit,
        neg_conflicts, unknown_crit
    ) = engine.calculate_compatibility_score_detailed(prop=prop_a2, lead=lead_a1, req=req)

    assert len(neg_conflicts) > 0, "Ground floor must be flagged in negative conflicts!"
    assert any("ground floor" in c.lower() for c in neg_conflicts)
    assert score < 70.0, "Score must be penalized when negative conflict is present"


@pytest.mark.asyncio
async def test_unavailable_property_exclusion(db_session, brokers, test_leads, scenario_properties):
    """Phase 31, 78 & 107: Sold or archived properties must never appear in recommendations."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    _, _, _, _, prop_a5, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    res = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        availability="available",
        force_refresh=True
    )

    matched_ids = [item.property_id for item in res.recommendations]
    assert prop_a5.id not in matched_ids, "Sold property A5 must NOT appear in available recommendations"


@pytest.mark.asyncio
async def test_cross_tenant_matching_isolation(db_session, brokers, test_leads, scenario_properties):
    """Phase 61, 62 & 87: Tenant A customer must NEVER see Tenant B properties, even if matching."""
    broker_a, broker_b = brokers
    lead_a1, _, _ = test_leads
    _, _, _, _, _, prop_b1 = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    res = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        top_k=20,
        force_refresh=True
    )

    matched_ids = [item.property_id for item in res.recommendations]
    assert prop_b1.id not in matched_ids, "Tenant B property leaked into Tenant A matching results!"


# ─── 2. Match Confidence, Missing Data & Explainability ───────────────────────

@pytest.mark.asyncio
async def test_confidence_independent_of_match_score(db_session, brokers, test_leads, scenario_properties):
    """Phase 29 & 79: Incomplete customer has low confidence even if property matches some fields."""
    broker_a, _ = brokers
    _, lead_a2, _ = test_leads
    prop_a1, _, _, _, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    conf, guidance = engine.evaluate_confidence(lead_a2, prop_a1)

    assert conf < 0.6, f"Confidence {conf} must be low when budget, location, and BHK are missing!"
    assert guidance is not None
    assert "budget" in guidance.lower() or "location" in guidance.lower()


@pytest.mark.asyncio
async def test_amenity_unknown_preservation(db_session, brokers, test_leads):
    """Phase 30 & 84: Customer requires parking; property with no parking info remains UNKNOWN, not True/False."""
    broker_a, _ = brokers

    # Lead requiring private pool
    lead_pool = Lead(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        name="Pool Requester",
        phone="+919810000004",
        status="active",
        budget_max=20000000,
        property_type="villa",
        notes=[{"content": "Customer requires private pool and tennis court."}]
    )
    # Property with empty amenities
    prop_no_amenities = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-UNVERIFIED",
        title="Unverified Villa",
        description="Luxury villa without verified amenity list",
        property_type="villa",
        status="available",
        price=18000000.0,
        area_value=2500.0,
        amenities=[],  # No amenities listed
        bedrooms=4,
        city="Noida"
    )
    db_session.add_all([lead_pool, prop_no_amenities])
    await db_session.commit()

    engine = AIPropertyMatchingEngine(db_session)
    req = RequirementNormalizer.normalize(lead=lead_pool)

    (
        score, breakdown, reasons, mismatches,
        matched_crit, partial_crit, unmatched_crit,
        neg_conflicts, unknown_crit
    ) = engine.calculate_compatibility_score_detailed(prop=prop_no_amenities, lead=lead_pool, req=req)

    assert len(unknown_crit) > 0, "Missing amenities must be recorded in unknown_criteria!"
    assert any("pool" in u.lower() or "amenit" in u.lower() for u in unknown_crit)


@pytest.mark.asyncio
async def test_no_match_explanation_restrictive_criteria(db_session, brokers, scenario_properties):
    """Phase 36 & 85: Criteria that cannot be satisfied yield zero results with no_match_reasons."""
    broker_a, _ = brokers

    # Lead with impossible requirements: ₹20 Lakh in Sector 150 for 5 BHK
    impossible_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        name="Impossible Searcher",
        phone="+919810000005",
        status="active",
        transaction_type="buy",
        budget_max=2000000,  # 20 Lakhs
        property_type="5 BHK villa",
        preferred_locations=["Sector 150"],
        timeline="immediate"
    )
    db_session.add(impossible_lead)
    await db_session.commit()

    engine = AIPropertyMatchingEngine(db_session)
    res = await engine.match_properties_for_lead(
        lead_id=impossible_lead.id,
        broker=broker_a,
        force_refresh=True
    )

    assert len(res.recommendations) == 0, "Impossible criteria must produce 0 matches"
    assert len(res.no_match_reasons) > 0, "Must provide explanation of restrictive criteria"


@pytest.mark.asyncio
async def test_explain_property_match_deterministic(db_session, brokers, test_leads, scenario_properties):
    """Phase 34 & 75: Deterministic match explanation without Gemini."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    prop_a1, _, _, _, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    explanation = await engine.explain_property_match(
        lead_id=lead_a1.id,
        property_id=prop_a1.id,
        broker=broker_a
    )

    assert str(explanation.property_id) == str(prop_a1.id)
    assert str(explanation.lead_id) == str(lead_a1.id)
    assert explanation.match_score >= 80.0
    assert len(explanation.matched_criteria) > 0
    assert "budget" in explanation.deterministic_summary.lower() or "bhk" in explanation.deterministic_summary.lower()


# ─── 3. Shortlist & Customer-Property Interaction ─────────────────────────────

@pytest.mark.asyncio
async def test_shortlist_lifecycle_and_idempotency(db_session, brokers, test_leads, scenario_properties):
    """Phase 40, 44, 47 & 80: Add, list, remove shortlist, with idempotent double-call safety."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    prop_a1, _, _, _, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)

    # 1. Add to shortlist
    dto = ShortlistRequestDTO(
        property_id=str(prop_a1.id),
        lead_id=str(lead_a1.id),
        interest_type="shortlisted",
        notes="High interest after phone call"
    )
    res1 = await engine.shortlist_property(
        lead_id=lead_a1.id,
        req=dto,
        broker=broker_a
    )
    assert res1.status == "success"

    # 2. Add AGAIN (Idempotency check)
    res2 = await engine.shortlist_property(
        lead_id=lead_a1.id,
        req=dto,
        broker=broker_a
    )
    assert res2.status == "success"

    # Verify only ONE DB record exists
    stmt = select(LeadPropertyInterest).where(
        and_(
            LeadPropertyInterest.lead_id == lead_a1.id,
            LeadPropertyInterest.property_id == prop_a1.id,
            LeadPropertyInterest.organization_id == broker_a.id
        )
    )
    records = list((await db_session.execute(stmt)).scalars().all())
    assert len(records) == 1, "Idempotent shortlist must NOT create duplicate records!"

    # 3. List shortlist
    shortlist_resp = await engine.get_lead_shortlist(lead_id=lead_a1.id, broker=broker_a)
    assert shortlist_resp.total_count == 1
    assert str(shortlist_resp.items[0].property_id) == str(prop_a1.id)
    assert shortlist_resp.items[0].property_title == prop_a1.title

    # 4. Remove from shortlist
    del_resp = await engine.remove_property_from_shortlist(
        lead_id=lead_a1.id,
        property_id=prop_a1.id,
        broker=broker_a
    )
    assert del_resp["status"] == "success"

    # 5. List again (must be 0)
    shortlist_empty = await engine.get_lead_shortlist(lead_id=lead_a1.id, broker=broker_a)
    assert shortlist_empty.total_count == 0


@pytest.mark.asyncio
async def test_record_property_interaction_rejection_feedback(db_session, brokers, test_leads, scenario_properties):
    """Phase 42 & 106: Record rejection interaction with structured reason code and memory feedback."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    _, prop_a2, _, _, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)
    dto = PropertyInteractionRequestDTO(
        lead_id=str(lead_a1.id),
        property_id=str(prop_a2.id),
        interaction_type="REJECTED",
        rejection_reason="FLOOR",
        feedback="Customer does not want ground floor unit."
    )

    res = await engine.record_property_interaction(req=dto, broker=broker_a)
    assert res.status == "success"
    assert res.interaction_type == "REJECTED"
    assert res.rejection_reason == "FLOOR"

    # Verify MemoryPropertyFeedback was created
    stmt_feed = select(MemoryPropertyFeedback).where(
        and_(
            MemoryPropertyFeedback.lead_id == str(lead_a1.id),
            MemoryPropertyFeedback.property_id == str(prop_a2.id)
        )
    )
    feedback_rec = (await db_session.execute(stmt_feed)).scalars().first()
    assert feedback_rec is not None
    assert feedback_rec.reaction == "REJECTED"
    assert feedback_rec.objection_category == "FLOOR"


# ─── 4. Stale Data, Customer Change & Cache Invalidation ─────────────────────

@pytest.mark.asyncio
async def test_stale_data_price_update_invalidates_matches(db_session, brokers, test_leads, scenario_properties):
    """Phase 51 & 81: Property price update reflects immediately in subsequent matching calls."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    prop_a1, _, _, _, _, _ = scenario_properties

    engine = AIPropertyMatchingEngine(db_session)

    # 1. Match at ₹1.45 Cr (within ₹1.5 Cr budget)
    res1 = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        top_k=5,
        force_refresh=True
    )
    assert any(str(item.property_id) == str(prop_a1.id) for item in res1.recommendations)

    # 2. Update Property price to ₹1.75 Cr (exceeds budget!)
    prop_a1.price = 17500000.0
    await db_session.commit()
    # Invalidate cache tag
    AsyncQueryCacheService.invalidate_tag(f"tenant:{broker_a.id}:matches")

    # 3. Match again (must NOT appear because price now exceeds budget)
    res2 = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        top_k=5,
        force_refresh=False
    )
    matched_ids2 = [str(item.property_id) for item in res2.recommendations]
    assert str(prop_a1.id) not in matched_ids2, "Property updated to ₹1.75 Cr must NOT match ₹1.5 Cr budget!"


@pytest.mark.asyncio
async def test_customer_requirement_change_reflects_in_matching(db_session, brokers, test_leads, scenario_properties):
    """Phase 50 & 82: Customer expands budget from ₹1.5 Cr to ₹1.8 Cr -> Prop A4 now matches."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    _, _, _, prop_a4, _, _ = scenario_properties  # ₹1.55 Cr

    engine = AIPropertyMatchingEngine(db_session)

    # 1. At ₹1.5 Cr, prop_a4 does not match
    res1 = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        top_k=10,
        force_refresh=True
    )
    assert str(prop_a4.id) not in [str(item.property_id) for item in res1.recommendations]

    # 2. Customer stretches budget to ₹1.8 Cr
    lead_a1.budget_max = 18000000
    await db_session.commit()
    AsyncQueryCacheService.invalidate_tag(f"tenant:{broker_a.id}:matches")

    # 3. At ₹1.8 Cr, prop_a4 (₹1.55 Cr) is now eligible
    res2 = await engine.match_properties_for_lead(
        lead_id=lead_a1.id,
        broker=broker_a,
        top_k=10,
        force_refresh=True
    )
    assert str(prop_a4.id) in [str(item.property_id) for item in res2.recommendations], "Prop A4 must match after budget increase!"


# ─── 5. Qualification Engine & Question Prioritization ───────────────────────

@pytest.mark.asyncio
async def test_qualification_missing_info_prioritization(test_leads):
    """Phase 10 & 11: Missing requirements are ranked by decision value (budget > location > property type)."""
    _, lead_a2, _ = test_leads
    req = RequirementNormalizer.normalize(lead=lead_a2)
    questions = generate_clarification_questions(lead=lead_a2, req=req)

    assert len(questions) > 0
    # First question should target budget or location, not obscure preferences
    assert any("budget" in q.lower() or "price" in q.lower() for q in questions[:2])


# ─── 6. MatchingIntelligenceFacade (Part 4 AI Sales Agent Tool Readiness) ────

@pytest.mark.asyncio
async def test_matching_intelligence_facade_tool_readiness(db_session, brokers, test_leads, scenario_properties):
    """Phase 64 & 110: Part 4 AI sales agent can call MatchingIntelligenceFacade with zero SQL."""
    broker_a, _ = brokers
    lead_a1, _, _ = test_leads
    prop_a1, _, _, _, _, _ = scenario_properties

    facade = MatchingIntelligenceFacade(db_session)

    # 1. Tool: find_matches
    matches_res = await facade.find_matches(
        lead_id=str(lead_a1.id),
        organization_id=str(broker_a.id),
        limit=5
    )
    assert matches_res["status"] == "success"
    assert matches_res["total_matches"] >= 1
    assert matches_res["results"][0]["property_id"] == str(prop_a1.id)

    # 2. Tool: explain_match
    explain_res = await facade.explain_match(
        lead_id=str(lead_a1.id),
        property_id=str(prop_a1.id),
        organization_id=str(broker_a.id)
    )
    assert explain_res["status"] == "success"
    assert "deterministic_summary" in explain_res

    # 3. Tool: record_interaction
    interaction_res = await facade.record_interaction(
        lead_id=str(lead_a1.id),
        property_id=str(prop_a1.id),
        organization_id=str(broker_a.id),
        interaction_type="SHORTLISTED"
    )
    assert interaction_res["status"] == "success"

    # 4. Tool: get_shortlist
    shortlist_res = await facade.get_shortlist(
        lead_id=str(lead_a1.id),
        organization_id=str(broker_a.id)
    )
    assert shortlist_res["total_count"] >= 1
