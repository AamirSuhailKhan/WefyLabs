"""
PART 31 — API Test Suite: Customer Onboarding, Tenant Activation & Demo Mode
=============================================================================
16 comprehensive FastAPI endpoint tests covering:
- GET  /api/v1/onboarding/status
- POST /api/v1/onboarding/step (complete action)
- POST /api/v1/onboarding/step (skip action)
- POST /api/v1/onboarding/business-profile
- GET  /api/v1/onboarding/activation
- POST /api/v1/onboarding/demo/start
- POST /api/v1/onboarding/demo/reset
- POST /api/v1/onboarding/demo/reset (404 error state)
- POST /api/v1/onboarding/import/preview (leads)
- POST /api/v1/onboarding/import/preview (properties)
- POST /api/v1/onboarding/import/preview (empty error handling)
- POST /api/v1/onboarding/import/commit (leads)
- POST /api/v1/onboarding/import/commit (properties)
- POST /api/v1/onboarding/invite-team
- 401 Unauthorized protection on private onboarding endpoints
- Multi-tenant tenant ID isolation at REST API layer
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
from app.models.organization import Organization, OrganizationMember

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
async def mock_broker(db_session: AsyncSession):
    b_id = uuid.uuid4()
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name="Prestige Real Estate Agency",
        slug=f"org-{b_id.hex[:6]}",
        plan="pro",
        country_code="IN",
        currency_code="INR",
        default_timezone="Asia/Kolkata",
        business_type="agency"
    )
    db_session.add(org)

    broker = Broker(
        id=b_id,
        email=f"agent_{b_id.hex[:6]}@prestige.com",
        name="Prestige Agent",
        agency_name="Prestige Real Estate Agency",
        city="Bengaluru",
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(broker)

    member = OrganizationMember(
        organization_id=org_id,
        broker_id=b_id,
        role="owner"
    )
    db_session.add(member)
    await db_session.flush()
    return broker


@pytest_asyncio.fixture
async def mock_broker_second(db_session: AsyncSession):
    b_id = uuid.uuid4()
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name="Second Agency",
        slug=f"org-2-{b_id.hex[:6]}",
        plan="pro",
        country_code="IN"
    )
    db_session.add(org)

    broker = Broker(
        id=b_id,
        email=f"agent2_{b_id.hex[:6]}@second.com",
        name="Second Agent",
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(broker)

    member = OrganizationMember(organization_id=org_id, broker_id=b_id, role="owner")
    db_session.add(member)
    await db_session.flush()
    return broker


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_broker: Broker):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: mock_broker
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ─── 1. Status & Progression Endpoints ────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_get_onboarding_status(client: AsyncClient):
    res = await client.get("/api/v1/onboarding/status")
    assert res.status_code == 200
    data = res.json()
    assert "current_step" in data
    assert "progress_percentage" in data
    assert "checklist" in data
    assert len(data["checklist"]) == 8


@pytest.mark.asyncio
async def test_api_update_step_complete(client: AsyncClient):
    payload = {
        "step": "DATA_SOURCE",
        "action": "complete",
        "payload": {"preference": "csv"}
    }
    res = await client.post("/api/v1/onboarding/step", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "DATA_SOURCE" in data["completed_steps"]
    assert data["current_step"] == "PROPERTY_SETUP"


@pytest.mark.asyncio
async def test_api_update_step_skip(client: AsyncClient):
    payload = {
        "step": "CALENDAR_CONNECT",
        "action": "skip"
    }
    res = await client.post("/api/v1/onboarding/step", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "CALENDAR_CONNECT" in data["skipped_steps"]


@pytest.mark.asyncio
async def test_api_update_business_profile(client: AsyncClient):
    payload = {
        "agency_name": "Apex Prime Realty",
        "business_type": "brokerage",
        "city": "Bengaluru",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
        "currency_code": "INR",
        "team_size": "6-20",
        "primary_business_model": "residential_sales"
    }
    res = await client.post("/api/v1/onboarding/business-profile", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "ORGANIZATION_SETUP" in data["completed_steps"]


@pytest.mark.asyncio
async def test_api_get_activation_status(client: AsyncClient):
    res = await client.get("/api/v1/onboarding/activation")
    assert res.status_code == 200
    data = res.json()
    assert "activation_score" in data
    assert "completed_milestones" in data
    assert "milestone_breakdown" in data
    assert len(data["milestone_breakdown"]) == 5


# ─── 2. Demo Mode Endpoints ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_demo_start(client: AsyncClient):
    payload = {
        "intended_agency_name": "API Test Demo Agency",
        "operating_city": "Bengaluru"
    }
    res = await client.post("/api/v1/onboarding/demo/start", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "session_token" in data
    assert data["seeded_properties_count"] == 10
    assert data["seeded_leads_count"] == 8
    assert "Demo Mode" in data["banner_message"]


@pytest.mark.asyncio
async def test_api_demo_reset(client: AsyncClient):
    # Start a demo session first
    start_res = await client.post("/api/v1/onboarding/demo/start", json={"operating_city": "Mumbai"})
    token = start_res.json()["session_token"]

    # Reset/purge the demo session
    reset_res = await client.post(f"/api/v1/onboarding/demo/reset?session_token={token}")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "success"


@pytest.mark.asyncio
async def test_api_demo_reset_404_on_invalid_token(client: AsyncClient):
    res = await client.post("/api/v1/onboarding/demo/reset?session_token=nonexistent_token_12345")
    assert res.status_code == 404


# ─── 3. CSV Import Endpoints ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_csv_preview_leads(client: AsyncClient):
    raw_csv = """name,phone,budget_max,property_type
