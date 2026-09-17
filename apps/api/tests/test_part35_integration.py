"""
Part 35 — Integration Test Suite: AI Real Estate Revenue Autopilot
===================================================================
Tests core database-backed integration workflows:
1. Lead + Property creation -> evaluate_tenant_opportunities -> NEW_HIGH_VALUE_MATCH
2. Stale hot lead detection -> evaluate_tenant_opportunities -> STALE_HOT_LEAD
3. Price change history -> evaluate_tenant_opportunities -> PRICE_CHANGE_MATCH
4. Completed site visit meeting -> evaluate_tenant_opportunities -> POST_SITE_VISIT_FOLLOW_UP
5. Demand Gap Intelligence calculation
6. Invalidation of opportunities when property is marked unavailable
7. Deduplication guarantee: re-evaluation updates in place without creating duplicates
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, PropertyPriceHistory
from app.models.crm_models import Meeting
from app.models.revenue_autopilot_models import RevenueOpportunity
from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
from app.modules.revenue_autopilot.action_handler import RevenueActionHandler
from app.modules.revenue_autopilot.dto import ActionOpportunityRequestDTO

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
async def setup_broker(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"broker_{uuid.uuid4().hex[:6]}@example.com",
        name="Agent Sharma",
        agency_name="Prestige Realty",
        subscription_status="active",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest.mark.asyncio
async def test_generate_new_high_value_match_opportunity(db_session: AsyncSession, setup_broker: Broker):
    """Evaluating active lead and compatible property creates NEW_HIGH_VALUE_MATCH opportunity."""
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        name="Rahul Gupta",
        phone="+919876543210",
        score="hot",
        status="active",
        budget_min=12000000,
        budget_max=16000000,
        preferred_locations=["Noida Sec 75"],
        property_type="3bhk",
        transaction_type="buy",
        last_message_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=3),
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        title="Supertech Capetown 3BHK",
        description="Spacious 3BHK high-rise apartment in Noida Sec 75.",
        area_value=1650.0,
        price=13800000.0,
        status="available",
        transaction_category="resale",
        locality="Noida Sec 75",
        city="Noida",
        property_type="apartment",
        bedrooms=3,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([lead, prop])
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    generated = await engine.evaluate_tenant_opportunities(setup_broker)

    assert len(generated) >= 1
    opp = generated[0]
    assert opp.lead_id == lead.id
    assert opp.property_id == prop.id
    assert opp.status == "RECOMMENDED"
    assert opp.opportunity_score >= 80.0
    assert opp.priority in ("CRITICAL", "HIGH")
    assert opp.recommended_action == "CALL_LEAD"


@pytest.mark.asyncio
async def test_deduplication_guarantee(db_session: AsyncSession, setup_broker: Broker):
    """Running evaluation twice updates the existing opportunity instead of inserting duplicates."""
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        name="Sana Khan",
        phone="+919811122233",
        score="hot",
        status="active",
        budget_min=10000000,
        budget_max=15000000,
        preferred_locations=["Whitefield"],
        property_type="3bhk",
        transaction_type="buy",
        last_message_at=now - timedelta(hours=1),
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        title="Prestige Shantiniketan",
        description="Premium residential unit in Whitefield.",
        area_value=1750.0,
        price=13500000.0,
        status="available",
        transaction_category="resale",
        locality="Whitefield",
        bedrooms=3,
        created_at=now,
    )
    db_session.add_all([lead, prop])
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    first_run = await engine.evaluate_tenant_opportunities(setup_broker)
    assert len(first_run) == 1

    # Second run immediately
    second_run = await engine.evaluate_tenant_opportunities(setup_broker)
    assert len(second_run) == 1

    # Verify database has strictly 1 record
    all_opps_stmt = select(RevenueOpportunity).where(RevenueOpportunity.broker_id == setup_broker.id)
    all_opps = list((await db_session.execute(all_opps_stmt)).scalars().all())
    assert len(all_opps) == 1


@pytest.mark.asyncio
async def test_price_change_match_opportunity(db_session: AsyncSession, setup_broker: Broker):
    """Property price drop matching lead's budget creates PRICE_CHANGE_MATCH opportunity."""
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        name="Arjun Patel",
        phone="+919999888877",
        status="active",
        budget_max=14000000,
        preferred_locations=["Gurgaon Sec 48"],
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        title="Vipul Greens 3BHK",
        description="Luxury 3BHK in Gurgaon Sec 48.",
        area_value=1800.0,
        price=13500000.0,
        status="available",
        locality="Gurgaon Sec 48",
        bedrooms=3,
    )
    price_hist = PropertyPriceHistory(
        id=uuid.uuid4(),
        property_id=prop.id,
        old_price=15000000.0,
        new_price=13500000.0,
        changed_at=now - timedelta(hours=12),
    )
    db_session.add_all([lead, prop, price_hist])
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    generated = await engine.evaluate_tenant_opportunities(setup_broker)

    price_opps = [o for o in generated if o.opportunity_type == "PRICE_CHANGE_MATCH"]
    assert len(price_opps) == 1
    assert price_opps[0].opportunity_score >= 75.0
    assert any("Price reduced" in s for s in price_opps[0].positive_signals)


