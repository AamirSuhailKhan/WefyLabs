"""
Part 35 — Copilot Test Suite: AI Real Estate Revenue Autopilot Tools
====================================================================
Verifies that the Revenue Autopilot tools are registered in COPILOT_TOOL_REGISTRY
and can be invoked by the AI Copilot:
1. get_revenue_action_queue
2. explain_revenue_opportunity
3. action_revenue_opportunity
4. dismiss_revenue_opportunity
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.revenue_autopilot_models import RevenueOpportunity
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
        email=f"copilot_agent_{uuid.uuid4().hex[:6]}@agency.com",
        name="Copilot Agent",
        agency_name="Apex Realty",
        subscription_status="active",
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def copilot_opportunity(db_session: AsyncSession, broker: Broker):
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Kavita Rao",
        phone="+919876543210",
        budget_max=18000000,
        status="active",
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        title="DLF Phase 5 Penthouse",
        description="Luxury 4BHK penthouse.",
        area_value=2800.0,
        price=17500000.0,
        status="available",
        locality="DLF Phase 5",
        bedrooms=4,
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
        opportunity_score=91.0,
        match_score=95.0,
        status="RECOMMENDED",
        reason="Budget and location match live inventory",
        why_now="Active buyer today",
        why_property="Matches 4BHK in DLF Phase 5",
        risk_of_inactivity="High competitor interest",
        recommended_action="CALL_LEAD",
        recommended_channel="CALL",
        recommended_property_snapshot={
            "property_id": str(prop.id),
            "title": prop.title,
            "price": prop.price,
        },
        positive_signals=["Budget matches", "Active today"],
        negative_signals=[],
        dedup_key=f"{broker.id}:{lead.id}:{prop.id}:NEW_HIGH_VALUE_MATCH",
    )
    db_session.add_all([lead, prop, opp])
    await db_session.commit()
    return {"lead": lead, "prop": prop, "opp": opp}


# ── Test 1: Tool Registry Presence ────────────────────────────────────────────
def test_copilot_revenue_tools_registered():
    """All 4 Revenue Autopilot tools are registered in COPILOT_TOOL_REGISTRY."""
    expected_tools = [
        "get_revenue_action_queue",
        "explain_revenue_opportunity",
        "dismiss_revenue_opportunity",
        "action_revenue_opportunity",
    ]
    for name in expected_tools:
        tool = COPILOT_TOOL_REGISTRY.get(name)
        assert tool is not None, f"Tool '{name}' must be registered"
        assert callable(tool.handler), f"Tool '{name}' must have an executable handler"


# ── Test 2: get_revenue_action_queue Tool Execution ───────────────────────────
@pytest.mark.asyncio
async def test_copilot_get_action_queue_execution(db_session: AsyncSession, broker: Broker, copilot_opportunity):
    """Copilot tool 'get_revenue_action_queue' retrieves prioritized actions for agent."""
    tool = COPILOT_TOOL_REGISTRY["get_revenue_action_queue"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={"limit": 5}
    )
    assert res is not None
    assert "actions" in res
    assert len(res["actions"]) >= 1
    first = res["actions"][0]
    assert first["opportunity_id"] == str(copilot_opportunity["opp"].id)
    assert first["lead_name"] == "Kavita Rao"
    assert first["opportunity_score"] == 91.0


# ── Test 3: explain_revenue_opportunity Tool Execution ────────────────────────
@pytest.mark.asyncio
async def test_copilot_explain_opportunity_execution(db_session: AsyncSession, broker: Broker, copilot_opportunity):
    """Copilot tool 'explain_revenue_opportunity' returns explainability breakdown."""
    tool = COPILOT_TOOL_REGISTRY["explain_revenue_opportunity"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={"opportunity_id": str(copilot_opportunity["opp"].id)}
    )
    assert res is not None
    assert res["opportunity_id"] == str(copilot_opportunity["opp"].id)
    assert "why_now" in res
    assert "why_property" in res
    assert "positive_signals" in res
    assert res["why_now"] == "Active buyer today"


# ── Test 4: action_revenue_opportunity Tool Execution ─────────────────────────
@pytest.mark.asyncio
async def test_copilot_action_opportunity_execution(db_session: AsyncSession, broker: Broker, copilot_opportunity):
    """Copilot tool 'action_revenue_opportunity' executes agent action and returns status."""
    tool = COPILOT_TOOL_REGISTRY["action_revenue_opportunity"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "opportunity_id": str(copilot_opportunity["opp"].id),
            "action_type": "CALL_LEAD",
            "notes": "Called Kavita via Copilot suggestion."
        }
    )
    assert res is not None
    assert res["status"] == "ACTIONED"


# ── Test 5: dismiss_revenue_opportunity Tool Execution ────────────────────────
@pytest.mark.asyncio
async def test_copilot_dismiss_opportunity_execution(db_session: AsyncSession, broker: Broker, copilot_opportunity):
    """Copilot tool 'dismiss_revenue_opportunity' dismisses opportunity."""
    tool = COPILOT_TOOL_REGISTRY["dismiss_revenue_opportunity"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "opportunity_id": str(copilot_opportunity["opp"].id),
            "reason": "Not relevant"
        }
    )
    assert res is not None
    assert res["status"] == "DISMISSED"
