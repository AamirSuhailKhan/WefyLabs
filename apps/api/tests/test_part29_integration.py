"""
Part 29 — Integration Test Suite: AI Lead ↔ Property Matching Engine
===================================================================
18 integration tests covering:
- Lead -> Property candidates ranking
- Property -> Lead reverse candidates
- Tenant isolation (Lead & Property)
- LeadPropertyInterest integration (Shortlist & Recommend)
- Task creation on recommendation
- AuditLog recording
- Match feedback updates
- Invalidation on property status transition
- Property comparison matrix & scoping
- Pagination (limit & offset)
- Filters (property_type, location, availability)
- Sorting (score, price)
- Concurrency & idempotency
"""
import asyncio
import uuid
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_

from app.models import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.crm_models import Task, Activity
from app.models.audit_log import AuditLog
from app.modules.property_recommendation.matching_service import AIPropertyMatchingEngine
from app.modules.property_recommendation.dto import ShortlistRequestDTO, RecommendRequestDTO

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


@pytest_asyncio.fixture
async def broker_a(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"broker_a_{uuid.uuid4().hex[:6]}@crm.com",
        name="Broker Alpha",
        subscription_status="active"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture
async def broker_b(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"broker_b_{uuid.uuid4().hex[:6]}@crm.com",
        name="Broker Beta",
        subscription_status="active"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession, broker_a: Broker, broker_b: Broker):
    # Tenant A Lead: Wants 3BHK in Whitefield around 1 Cr, parking required
    lead_a = Lead(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        name="Rajesh Khanna",
        phone="+919876500001",
        budget_min=8000000,
        budget_max=11000000,
        property_type="3 BHK apartment",
        preferred_locations=["Whitefield"],
        transaction_type="buy",
        status="active",
        notes=[{"content": "Parking mandatory"}]
    )

    # Tenant A Properties:
    # 1. Perfect match: 3BHK in Whitefield at 95L with parking
    prop_1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A-1",
        title="Prestige Palms 3BHK",
        description="Spacious 3BHK apartment in Whitefield",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=9500000.0,
        area_value=1650.0,
        area_unit="sqft",
        bedrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking", "Gym"]
    )
    # 2. Lower fit: 2BHK in Electronic City at 60L
    prop_2 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A-2",
        title="Compact 2BHK Electronic City",
        description="Affordable 2BHK in Electronic City",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=6000000.0,
        area_value=1100.0,
        area_unit="sqft",
        bedrooms=2,
        locality="Electronic City",
        city="Bengaluru",
        amenities=["Parking"]
    )
    # 3. Villa in Whitefield at 1.05 Cr
    prop_3 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        property_code="PROP-A-3",
        title="Palm Meadows Villa",
        description="Luxury villa in Palm Meadows",
        property_type="villa",
        status="available",
        transaction_category="resale",
        price=10500000.0,
        area_value=2800.0,
        area_unit="sqft",
        bedrooms=4,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking", "Pool"]
    )

    # Tenant B Property (Foreign):
    prop_b = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_b.id,
        property_code="PROP-B-1",
        title="Sobha Foreign 3BHK",
        description="Luxury foreign property in Whitefield",
        property_type="apartment",
        status="available",
        price=9000000.0,
        area_value=1700.0,
        area_unit="sqft",
        bedrooms=3,
        locality="Whitefield",
        city="Bengaluru"
    )

    db_session.add_all([lead_a, prop_1, prop_2, prop_3, prop_b])
    await db_session.commit()

    return {
        "lead_a": lead_a,
        "prop_1": prop_1,
        "prop_2": prop_2,
        "prop_3": prop_3,
        "prop_b": prop_b
    }


# ─── Integration Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_integration_lead_to_property_matching(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Verifies that the best candidate (Prestige Palms 3BHK) ranks #1 for lead."""
    engine = AIPropertyMatchingEngine(db=db_session)
    res = await engine.match_properties_for_lead(
        lead_id=seed_data["lead_a"].id,
        broker=broker_a,
        top_k=5
    )
    assert len(res.items) >= 1
    top_match = res.items[0]
    assert top_match.property_id == str(seed_data["prop_1"].id)
    assert top_match.match_score >= 85.0
    assert "Prestige Palms" in top_match.title


