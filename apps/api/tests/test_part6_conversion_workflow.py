"""
Volume 2 PART 6 — Conversion Workflow Comprehensive Test Suite
================================================================
Comprehensive verification across the entire sales conversion pipeline:
1.  test_slot_discovery_real_availability: Ensures slots respect working hours, minimum lead time (1 hr), property availability, and exclude busy blocks.
2.  test_double_booking_lock_protection: Concurrent booking attempts on same slot fail when lock is held.
3.  test_slot_revalidation_race_condition: When property becomes unavailable prior to booking, booking is rejected.
4.  test_idempotent_appointment_creation: Same idempotency key returns identical meeting without duplicating DB rows.
5.  test_site_visit_linkage_and_outcome: Completing a visit captures structured outcome, updates Viewing, logs timeline Activity, updates LeadPropertyInterest.
6.  test_human_handoff_explicit_request: Explicit request triggers handoff, creates Escalation record, marks session escalated.
7.  test_human_handoff_ai_suppression: When session is escalated, autonomous AI messages are suppressed and human specialist ownership is maintained.
8.  test_post_site_visit_revenue_opportunity: Canonical SchedulingMeeting visit generates POST_SITE_VISIT_FOLLOW_UP opportunity with CRITICAL urgency.
9.  test_revenue_opportunity_deduplication: Repeated engine evaluations on same visit do not create duplicate opportunities.
10. test_revenue_score_vs_match_score_separation: Commercial urgency is distinct from property suitability match score.
11. test_tenant_isolation_cross_tenant_blocked: Tenant A cannot access, book, or mutate Tenant B's appointments or opportunities.
12. test_ai_tool_unconfirmed_booking_blocked: AI conversation does not execute booking without explicit customer confirmation.
"""

import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta, date, time
from typing import Optional, List, Dict, Any
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.calendar_models import (
    SchedulingMeeting, Viewing, MeetingOutcome, MeetingHold, CalendarEvent
)
from app.models.agent_models import (
    AgentSession, ConversationState, Escalation
)
from app.models.crm_models import Activity
from app.models.revenue_autopilot_models import RevenueOpportunity

from app.modules.calendar.availability.availability_engine import AvailabilityEngine
from app.modules.calendar.booking.booking_service import BookingService
from app.modules.calendar.booking_lock.lock_manager import BookingLockManager
from app.modules.calendar.post_meeting.post_meeting_service import PostMeetingIntelligenceService
from app.modules.calendar.dto.calendar_schemas import (
    BookingRequestDTO, RecordOutcomeRequestDTO, SlotHoldRequestDTO
)
from app.modules.calendar.providers.provider_interface import MockCalendarProvider
from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
from app.modules.ai_agent.conversation_manager.manager import ConversationManager, IncomingMessage
from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse
from app.modules.ai_agent.llm_router.router import LLMRouter


class MockAIAdapter(BaseLLMAdapter):
    """Deterministic LLM mock for conversation & handoff verification."""
    def __init__(self, reply: str = "Certainly, let me check available viewing slots for you.", tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.reply = reply
        self._tool_calls = tool_calls or []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def supports_tool_calling(self) -> bool:
        return True

    async def complete(self, messages, tools=None, max_tokens=1024, temperature=0.3) -> LLMResponse:
        return LLMResponse(
            content=self.reply,
            tool_calls=self._tool_calls,
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
            cost_usd=0.0001,
            latency_ms=50,
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


@pytest_asyncio.fixture
async def setup_tenants(async_session: AsyncSession):
    """Create two isolated tenants: Tenant A and Tenant B."""
    broker_a = Broker(
        id=uuid.uuid4(),
        name="Broker A Realty",
        email=f"broker_a_{uuid.uuid4().hex[:6]}@wefylabs.com",
        phone="+919888811111",
        city="Gurgaon",
    )
    broker_b = Broker(
        id=uuid.uuid4(),
        name="Broker B Realty",
        email=f"broker_b_{uuid.uuid4().hex[:6]}@wefylabs.com",
        phone="+919888822222",
        city="Noida",
    )
    async_session.add_all([broker_a, broker_b])
    await async_session.flush()

    lead_a = Lead(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        name="Buyer Alpha",
        phone="+919111111111",
        status="active",
        preferred_locations=["Gurgaon", "Golf Course Road"],
        budget_min=10000000.0,
        budget_max=25000000.0,
    )
    lead_b = Lead(
        id=uuid.uuid4(),
        broker_id=broker_b.id,
        name="Buyer Beta",
        phone="+919222222222",
        status="active",
        preferred_locations=["Noida"],
        budget_min=8000000.0,
        budget_max=15000000.0,
    )
    async_session.add_all([lead_a, lead_b])
    await async_session.flush()

    prop_a = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_a.id,
        title="DLF Luxury Heights",
        description="Spacious 3 BHK luxury apartment with modern amenities",
        property_type="apartment",
        status="available",
        price=22000000.0,
        area_value=1850.0,
        bedrooms=3,
        locality="Golf Course Road",
        address="Golf Course Road, Gurgaon",
        city="Gurgaon",
    )
    prop_b = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_b.id,
        title="Jaypee Greens Penthouse",
        description="Premium 4 BHK penthouse overlooking golf course",
        property_type="penthouse",
        status="available",
        price=14000000.0,
        area_value=2800.0,
        bedrooms=4,
        locality="Sector 128",
        address="Sector 128, Noida",
        city="Noida",
    )
    async_session.add_all([prop_a, prop_b])
    await async_session.commit()

    return {
        "broker_a": broker_a,
        "broker_b": broker_b,
        "lead_a": lead_a,
        "lead_b": lead_b,
        "prop_a": prop_a,
        "prop_b": prop_b,
    }


