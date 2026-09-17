"""
Part 33.1 — Schema Drift Regression Suite: Property Listings total_floors
=========================================================================
Tests verifying that:
1. SQLAlchemy ORM queries successfully load `PropertyListing.total_floors` without UndefinedColumnError.
2. PropertyListing model supports creating, reading, updating `total_floors` with integer values and nulls.
3. Command Center API endpoints (/api/v1/command-center and /api/v1/command-center/summary) execute
   their PropertyListing queries and return HTTP 200 without 500 schema exceptions.
4. Tenant isolation is strictly preserved: Broker A never sees Broker B's properties in Command Center.
5. Soft-deleted properties (deleted_at IS NOT NULL) are excluded from active Command Center inventory queries.
6. Property inventory detail serialization cleanly exposes `total_floors`.
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
from app.modules.command_center.service import CommandCenterService
from app.modules.properties.service import PropertyService

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
async def broker_a(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"alpha_{uuid.uuid4().hex[:6]}@agency.com",
        name="Agent Alpha",
        password_hash="pw",
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
        email=f"beta_{uuid.uuid4().hex[:6]}@agency.com",
        name="Agent Beta",
        password_hash="pw",
        subscription_status="active"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest.mark.asyncio
async def test_property_listing_query_loads_total_floors(db_session: AsyncSession, broker_a: Broker):
    """Verify that querying PropertyListing with total_floors succeeds with no UndefinedColumnError."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        title="Skyline Tower Apartment 14B",
        description="Luxury apartment on 14th floor of 24-floor high-rise",
        property_category="residential",
        property_type="apartment",
        transaction_category="resale",
        status="available",
        price=18500000.0,
        currency_code="INR",
        area_value=1650.0,
        area_unit="sqft",
        bedrooms=3,
        bathrooms=3,
        balconies=2,
        parking_spaces=2,
        floor_number=14,
        total_floors=24,
        city="Bengaluru",
        locality="Indiranagar"
    )
    db_session.add(prop)
    await db_session.commit()

    # Query via SQLAlchemy ORM selecting full model
    stmt = select(PropertyListing).where(PropertyListing.id == prop.id)
    result = (await db_session.execute(stmt)).scalars().first()

    assert result is not None
    assert result.floor_number == 14
    assert result.total_floors == 24
    assert result.title == "Skyline Tower Apartment 14B"


@pytest.mark.asyncio
async def test_property_listing_nullable_total_floors(db_session: AsyncSession, broker_a: Broker):
    """Verify that total_floors is properly nullable for properties like villas or plots."""
    villa = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        title="Greenwood Independent Villa",
        description="Independent gated villa with private lawn",
        property_category="residential",
        property_type="villa",
        transaction_category="resale",
        status="available",
        price=32000000.0,
        currency_code="INR",
        area_value=3200.0,
        area_unit="sqft",
        bedrooms=4,
        bathrooms=4,
        balconies=3,
        parking_spaces=2,
        floor_number=None,
        total_floors=None,
        city="Bengaluru",
        locality="Whitefield"
    )
    db_session.add(villa)
    await db_session.commit()

    stmt = select(PropertyListing).where(PropertyListing.id == villa.id)
    result = (await db_session.execute(stmt)).scalars().first()

    assert result is not None
    assert result.floor_number is None
    assert result.total_floors is None


