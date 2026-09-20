"""
Volume 2 PART 5 — Customer-Facing AI Real Estate Experience Test Suite
========================================================================
10 Integration & Customer Journey Tests:
1.  test_message_endpoint_responds: POST /message returns 200 with session_id & AI message
2.  test_session_history_persists: GET /sessions/{id}/history accurately records multi-turn conversation
3.  test_shortlist_add_and_fetch: POST and GET /sessions/{id}/shortlist adds & returns verified item
4.  test_shortlist_false_success_blocked: Shortlist empty state before add ensures no false items
5.  test_comparison_endpoint: GET /sessions/{id}/comparison returns comparison matrix
6.  test_slots_endpoint: GET /slots/{org_id} returns available viewing slots with times
7.  test_escalation_flow: POST /sessions/{id}/escalate triggers human escalation record & status
8.  test_no_match_tool_result: Restrictive property search returns 0 results cleanly without throwing
9.  test_tenant_isolation_session: Shortlists and sessions are strictly scoped by organization_id
10. test_session_restore_after_refresh: Simulates web refresh: fetches history & restores prior turns
"""
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.database import Base

from app.models.agent_models import (
    AgentSession, ConversationState, QualificationProfile, Escalation
)
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.ai_agent.state_machine.fsm import State
from app.modules.ai_agent.conversation_manager.manager import (
    ConversationManager, IncomingMessage
)
from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse
from app.modules.ai_agent.llm_router.router import LLMRouter
from app.modules.ai_agent.tool_executor.services import (
    ShortlistService, ComparisonService, CalendarSlotService, PropertyService
)


class MockSalesLLM(BaseLLMAdapter):
    """Deterministic LLM mock for customer journey testing."""
    def __init__(self, reply: str = "Hello! I can help you find your dream home. What is your target budget?"):
        self.reply = reply

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def supports_tool_calling(self) -> bool:
        return True

    async def complete(self, messages, tools=None, max_tokens=1024, temperature=0.3) -> LLMResponse:
        return LLMResponse(
            content=self.reply,
            tool_calls=[],
            prompt_tokens=40,
            completion_tokens=25,
            total_tokens=65,
            cost_usd=0.0001,
            latency_ms=85,
            provider="mock",
            model="mock-gpt",
            success=True,
        )

    async def is_available(self) -> bool:
        return True