@pytest.mark.asyncio
async def test_integration_property_to_lead_reverse_matching(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Reverse matching for Prop 1 finds Rajesh Khanna as the top buyer match."""
    engine = AIPropertyMatchingEngine(db=db_session)
    leads = await engine.match_leads_for_property(
        property_id=seed_data["prop_1"].id,
        broker=broker_a,
        top_k=5
    )
    assert len(leads) >= 1
    top_lead = leads[0]
    assert top_lead.lead_id == str(seed_data["lead_a"].id)
    assert top_lead.match_score >= 85.0


@pytest.mark.asyncio
async def test_integration_tenant_isolation_lead_matching(db_session: AsyncSession, broker_b: Broker, seed_data):
    """Broker B cannot access matches for Broker A's lead."""
    engine = AIPropertyMatchingEngine(db=db_session)
    with pytest.raises(Exception) as exc:
        await engine.match_properties_for_lead(
            lead_id=seed_data["lead_a"].id,
            broker=broker_b,
            top_k=5
        )
    assert "not found" in str(exc.value).lower() or "404" in str(exc.value)


@pytest.mark.asyncio
async def test_integration_tenant_isolation_property_reverse_matching(db_session: AsyncSession, broker_b: Broker, seed_data):
    """Broker B cannot reverse-match Broker A's property."""
    engine = AIPropertyMatchingEngine(db=db_session)
    with pytest.raises(Exception) as exc:
        await engine.match_leads_for_property(
            property_id=seed_data["prop_1"].id,
            broker=broker_b,
            top_k=5
        )
    assert "not found" in str(exc.value).lower() or "404" in str(exc.value)


@pytest.mark.asyncio
async def test_integration_lead_property_interest_shortlist(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Shortlist action upserts LeadPropertyInterest with score and reasons."""
    engine = AIPropertyMatchingEngine(db=db_session)
    dto = ShortlistRequestDTO(
        lead_id=str(seed_data["lead_a"].id),
        property_id=str(seed_data["prop_1"].id),
        notes="High priority client interest"
    )
    res = await engine.shortlist_property_for_lead(
        lead_id=seed_data["lead_a"].id,
        property_id=seed_data["prop_1"].id,
        broker=broker_a,
        dto=dto
    )
    assert res["status"] == "success"

    # Verify in DB
    stmt = select(LeadPropertyInterest).where(
        and_(
            LeadPropertyInterest.lead_id == seed_data["lead_a"].id,
            LeadPropertyInterest.property_id == seed_data["prop_1"].id
        )
    )
    interest = (await db_session.execute(stmt)).scalars().first()
    assert interest is not None
    assert interest.status == "SHORTLISTED"
    assert interest.match_score >= 80.0


@pytest.mark.asyncio
async def test_integration_recommend_creates_followup_task(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Recommend action updates interest to MATCHED and creates a follow-up Task."""
    engine = AIPropertyMatchingEngine(db=db_session)
    dto = RecommendRequestDTO(
        lead_id=str(seed_data["lead_a"].id),
        property_id=str(seed_data["prop_1"].id),
        notes="Recommend during weekly call",
        create_followup_task=True
    )
    res = await engine.recommend_property_to_lead(
        lead_id=seed_data["lead_a"].id,
        property_id=seed_data["prop_1"].id,
        broker=broker_a,
        dto=dto
    )
    assert res["status"] == "success"

    # Verify task created
    task_stmt = select(Task).where(
        and_(
            Task.lead_id == seed_data["lead_a"].id,
            Task.broker_id == broker_a.id
        )
    )
    task = (await db_session.execute(task_stmt)).scalars().first()
    assert task is not None
    assert "Prestige Palms" in task.title


@pytest.mark.asyncio
async def test_integration_audit_log_on_shortlist(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Shortlisting records AuditLog entry with action 'match.shortlist'."""
    engine = AIPropertyMatchingEngine(db=db_session)
    dto = ShortlistRequestDTO(
        lead_id=str(seed_data["lead_a"].id),
        property_id=str(seed_data["prop_1"].id),
    )
    await engine.shortlist_property_for_lead(seed_data["lead_a"].id, seed_data["prop_1"].id, broker_a, dto)

    audit_stmt = select(AuditLog).where(
        and_(
            AuditLog.organization_id == broker_a.id,
            AuditLog.action == "match.shortlist"
        )
    )
    audit = (await db_session.execute(audit_stmt)).scalars().first()
    assert audit is not None
    assert audit.resource_type == "lead_property_interest"


@pytest.mark.asyncio
async def test_integration_audit_log_on_recommend(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Recommending records AuditLog entry with action 'match.recommend'."""
    engine = AIPropertyMatchingEngine(db=db_session)
    dto = RecommendRequestDTO(
        lead_id=str(seed_data["lead_a"].id),
        property_id=str(seed_data["prop_1"].id),
    )
    await engine.recommend_property_to_lead(seed_data["lead_a"].id, seed_data["prop_1"].id, broker_a, dto)

    audit_stmt = select(AuditLog).where(
        and_(
            AuditLog.organization_id == broker_a.id,
            AuditLog.action == "match.recommend"
        )
    )
    audit = (await db_session.execute(audit_stmt)).scalars().first()
    assert audit is not None


@pytest.mark.asyncio
async def test_integration_audit_log_on_feedback(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Feedback records AuditLog entry with action 'match.feedback'."""
    engine = AIPropertyMatchingEngine(db=db_session)
    await engine.record_match_feedback(
        lead_id=seed_data["lead_a"].id,
        property_id=seed_data["prop_1"].id,
        broker=broker_a,
        feedback="wrong_budget",
        notes="Customer wants strictly below 90L"
    )

    audit_stmt = select(AuditLog).where(
        and_(
            AuditLog.organization_id == broker_a.id,
            AuditLog.action == "match.feedback"
        )
    )
    audit = (await db_session.execute(audit_stmt)).scalars().first()
    assert audit is not None
    assert audit.new_values.get("feedback") == "wrong_budget"


@pytest.mark.asyncio
async def test_integration_feedback_updates_interest_status(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Feedback 'reject' updates LeadPropertyInterest status to REJECTED."""
    engine = AIPropertyMatchingEngine(db=db_session)
    await engine.record_match_feedback(
        lead_id=seed_data["lead_a"].id,
        property_id=seed_data["prop_1"].id,
        broker=broker_a,
        feedback="reject_locality",
        notes="Rejected by client"
    )

    interest_stmt = select(LeadPropertyInterest).where(
        and_(
            LeadPropertyInterest.lead_id == seed_data["lead_a"].id,
            LeadPropertyInterest.property_id == seed_data["prop_1"].id
        )
    )
    interest = (await db_session.execute(interest_stmt)).scalars().first()
    assert interest is not None
    assert interest.status == "REJECTED"


@pytest.mark.asyncio
async def test_integration_property_status_sold_excluded_immediately(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Updating property status to 'sold' immediately excludes it from candidate matches."""
    engine = AIPropertyMatchingEngine(db=db_session)

    # Mark prop_1 as sold
    seed_data["prop_1"].status = "sold"
    await db_session.commit()

    res = await engine.match_properties_for_lead(
        lead_id=seed_data["lead_a"].id,
        broker=broker_a,
        top_k=5
    )
    # prop_1 must not be in returned items
    matched_ids = [item.property_id for item in res.items]
    assert str(seed_data["prop_1"].id) not in matched_ids


@pytest.mark.asyncio
async def test_integration_side_by_side_property_comparison(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Comparison matrix evaluates up to 5 properties side-by-side with match scores."""
    engine = AIPropertyMatchingEngine(db=db_session)
    prop_ids = [str(seed_data["prop_1"].id), str(seed_data["prop_2"].id)]
    comp = await engine.compare_properties(
        property_ids=prop_ids,
        broker=broker_a,
        lead_id=str(seed_data["lead_a"].id)
    )
    assert comp["status"] == "success"
    assert comp["property_count"] == 2
    assert len(comp["properties"]) == 2
    assert comp["properties"][0]["match_score"] is not None


@pytest.mark.asyncio
async def test_integration_comparison_tenant_isolation(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Cannot compare properties belonging to another broker's tenant."""
    engine = AIPropertyMatchingEngine(db=db_session)
    foreign_id = str(seed_data["prop_b"].id)
    with pytest.raises(Exception) as exc:
        await engine.compare_properties(
            property_ids=[foreign_id],
            broker=broker_a
        )
    assert "404" in str(exc.value) or "not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_integration_pagination_limit_and_offset(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Validates limit and offset pagination."""
    engine = AIPropertyMatchingEngine(db=db_session)
    res_page1 = await engine.match_properties_for_lead(
        lead_id=seed_data["lead_a"].id,
        broker=broker_a,
        limit=1,
        offset=0
    )
    assert len(res_page1.items) <= 1

    res_page2 = await engine.match_properties_for_lead(
        lead_id=seed_data["lead_a"].id,
        broker=broker_a,
        limit=1,
        offset=1
    )
    if res_page1.items and res_page2.items:
        assert res_page1.items[0].property_id != res_page2.items[0].property_id


@pytest.mark.asyncio
async def test_integration_property_type_filtering(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Filtering by property_type='villa' returns only villa listings."""
    engine = AIPropertyMatchingEngine(db=db_session)
    res = await engine.match_properties_for_lead(
        lead_id=seed_data["lead_a"].id,
        broker=broker_a,
        property_type="villa",
        top_k=5,
        allow_alternatives=True
    )
    for item in res.items:
        assert "villa" in item.title.lower() or item.property_id == str(seed_data["prop_3"].id)


@pytest.mark.asyncio
async def test_integration_location_filtering(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Filtering by location='Whitefield' returns only properties in Whitefield."""
    engine = AIPropertyMatchingEngine(db=db_session)
    res = await engine.match_properties_for_lead(
        lead_id=seed_data["lead_a"].id,
        broker=broker_a,
        location="Whitefield",
        top_k=5
    )
    for item in res.items:
        assert "whitefield" in (item.locality or "").lower()


@pytest.mark.asyncio
async def test_integration_sorting_by_price(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Verifies sorting by price_asc."""
    engine = AIPropertyMatchingEngine(db=db_session)
    res = await engine.match_properties_for_lead(
        lead_id=seed_data["lead_a"].id,
        broker=broker_a,
        sort="price_asc",
        top_k=5,
        allow_alternatives=True
    )
    prices = [item.price for item in res.items]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_integration_concurrency_idempotent_shortlist(db_session: AsyncSession, broker_a: Broker, seed_data):
    """Multiple concurrent or repeated shortlist calls do not duplicate records."""
    engine = AIPropertyMatchingEngine(db=db_session)
    dto = ShortlistRequestDTO(
        lead_id=str(seed_data["lead_a"].id),
        property_id=str(seed_data["prop_1"].id),
    )
    # Execute consecutively
    await engine.shortlist_property_for_lead(seed_data["lead_a"].id, seed_data["prop_1"].id, broker_a, dto)
    await engine.shortlist_property_for_lead(seed_data["lead_a"].id, seed_data["prop_1"].id, broker_a, dto)

    stmt = select(LeadPropertyInterest).where(
        and_(
            LeadPropertyInterest.lead_id == seed_data["lead_a"].id,
            LeadPropertyInterest.property_id == seed_data["prop_1"].id
        )
    )
    interests = list((await db_session.execute(stmt)).scalars().all())
    assert len(interests) == 1