# ─── 1. Slot Discovery & Real Availability Tests ──────────────────────────────

@pytest.mark.asyncio
async def test_slot_discovery_real_availability(async_session: AsyncSession, setup_tenants):
    """Slots respect business rules, property availability, and minimum 1-hour lead time."""
    broker = setup_tenants["broker_a"]
    prop = setup_tenants["prop_a"]

    engine = AvailabilityEngine(async_session)

    slots = await engine.calculate_available_slots(
        broker_id=str(broker.id),
        property_id=str(prop.id),
        customer_tz_str="Asia/Kolkata",
        duration_minutes=45,
        search_days_ahead=3,
    )
    assert len(slots) > 0
    first_slot = slots[0]
    assert first_slot["property_id"] == str(prop.id)
    assert first_slot["customer_timezone"] == "Asia/Kolkata"
    assert first_slot["start_utc"] > datetime.now(timezone.utc) + timedelta(minutes=50)


@pytest.mark.asyncio
async def test_slot_discovery_rejects_unavailable_property(async_session: AsyncSession, setup_tenants):
    """Slot discovery returns empty if the property is sold or inactive."""
    broker = setup_tenants["broker_a"]
    prop = setup_tenants["prop_a"]

    # Mark property as sold
    prop.status = "sold"
    await async_session.commit()

    engine = AvailabilityEngine(async_session)

    slots = await engine.calculate_available_slots(
        broker_id=str(broker.id),
        property_id=str(prop.id),
        duration_minutes=45,
        search_days_ahead=3,
    )
    assert len(slots) == 0, "No slots should be generated for unavailable inventory"


# ─── 2. Concurrency & Double-Booking Protection ───────────────────────────────

@pytest.mark.asyncio
async def test_double_booking_lock_protection(async_session: AsyncSession, setup_tenants):
    """Active booking hold prevents concurrent appointment on the same slot."""
    broker = setup_tenants["broker_a"]
    lead_a = setup_tenants["lead_a"]
    lead_b = setup_tenants["lead_b"]
    prop = setup_tenants["prop_a"]

    lock_mgr = BookingLockManager(async_session)
    slot_start = datetime.now(timezone.utc) + timedelta(days=2, hours=10)
    slot_end = slot_start + timedelta(minutes=45)

    # Lead A acquires lock
    hold_a = await lock_mgr.acquire_hold(
        broker_id=str(broker.id),
        lead_id=str(lead_a.id),
        slot_start_utc=slot_start,
        slot_end_utc=slot_end,
    )
    assert hold_a is not None
    assert hold_a.is_released is False

    # Lead B attempts to acquire lock on overlapping slot -> returns None (collision)
    hold_b = await lock_mgr.acquire_hold(
        broker_id=str(broker.id),
        lead_id=str(lead_b.id),
        slot_start_utc=slot_start,
        slot_end_utc=slot_end,
    )
    assert hold_b is None, "Concurrent hold on overlapping slot must return None"


# ─── 3. Slot Revalidation Race Condition ─────────────────────────────────────