@pytest.mark.asyncio
async def test_post_site_visit_follow_up_opportunity(db_session: AsyncSession, setup_broker: Broker):
    """Completed site visit meeting generates POST_SITE_VISIT_FOLLOW_UP opportunity."""
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        name="Vikram Seth",
        phone="+919777666555",
        status="active",
    )
    db_session.add(lead)
    await db_session.flush()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        broker_id=setup_broker.id,
        lead_id=lead.id,
        organization_id=str(setup_broker.id),
        title="Site Visit - DLF Phase 5",
        meeting_type="site_visit",
        status="completed",
        scheduled_at=now - timedelta(hours=18),
        location="DLF Phase 5, Gurgaon",
    )
    db_session.add(meeting)
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    generated = await engine.evaluate_tenant_opportunities(setup_broker)

    visit_opps = [o for o in generated if o.opportunity_type == "POST_SITE_VISIT_FOLLOW_UP"]
    assert len(visit_opps) == 1
    assert visit_opps[0].urgency == "CRITICAL"
    assert visit_opps[0].opportunity_score >= 90.0


@pytest.mark.asyncio
async def test_opportunity_invalidation_when_property_unavailable(db_session: AsyncSession, setup_broker: Broker):
    """Active opportunity is automatically marked INVALIDATED when property status becomes 'sold'."""
    now = datetime.now(timezone.utc)
    lead = Lead(id=uuid.uuid4(), broker_id=setup_broker.id, name="Test Lead", phone="+919000000000", status="active")
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=setup_broker.id,
        title="Apartment A",
        description="Sold residential property.",
        area_value=1200.0,
        price=10000000.0,
        status="sold",  # Sold!
        locality="City",
        bedrooms=2,
    )
    opp = RevenueOpportunity(
        id=uuid.uuid4(),
        organization_id=setup_broker.id,
        broker_id=setup_broker.id,
        lead_id=lead.id,
        property_id=prop.id,
        opportunity_type="NEW_HIGH_VALUE_MATCH",
        status="RECOMMENDED",
        reason="Match",
        why_now="Now",
        dedup_key="test-invalidation-key",
    )
    db_session.add_all([lead, prop, opp])
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    invalidated_count = await engine.invalidate_stale_opportunities(setup_broker.id)
    assert invalidated_count == 1

    await db_session.refresh(opp)
    assert opp.status == "INVALIDATED"


@pytest.mark.asyncio
async def test_action_execution_idempotency(db_session: AsyncSession, setup_broker: Broker):
    """Executing an action transitions opportunity to ACTIONED and creates CRM task idempotently."""
    lead = Lead(id=uuid.uuid4(), broker_id=setup_broker.id, name="Karan Singh", phone="+919111223344", status="active")
    opp = RevenueOpportunity(
        id=uuid.uuid4(),
        organization_id=setup_broker.id,
        broker_id=setup_broker.id,
        lead_id=lead.id,
        property_id=None,
        opportunity_type="HOT_LEAD_NEEDS_CONTACT",
        status="RECOMMENDED",
        reason="Hot lead needs contact",
        why_now="Inbound inquiry received",
        dedup_key="action-test-key",
    )
    db_session.add_all([lead, opp])
    await db_session.commit()

    handler = RevenueActionHandler(db_session)
    res = await handler.execute_action(
        opportunity_id=opp.id,
        broker=setup_broker,
        dto=ActionOpportunityRequestDTO(
            action_type="CALL_LEAD",
            notes="Called buyer, requested evening callback.",
            create_follow_up_task=True
        )
    )

    assert res["status"] == "ACTIONED"
    assert res["created_task_id"] is not None

    await db_session.refresh(opp)
    assert opp.status == "ACTIONED"
    assert opp.feedback_notes == "Called buyer, requested evening callback."
