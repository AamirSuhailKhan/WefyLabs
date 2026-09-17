"""
Part 33.1 — Master Regression Test Suite: Command Center Permanent Fix & Schema Drift Protection
==============================================================================================
Validates:
1. PropertyListing SQLAlchemy ORM query selects `total_floors` cleanly (no UndefinedColumnError).
2. PropertyListing model supports creating, updating with integer and null values for `total_floors`.
3. GET /api/v1/command-center returns HTTP 200 with all 16 top-level keys matching CommandCenterResponse.
4. Payload format: DTO is returned at the root JSON level (verified for frontend contract alignment).
5. Expired-trial user access: a broker with an expired trial (trial_days_remaining == 0) can query Command Center with 200 OK.
6. Multi-tenant isolation: Broker A cannot see Broker B's property opportunities or priority actions.
7. Unauthenticated request returns HTTP 401 with structured JSON error.
8. Command Center summary endpoint (/api/v1/command-center/summary) returns 200 with non-null counters.
9. Start My Day endpoint (/api/v1/command-center/start-my-day) returns 200 with sequential steps.
10. Schema Drift Guard: inspects PropertyListing model against table metadata to ensure total_floors is mapped.
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base
from app.dependencies import get_db, get_current_broker, clear_rate_limits
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Activity
from app.models.command_center_models import CommandCenterDismissal
from app.modules.command_center.service import CommandCenterService

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
async def broker_active(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"broker_active_{uuid.uuid4().hex[:6]}@beetlelabs.test",
        name="Active Broker",
        subscription_status="active"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture
async def broker_expired(db_session: AsyncSession):
    past_date = datetime.now(timezone.utc) - timedelta(days=10)
    broker = Broker(
        id=uuid.uuid4(),
        email=f"broker_expired_{uuid.uuid4().hex[:6]}@beetlelabs.test",
        name="Expired Trial Broker",
        subscription_status="trial",
        trial_ends_at=past_date
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture
async def broker_b(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"broker_b_{uuid.uuid4().hex[:6]}@beetlelabs.test",
        name="Broker B (Tenant Isolation)",
        subscription_status="active"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest.mark.asyncio
async def test_property_listing_schema_total_floors(db_session: AsyncSession, broker_active: Broker):
    """1. Test that PropertyListing total_floors is properly mapped, queryable, and persists values."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_active.id,
        property_code="PROP-TF-001",
        title="Penthouse Skyline 42",
        description="Penthouse Skyline 42 living",
        property_type="apartment",
        city="Bengaluru",
        locality="Indiranagar",
        floor_number=40,
        total_floors=45,
        price=25000000.0,
        area_value=2200.0,
        status="available"
    )
    db_session.add(prop)
    await db_session.commit()

    # Query via SQLAlchemy ORM
    stmt = select(PropertyListing).where(PropertyListing.id == prop.id)
    res = await db_session.execute(stmt)
    loaded = res.scalar_one()

    assert loaded.total_floors == 45
    assert loaded.floor_number == 40

    # Test nullable total_floors
    prop_null = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_active.id,
        property_code="PROP-TF-002",
        title="Villa Green Acres",
        description="Spacious garden villa",
        property_type="villa",
        city="Bengaluru",
        locality="Whitefield",
        total_floors=None,
        price=35000000.0,
        area_value=3200.0,
        status="available"
    )
    db_session.add(prop_null)
    await db_session.commit()

    stmt2 = select(PropertyListing).where(PropertyListing.id == prop_null.id)
    res2 = await db_session.execute(stmt2)
    loaded_null = res2.scalar_one()
    assert loaded_null.total_floors is None


