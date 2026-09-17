"""
Part 30 — API Test Suite: AI Real-Estate Agent Daily Command Center REST Endpoints
==================================================================================
16 comprehensive API tests covering:
- GET  /api/v1/command-center (Full command center payload)
- GET  /api/v1/command-center/summary (Overview metrics)
- GET  /api/v1/command-center/priorities (Priority queue with limits)
- GET  /api/v1/command-center/priorities (Filter by priority level)
- GET  /api/v1/command-center/today (Schedule: meetings, site visits, tasks)
- GET  /api/v1/command-center/inventory-intelligence (Demand heatmap, gaps, opportunities)
- GET  /api/v1/command-center/briefing (AI daily briefing synthesis)
- GET  /api/v1/command-center/start-my-day (Interactive queue generation)
- POST /api/v1/command-center/items/dismiss (Dismiss action item)
- POST /api/v1/command-center/items/dismiss (Snooze action item)
- POST /api/v1/command-center/items/dismiss (Validation error on empty item_key)
- Multi-tenant isolation at API level (Broker A vs Broker B)
- Timezone query param handling
- Unauthorized request returns 401
- Empty state: clean broker returns well-formed empty dashboard with 200 OK
- Partial section filtering: priorities entity_type check
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base
from app.dependencies import get_db, get_current_broker, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.crm_models import Task, Meeting, Activity
from app.models.command_center_models import CommandCenterDismissal

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
        email=f"cc_broker_{uuid.uuid4().hex[:6]}@crm.com",
        name="Vikram Command Agent",
        subscription_status="active"
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def other_broker(db_session: AsyncSession):
    b = Broker(
        id=uuid.uuid4(),
        email=f"other_broker_{uuid.uuid4().hex[:6]}@crm.com",
        name="Other Broker",
        subscription_status="active"
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def seed_command_center_data(db_session: AsyncSession, broker: Broker):
    now = datetime.now(timezone.utc)
    
    # 1. SLA overdue lead
    lead1 = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Arjun Verma",
        phone="+919876500011",
        pipeline_stage="new",
        score="hot",
        status="active",
        preferred_locations=["Whitefield"],
        property_type="apartment",
        budget_min=8000000,
        budget_max=12000000,
        created_at=now - timedelta(hours=2),
    )
    
    # 2. Overdue task
    lead2 = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Pooja Sharma",
        phone="+919876500022",
        pipeline_stage="contacted",
        score="warm",
        status="active",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(days=4),
    )
    
    task1 = Task(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead2.id,
        title="Follow up on mortgage documents",
        status="pending",
        due_at=now - timedelta(days=1),
        priority="high",
        created_at=now - timedelta(days=3),
    )
    
    # 3. Today's meeting
    meeting1 = Meeting(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead1.id,
        title="Site visit with Arjun Verma",
        meeting_type="site_visit",
        scheduled_at=now + timedelta(hours=2),
        duration_minutes=60,
        status="scheduled",
        location="Prestige Palms, Whitefield",
    )
    
    # 4. Property Listing
    prop1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="PROP-CC-1",
        title="Luxury 3BHK Whitefield",
        description="Spacious luxury apartment",
        property_type="apartment",
        city="Bengaluru",
        locality="Whitefield",
        bedrooms=3,
        price=11000000.0,
        status="available",
        area_value=1800.0,
        area_unit="sqft",
        created_at=now - timedelta(days=1),
    )
    
    db_session.add_all([lead1, lead2, task1, meeting1, prop1])
    await db_session.commit()
    return {"lead1": lead1, "lead2": lead2, "task1": task1, "meeting1": meeting1, "prop1": prop1}


@pytest.mark.asyncio
async def test_api_command_center_full(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center")
        assert response.status_code == 200
        payload = response.json()
        assert "summary" in payload
        assert "priorities" in payload
        assert "first_contact_queue" in payload
        assert "overdue_followups" in payload
        assert "today_schedule" in payload
        assert "inventory_gaps" in payload
        assert "daily_briefing" in payload


@pytest.mark.asyncio
async def test_api_command_center_summary(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/summary")
        assert response.status_code == 200
        summary = response.json()
        assert summary["total_priority_actions"] >= 1
        assert summary["sla_breaches_count"] >= 1


@pytest.mark.asyncio
async def test_api_command_center_priorities(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/priorities?limit=5")
        assert response.status_code == 200
        priorities = response.json()
        assert isinstance(priorities, list)
        assert len(priorities) <= 5
        assert len(priorities) > 0
        assert priorities[0]["priority"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


@pytest.mark.asyncio
async def test_api_command_center_priorities_filter(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/priorities?priority_filter=CRITICAL")
        assert response.status_code == 200
        priorities = response.json()
        for item in priorities:
            assert item["priority"] == "CRITICAL"


@pytest.mark.asyncio
async def test_api_command_center_today(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/today")
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        assert any("Site visit" in item["title"] for item in items)


@pytest.mark.asyncio
async def test_api_command_center_inventory_intelligence(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/inventory-intelligence")
        assert response.status_code == 200
        intel = response.json()
        assert "demand_heatmap" in intel
        assert "inventory_gaps" in intel
        assert "inventory_opportunities" in intel


@pytest.mark.asyncio
async def test_api_command_center_briefing(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/briefing")
        assert response.status_code == 200
        briefing = response.json()
        assert "briefing_text" in briefing
        assert "highlights" in briefing
        assert "is_ai_generated" in briefing
        assert isinstance(briefing["highlights"], list)


@pytest.mark.asyncio
async def test_api_command_center_start_my_day(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/start-my-day")
        assert response.status_code == 200
        res = response.json()
        assert "steps" in res
        assert "total_items" in res
        assert res["total_items"] >= 1
        assert res["steps"][0]["step_number"] == 1


@pytest.mark.asyncio
async def test_api_command_center_dismiss_item(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    item_key = "lead_sla_test_item_1"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "item_key": item_key,
            "entity_type": "lead",
            "entity_id": str(seed_command_center_data["lead1"].id),
            "action_type": "dismissed"
        }
        response = await client.post("/api/v1/command-center/items/dismiss", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["item_key"] == item_key
        assert data["action_type"] == "dismissed"


@pytest.mark.asyncio
async def test_api_command_center_snooze_item(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    item_key = "task_overdue_test_item_2"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "item_key": item_key,
            "entity_type": "task",
            "entity_id": str(uuid.uuid4()),
            "action_type": "snoozed",
            "snooze_hours": 2
        }
        response = await client.post("/api/v1/command-center/items/dismiss", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["action_type"] == "snoozed"


@pytest.mark.asyncio
async def test_api_command_center_dismiss_invalid_payload(db_session: AsyncSession, broker: Broker):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "item_key": "",  # invalid
            "entity_type": "lead",
            "entity_id": "123",
            "action_type": "dismissed"
        }
        response = await client.post("/api/v1/command-center/items/dismiss", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_command_center_tenant_isolation(
    db_session: AsyncSession, broker: Broker, other_broker: Broker, seed_command_center_data
):
    # Other broker should see 0 items
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: other_broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_priority_actions"] == 0
        assert len(data["priorities"]) == 0
        assert len(data["first_contact_queue"]) == 0
        assert len(data["overdue_followups"]) == 0
        assert len(data["today_schedule"]) == 0


@pytest.mark.asyncio
async def test_api_command_center_timezone_handling(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center?timezone=Asia/Kolkata")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data


@pytest.mark.asyncio
async def test_api_command_center_unauthorized(db_session: AsyncSession):
    # Without get_current_broker override
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center")
        assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_api_command_center_empty_state(db_session: AsyncSession, other_broker: Broker):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: other_broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_priority_actions"] == 0


@pytest.mark.asyncio
async def test_api_command_center_priorities_entity_type_filter(db_session: AsyncSession, broker: Broker, seed_command_center_data):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/command-center/priorities?entity_type=lead")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["entity_type"] == "lead"