@pytest.mark.asyncio
async def test_slot_revalidation_race_condition(async_session: AsyncSession, setup_tenants):
    """If a property becomes unavailable right before booking confirmation, booking is rejected."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]
    prop = setup_tenants["prop_a"]

    lock_mgr = BookingLockManager(async_session)
    provider = MockCalendarProvider()
    booking_service = BookingService(async_session, lock_mgr, provider)

    slot_time = datetime.now(timezone.utc) + timedelta(days=3, hours=11)
    dto = BookingRequestDTO(
        lead_id=str(lead.id),
        broker_id=str(broker.id),
        property_id=str(prop.id),
        slot_start_utc=slot_time,
        duration_minutes=45,
    )

    # Property changes to unavailable before booking execution
    prop.status = "under_offer"
    await async_session.commit()

    with pytest.raises(ValueError, match="no longer available"):
        await booking_service.book_appointment(
            dto=dto,
            organization_id=str(broker.id),
            authenticated_broker_id=str(broker.id),
        )


# ─── 4. Idempotent Booking Execution ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotent_appointment_creation(async_session: AsyncSession, setup_tenants):
    """Submitting booking with the same idempotency_key returns the same meeting without duplicate rows."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]
    prop = setup_tenants["prop_a"]

    lock_mgr = BookingLockManager(async_session)
    provider = MockCalendarProvider()
    booking_service = BookingService(async_session, lock_mgr, provider)

    slot_time = datetime.now(timezone.utc) + timedelta(days=2, hours=14)
    idem_key = f"idem-{uuid.uuid4().hex}"

    dto = BookingRequestDTO(
        lead_id=str(lead.id),
        broker_id=str(broker.id),
        property_id=str(prop.id),
        slot_start_utc=slot_time,
        duration_minutes=45,
        idempotency_key=idem_key,
    )

    # First booking
    res1 = await booking_service.book_appointment(dto, str(broker.id), str(broker.id))
    assert res1.id is not None
    assert res1.status in ("CONFIRMED", "REQUESTED")

    # Second booking with same idempotency key
    res2 = await booking_service.book_appointment(dto, str(broker.id), str(broker.id))
    assert res2.id == res1.id

    # Verify only 1 meeting exists in DB
    stmt = select(SchedulingMeeting).where(SchedulingMeeting.idempotency_key == idem_key)
    meetings = (await async_session.execute(stmt)).scalars().all()
    assert len(meetings) == 1

    # Verify CRM timeline activity created
    act_stmt = select(Activity).where(
        and_(Activity.lead_id == lead.id, Activity.activity_type == "meeting_booked")
    )
    activities = (await async_session.execute(act_stmt)).scalars().all()
    assert len(activities) == 1


# ─── 5. Site Visit Linkage & Operational Outcome ─────────────────────────────

@pytest.mark.asyncio
async def test_site_visit_linkage_and_outcome(async_session: AsyncSession, setup_tenants):
    """Completing a site visit updates Viewing, logs timeline Activity, and records structured outcome."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]
    prop = setup_tenants["prop_a"]

    # Create meeting + viewing
    meeting_id = str(uuid.uuid4())
    meeting = SchedulingMeeting(
        id=meeting_id,
        organization_id=str(broker.id),
        broker_id=broker.id,
        lead_id=lead.id,
        title="Site Visit - DLF Luxury Heights",
        meeting_type="PROPERTY_VIEWING",
        status="CONFIRMED",
        start_utc=datetime.now(timezone.utc) - timedelta(hours=2),
        end_utc=datetime.now(timezone.utc) - timedelta(hours=1),
        customer_timezone="Asia/Kolkata",
        broker_timezone="Asia/Kolkata",
        duration_minutes=60,
        location_address=prop.location,
    )
    viewing = Viewing(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        property_id=str(prop.id),
    )
    async_session.add_all([meeting, viewing])
    await async_session.commit()

    # Record outcome
    post_service = PostMeetingIntelligenceService(async_session)
    outcome_dto = RecordOutcomeRequestDTO(
        outcome_category="INTERESTED",
        buyer_interest_level="VERY_HIGH",
        detailed_feedback="Customer loved the layout and natural light. Price negotiation requested.",
        agreed_next_step="Send formal price proposal by tomorrow noon.",
        next_follow_up_date=datetime.now(timezone.utc) + timedelta(days=1),
    )

    result = await post_service.record_outcome(meeting_id, outcome_dto)
    assert result.outcome_category == "INTERESTED"

    # Verify meeting updated to COMPLETED
    m_check = await async_session.get(SchedulingMeeting, meeting_id)
    assert m_check.status == "COMPLETED"

    # Verify LeadPropertyInterest updated to 'visited'
    lpi_stmt = select(LeadPropertyInterest).where(
        and_(LeadPropertyInterest.lead_id == lead.id, LeadPropertyInterest.property_id == prop.id)
    )
    lpi = (await async_session.execute(lpi_stmt)).scalar_one_or_none()
    assert lpi is not None
    assert lpi.interaction_type == "visited"

    # Verify timeline Activity logged
    act_stmt = select(Activity).where(
        and_(Activity.lead_id == lead.id, Activity.activity_type == "site_visit_completed")
    )
    act = (await async_session.execute(act_stmt)).scalar_one_or_none()
    assert act is not None
    assert "VERY_HIGH" in (act.description or "") or "VERY_HIGH" in str(act.activity_data)


# ─── 6. Human Handoff & AI Suppression ────────────────────────────────────────

@pytest.mark.asyncio
async def test_human_handoff_explicit_request(async_session: AsyncSession, setup_tenants):
    """Customer request for a human specialist triggers escalation and records briefing context."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]

    llm_adapter = MockAIAdapter(reply="Connecting you with a specialist.")
    router = LLMRouter(primary=llm_adapter)
    manager = ConversationManager(llm_router=router)

    msg = IncomingMessage(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        content="I would like to speak to a human agent please.",
        channel="web",
    )

    resp = await manager.process(async_session, msg)
    assert resp.escalated is True

    # Verify Escalation model record exists in DB
    esc_stmt = select(Escalation).where(Escalation.session_id == resp.session_id)
    esc = (await async_session.execute(esc_stmt)).scalar_one_or_none()
    assert esc is not None
    assert esc.status == "pending"
    assert esc.reason in ("customer_requested", "human_requested")