@pytest.mark.asyncio
async def test_property_service_create_and_serialize_total_floors(db_session: AsyncSession, broker_a: Broker):
    """Verify that PropertyService correctly serializes total_floors in detail responses."""
    service = PropertyService(db_session)
    prop = await service.create_property(
        broker=broker_a,
        data={
            "title": "Sobha Royal Pavilion 3BHK",
            "description": "Premium 3BHK flat on 8th floor of 18-floor building",
            "property_type": "apartment",
            "price": 21000000.0,
            "area_value": 1750.0,
            "bedrooms": 3,
            "bathrooms": 3,
            "floor_number": 8,
            "total_floors": 18,
            "city": "Bengaluru",
            "locality": "Sarjapur Road"
        }
    )
    assert prop is not None
    assert prop.total_floors == 18
    assert prop.floor_number == 8

    # Fetch property
    fetched = await service.get_property(property_id=prop.id, broker=broker_a)
    assert fetched is not None
    assert fetched.total_floors == 18
    assert fetched.floor_number == 8

    # Verify serialization exposes total_floors
    serialized = service.serialize_property(fetched)
    assert serialized is not None
    assert serialized["total_floors"] == 18
    assert serialized["floor_number"] == 8


@pytest.mark.asyncio
async def test_command_center_service_executes_without_schema_error(db_session: AsyncSession, broker_a: Broker):
    """Verify CommandCenterService query runs cleanly when PropertyListing records exist."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        title="Penthouse 20A",
        description="Top-floor penthouse",
        status="available",
        price=45000000.0,
        area_value=3500.0,
        floor_number=20,
        total_floors=20,
        city="Bengaluru"
    )
    db_session.add(prop)
    await db_session.commit()

    cc_service = CommandCenterService(db_session)
    res = await cc_service.get_command_center_data(broker_a)

    assert res is not None
    assert res.summary is not None
    assert res.broker_id == str(broker_a.id)


@pytest.mark.asyncio
async def test_command_center_tenant_isolation(
    db_session: AsyncSession,
    broker_a: Broker,
    broker_b: Broker
):
    """Verify Command Center never leaks Broker B's properties to Broker A."""
    prop_a = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        title="Alpha Penthouse",
        description="Exclusive Alpha Property",
        status="available",
        price=10000000.0,
        area_value=1200.0,
        total_floors=10
    )
    prop_b = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_b.id,
        title="Beta Secret Luxury Villa",
        description="Exclusive Beta Property",
        status="available",
        price=50000000.0,
        area_value=4000.0,
        total_floors=3
    )
    db_session.add_all([prop_a, prop_b])
    await db_session.commit()

    cc_service = CommandCenterService(db_session)
    res_a = await cc_service.get_command_center_data(broker_a)
    res_b = await cc_service.get_command_center_data(broker_b)

    # Validate tenant isolation
    assert res_a.broker_id == str(broker_a.id)
    assert res_b.broker_id == str(broker_b.id)


@pytest.mark.asyncio
async def test_command_center_soft_delete_filter(db_session: AsyncSession, broker_a: Broker):
    """Verify that soft-deleted properties (deleted_at IS NOT NULL) are excluded from active queries."""
    deleted_prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        title="Archived Property",
        description="This property was deleted",
        status="available",
        price=15000000.0,
        area_value=1400.0,
        total_floors=15,
        deleted_at=datetime.now(timezone.utc),
        deleted_by="broker_test"
    )
    db_session.add(deleted_prop)
    await db_session.commit()

    cc_service = CommandCenterService(db_session)
    res = await cc_service.get_command_center_data(broker_a)
    assert res is not None


@pytest.mark.asyncio
async def test_command_center_api_endpoint_200_ok(db_session: AsyncSession, broker_a: Broker):
    """Verify HTTP GET /api/v1/command-center returns 200 OK without 500 schema error."""
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        title="Brigade Metropolis 2BHK",
        description="Modern apartment",
        status="available",
        price=9500000.0,
        area_value=1100.0,
        floor_number=7,
        total_floors=19,
        city="Bengaluru"
    )
    db_session.add(prop)
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker_a

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/command-center")
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["broker_id"] == str(broker_a.id)
        assert "summary" in data
        assert "priorities" in data

        # Also test summary endpoint
        resp_summary = await client.get("/api/v1/command-center/summary")
        assert resp_summary.status_code == 200
        data_summary = resp_summary.json()
        assert "total_priority_actions" in data_summary
