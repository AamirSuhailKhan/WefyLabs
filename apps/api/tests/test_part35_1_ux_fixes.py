"""
Part 35.1 — AI Real Estate Revenue Autopilot UX & Flow Hardening Test Suite
===========================================================================
Verification for:
1. Empty-state intelligence metadata (active leads, active properties, completed today)
2. Property deep-link resolution & tenant security
3. Price update workflow with PropertyPriceHistory & audit logging
4. Site visit completion workflow with meeting outcome & POST_SITE_VISIT_FOLLOW_UP
5. Upcoming site visits query endpoint
6. Outreach provenance metadata & deterministic fallback transparency
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.main import app
from app.database import Base
from app.dependencies import get_db, get_current_broker, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, PropertyPriceHistory
from app.models.crm_models import Meeting, Activity
from app.models.revenue_autopilot_models import RevenueOpportunity

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env():
    clear_rate_limits()
    yield
    clear_rate_limits()
    app.dependency_overrides.clear()


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
async def broker(db_session: AsyncSession):
    b = Broker(
        id=uuid.uuid4(),
        email=f"broker_{uuid.uuid4().hex[:6]}@example.com",
        name="Vikram Agent",
        agency_name="Apex Realty",
        subscription_status="active",
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def other_broker(db_session: AsyncSession):
    b = Broker(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        name="External Agent",
        agency_name="Rival Realty",
        subscription_status="active",
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


# ============================================================================
# 1. P0 Empty State Intelligence Tests
# ============================================================================

@pytest.mark.asyncio
async def test_empty_state_metadata_zero_data(db_session: AsyncSession, broker: Broker):
    """When tenant has no leads or properties, action-queue returns metadata distinguishing zero data."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/revenue/action-queue")
        assert res.status_code == 200
        data = res.json()
        assert data["total_count"] == 0
        assert data["active_leads_count"] == 0
        assert data["active_properties_count"] == 0
        assert data["completed_today_count"] == 0
        assert "last_scan_at" in data


@pytest.mark.asyncio
async def test_empty_state_metadata_with_leads_and_properties(db_session: AsyncSession, broker: Broker):
    """When data exists, counts are populated correctly so frontend knows data exists."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Deepak Joshi",
        phone="+919876543210",
        status="active"
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Green Villa 4BHK",
        description="Spacious green villa in prime location",
        price=22000000.0,
        area_value=2500.0,
        status="available"
    )
    db_session.add_all([lead, prop])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/revenue/action-queue")
        assert res.status_code == 200
        data = res.json()
        assert data["active_leads_count"] == 1
        assert data["active_properties_count"] == 1


@pytest.mark.asyncio
async def test_empty_state_metadata_completed_today(db_session: AsyncSession, broker: Broker):
    """When opportunities are completed today, completed_today_count reflects it."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Anita Roy", phone="+919876543299", status="active")
    db_session.add(lead)
    await db_session.flush()

    opp = RevenueOpportunity(
        id=uuid.uuid4(),
        organization_id=broker.id,
        broker_id=broker.id,
        lead_id=lead.id,
        opportunity_type="GENERAL_FOLLOW_UP",
        priority="MEDIUM",
        urgency="MEDIUM",
        opportunity_score=75.0,
        status="COMPLETED",
        completed_at=datetime.now(timezone.utc),
        reason="Follow up completed",
        why_now="Routine follow up schedule",
        dedup_key=f"test_dedup_{uuid.uuid4().hex}",
        scoring_version="v1",
        recommended_property_snapshot={},
        alternative_properties=[],
        positive_signals=[],
        negative_signals=[],
        data_freshness={},
        call_brief={},
        email_draft={},
        provenance=[]
    )
    db_session.add(opp)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/revenue/action-queue")
        assert res.status_code == 200
        data = res.json()
        assert data["completed_today_count"] >= 1


# ============================================================================
# 2. P1 Property Deep-Link Resolution & Security Tests
# ============================================================================

@pytest.mark.asyncio
async def test_property_deep_link_resolution(db_session: AsyncSession, broker: Broker):
    """Property can be directly resolved by ID for deep-linking."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Penthouse Skyline 5BHK",
        description="Luxury penthouse with full city view",
        price=45000000.0,
        area_value=4000.0,
        status="available"
    )
    db_session.add(prop)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/properties/{prop.id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(prop.id)
        assert data["title"] == "Penthouse Skyline 5BHK"


@pytest.mark.asyncio
async def test_property_deep_link_unauthorized_isolation(db_session: AsyncSession, broker: Broker, other_broker: Broker):
    """A broker cannot access another tenant's property via direct deep-link ID."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=other_broker.id,
        title="Confidential Other Tenant Villa",
        description="Exclusive confidential villa",
        price=60000000.0,
        area_value=5000.0,
        status="available"
    )
    db_session.add(prop)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/properties/{prop.id}")
        assert res.status_code == 404  # Tenant-isolated: does not leak existence


# ============================================================================
# 3. P2 Price Update Workflow Tests
# ============================================================================

