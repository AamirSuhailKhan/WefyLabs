"""
Part 29 — API Test Suite: AI Lead ↔ Property Matching Engine REST Endpoints
==========================================================================
17 comprehensive API tests covering:
- GET  /api/v1/leads/{lead_id}/property-matches (canonical)
- GET  /api/v1/leads/{lead_id}/matches (alias)
- GET  /api/v1/properties/{property_id}/lead-matches (canonical)
- GET  /api/v1/properties/{property_id}/matches (alias)
- Pagination (limit & offset)
- Filters (minimum_score, property_type, location, sort)
- Alternatives query parameter
- 404 handling for invalid Lead and Property IDs
- POST /api/v1/matches/shortlist
- POST /api/v1/matches/recommend
- POST /api/v1/matches/feedback
- POST /api/v1/matches/compare
- POST /api/v1/matches/extract-requirements
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base
from app.dependencies import get_db, get_current_broker, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing

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
        email=f"api_broker_{uuid.uuid4().hex[:6]}@crm.com",
        name="Vikram Agent",
        subscription_status="active"
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def seed_api_data(db_session: AsyncSession, broker: Broker):
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Sanjay Gupta",
        phone="+919876500099",
        budget_min=7000000,
        budget_max=10000000,
        property_type="3 BHK apartment",
        preferred_locations=["Whitefield"],
        transaction_type="buy",
        status="active"
    )
    prop1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="API-PROP-1",
        title="Brigade Metropolis 3BHK",
        description="Spacious 3BHK in Whitefield",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=9500000.0,
        area_value=1600.0,
        area_unit="sqft",
        bedrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking", "Gym"]
    )
    prop2 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="API-PROP-2",
        title="Godrej Woods 2BHK",
        description="2BHK apartment in Electronic City",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=6500000.0,
        area_value=1100.0,
        area_unit="sqft",
        bedrooms=2,
        locality="Electronic City",
        city="Bengaluru",
        amenities=["Parking"]
    )
    db_session.add_all([lead, prop1, prop2])
    await db_session.commit()

    return {"lead": lead, "prop1": prop1, "prop2": prop2}


# ─── API Tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_get_lead_property_matches_canonical(db_session: AsyncSession, broker: Broker, seed_api_data):
    """GET /api/v1/leads/{id}/property-matches returns 200 with ranked matches."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/property-matches")
        assert res.status_code == 200
        data = res.json()
        assert data["lead_id"] == str(seed_api_data["lead"].id)
        assert len(data["items"]) >= 1
        assert data["items"][0]["property_id"] == str(seed_api_data["prop1"].id)
        assert data["items"][0]["match_score"] >= 80.0


@pytest.mark.asyncio
async def test_api_get_lead_matches_alias(db_session: AsyncSession, broker: Broker, seed_api_data):
    """GET /api/v1/leads/{id}/matches alias endpoint behaves identically."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/matches")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_api_get_property_lead_matches_canonical(db_session: AsyncSession, broker: Broker, seed_api_data):
    """GET /api/v1/properties/{id}/lead-matches returns 200 with qualified buyers."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/properties/{seed_api_data['prop1'].id}/lead-matches")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["lead_id"] == str(seed_api_data["lead"].id)


@pytest.mark.asyncio
async def test_api_get_property_matches_alias(db_session: AsyncSession, broker: Broker, seed_api_data):
    """GET /api/v1/properties/{id}/matches alias returns 200."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/properties/{seed_api_data['prop1'].id}/matches")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_api_lead_matches_pagination_limit_offset(db_session: AsyncSession, broker: Broker, seed_api_data):
    """Passing limit and offset paginates response."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/property-matches?limit=1&offset=0")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) <= 1


