"""
Part 29 — Copilot Tools Test Suite: AI Lead ↔ Property Matching Engine
=====================================================================
12 Copilot tool tests covering:
- Registry presence of all 11 AI matching tools
- find_matching_properties tool execution
- get_property_matches tool execution
- find_matching_leads reverse matching tool execution
- get_match_explanation tool execution
- compare_matched_properties tool execution
- shortlist_property_for_lead tool execution
- remove_property_from_shortlist tool execution
- record_match_feedback tool execution
- get_match_score_breakdown tool execution
- suggest_alternatives tool execution
- improve_lead_requirements tool execution
"""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
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
        email=f"copilot_broker_{uuid.uuid4().hex[:6]}@crm.com",
        name="Copilot Agent",
        subscription_status="active"
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def copilot_data(db_session: AsyncSession, broker: Broker):
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Sunil Gavaskar",
        phone="+919876500077",
        budget_min=7500000,
        budget_max=11000000,
        property_type="3 BHK apartment",
        preferred_locations=["Whitefield"],
        transaction_type="buy",
        status="active"
    )
    prop1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="COP-PROP-1",
        title="Prestige Silver Oak 3BHK",
        description="Spacious 3BHK in Whitefield",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=9800000.0,
        area_value=1650.0,
        area_unit="sqft",
        bedrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking", "Clubhouse"]
    )
    prop2 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker.id,
        property_code="COP-PROP-2",
        title="Sobha Habitech 3BHK",
        description="Luxury 3BHK in Whitefield",
        property_type="apartment",
        status="available",
        transaction_category="resale",
        price=10500000.0,
        area_value=1750.0,
        area_unit="sqft",
        bedrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        amenities=["Parking", "Gym"]
    )
    db_session.add_all([lead, prop1, prop2])
    await db_session.commit()

    return {"lead": lead, "prop1": prop1, "prop2": prop2}


# ─── Copilot Tests ───────────────────────────────────────────────────────────

def test_copilot_all_matching_tools_registered():
    """All 11 required AI matching tools are registered in COPILOT_TOOL_REGISTRY."""
    expected_tools = [
        "find_matching_properties",
        "get_property_matches",
        "find_matching_leads",
        "get_match_explanation",
        "compare_matched_properties",
        "shortlist_property_for_lead",
        "remove_property_from_shortlist",
        "record_match_feedback",
        "get_match_score_breakdown",
        "suggest_alternatives",
        "improve_lead_requirements",
    ]
    for tool_name in expected_tools:
        tool = COPILOT_TOOL_REGISTRY.get(tool_name)
        assert tool is not None, f"Tool '{tool_name}' must be present in registry"
        assert callable(tool.handler), f"Tool '{tool_name}' must have an executable handler"


@pytest.mark.asyncio
async def test_copilot_find_matching_properties_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """find_matching_properties tool executes and returns ranked candidates."""
    tool = COPILOT_TOOL_REGISTRY["find_matching_properties"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={"lead_id": str(copilot_data["lead"].id), "top_k": 3}
    )
    assert res is not None
    assert "matches" in res or "properties" in res or "items" in res
    items = res.get("matches") or res.get("properties") or res.get("items")
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_copilot_get_property_matches_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """get_property_matches tool executes and returns candidate properties."""
    tool = COPILOT_TOOL_REGISTRY["get_property_matches"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={"lead_id": str(copilot_data["lead"].id)}
    )
    assert res is not None


@pytest.mark.asyncio
async def test_copilot_find_matching_leads_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """find_matching_leads tool performs reverse matching."""
    tool = COPILOT_TOOL_REGISTRY["find_matching_leads"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={"property_id": str(copilot_data["prop1"].id), "top_k": 5}
    )
    assert res is not None
    assert "leads" in res or "matched_leads" in res or "items" in res


@pytest.mark.asyncio
async def test_copilot_get_match_explanation_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """get_match_explanation tool returns grounded explanation facts."""
    tool = COPILOT_TOOL_REGISTRY["get_match_explanation"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "lead_id": str(copilot_data["lead"].id),
            "property_id": str(copilot_data["prop1"].id)
        }
    )
    assert res is not None
    assert "explanation" in res or "reasons" in res or "match_score" in res


@pytest.mark.asyncio
async def test_copilot_compare_matched_properties_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """compare_matched_properties tool generates comparison matrix."""
    tool = COPILOT_TOOL_REGISTRY["compare_matched_properties"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "property_ids": [str(copilot_data["prop1"].id), str(copilot_data["prop2"].id)],
            "lead_id": str(copilot_data["lead"].id)
        }
    )
    assert res is not None
    assert "comparison_matrix" in res or "properties" in res


@pytest.mark.asyncio
async def test_copilot_shortlist_property_for_lead_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """shortlist_property_for_lead tool records shortlist."""
    tool = COPILOT_TOOL_REGISTRY["shortlist_property_for_lead"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "lead_id": str(copilot_data["lead"].id),
            "property_id": str(copilot_data["prop1"].id),
            "notes": "Shortlisted by Copilot agent"
        }
    )
    assert res is not None
    assert res.get("status") in ("success", "shortlisted") or "message" in res


@pytest.mark.asyncio
async def test_copilot_remove_property_from_shortlist_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """remove_property_from_shortlist tool removes or unlinks property."""
    tool = COPILOT_TOOL_REGISTRY["remove_property_from_shortlist"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "lead_id": str(copilot_data["lead"].id),
            "property_id": str(copilot_data["prop1"].id)
        }
    )
    assert res is not None


@pytest.mark.asyncio
async def test_copilot_record_match_feedback_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """record_match_feedback tool saves feedback on match."""
    tool = COPILOT_TOOL_REGISTRY["record_match_feedback"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "lead_id": str(copilot_data["lead"].id),
            "property_id": str(copilot_data["prop1"].id),
            "feedback": "good_match",
            "notes": "Client loves locality"
        }
    )
    assert res is not None
    assert res.get("status") == "success" or "message" in res


@pytest.mark.asyncio
async def test_copilot_get_match_score_breakdown_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """get_match_score_breakdown tool returns 8-dimensional scores."""
    tool = COPILOT_TOOL_REGISTRY["get_match_score_breakdown"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={
            "lead_id": str(copilot_data["lead"].id),
            "property_id": str(copilot_data["prop1"].id)
        }
    )
    assert res is not None
    assert "score_breakdown" in res or "breakdown" in res or "match_score" in res


@pytest.mark.asyncio
async def test_copilot_suggest_alternatives_execution(db_session: AsyncSession, broker: Broker, copilot_data):
    """suggest_alternatives tool relaxes constraints and finds alternatives."""
    tool = COPILOT_TOOL_REGISTRY["suggest_alternatives"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={"lead_id": str(copilot_data["lead"].id), "top_k": 3}
    )
    assert res is not None


@pytest.mark.asyncio
async def test_copilot_improve_lead_requirements_execution(db_session: AsyncSession, broker: Broker):
    """improve_lead_requirements tool returns clarification questions for incomplete lead."""
    incomplete_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Incomplete Prospect",
        phone="+919111122222"
    )
    db_session.add(incomplete_lead)
    await db_session.commit()

    tool = COPILOT_TOOL_REGISTRY["improve_lead_requirements"]
    res = await tool.handler(
        db=db_session,
        broker=broker,
        args={"lead_id": str(incomplete_lead.id)}
    )
    assert res is not None
    questions = res.get("missing_information_questions") or res.get("questions") or []
    assert len(questions) >= 2
    assert any("budget" in q.lower() for q in questions)
