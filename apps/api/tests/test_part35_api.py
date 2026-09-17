"""
Part 35 — API Test Suite: AI Real Estate Revenue Autopilot Endpoints
====================================================================
Comprehensive API endpoint verification for:
1. GET  /api/v1/revenue/action-queue (The Action Queue / "DO THIS NOW")
2. GET  /api/v1/revenue/opportunities (List with pagination, priority/status filters)
3. GET  /api/v1/revenue/opportunities/{id} (Detail view)
4. GET  /api/v1/revenue/opportunities/{id} (404 Not Found)
5. POST /api/v1/revenue/opportunities/{id}/action (Execute Action: CALL_LEAD)
6. POST /api/v1/revenue/opportunities/{id}/dismiss (Dismiss Opportunity)
7. POST /api/v1/revenue/opportunities/{id}/feedback (Record Agent Feedback)
8. POST /api/v1/revenue/opportunities/{id}/complete (Complete Opportunity)
9. GET  /api/v1/revenue/opportunities/{id}/outreach (Generate Call Brief & Email Draft)
10. GET  /api/v1/revenue/demand-intelligence (Demand vs Supply Gap Breakdown)
11. GET  /api/v1/revenue/briefing (Daily Revenue Briefing)
12. POST /api/v1/revenue/evaluate (On-Demand Opportunity Re-evaluation)
"""
import uuid
from datetime import datetime, timezone, timedelta
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
async def seed_data(db_session: AsyncSession, broker: Broker):
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Sunil Mehra",
        phone="+919876543210",
        budget_min=12000000,
        budget_max=16000000,
        preferred_locations=["Sector 150"],
        property_type="3bhk",
        transaction_type="buy",
        status="active",
        last_message_at=now - timedelta(hours=2),
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="ATS Pristine 3BHK",
        description="Luxury 3BHK high-rise apartment in Sector 150.",
        area_value=1750.0,
        price=14500000.0,
        status="available",
        transaction_category="resale",
        locality="Sector 150",
        city="Noida",
        bedrooms=3,
        created_at=now,
    )
    opp = RevenueOpportunity(
        id=uuid.uuid4(),
        organization_id=broker.id,
        broker_id=broker.id,
        lead_id=lead.id,
        property_id=prop.id,
        assigned_agent_id=broker.id,
        opportunity_type="NEW_HIGH_VALUE_MATCH",
        priority="HIGH",
        urgency="HIGH",
        opportunity_score=89.0,
        match_score=94.0,
        confidence=0.92,
        status="RECOMMENDED",
        reason="Budget and location match live inventory",
        why_now="Active buyer inquiry received today",
        why_property="Matches 3BHK requirement in Sector 150",
        risk_of_inactivity="Buyer is evaluating other listings",
        recommended_action="CALL_LEAD",
        recommended_channel="CALL",
        recommended_property_snapshot={
            "property_id": str(prop.id),
            "title": prop.title,
            "price": prop.price,
            "locality": prop.locality,
            "bedrooms": prop.bedrooms,
        },
        alternative_properties=[],
        positive_signals=["Budget matches", "Location matches Sector 150"],
        negative_signals=[],
        data_freshness={"lead_activity": "2 hours ago"},
        dedup_key=f"{broker.id}:{lead.id}:{prop.id}:NEW_HIGH_VALUE_MATCH",
        scoring_version="v1",
    )
    db_session.add_all([lead, prop, opp])
    await db_session.commit()
    return {"lead": lead, "prop": prop, "opp": opp}


# ── Test 1: Action Queue ("DO THIS NOW") ──────────────────────────────────────
@pytest.mark.asyncio
async def test_api_get_action_queue(db_session: AsyncSession, broker: Broker, seed_data):
    """GET /api/v1/revenue/action-queue returns prioritized actionable queue."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/revenue/action-queue")
        assert res.status_code == 200
        data = res.json()
        assert data["total_count"] >= 1
        assert "items" in data
        first = data["items"][0]
        assert first["id"] == str(seed_data["opp"].id)
        assert first["lead_name"] == "Sunil Mehra"
        assert first["recommended_action"] == "CALL_LEAD"
        assert first["opportunity_score"] == 89.0
        assert data["high_count"] >= 1


# ── Test 2: List Opportunities with Filters ───────────────────────────────────
@pytest.mark.asyncio
async def test_api_list_opportunities_pagination_and_filters(db_session: AsyncSession, broker: Broker, seed_data):
    """GET /api/v1/revenue/opportunities filters by priority and status."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Match filter
        res = await ac.get("/api/v1/revenue/opportunities?status=RECOMMENDED&priority=HIGH")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) >= 1
        assert data["items"][0]["status"] == "RECOMMENDED"

        # Mismatch filter returns 0
        res_empty = await ac.get("/api/v1/revenue/opportunities?status=DISMISSED")
        assert res_empty.status_code == 200
        assert len(res_empty.json()["items"]) == 0


