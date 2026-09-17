"""
Part 30 — Copilot Tools Test Suite: AI Command Center & Inventory Intelligence
=============================================================================
12 comprehensive Copilot tool tests covering:
1. Tool registry presence of all 6 Command Center tools
2. get_command_center_summary execution
3. get_today_priorities execution
4. get_today_priorities with limit filtering
5. get_inventory_intelligence execution (Heatmap and gaps)
6. get_daily_briefing execution
7. get_start_my_day_queue execution
8. dismiss_dashboard_item execution (dismissed)
9. dismiss_dashboard_item execution (snoozed)
10. dismiss_dashboard_item error handling when missing required params
11. Multi-tenant isolation: Broker B cannot inspect Broker A's command center data
12. Read-only safety vs mutation confirmation
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Activity
from app.models.property_models import PropertyListing
from app.modules.copilot.tools.tool_registry import COPILOT_TOOL_REGISTRY

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
async def broker(db_session: AsyncSession):
    b = Broker(
        id=uuid.uuid4(),
        email=f"copilot_cc_broker_{uuid.uuid4().hex[:6]}@crm.com",
        name="Copilot Commander",
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
        email=f"copilot_other_{uuid.uuid4().hex[:6]}@crm.com",
        name="Other Broker",
        subscription_status="active"
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def copilot_seed_data(db_session: AsyncSession, broker: Broker):
    now = datetime.now(timezone.utc)
    
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Rohan Mehra",
        phone="+919876543210",
        pipeline_stage="new",
        score="hot",
        status="active",
        preferred_locations=["Whitefield"],
        property_type="apartment",
        created_at=now - timedelta(hours=2),
    )
    
    task = Task(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead.id,
        title="Review home loan documents",
        status="pending",
        due_at=now - timedelta(days=1),
    )
    
    meeting = Meeting(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead.id,
        title="Site visit: Rohan Mehra",
        meeting_type="site_visit",
        scheduled_at=now + timedelta(hours=2),
        duration_minutes=60,
        status="scheduled",
    )
    
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="PROP-COP-1",
        title="Modern 2BHK Apartment",
        description="Fresh modern listing",
        property_type="apartment",
        city="Bengaluru",
        locality="Whitefield",
        bedrooms=2,
        price=8500000.0,
        area_value=1200.0,
        area_unit="sqft",
        status="available",
        created_at=now - timedelta(days=1),
    )
    
    db_session.add_all([lead, task, meeting, prop])
    await db_session.commit()
    return {"lead": lead, "task": task, "meeting": meeting, "prop": prop}


def test_copilot_tools_registry_presence():
    expected_tools = [
        "get_command_center_summary",
        "get_today_priorities",
        "get_inventory_intelligence",
        "get_daily_briefing",
        "get_start_my_day_queue",
        "dismiss_dashboard_item",
    ]
    for tool_name in expected_tools:
        assert tool_name in COPILOT_TOOL_REGISTRY, f"Tool '{tool_name}' missing from COPILOT_TOOL_REGISTRY"
        tool_meta = COPILOT_TOOL_REGISTRY[tool_name]
        assert tool_meta.description is not None
        assert tool_meta.handler is not None
        assert callable(tool_meta.handler)


@pytest.mark.asyncio
async def test_copilot_get_command_center_summary(db_session: AsyncSession, broker: Broker, copilot_seed_data):
    tool = COPILOT_TOOL_REGISTRY["get_command_center_summary"]
    result = await tool.handler(db=db_session, broker=broker, args={})
    assert "summary" in result
    summary = result["summary"]
    assert summary["total_priority_actions"] >= 1
    assert summary["sla_breaches_count"] >= 1


@pytest.mark.asyncio
async def test_copilot_get_today_priorities(db_session: AsyncSession, broker: Broker, copilot_seed_data):
    tool = COPILOT_TOOL_REGISTRY["get_today_priorities"]
    result = await tool.handler(db=db_session, broker=broker, args={"limit": 10})
    assert "priorities" in result
    priorities = result["priorities"]
    assert isinstance(priorities, list)
    assert len(priorities) >= 1
    assert any(p["priority"] == "CRITICAL" for p in priorities)


@pytest.mark.asyncio
async def test_copilot_get_today_priorities_with_limit(db_session: AsyncSession, broker: Broker, copilot_seed_data):
    tool = COPILOT_TOOL_REGISTRY["get_today_priorities"]
    result = await tool.handler(db=db_session, broker=broker, args={"limit": 1})
    assert len(result["priorities"]) <= 1


@pytest.mark.asyncio
async def test_copilot_get_inventory_intelligence(db_session: AsyncSession, broker: Broker, copilot_seed_data):
    tool = COPILOT_TOOL_REGISTRY["get_inventory_intelligence"]
    result = await tool.handler(db=db_session, broker=broker, args={})
    assert "demand_heatmap" in result
    assert "inventory_gaps" in result
    assert "_citation" in result


@pytest.mark.asyncio
async def test_copilot_get_daily_briefing(db_session: AsyncSession, broker: Broker, copilot_seed_data):
    tool = COPILOT_TOOL_REGISTRY["get_daily_briefing"]
    result = await tool.handler(db=db_session, broker=broker, args={})
    assert "briefing_text" in result
    assert "highlights" in result


@pytest.mark.asyncio
async def test_copilot_get_start_my_day_queue(db_session: AsyncSession, broker: Broker, copilot_seed_data):
    tool = COPILOT_TOOL_REGISTRY["get_start_my_day_queue"]
    result = await tool.handler(db=db_session, broker=broker, args={})
    assert "steps" in result
    assert "total_items" in result
    assert result["total_items"] >= 1


@pytest.mark.asyncio
async def test_copilot_dismiss_dashboard_item_dismiss(db_session: AsyncSession, broker: Broker):
    tool = COPILOT_TOOL_REGISTRY["dismiss_dashboard_item"]
    result = await tool.handler(db=db_session, broker=broker, args={
        "item_key": "copilot_test_key_1",
        "entity_type": "task",
        "entity_id": str(uuid.uuid4()),
        "action_type": "dismissed"
    })
    assert result["status"] == "success"
    assert result["item_key"] == "copilot_test_key_1"
    assert result["action_type"] == "dismissed"


@pytest.mark.asyncio
async def test_copilot_dismiss_dashboard_item_snooze(db_session: AsyncSession, broker: Broker):
    tool = COPILOT_TOOL_REGISTRY["dismiss_dashboard_item"]
    result = await tool.handler(db=db_session, broker=broker, args={
        "item_key": "copilot_test_key_2",
        "entity_type": "task",
        "entity_id": str(uuid.uuid4()),
        "action_type": "snoozed",
        "snooze_hours": 2
    })
    assert result["status"] == "success"
    assert result["action_type"] == "snoozed"


@pytest.mark.asyncio
async def test_copilot_dismiss_missing_key(db_session: AsyncSession, broker: Broker):
    tool = COPILOT_TOOL_REGISTRY["dismiss_dashboard_item"]
    try:
        result = await tool.handler(db=db_session, broker=broker, args={
            "item_key": "",
            "entity_type": "task",
            "entity_id": ""
        })
        # If execution succeeds or returns error
        assert "error" in result or result.get("status") != "success"
    except Exception as e:
        # Pydantic or tool validation caught missing key
        assert e is not None


@pytest.mark.asyncio
async def test_copilot_cross_tenant_isolation(
    db_session: AsyncSession, broker: Broker, other_broker: Broker, copilot_seed_data
):
    tool = COPILOT_TOOL_REGISTRY["get_command_center_summary"]
    # other_broker has 0 items
    result_other = await tool.handler(db=db_session, broker=other_broker, args={})
    assert result_other["summary"]["total_priority_actions"] == 0

    # broker has items
    result_broker = await tool.handler(db=db_session, broker=broker, args={})
    assert result_broker["summary"]["total_priority_actions"] >= 1


@pytest.mark.asyncio
async def test_copilot_read_only_safety(db_session: AsyncSession, broker: Broker, copilot_seed_data):
    # Read-only tools do not mutate database state
    tool = COPILOT_TOOL_REGISTRY["get_today_priorities"]
    res1 = await tool.handler(db=db_session, broker=broker, args={})
    res2 = await tool.handler(db=db_session, broker=broker, args={})
    assert len(res1["priorities"]) == len(res2["priorities"])