Siddharth Malhotra,+919876543201,25000000,apartment
Kiara Advani,+919876543202,30000000,villa"""

    res = await client.post(
        "/api/v1/onboarding/import/preview?entity_type=leads",
        content=raw_csv,
        headers={"Content-Type": "text/plain"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_rows"] == 2
    assert data["valid_rows_count"] == 2
    assert data["duplicate_rows_count"] == 0


@pytest.mark.asyncio
async def test_api_csv_preview_properties(client: AsyncClient):
    raw_csv = """title,price,bedrooms,bathrooms,city
Indiranagar 3BHK Penthouse,35000000,3,3,Bengaluru"""

    res = await client.post(
        "/api/v1/onboarding/import/preview?entity_type=properties",
        content=raw_csv,
        headers={"Content-Type": "text/plain"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid_rows_count"] == 1


@pytest.mark.asyncio
async def test_api_csv_preview_empty_handling(client: AsyncClient):
    res = await client.post(
        "/api/v1/onboarding/import/preview?entity_type=leads",
        content="",
        headers={"Content-Type": "text/plain"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_rows"] == 0
    assert "CSV content is empty." in data["validation_errors"]


@pytest.mark.asyncio
async def test_api_csv_commit_leads(client: AsyncClient):
    payload = {
        "entity_type": "leads",
        "items": [
            {
                "name": "Ranveer Singh",
                "phone": "+919811122233",
                "budget_min": 15000000,
                "budget_max": 25000000,
                "property_type": "apartment"
            }
        ]
    }
    res = await client.post("/api/v1/onboarding/import/commit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1


@pytest.mark.asyncio
async def test_api_csv_commit_properties(client: AsyncClient):
    payload = {
        "entity_type": "properties",
        "items": [
            {
                "title": "DLF Phase 5 Luxury 4BHK",
                "price": 45000000.0,
                "bedrooms": 4,
                "bathrooms": 4,
                "city": "Gurugram"
            }
        ]
    }
    res = await client.post("/api/v1/onboarding/import/commit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1


# ─── 4. Team Invite & Auth Security Endpoints ─────────────────────────────────

@pytest.mark.asyncio
async def test_api_invite_team_member(client: AsyncClient):
    payload = {
        "email": "coagent@prestige.com",
        "role": "agent"
    }
    res = await client.post("/api/v1/onboarding/invite-team", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "coagent@prestige.com" in data["message"]


@pytest.mark.asyncio
async def test_api_unauthorized_access_fails():
    # Fresh client without auth overrides
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as unauth_client:
        res = await unauth_client.get("/api/v1/onboarding/status")
        assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_api_multi_tenant_isolation(
    db_session: AsyncSession,
    mock_broker: Broker,
    mock_broker_second: Broker
):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    # Call as Broker 1
    app.dependency_overrides[get_current_broker] = lambda: mock_broker
    async with AsyncClient(transport=transport, base_url="http://test") as c1:
        res1 = await c1.get("/api/v1/onboarding/status")
        data1 = res1.json()

    # Call as Broker 2
    app.dependency_overrides[get_current_broker] = lambda: mock_broker_second
    async with AsyncClient(transport=transport, base_url="http://test") as c2:
        res2 = await c2.get("/api/v1/onboarding/status")
        data2 = res2.json()

    assert data1["organization_id"] != data2["organization_id"]
    assert data1["broker_id"] == str(mock_broker.id)
    assert data2["broker_id"] == str(mock_broker_second.id)
