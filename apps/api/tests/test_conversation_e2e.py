"""
Test Suite: End-to-End AI Sales Agent Scenarios
Covers 5 core revenue workflow scenarios:
  1. Buyer Discovery & Qualification Fact Extraction
  2. Property Shortlisting Flow
  3. Viewing Slot Discovery & Calendar Integration
  4. Human Escalation & Handoff Briefing
  5. Multi-Property Side-by-Side Comparison
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.agent_models import AgentSession, ConversationState, Escalation
from app.models.property_models import PropertyListing
from app.modules.ai_agent.conversation_manager.manager import (
    ConversationManager, IncomingMessage, OutgoingMessage
)
from app.modules.ai_agent.tool_executor.executor import ToolExecutor, ToolResult
from app.modules.ai_agent.tool_executor.services import (
    ShortlistService, CalendarSlotService, ComparisonService
)


@pytest.mark.asyncio
async def test_scenario_1_buyer_qualification_flow(db_session, test_broker, test_lead):
    """
    Scenario 1: Buyer introduces themselves with requirements.
    Verifies that incoming message initializes session, processes turn,
    and updates conversation state.
    """
    manager = ConversationManager()
    msg = IncomingMessage(
        lead_id=str(test_lead.id),
        organization_id=str(test_broker.id),
        channel="web",
        content="Hello, I am looking for a 3BHK apartment in Whitefield around 1.5 Cr for self use.",
        sender_name="Vikram Rao",
    )

    # Mock the LLM completion so test does not require live Gemini API key
    with patch(
        "app.modules.ai_agent.llm_router.adapters.google_adapter.GoogleAdapter.complete",
        new_callable=AsyncMock
    ) as mock_complete:
        from app.modules.ai_agent.llm_router.base_adapter import LLMResponse
        mock_complete.return_value = LLMResponse(
            success=True,
            content="Great to meet you Vikram! We have great 3BHK listings in Whitefield. Are you looking to move in immediately?",
            tool_calls=[],
            provider="google",
            model="gemini-2.5-flash",
        )

        response = await manager.process(db_session, msg)
        assert response.session_id is not None
        assert response.lead_id == str(test_lead.id)
        assert len(response.content) > 0
        assert response.escalated is False


@pytest.mark.asyncio
async def test_scenario_2_property_shortlisting(db_session, test_broker, test_lead):
    """
    Scenario 2: Buyer saves a property to their shortlist.
    Verifies ShortlistService creates LeadPropertyInterest and retrieves it.
    """
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        title="Prestige Palms 3BHK",
        description="Luxury apartment with pool view",
        property_type="apartment",
        price=15000000.0,
        currency_code="INR",
        bedrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        area_value=1850.0,
    )
    db_session.add(prop)
    await db_session.commit()

    shortlist_svc = ShortlistService(db_session)
    add_res = await shortlist_svc.add(
        lead_id=str(test_lead.id),
        property_id=str(prop.id),
        status="shortlisted",
        organization_id=str(test_broker.id),
        notes="High interest in pool view unit",
    )
    assert add_res["success"] is True
    assert add_res["source_verified"] is True

    # Retrieve shortlist
    shortlist = await shortlist_svc.get(
        lead_id=str(test_lead.id),
        organization_id=str(test_broker.id),
    )
    assert shortlist["total"] == 1
    assert shortlist["items"][0]["property_id"] == str(prop.id)
    assert shortlist["items"][0]["name"] == "Prestige Palms 3BHK"


@pytest.mark.asyncio
async def test_scenario_3_viewing_slot_discovery(db_session, test_broker):
    """
    Scenario 3: Buyer inquires about viewing availability.
    Verifies CalendarSlotService returns structured slots without hallucinations.
    """
    slot_svc = CalendarSlotService(db_session)
    slots_data = await slot_svc.get_available_slots(
        organization_id=str(test_broker.id),
        days_ahead=5,
    )
    assert len(slots_data["slots"]) > 0
    assert slots_data["source_verified"] is True
    first_slot = slots_data["slots"][0]
    assert "date" in first_slot
    assert "time" in first_slot


@pytest.mark.asyncio
async def test_scenario_4_human_escalation_handoff(db_session, test_broker, test_lead):
    """
    Scenario 4: Buyer triggers escalation.
    Verifies ToolExecutor creates Escalation record with full handoff context.
    """
    executor = ToolExecutor()
    ctx = {
        "db": db_session,
        "organization_id": str(test_broker.id),
        "lead_id": str(test_lead.id),
        "lead_data": {"name": test_lead.name, "phone": test_lead.phone},
        "qualification": {"budget_max": 15000000, "bedrooms": 3},
    }
    res = await executor.run(
        db=db_session,
        session_id="sess-esc-123",
        turn_index=3,
        tool_name="escalate_to_human",
        arguments={
            "reason": "human_requested",
            "priority": "high",
            "notes": "Customer requested immediate callback regarding payment schedules.",
        },
        context=ctx,
    )
    assert res.success is True
    assert res.result["escalated"] is True
    assert res.result["reason"] == "human_requested"


@pytest.mark.asyncio
async def test_scenario_5_property_comparison(db_session, test_broker):
    """
    Scenario 5: Side-by-side comparison of 2 properties.
    Verifies ComparisonService aggregates verified specifications into a comparison matrix.
    """
    p1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        title="Brigade Metropolis 3BHK",
        description="Spacious high-rise flat",
        property_type="apartment",
        price=18000000.0,
        currency_code="INR",
        bedrooms=3,
        locality="Mahadevapura",
        city="Bengaluru",
        area_value=1950.0,
    )
    p2 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        title="Sobha Dream Acres 2BHK",
        description="Compact smart home",
        property_type="apartment",
        price=11000000.0,
        currency_code="INR",
        bedrooms=2,
        locality="Panathur",
        city="Bengaluru",
        area_value=1200.0,
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    cmp_svc = ComparisonService(db_session)
    res = await cmp_svc.compare(
        property_ids=[str(p1.id), str(p2.id)],
        organization_id=str(test_broker.id),
    )
    assert res["total"] == 2
    assert res["source_verified"] is True
    matrix = res["comparison_matrix"]
    assert matrix["price"][str(p1.id)] == 18000000.0
    assert matrix["price"][str(p2.id)] == 11000000.0
    assert matrix["bedrooms"][str(p1.id)] == 3
    assert matrix["bedrooms"][str(p2.id)] == 2