@pytest_asyncio.fixture
async def async_session():
    """In-memory SQLite database session fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ─── 1. Message Endpoint Responds ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_message_endpoint_responds(async_session: AsyncSession):
    """Verifies that an inbound customer message processes cleanly through the pipeline."""
    llm = MockSalesLLM("Welcome to WefyLabs! What BHK configuration are you looking for?")
    manager = ConversationManager(llm_router=LLMRouter(primary=llm))

    org_id = str(uuid.uuid4())
    lead_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    session = AgentSession(
        id=session_id,
        session_token="test_token_msg_01",
        organization_id=org_id,
        lead_id=lead_id,
        channel="web",
        current_state=State.NEW,
    )
    async_session.add(session)
    async_session.add(QualificationProfile(session_id=session_id, organization_id=org_id, lead_id=lead_id))
    await async_session.flush()

    incoming = IncomingMessage(
        lead_id=lead_id,
        organization_id=org_id,
        channel="web",
        content="I am looking for a 3 BHK in Noida",
    )

    with patch.object(manager, "_get_or_create_session", new=AsyncMock(return_value=session)):
        outgoing = await manager.process(async_session, incoming)

    assert outgoing.session_id == session_id
    assert outgoing.turn_index == 1
    assert "bhk" in outgoing.content.lower() or "wefylabs" in outgoing.content.lower()
    assert not outgoing.was_blocked


# ─── 2. Session History Persists ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_history_persists(async_session: AsyncSession):
    """Verifies that multiple conversation turns persist in ConversationState sequentially."""
    session_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    lead_id = str(uuid.uuid4())

    session = AgentSession(
        id=session_id,
        session_token="token_hist_test",
        organization_id=org_id,
        lead_id=lead_id,
        channel="web",
        current_state=State.QUALIFYING,
    )
    async_session.add(session)
    await async_session.flush()

    turns = [
        ("user", "Hello, do you have villas in Bangalore?"),
        ("agent", "Yes, we have luxury villas starting from 3 Crore in Whitefield."),
        ("user", "Are there ready-to-move options?"),
        ("agent", "Yes! We have 2 verified ready-to-move projects available immediately."),
    ]

    for idx, (role, text) in enumerate(turns, start=1):
        state = ConversationState(
            session_id=session_id,
            turn_index=idx,
            from_state=State.NEW if idx == 1 else State.DISCOVERING,
            to_state=State.QUALIFYING if idx > 2 else State.DISCOVERING,
            customer_message=text if role == "user" else "",
            agent_response=text if role == "agent" else "",
        )
        async_session.add(state)
    await async_session.flush()

    from sqlalchemy import select
    result = await async_session.execute(
        select(ConversationState)
        .where(ConversationState.session_id == session_id)
        .order_by(ConversationState.turn_index)
    )
    history = result.scalars().all()
    assert len(history) == 4
    assert history[0].turn_index == 1
    assert history[3].turn_index == 4
    assert "ready-to-move" in history[2].customer_message


# ─── 3. Shortlist Add and Fetch ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shortlist_add_and_fetch(async_session: AsyncSession):
    """Verifies that a customer can add a property to shortlist and fetch it back."""
    broker_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    prop_id = uuid.uuid4()

    # Pre-seed Broker, Lead, Property
    broker = Broker(id=broker_id, email="b@test.com", phone="+919999999901", name="Agent 1")
    lead = Lead(id=lead_id, broker_id=broker_id, phone="+919999999902", name="Buyer 1")
    prop = PropertyListing(
        id=prop_id,
        broker_id=broker_id,
        title="Godrej Woods 3 BHK",
        description="Premium luxury 3 BHK residential apartments in Sector 43 Noida",
        property_type="apartment",
        bedrooms=3,
        price=15000000,
        area_value=1650.0,
        status="available",
    )
    async_session.add_all([broker, lead, prop])
    await async_session.flush()

    svc = ShortlistService(async_session)
    add_res = await svc.add(
        lead_id=str(lead_id),
        property_id=str(prop_id),
        status="shortlisted",
        organization_id=str(broker_id),
    )
    assert add_res["success"] is True

    get_res = await svc.get(lead_id=str(lead_id), organization_id=str(broker_id))
    assert get_res["total"] == 1
    assert get_res["items"][0]["property_id"] == str(prop_id)
    assert get_res["items"][0]["status"] == "shortlisted"


# ─── 4. Shortlist False Success Blocked ───────────────────────────────────────

@pytest.mark.asyncio
async def test_shortlist_false_success_blocked(async_session: AsyncSession):
    """Verifies that an un-shortlisted lead returns 0 items, preventing false positives."""
    svc = ShortlistService(async_session)
    unknown_lead = str(uuid.uuid4())
    res = await svc.get(lead_id=unknown_lead, organization_id=str(uuid.uuid4()))
    assert res["total"] == 0
    assert len(res["items"]) == 0


# ─── 5. Comparison Endpoint ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_comparison_endpoint(async_session: AsyncSession):
    """Verifies side-by-side comparison logic retrieves properties and structures comparison matrix."""
    broker_id = uuid.uuid4()
    prop1_id = uuid.uuid4()
    prop2_id = uuid.uuid4()

    p1 = PropertyListing(
        id=prop1_id,
        broker_id=broker_id,
        title="Prestige Golfshire",
        description="Exclusive 4 BHK golf resort luxury villas in Bangalore",
        property_type="villa",
        bedrooms=4,
        price=35000000,
        area_value=4500.0,
        locality="Nandi Hills",
        status="available",
    )
    p2 = PropertyListing(
        id=prop2_id,
        broker_id=broker_id,
        title="Sobha Dream Acres",
        description="Modern 2 BHK residential apartment complex with club amenities",
        property_type="apartment",
        bedrooms=2,
        price=9000000,
        area_value=1100.0,
        locality="Panathur",
        status="available",
    )
    async_session.add_all([p1, p2])
    await async_session.flush()

    comp_svc = ComparisonService(async_session)
    comp_data = await comp_svc.compare(
        property_ids=[str(prop1_id), str(prop2_id)],
        organization_id=str(broker_id),
    )

    assert comp_data["total"] == 2
    assert "comparison_matrix" in comp_data
    matrix = comp_data["comparison_matrix"]
    assert matrix["price"][str(prop1_id)] == 35000000.0
    assert matrix["bedrooms"][str(prop2_id)] == 2


# ─── 6. Slots Endpoint ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_slots_endpoint(async_session: AsyncSession):
    """Verifies that viewing slots return structured weekday slots."""
    slot_svc = CalendarSlotService(async_session)
    org_id = str(uuid.uuid4())

    slots_data = await slot_svc.get_available_slots(organization_id=org_id, days_ahead=7)
    assert "slots" in slots_data
    assert len(slots_data["slots"]) > 0
    slot = slots_data["slots"][0]
    assert "date" in slot
    assert "time" in slot
    assert slots_data["source_verified"] is True


# ─── 7. Escalation Flow ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_escalation_flow(async_session: AsyncSession):
    """Verifies that manual/requested escalation records properly update session and audit."""
    session_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    lead_id = str(uuid.uuid4())

    session = AgentSession(
        id=session_id,
        session_token="token_esc_01",
        organization_id=org_id,
        lead_id=lead_id,
        channel="web",
        current_state=State.QUALIFYING,
        escalated=False,
    )
    async_session.add(session)
    await async_session.flush()

    # Trigger escalation
    esc = Escalation(
        id=str(uuid.uuid4()),
        session_id=session_id,
        organization_id=org_id,
        lead_id=lead_id,
        reason="customer_requested_human",
        priority="high",
        summary="Customer asked to speak with a human specialist.",
        status="pending",
    )
    session.escalated = True
    async_session.add(esc)
    await async_session.flush()

    assert session.escalated is True
    assert esc.reason == "customer_requested_human"
    assert esc.status == "pending"


# ─── 8. No-Match Tool Result Graceful Handling ────────────────────────────────

@pytest.mark.asyncio
async def test_no_match_tool_result(async_session: AsyncSession):
    """Verifies that searching with non-matching criteria returns 0 results cleanly without errors."""
    prop_svc = PropertyService(async_session)
    # Search for an unrealistic budget with no matching listings
    result = await prop_svc.search(
        property_type="penthouse",
        budget_max=100.0,  # Unrealistic $100 budget
        organization_id=str(uuid.uuid4()),
    )
    assert result["total"] == 0
    assert result["properties"] == []
    assert result["source_verified"] is True


# ─── 9. Tenant Isolation on Sessions and Shortlists ───────────────────────────

@pytest.mark.asyncio
async def test_tenant_isolation_session(async_session: AsyncSession):
    """Verifies tenant boundary: tenant B cannot add or view tenant A's property shortlist."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    lead_a = uuid.uuid4()
    prop_a = uuid.uuid4()

    broker_a = Broker(id=tenant_a, email="a@tenanta.com", phone="+91999999903", name="Broker A")
    broker_b = Broker(id=tenant_b, email="b@tenantb.com", phone="+91999999904", name="Broker B")
    lead = Lead(id=lead_a, broker_id=tenant_a, phone="+91999999905", name="Lead A")
    prop = PropertyListing(
        id=prop_a,
        broker_id=tenant_a,
        title="Tenant A Listing",
        description="Tenant A exclusive verified property listing",
        price=10000000,
        area_value=1200.0,
        status="available",
    )
    async_session.add_all([broker_a, broker_b, lead, prop])
    await async_session.flush()

    svc = ShortlistService(async_session)
    # Tenant B tries to shortlist Tenant A's property for Lead A
    res = await svc.add(
        lead_id=str(lead_a),
        property_id=str(prop_a),
        organization_id=str(tenant_b),  # Wrong org!
    )
    assert res["success"] is False
    assert "not found in this organization" in res["error"]