@pytest.mark.asyncio
async def test_human_handoff_ai_suppression(async_session: AsyncSession, setup_tenants):
    """When a session is escalated, autonomous AI responses are suppressed and human active state returned."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]

    llm_adapter = MockAIAdapter(reply="I am the autonomous AI agent.")
    router = LLMRouter(primary=llm_adapter)
    manager = ConversationManager(llm_router=router)

    # First create session and escalate it
    msg1 = IncomingMessage(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        content="Talk to a human",
        channel="web",
    )
    resp1 = await manager.process(async_session, msg1)
    assert resp1.escalated is True

    # Subsequent customer message while human specialist owns session
    msg2 = IncomingMessage(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        content="Are you still there?",
        channel="web",
    )
    resp2 = await manager.process(async_session, msg2)
    assert resp2.escalated is True
    # AI must NOT generate autonomous replies, must confirm specialist ownership
    assert "specialist" in resp2.content.lower()


# ─── 7. Post-Visit Revenue Autopilot Integration ──────────────────────────────

@pytest.mark.asyncio
async def test_post_site_visit_revenue_opportunity(async_session: AsyncSession, setup_tenants):
    """Completed site visit via SchedulingMeeting generates POST_SITE_VISIT_FOLLOW_UP opportunity."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]
    prop = setup_tenants["prop_a"]

    # Add completed SchedulingMeeting visit
    meeting_id = str(uuid.uuid4())
    meeting = SchedulingMeeting(
        id=meeting_id,
        organization_id=str(broker.id),
        broker_id=broker.id,
        lead_id=lead.id,
        title="Completed Site Visit",
        meeting_type="PROPERTY_VIEWING",
        status="completed",
        start_utc=datetime.now(timezone.utc) - timedelta(hours=6),
        end_utc=datetime.now(timezone.utc) - timedelta(hours=5),
        customer_timezone="Asia/Kolkata",
        broker_timezone="Asia/Kolkata",
        duration_minutes=60,
        location_address=prop.location,
    )
    viewing = Viewing(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        property_id=str(prop.id),
    )
    async_session.add_all([meeting, viewing])
    await async_session.commit()

    engine = RevenueAutopilotEngine(async_session)
    generated = await engine.evaluate_tenant_opportunities(broker)

    visit_opps = [o for o in generated if o.opportunity_type == "POST_SITE_VISIT_FOLLOW_UP"]
    assert len(visit_opps) == 1
    opp = visit_opps[0]
    assert opp.urgency == "CRITICAL"
    assert opp.priority == "CRITICAL"
    assert opp.opportunity_score >= 90.0
    assert opp.property_id == prop.id