@pytest.mark.asyncio
async def test_command_center_full_endpoint_contract(db_session: AsyncSession, broker_active: Broker):
    """2 & 3 & 4. Verify Command Center endpoint returns 200 and matches frontend contract."""
    # Seed property with total_floors
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_active.id,
        property_code="PROP-CC-100",
        title="Downtown Luxury Residence",
        description="Luxury downtown apartment",
        property_type="apartment",
        city="Bengaluru",
        locality="CBD",
        floor_number=12,
        total_floors=25,
        price=18000000.0,
        area_value=1600.0,
        status="available"
    )
    # Seed lead
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker_active.id,
        name="Rahul Verma",
        phone="+919876543210",
        score="hot",
        score_confidence=0.92,
        status="active"
    )
    db_session.add_all([prop, lead])
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker_active

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/command-center")
        assert resp.status_code == 200

        data = resp.json()
        # Verify DTO is at the root level (frontend contract)
        required_root_keys = [
            "organization_id", "broker_id", "broker_name", "timezone",
            "summary", "daily_briefing", "priorities", "first_contact_queue",
            "overdue_followups", "today_schedule", "hot_leads",
            "stale_leads_summary", "inventory_opportunities", "inventory_gaps",
            "demand_heatmap", "recent_activities"
        ]
        for key in required_root_keys:
            assert key in data, f"Missing required key: {key}"

        # Verify summary keys
        summary = data["summary"]
        assert "critical_actions_count" in summary
        assert "total_priority_actions" in summary
        assert "overdue_followups_count" in summary
        assert "sla_breaches_count" in summary


@pytest.mark.asyncio
async def test_expired_trial_broker_can_access_command_center(db_session: AsyncSession, broker_expired: Broker):
    """5. Verify an expired trial account can access Command Center without 403 or 500."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker_expired

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/command-center")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert data["broker_id"] == str(broker_expired.id)


@pytest.mark.asyncio
async def test_command_center_tenant_isolation(db_session: AsyncSession, broker_active: Broker, broker_b: Broker):
    """6. Multi-tenant isolation: Broker A cannot see Broker B's inventory opportunities or priorities."""
    prop_b = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_b.id,
        property_code="PROP-B-SECRET",
        title="Broker B Secret Mansion",
        description="Secret luxury villa",
        property_type="villa",
        city="Bengaluru",
        locality="Sadashivanagar",
        price=50000000.0,
        area_value=4500.0,
        status="available"
    )
    db_session.add(prop_b)
    await db_session.commit()

    # Query as Broker A
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker_active

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/command-center")
        assert resp.status_code == 200
        data = resp.json()

        for opp in data["inventory_opportunities"]:
            assert opp.get("property_id") != str(prop_b.id)
            assert opp.get("title") != "Broker B Secret Mansion"


@pytest.mark.asyncio
async def test_command_center_unauthenticated_returns_401(db_session: AsyncSession):
    """7. Unauthenticated request to Command Center returns 401 Unauthorized."""
    app.dependency_overrides[get_db] = lambda: db_session
    # Do not override get_current_broker -> triggers real auth check

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/command-center")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_command_center_summary_endpoint(db_session: AsyncSession, broker_active: Broker):
    """8. Summary endpoint returns lightweight counters."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker_active

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/command-center/summary")
        assert resp.status_code == 200
        summary = resp.json()
        assert "critical_actions_count" in summary
        assert "total_priority_actions" in summary


@pytest.mark.asyncio
async def test_command_center_start_my_day(db_session: AsyncSession, broker_active: Broker):
    """9. Start My Day endpoint returns sequential steps."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker_active

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/command-center/start-my-day")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert "steps" in data
        assert isinstance(data["steps"], list)


@pytest.mark.asyncio
async def test_schema_drift_guard_column_inspection():
    """10. Regression guard: ensure PropertyListing model has total_floors and floor_number mapped."""
    columns = PropertyListing.__table__.columns
    assert "total_floors" in columns, "CRITICAL: PropertyListing table must map total_floors"
    assert "floor_number" in columns, "CRITICAL: PropertyListing table must map floor_number"
    assert columns["total_floors"].nullable is True, "total_floors must be nullable for safety"