# ── Test 3: Get Opportunity Detail ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_get_opportunity_detail(db_session: AsyncSession, broker: Broker, seed_data):
    """GET /api/v1/revenue/opportunities/{id} returns full opportunity detail."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        opp_id = str(seed_data["opp"].id)
        res = await ac.get(f"/api/v1/revenue/opportunities/{opp_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == opp_id
        assert data["lead_id"] == str(seed_data["lead"].id)
        assert data["property_id"] == str(seed_data["prop"].id)
        assert data["why_now"] == "Active buyer inquiry received today"


# ── Test 4: Get Opportunity 404 Not Found ─────────────────────────────────────
@pytest.mark.asyncio
async def test_api_get_opportunity_not_found(db_session: AsyncSession, broker: Broker):
    """GET /api/v1/revenue/opportunities/{fake_id} returns 404."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    fake_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/revenue/opportunities/{fake_id}")
        assert res.status_code == 404


# ── Test 5: Execute Action ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_execute_action_call_lead(db_session: AsyncSession, broker: Broker, seed_data):
    """POST /api/v1/revenue/opportunities/{id}/action executes action and updates status."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    opp_id = str(seed_data["opp"].id)
    payload = {
        "action_type": "CALL_LEAD",
        "notes": "Discussed ATS Pristine 3BHK. Client requested brochure.",
        "create_follow_up_task": True,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/revenue/opportunities/{opp_id}/action", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ACTIONED"
        assert data["action_type"] == "CALL_LEAD"


# ── Test 6: Dismiss Opportunity ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_dismiss_opportunity(db_session: AsyncSession, broker: Broker, seed_data):
    """POST /api/v1/revenue/opportunities/{id}/dismiss marks opportunity as DISMISSED."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    opp_id = str(seed_data["opp"].id)
    payload = {"reason": "Already contacted", "notes": "Client spoke with another partner."}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/revenue/opportunities/{opp_id}/dismiss", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "DISMISSED"
        assert data["reason"] == "Already contacted"


# ── Test 7: Submit Feedback ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_submit_feedback(db_session: AsyncSession, broker: Broker, seed_data):
    """POST /api/v1/revenue/opportunities/{id}/feedback logs rating and reason."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    opp_id = str(seed_data["opp"].id)
    payload = {"rating": "YES", "reason": "Accurate recommendation", "actual_outcome": "Site Visit Booked"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/revenue/opportunities/{opp_id}/feedback", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "FEEDBACK_LOGGED"


# ── Test 8: Complete Opportunity ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_complete_opportunity(db_session: AsyncSession, broker: Broker, seed_data):
    """POST /api/v1/revenue/opportunities/{id}/complete transitions to COMPLETED."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    opp_id = str(seed_data["opp"].id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/revenue/opportunities/{opp_id}/complete?outcome=DEAL_WON")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED"


# ── Test 9: Outreach Generation ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_get_outreach_draft(db_session: AsyncSession, broker: Broker, seed_data):
    """GET /api/v1/revenue/opportunities/{id}/outreach generates call brief & email."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    opp_id = str(seed_data["opp"].id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/revenue/opportunities/{opp_id}/outreach")
        assert res.status_code == 200
        data = res.json()
        assert data["opportunity_id"] == opp_id
        assert "call_brief" in data
        assert "email_draft" in data
        assert "ATS Pristine 3BHK" in data["call_brief"].get("objective", "") or "Sunil" in data["call_brief"].get("lead_name", "")


# ── Test 10: Demand Gap Intelligence ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_get_demand_intelligence(db_session: AsyncSession, broker: Broker, seed_data):
    """GET /api/v1/revenue/demand-intelligence returns demand vs supply breakdown."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/revenue/demand-intelligence")
        assert res.status_code == 200
        data = res.json()
        assert "total_active_buyers" in data
        assert "total_available_listings" in data
        assert "top_demand_gaps" in data


# ── Test 11: Revenue Briefing ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_get_briefing(db_session: AsyncSession, broker: Broker, seed_data):
    """GET /api/v1/revenue/briefing returns comprehensive executive briefing."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/revenue/briefing")
        assert res.status_code == 200
        data = res.json()
        assert "greeting" in data
        assert "headline" in data
        assert "immediate_actions_count" in data
        assert "top_recommendation_text" in data
        assert "evidence_points" in data


# ── Test 12: On-Demand Evaluation ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_evaluate_opportunities(db_session: AsyncSession, broker: Broker, seed_data):
    """POST /api/v1/revenue/evaluate triggers opportunity scanning."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/revenue/evaluate")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "evaluated_opportunities_count" in data