@pytest.mark.asyncio
async def test_api_lead_matches_minimum_score_filter(db_session: AsyncSession, broker: Broker, seed_api_data):
    """Passing minimum_score=90 filters out lower score properties."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/property-matches?minimum_score=95")
        assert res.status_code == 200
        data = res.json()
        for item in data["items"]:
            assert item["match_score"] >= 95.0


@pytest.mark.asyncio
async def test_api_lead_matches_property_type_filter(db_session: AsyncSession, broker: Broker, seed_api_data):
    """Passing property_type=apartment returns matching listings."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/property-matches?property_type=apartment")
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_api_lead_matches_location_filter(db_session: AsyncSession, broker: Broker, seed_api_data):
    """Passing location=Whitefield returns matching listings."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/property-matches?location=Whitefield")
        assert res.status_code == 200
        data = res.json()
        for item in data["items"]:
            assert "whitefield" in (item["locality"] or "").lower()


@pytest.mark.asyncio
async def test_api_lead_matches_sort_options(db_session: AsyncSession, broker: Broker, seed_api_data):
    """Passing sort=price_asc sorts results by price."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/property-matches?sort=price_asc&allow_alternatives=true")
        assert res.status_code == 200
        data = res.json()
        prices = [it["price"] for it in data["items"]]
        assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_api_lead_matches_allow_alternatives(db_session: AsyncSession, broker: Broker, seed_api_data):
    """Passing allow_alternatives=true sets recommendation_mode to controlled_alternatives."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{seed_api_data['lead'].id}/property-matches?allow_alternatives=true")
        assert res.status_code == 200
        data = res.json()
        assert data["recommendation_mode"] == "controlled_alternatives"


@pytest.mark.asyncio
async def test_api_lead_matches_404_nonexistent_lead(db_session: AsyncSession, broker: Broker):
    """Non-existent lead ID returns 404."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    fake_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leads/{fake_id}/property-matches")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_property_matches_404_nonexistent_property(db_session: AsyncSession, broker: Broker):
    """Non-existent property ID returns 404."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    fake_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/properties/{fake_id}/lead-matches")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_shortlist_property_endpoint(db_session: AsyncSession, broker: Broker, seed_api_data):
    """POST /api/v1/matches/shortlist shortlists property."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    payload = {
        "lead_id": str(seed_api_data["lead"].id),
        "property_id": str(seed_api_data["prop1"].id),
        "interest_level": "HIGH",
        "notes": "Shortlisted via API"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/matches/shortlist", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["interest_status"] == "SHORTLISTED"


@pytest.mark.asyncio
async def test_api_recommend_property_endpoint(db_session: AsyncSession, broker: Broker, seed_api_data):
    """POST /api/v1/matches/recommend records recommendation and creates task."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    payload = {
        "lead_id": str(seed_api_data["lead"].id),
        "property_id": str(seed_api_data["prop1"].id),
        "notes": "Recommended via API",
        "create_followup_task": True
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/matches/recommend", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"


@pytest.mark.asyncio
async def test_api_record_feedback_endpoint(db_session: AsyncSession, broker: Broker, seed_api_data):
    """POST /api/v1/matches/feedback records agent feedback."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    payload = {
        "lead_id": str(seed_api_data["lead"].id),
        "property_id": str(seed_api_data["prop1"].id),
        "feedback": "good_match",
        "notes": "Client requested brochure"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/matches/feedback", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"


@pytest.mark.asyncio
async def test_api_compare_properties_endpoint(db_session: AsyncSession, broker: Broker, seed_api_data):
    """POST /api/v1/matches/compare compares selected properties side-by-side."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    payload = {
        "property_ids": [str(seed_api_data["prop1"].id), str(seed_api_data["prop2"].id)],
        "lead_id": str(seed_api_data["lead"].id)
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/matches/compare", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert len(data["comparison_matrix"]) == 2


@pytest.mark.asyncio
async def test_api_extract_requirements_endpoint(broker: Broker):
    """POST /api/v1/matches/extract-requirements extracts structured requirements from text."""
    app.dependency_overrides[get_current_broker] = lambda: broker

    payload = {
        "text": "Looking for a 3BHK in Whitefield around 1.2 crore with parking."
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/matches/extract-requirements", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["extracted_requirements"]["bedrooms"] == 3
        assert data["extracted_requirements"]["budget_max"] == 12000000
        assert "Whitefield" in data["extracted_requirements"]["preferred_locations"]