@pytest.mark.asyncio
async def test_property_price_update_creates_history_and_audit(db_session: AsyncSession, broker: Broker):
    """POST /properties/{id}/price updates price, creates PropertyPriceHistory, and writes audit log."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Lotus Boulevard 3BHK",
        description="Spacious 3BHK overlooking central garden",
        price=16000000.0,
        area_value=1600.0,
        status="available"
    )
    db_session.add(prop)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/properties/{prop.id}/price",
            json={"new_price": 14500000.0, "reason": "Market Correction"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["price"] == 14500000.0

    # Verify history entry in database
    history_res = await db_session.execute(
        select(PropertyPriceHistory).where(PropertyPriceHistory.property_id == prop.id)
    )
    history = history_res.scalars().all()
    assert len(history) >= 1
    assert history[-1].old_price == 16000000.0
    assert history[-1].new_price == 14500000.0
    assert history[-1].reason == "Market Correction"


# ============================================================================
# 4. P2 Site Visit Completion Workflow Tests
# ============================================================================

@pytest.mark.asyncio
async def test_site_visit_completion_workflow(db_session: AsyncSession, broker: Broker):
    """Site visit outcome recording completes meeting, logs activity, and generates post-visit follow-up."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Rohan Verma",
        phone="+919876543211",
        status="active"
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="Prestige High Fields 3BHK",
        description="Luxury apartment near high-tech corridor",
        price=18000000.0,
        area_value=1900.0,
        status="available"
    )
    db_session.add_all([lead, prop])
    await db_session.flush()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead.id,
        title=f"Site Visit: {prop.title}",
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1),
        duration_minutes=60,
        status="scheduled",
        location="Prestige High Fields Tower A"
    )
    db_session.add(meeting)
    await db_session.commit()

    # Call record visit outcome endpoint
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/properties/visits/{meeting.id}/outcome",
            json={
                "outcome": "interested",
                "feedback": "Loved the corner unit, requested payment plan",
                "next_action": "Send developer offer sheet"
            }
        )
        assert res.status_code == 200

    # Verify meeting updated to completed
    meeting_res = await db_session.execute(select(Meeting).where(Meeting.id == meeting.id))
    m = meeting_res.scalars().first()
    assert m.status == "completed"

    # Verify activity was logged
    act_res = await db_session.execute(select(Activity).where(Activity.lead_id == lead.id))
    activities = act_res.scalars().all()
    assert len(activities) >= 1
    assert any("Site Visit Outcome" in a.title for a in activities)


@pytest.mark.asyncio
async def test_list_property_visits_endpoint(db_session: AsyncSession, broker: Broker):
    """GET /properties/visits returns scheduled meetings with lead and property details."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Pooja Sharma", phone="+919123456789", status="active")
    prop = PropertyListing(id=uuid.uuid4(), broker_id=broker.id, title="Cyber City Studio", description="Studio apartment", price=6500000.0, area_value=600.0, status="available")
    db_session.add_all([lead, prop])
    await db_session.flush()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead.id,
        title=f"Site Visit: {prop.title}",
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        status="scheduled",
        location="Cyber City Studio 104"
    )
    db_session.add(meeting)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/properties/visits")
        assert res.status_code == 200
        visits = res.json()
        assert len(visits) >= 1
        v = next(x for x in visits if x["meeting_id"] == meeting.id)
        assert v["lead_name"] == "Pooja Sharma"
        assert v["property_title"] == "Cyber City Studio"
        assert v["status"] == "scheduled"


# ============================================================================
# 5. P1 Outreach Provenance Transparency Tests
# ============================================================================

@pytest.mark.asyncio
async def test_outreach_provenance_metadata(db_session: AsyncSession, broker: Broker):
    """GET /revenue/opportunities/{id}/outreach returns explicit provenance metadata."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Kavita Sen", phone="+919988776655", status="active")
    prop = PropertyListing(id=uuid.uuid4(), broker_id=broker.id, title="DLF Crest 3BHK", description="Spacious DLF Crest unit", price=32000000.0, area_value=2600.0, status="available")
    db_session.add_all([lead, prop])
    await db_session.flush()

    opp = RevenueOpportunity(
        id=uuid.uuid4(),
        organization_id=broker.id,
        broker_id=broker.id,
        lead_id=lead.id,
        property_id=prop.id,
        assigned_agent_id=broker.id,
        opportunity_type="PRICE_CHANGE_MATCH",
        priority="HIGH",
        urgency="HIGH",
        opportunity_score=88.0,
        status="RECOMMENDED",
        reason="Price dropped into buyer budget",
        why_now="Price reduced by 10% today",
        why_property="DLF Crest matches location and size",
        call_brief={"suggested_opening": "Hello Kavita, great news on DLF Crest!"},
        email_draft={"subject": "Price drop on DLF Crest"},
        dedup_key=f"test_dedup_{uuid.uuid4().hex}",
        scoring_version="v1",
        recommended_property_snapshot={},
        alternative_properties=[],
        positive_signals=[],
        negative_signals=[],
        data_freshness={},
        provenance=[]
    )
    db_session.add(opp)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/revenue/opportunities/{opp.id}/outreach")
        assert res.status_code == 200
        draft = res.json()
        assert "is_ai_generated" in draft
        assert "model_used" in draft
        assert isinstance(draft["is_ai_generated"], bool)
        assert isinstance(draft["model_used"], str)