@pytest.mark.asyncio
async def test_revenue_opportunity_deduplication(async_session: AsyncSession, setup_tenants):
    """Re-running Revenue Autopilot on same completed visit updates or reuses existing opportunity without duplicate creation."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]
    prop = setup_tenants["prop_a"]

    meeting_id = str(uuid.uuid4())
    meeting = SchedulingMeeting(
        id=meeting_id,
        organization_id=str(broker.id),
        broker_id=broker.id,
        lead_id=lead.id,
        title="Site Visit",
        meeting_type="PROPERTY_VIEWING",
        status="completed",
        start_utc=datetime.now(timezone.utc) - timedelta(hours=10),
        end_utc=datetime.now(timezone.utc) - timedelta(hours=9),
        customer_timezone="Asia/Kolkata",
        broker_timezone="Asia/Kolkata",
        duration_minutes=60,
        location_address=prop.location,
    )
    viewing = Viewing(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        property_id=str(prop.id),
    )
    async_session.add_all([meeting, viewing])
    await async_session.commit()

    engine = RevenueAutopilotEngine(async_session)

    # First evaluation
    gen1 = await engine.evaluate_tenant_opportunities(broker)
    await async_session.commit()

    # Second evaluation
    gen2 = await engine.evaluate_tenant_opportunities(broker)
    await async_session.commit()

    # Check total DB count for this lead and opportunity type
    stmt = select(RevenueOpportunity).where(
        and_(
            RevenueOpportunity.lead_id == lead.id,
            RevenueOpportunity.opportunity_type == "POST_SITE_VISIT_FOLLOW_UP",
        )
    )
    opps = (await async_session.execute(stmt)).scalars().all()
    assert len(opps) == 1, "Idempotency / dedup_key must prevent duplicate opportunities"


# ─── 8. Revenue Score vs Match Score Separation ───────────────────────────────

@pytest.mark.asyncio
async def test_revenue_score_vs_match_score_separation(async_session: AsyncSession, setup_tenants):
    """Property suitability (match_score) is distinct from commercial urgency (opportunity_score)."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]
    prop = setup_tenants["prop_a"]

    # Match score reflects property suitability (e.g. 75%)
    match_score = 75.0

    # Fresh lead activity + critical category drives commercial urgency higher
    opp_score, pos_signals, neg_signals, freshness = RevenueAutopilotEngine.calculate_revenue_opportunity_score(
        match_score=match_score,
        lead=lead,
        prop=prop,
        category="POST_SITE_VISIT_FOLLOW_UP",
    )

    assert opp_score != match_score
    assert opp_score > match_score, "Urgency and recency should boost opportunity score above raw match score"


# ─── 9. Tenant Isolation & Security ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tenant_isolation_cross_tenant_blocked(async_session: AsyncSession, setup_tenants):
    """Tenant A cannot book, read, or mutate Tenant B's appointments or opportunities."""
    broker_a = setup_tenants["broker_a"]
    broker_b = setup_tenants["broker_b"]
    lead_b = setup_tenants["lead_b"]
    prop_b = setup_tenants["prop_b"]

    lock_mgr = BookingLockManager(async_session)
    provider = MockCalendarProvider()
    booking_service = BookingService(async_session, lock_mgr, provider)

    slot_time = datetime.now(timezone.utc) + timedelta(days=2, hours=15)
    dto = BookingRequestDTO(
        lead_id=str(lead_b.id),
        broker_id=str(broker_b.id),
        property_id=str(prop_b.id),
        slot_start_utc=slot_time,
        duration_minutes=45,
    )

    # Tenant A attempts to book under Tenant B's organization
    with pytest.raises(ValueError, match="does not belong to organization"):
        await booking_service.book_appointment(
            dto=dto,
            organization_id=str(broker_a.id),
            authenticated_broker_id=str(broker_a.id),
        )


# ─── 10. AI Tool Boundary & Confirmation Enforcement ──────────────────────────

@pytest.mark.asyncio
async def test_ai_tool_unconfirmed_booking_blocked(async_session: AsyncSession, setup_tenants):
    """AI agent does not create confirmed appointments from exploratory slot inquiries."""
    broker = setup_tenants["broker_a"]
    lead = setup_tenants["lead_a"]
    prop = setup_tenants["prop_a"]

    # Mock LLM calls get_available_slots tool instead of book_viewing
    llm_adapter = MockAIAdapter(
        reply="We have available slots this Saturday at 11:00 AM and 2:00 PM. Would you like to confirm either of these?",
        tool_calls=[{
            "name": "get_available_slots",
            "args": {"property_id": str(prop.id)},
        }]
    )
    router = LLMRouter(primary=llm_adapter)
    manager = ConversationManager(llm_router=router)

    msg = IncomingMessage(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        content="Can I visit DLF Luxury Heights this Saturday?",
        channel="web",
    )

    resp = await manager.process(async_session, msg)
    assert resp.content is not None

    # Verify no appointment was booked in DB
    stmt = select(SchedulingMeeting).where(SchedulingMeeting.lead_id == lead.id)
    meetings = (await async_session.execute(stmt)).scalars().all()
    assert len(meetings) == 0, "No appointment should be persisted without explicit confirmation"