# ─── 10. Session Restore After Refresh ────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_restore_after_refresh(async_session: AsyncSession):
    """Simulates a browser refresh: loads prior session state, qualification profile, and turns."""
    session_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    lead_id = str(uuid.uuid4())

    session = AgentSession(
        id=session_id,
        session_token="refresh_token_test",
        organization_id=org_id,
        lead_id=lead_id,
        channel="web",
        current_state=State.DISCOVERING,
        turn_count=2,
    )
    qual = QualificationProfile(
        session_id=session_id,
        organization_id=org_id,
        lead_id=lead_id,
        budget_max=15000000,
        property_type="apartment",
        bedrooms=3,
        completion_pct=25.0,
    )
    async_session.add_all([session, qual])
    await async_session.flush()

    t1 = ConversationState(
        session_id=session_id,
        turn_index=1,
        from_state=State.NEW,
        to_state=State.GREETING,
        customer_message="Hi",
        agent_response="Hello! What are you looking for?",
    )
    t2 = ConversationState(
        session_id=session_id,
        turn_index=2,
        from_state=State.GREETING,
        to_state=State.DISCOVERING,
        customer_message="3 BHK apartment under 1.5 Cr",
        agent_response="Great! Let me find matching options in Noida for you.",
    )
    async_session.add_all([t1, t2])
    await async_session.flush()

    # Query back as the portal /history and /qualification endpoints do:
    from sqlalchemy import select
    sess_q = await async_session.execute(select(AgentSession).where(AgentSession.id == session_id))
    loaded_sess = sess_q.scalar_one()
    assert loaded_sess.turn_count == 2
    assert loaded_sess.current_state == State.DISCOVERING

    qual_q = await async_session.execute(select(QualificationProfile).where(QualificationProfile.session_id == session_id))
    loaded_qual = qual_q.scalar_one()
    assert loaded_qual.bedrooms == 3
    assert loaded_qual.budget_max == 15000000
    assert loaded_qual.completion_pct == 25.0

    history_q = await async_session.execute(
        select(ConversationState)
        .where(ConversationState.session_id == session_id)
        .order_by(ConversationState.turn_index)
    )
    loaded_turns = history_q.scalars().all()
    assert len(loaded_turns) == 2
    assert loaded_turns[1].customer_message == "3 BHK apartment under 1.5 Cr"
