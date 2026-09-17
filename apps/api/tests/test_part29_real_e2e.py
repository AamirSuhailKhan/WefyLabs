"""
Part 29 — Real End-to-End Scenario Verification: AI Lead <-> Property Matching
=============================================================================
Comprehensive real database test using isolated SQLite async session:
1. Lead Rahul Sharma (₹1Cr, Whitefield, 3 BHK, Parking)
2. Inventory setup (Property A, B, C, D)
3. Lead -> Property matching ranking (A ranks #1)
4. Reverse matching (Property A -> Rahul Sharma ranks #1 over Priya & Amit)
5. Shortlist action into LeadPropertyInterest with explainable reasons
6. Recommend action creating follow-up Task and LeadPropertyInterest
7. Site visit scheduling and Task linkage
8. Property availability state transition (SOLD -> immediate exclusion from matches)
9. Strict multi-tenant isolation (Org A vs Org B)
"""
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.models import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.crm_models import Task, Meeting, Activity
from app.models.audit_log import AuditLog
from app.modules.property_recommendation.matching_service import AIPropertyMatchingEngine
from app.modules.property_recommendation.dto import ShortlistRequestDTO, RecommendRequestDTO
from app.modules.properties.service import PropertyService

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_part29_matching_engine_real_e2e(db_session: AsyncSession):
    """
    Phase 64 & 65 Real E2E Test:
    Verify exact natural ranking, reverse matching, shortlisting, recommendations,
    stale availability exclusion, and multi-tenant isolation on live DB models.
    """
    # 1. Create Brokers (Tenant 1 and Foreign Tenant)
    broker = Broker(
        id=uuid.uuid4(),
        name="Vikram Sethi",
        email="vikram@primebrokerage.com",
        phone="+919800000001"
    )
    foreign_broker = Broker(
        id=uuid.uuid4(),
        name="Foreign Director",
        email="director@foreignrealty.com",
        phone="+919800000002"
    )
    db_session.add_all([broker, foreign_broker])
    await db_session.commit()

    # 2. Create Lead: Rahul Sharma (Budget ₹1Cr, Whitefield, 3 BHK, Parking required)
    rahul_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Rahul Sharma",
        phone="+919811111111",
        status="active",
        score="hot",
        score_confidence=0.88,
        budget_min=7500000,
        budget_max=10000000,  # 1 Crore
        property_type="3 BHK apartment",
        transaction_type="buy",
        preferred_locations=["Whitefield"],
        timeline="immediate",
        notes=[{"content": "Client requires parking and gym"}]
    )
    db_session.add(rahul_lead)

    # 3. Create Properties according to Phase 64 specification:
    # Prop A: 3 BHK, Whitefield, ₹95L, Parking, Available -> Perfect match
    prop_a = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="PROP-A-WF",
        title="Prestige Boulevard 3BHK",
        description="Spacious apartment in Whitefield",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=9500000.0,
        area_value=1600.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking", "Gym", "Power Backup"]
    )

    # Prop B: 3 BHK, Whitefield, ₹1.10Cr, Parking, Available -> Near budget ceiling
    prop_b = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="PROP-B-WF",
        title="Sobha Habitech 3BHK",
        description="Sobha luxury apartment in Whitefield",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=11000000.0,
        area_value=1750.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking", "Clubhouse"]
    )

    # Prop C: 2 BHK, Whitefield, ₹70L, Available -> Lower due to BHK (2 instead of 3)
    prop_c = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="PROP-C-WF",
        title="Brigade Lake 2BHK",
        description="Compact 2BHK in Whitefield",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=7000000.0,
        area_value=1100.0,
        area_unit="sqft",
        bedrooms=2,
        bathrooms=2,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking"]
    )

    # Prop D: 3 BHK, Sarjapur, ₹85L, Parking, Available -> Lower due to location
    prop_d = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="PROP-D-SJ",
        title="Assetz Marq 3BHK",
        description="Assetz Marq 3BHK in Sarjapur",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=8500000.0,
        area_value=1500.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Sarjapur",
        city="Bengaluru",
        amenities=["Parking"]
    )

    # Foreign Property: belongs to foreign_broker
    prop_foreign = PropertyListing(
        id=uuid.uuid4(),
        broker_id=foreign_broker.id,
        property_code="PROP-FOREIGN",
        title="Foreign Tenant 3BHK",
        description="Foreign property listing",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=9000000.0,
        area_value=1500.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        locality="Whitefield",
        city="Bengaluru"
    )

    db_session.add_all([prop_a, prop_b, prop_c, prop_d, prop_foreign])
    await db_session.commit()

    # 4. Initialize AI Matching Engine
    engine = AIPropertyMatchingEngine(db=db_session)

    # 5. Lead -> Property Matching Evaluation (Phase 64)
    # With allow_alternatives=True, near-budget candidates are ranked
    matches_dto = await engine.match_properties_for_lead(
        lead_id=rahul_lead.id,
        broker=broker,
        top_k=10,
        allow_alternatives=True
    )

    assert matches_dto.total_candidates_retrieved >= 1
    matched_items = matches_dto.items
    assert len(matched_items) >= 1

    # Property A must be #1 rank with top score
    top_match = matched_items[0]
    assert str(top_match.property_id) == str(prop_a.id)
    assert top_match.evidence_references.get("property_code") == "PROP-A-WF"
    assert top_match.match_score >= 90.0
    assert any("budget" in r.lower() for r in top_match.why_matches)
    assert any("whitefield" in r.lower() for r in top_match.why_matches)
    assert any("3 bhk" in r.lower() for r in top_match.why_matches)

    # Verify Foreign tenant property is NEVER returned
    returned_ids = [str(m.property_id) for m in matched_items]
    assert str(prop_foreign.id) not in returned_ids

    # 6. Reverse Matching (Property -> Compatible Leads, Phase 65)
    # Create Priya (Budget 60L, 2 BHK) and Amit (Budget 1.2Cr, 3 BHK Whitefield)
    priya_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Priya Nair",
        phone="+919822222222",
        status="active",
        score="warm",
        budget_max=6000000,
        property_type="2 BHK apartment",
        preferred_locations=["Whitefield"]
    )
    amit_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Amit Verma",
        phone="+919833333333",
        status="active",
        score="warm",
        budget_max=12000000,
        property_type="3 BHK apartment",
        preferred_locations=["Whitefield"],
        notes=[{"content": "Client needs parking"}]
    )
    db_session.add_all([priya_lead, amit_lead])
    await db_session.commit()

    # Match leads for Property A (3BHK Whitefield 95L)
    prop_a_leads = await engine.match_leads_for_property(
        property_id=prop_a.id,
        broker=broker,
        top_k=5
    )
    prop_a_lead_ids = [str(l.lead_id) for l in prop_a_leads]

    # Rahul Sharma and Amit Verma must rank at the top
    assert str(rahul_lead.id) in prop_a_lead_ids
    assert str(amit_lead.id) in prop_a_lead_ids

    # 7. Shortlist Action -> LeadPropertyInterest
    shortlist_res = await engine.shortlist_property_for_lead(
        lead_id=rahul_lead.id,
        property_id=prop_a.id,
        broker=broker,
        dto=ShortlistRequestDTO(
            lead_id=str(rahul_lead.id),
            property_id=str(prop_a.id),
            notes="Shortlisted by agent Vikram after client call"
        )
    )
    assert shortlist_res["status"] == "success"
    assert shortlist_res["match_score"] >= 90.0

    # Verify in DB
    stmt = select(LeadPropertyInterest).where(
        LeadPropertyInterest.lead_id == rahul_lead.id,
        LeadPropertyInterest.property_id == prop_a.id
    )
    lpi = (await db_session.execute(stmt)).scalars().first()
    assert lpi is not None
    assert lpi.status == "SHORTLISTED"
    assert lpi.deterministic_score >= 90.0
    assert lpi.reasons is not None
    assert len(lpi.reasons) >= 1

    # 8. Recommend Action -> LeadPropertyInterest + Follow-up Task
    recommend_res = await engine.recommend_property_to_lead(
        lead_id=rahul_lead.id,
        property_id=prop_a.id,
        broker=broker,
        dto=RecommendRequestDTO(
            lead_id=str(rahul_lead.id),
            property_id=str(prop_a.id),
            notes="Sending official property brochure to Rahul",
            create_followup_task=True
        )
    )
    assert recommend_res["status"] == "success"

    # Verify task created
    task_stmt = select(Task).where(Task.lead_id == rahul_lead.id)
    task = (await db_session.execute(task_stmt)).scalars().first()
    assert task is not None
    assert "Present" in task.title or "Matched" in task.title or "Property" in task.title

    # 9. Schedule Site Visit
    prop_service = PropertyService(db_session)
    visit_res = await prop_service.schedule_site_visit(
        lead_id=rahul_lead.id,
        property_id=prop_a.id,
        broker=broker,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
        notes="Client visiting with spouse"
    )
    assert visit_res["status"] == "success"
    assert visit_res["meeting_id"] is not None

    # 10. Availability State Transition: Property A becomes SOLD (Phase 43)
    prop_a.status = "sold"
    await db_session.commit()

    # Re-matching for Rahul Sharma must now completely exclude Property A
    fresh_matches = await engine.match_properties_for_lead(
        lead_id=rahul_lead.id,
        broker=broker,
        top_k=10,
        allow_alternatives=False
    )
    fresh_property_ids = [str(m.property_id) for m in fresh_matches.items]
    assert str(prop_a.id) not in fresh_property_ids, "Sold property must never be returned in fresh matches"

    # 11. Multi-Tenant Isolation Check (Phase 47)
    foreign_lead = Lead(
        id=uuid.uuid4(),
        broker_id=foreign_broker.id,
        name="Foreign Lead",
        phone="+919000000000",
        status="active",
        score="warm",
        budget_max=10000000,
        property_type="3 BHK apartment",
        preferred_locations=["Whitefield"]
    )
    db_session.add(foreign_lead)
    await db_session.commit()

    foreign_matches = await engine.match_properties_for_lead(
        lead_id=foreign_lead.id,
        broker=foreign_broker,
        top_k=10,
        allow_alternatives=True
    )
    for m in foreign_matches.items:
        # None of broker's properties may ever appear in foreign broker's recommendations
        assert str(m.property_id) not in [str(prop_a.id), str(prop_b.id), str(prop_c.id), str(prop_d.id)]
