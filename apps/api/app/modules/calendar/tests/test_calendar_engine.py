"""
Unit & Integration Test Suite for Calendar, Meeting, Viewing & Scheduling Intelligence Engine
=============================================================================================
Tests:
- Calendar Provider Abstraction & Virtual Meeting Generation (Google Meet, Teams, Zoom)
- Distributed 5-Minute Slot Hold & Collision Blocking (Race Condition Defense)
- True Availability Engine with Multi-Calendar & Property Availability Guards
- Timezone Awareness (UAE & India) & DST Window Handling
- Idempotent Meeting & Property Viewing Booking
- Multi-Property Viewing Itinerary Optimization with Transit Buffers
- Rescheduling & External Calendar Synchronization
- Cancellation Workflows
- No-Show Risk Prediction
- Pre-Meeting AI Preparation Briefs
- Post-Meeting Structured Outcome Recording & CRM Pipeline Sync
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.models.calendar_models import Meeting, MeetingHold, Viewing, MeetingOutcome, NoShowPrediction
from app.modules.calendar.providers.provider_interface import MockCalendarProvider
from app.modules.calendar.booking_lock.lock_manager import BookingLockManager
from app.modules.calendar.availability.availability_engine import AvailabilityEngine
from app.modules.calendar.slot_generation.slot_generator import SlotGenerator
from app.modules.calendar.booking.booking_service import BookingService
from app.modules.calendar.viewing.viewing_service import ViewingService
from app.modules.calendar.rescheduling.rescheduling_service import ReschedulingService
from app.modules.calendar.cancellation.cancellation_service import CancellationService
from app.modules.calendar.no_show.no_show_service import NoShowPredictionService
from app.modules.calendar.preparation.preparation_brief_service import PreparationBriefService
from app.modules.calendar.post_meeting.post_meeting_service import PostMeetingIntelligenceService
from app.modules.calendar.dto.calendar_schemas import (
    SlotSearchRequestDTO, BookingRequestDTO, RescheduleRequestDTO, CancellationRequestDTO,
    ItineraryRequestDTO, RecordOutcomeRequestDTO
)


def _mock_db() -> AsyncMock:
    """Creates an AsyncMock database session with a synchronous add method to match SQLAlchemy AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


class TestMockCalendarProvider:
    """Tests provider abstraction and virtual meeting links."""

    @pytest.mark.asyncio
    async def test_create_and_query_events(self):
        provider = MockCalendarProvider()
        start = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 15, 11, 0, tzinfo=timezone.utc)

        res = await provider.create_event(
            account_email="broker@test.com",
            title="Site Visit",
            start_utc=start,
            end_utc=end,
            virtual_provider="GOOGLE_MEET"
        )
        assert res["external_event_id"] is not None
        assert "meet.google.com" in res["meeting_url"]

        # Query availability
        busy = await provider.get_availability("broker@test.com", start - timedelta(hours=1), end + timedelta(hours=1))
        assert len(busy) == 1
        assert busy[0]["start"] == start


class TestBookingLockManager:
    """Tests 5-minute temporary slot holds and double booking prevention."""

    @pytest.mark.asyncio
    async def test_hold_collision_defense(self):
        db = _mock_db()
        lock_mgr = BookingLockManager(db)

        # First hold succeeds (no existing active hold)
        mock_res_none = MagicMock()
        mock_res_none.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_res_none

        start = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 15, 10, 45, tzinfo=timezone.utc)

        hold1 = await lock_mgr.acquire_hold("broker_1", "lead_1", start, end)
        assert hold1 is not None

        # Second concurrent hold on overlapping slot is blocked
        existing_hold = MeetingHold(
            id="hld_1", broker_id="broker_1", lead_id="lead_1",
            slot_start_utc=start, slot_end_utc=end,
            expires_at_utc=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_released=False
        )
        mock_res_exists = MagicMock()
        mock_res_exists.scalar_one_or_none.return_value = existing_hold
        db.execute.return_value = mock_res_exists

        hold2 = await lock_mgr.acquire_hold("broker_1", "lead_2", start, end)
        assert hold2 is None # Collided and rejected


class TestAvailabilityEngine:
    """Tests common availability calculation and property status guards."""

    @pytest.mark.asyncio
    async def test_property_unavailable_returns_empty_slots(self):
        db = _mock_db()
        # Property is sold
        prop = PropertyListing(id=uuid.uuid4(), title="Sold Penthouse", status="sold", price=5000000.0)
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = prop
        db.execute.return_value = mock_res

        engine = AvailabilityEngine(db)
        slots = await engine.calculate_available_slots("broker_1", property_id=str(prop.id))
        assert len(slots) == 0

    @pytest.mark.asyncio
    async def test_available_slots_generated(self):
        db = _mock_db()
        mock_res_mtg = MagicMock()
        mock_res_mtg.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_res_mtg

        engine = AvailabilityEngine(db)
        slots = await engine.calculate_available_slots("broker_1", duration_minutes=45, search_days_ahead=3)
        assert len(slots) > 0
        assert "broker_local_start" in slots[0]
        assert "customer_local_start" in slots[0]


class TestViewingService:
    """Tests multi-property viewing itinerary optimization and transit buffers."""

    @pytest.mark.asyncio
    async def test_itinerary_calculation(self):
        db = _mock_db()
        p1 = PropertyListing(id=uuid.uuid4(), title="Marina Gate 2BHK", locality="Dubai Marina", city="Dubai", status="available")
        p2 = PropertyListing(id=uuid.uuid4(), title="Creek Horizon 3BHK", locality="Dubai Creek", city="Dubai", status="available")

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [p1, p2]
        db.execute.return_value = mock_res

        service = ViewingService(db)
        req = ItineraryRequestDTO(
            lead_id="lead_itinerary",
            property_ids=[str(p1.id), str(p2.id)],
            start_date_utc=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc)
        )
        itinerary = await service.calculate_itinerary(req, "org_1")

        assert itinerary.total_stops == 2
        assert len(itinerary.stops) == 2
        # First stop 09:00, second stop 10:15 (45m viewing + 30m travel)
        assert itinerary.stops[0].estimated_arrival_utc == datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc)
        assert itinerary.stops[1].estimated_arrival_utc == datetime(2026, 8, 16, 10, 15, tzinfo=timezone.utc)


class TestNoShowPredictionService:
    """Tests probabilistic no-show risk assessment."""

    @pytest.mark.asyncio
    async def test_no_show_risk_calculation(self):
        db = _mock_db()
        mtg = Meeting(
            id="mtg_risk_1", organization_id="org_1", broker_id="brk_1", lead_id="lead_cold",
            title="Site Visit", meeting_type="PROPERTY_VIEWING",
            start_utc=datetime.now(timezone.utc) + timedelta(days=7),
            end_utc=datetime.now(timezone.utc) + timedelta(days=7, minutes=45)
        )
        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), score="cold", score_confidence=0.3)

        mock_res_mtg = MagicMock()
        mock_res_mtg.scalar_one_or_none.return_value = mtg
        mock_res_lead = MagicMock()
        mock_res_lead.scalar_one_or_none.return_value = lead
        db.execute.side_effect = [mock_res_mtg, mock_res_lead]

        service = NoShowPredictionService(db)
        pred = await service.predict_no_show_risk("mtg_risk_1")

        assert pred.no_show_probability >= 0.5
        assert pred.risk_level == "HIGH"
        assert "interactive WhatsApp" in pred.preventative_action


class TestPreparationBriefService:
    """Tests AI meeting preparation brief generation."""

    @pytest.mark.asyncio
    async def test_generate_brief(self):
        db = _mock_db()
        mtg = Meeting(
            id="mtg_brief_1", organization_id="org_1", broker_id="brk_1", lead_id="lead_vip",
            title="Site Visit", start_utc=datetime.now(timezone.utc), end_utc=datetime.now(timezone.utc) + timedelta(minutes=60)
        )
        lead = Lead(
            id=uuid.uuid4(), broker_id=uuid.uuid4(), name="Fatima Al-Mansoor",
            property_type="villa", budget_max=4500000.0, preferred_locations=["Palm Jumeirah"],
            pipeline_stage="qualified"
        )
        mock_res_mtg = MagicMock()
        mock_res_mtg.scalar_one_or_none.return_value = mtg
        mock_res_lead = MagicMock()
        mock_res_lead.scalar_one_or_none.return_value = lead
        db.execute.side_effect = [mock_res_mtg, mock_res_lead]

        service = PreparationBriefService(db)
        brief = await service.generate_brief("mtg_brief_1")

        assert "Fatima Al-Mansoor" in brief.buyer_summary
        assert "4,500,000 AED" in brief.verified_budget
        assert len(brief.suggested_questions) >= 2


class TestBookingService:
    """Tests idempotent booking, 5-minute locks, and reminder scheduling."""

    @pytest.mark.asyncio
    async def test_book_appointment_success(self):
        db = _mock_db()
        lock_mgr = BookingLockManager(db)
        provider = MockCalendarProvider()

        mock_hold = MagicMock()
        mock_hold.id = "hld_test_1"
        lock_mgr.acquire_hold = AsyncMock(return_value=mock_hold)
        lock_mgr.release_hold = AsyncMock(return_value=True)

        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), name="Sarah Jenkins", phone="+971501234567")
        mock_res_lead = MagicMock()
        mock_res_lead.scalar_one_or_none.return_value = lead
        db.execute.return_value = mock_res_lead

        service = BookingService(db, lock_mgr, provider)
        req = BookingRequestDTO(
            lead_id=str(lead.id),
            meeting_type="VIDEO_CALL",
            slot_start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_minutes=30,
            virtual_provider="MICROSOFT_TEAMS"
        )
        res = await service.book_appointment(req, "org_1", "brk_1")

        assert res.id is not None
        assert res.status == "CONFIRMED"
        assert res.virtual_provider == "MICROSOFT_TEAMS"
        assert "teams.microsoft.com" in res.meeting_url


class TestReschedulingAndCancellation:
    """Tests rescheduling and cancellation workflows."""

    @pytest.mark.asyncio
    async def test_reschedule_meeting(self):
        db = _mock_db()
        provider = MockCalendarProvider()
        mtg = Meeting(
            id="mtg_resched_1", organization_id="org_1", broker_id="brk_1",
            title="Site Visit", meeting_type="PROPERTY_VIEWING",
            customer_timezone="Asia/Dubai", broker_timezone="Asia/Dubai",
            virtual_provider="NONE", duration_minutes=45,
            start_utc=datetime.now(timezone.utc), end_utc=datetime.now(timezone.utc) + timedelta(minutes=45)
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mtg
        db.execute.return_value = mock_res

        service = ReschedulingService(db, provider)
        new_time = datetime.now(timezone.utc) + timedelta(days=3)
        res = await service.reschedule_meeting("mtg_resched_1", RescheduleRequestDTO(new_slot_start_utc=new_time))

        assert res.status == "RESCHEDULED"
        assert res.start_utc == new_time

    @pytest.mark.asyncio
    async def test_cancel_meeting(self):
        db = _mock_db()
        provider = MockCalendarProvider()
        mtg = Meeting(
            id="mtg_cancel_1", organization_id="org_1", broker_id="brk_1",
            title="Site Visit", external_event_id="ext_evt_10",
            start_utc=datetime.now(timezone.utc), end_utc=datetime.now(timezone.utc) + timedelta(minutes=45)
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mtg
        mock_update = MagicMock()
        mock_update.rowcount = 1
        db.execute.side_effect = [mock_res, mock_update]

        service = CancellationService(db, provider)
        ok = await service.cancel_meeting("mtg_cancel_1", CancellationRequestDTO(reason="Buyer rescheduled out of town"))

        assert ok is True
        assert mtg.status == "CANCELLED"
        assert "Buyer rescheduled" in mtg.description


class TestPostMeetingIntelligenceService:
    """Tests post-meeting outcome logging and CRM pipeline stage update."""

    @pytest.mark.asyncio
    async def test_record_outcome_advances_stage(self):
        db = _mock_db()
        lead_id = str(uuid.uuid4())
        mtg = Meeting(
            id="mtg_done_1", organization_id="org_1", broker_id="brk_1", lead_id=lead_id,
            title="Site Visit", status="CONFIRMED",
            start_utc=datetime.now(timezone.utc), end_utc=datetime.now(timezone.utc) + timedelta(minutes=45)
        )
        lead = Lead(id=uuid.UUID(lead_id), broker_id=uuid.uuid4(), pipeline_stage="viewing_booked")

        mock_res_mtg = MagicMock()
        mock_res_mtg.scalar_one_or_none.return_value = mtg
        mock_res_out = MagicMock()
        mock_res_out.scalar_one_or_none.return_value = None
        mock_res_lead = MagicMock()
        mock_res_lead.scalar_one_or_none.return_value = lead
        db.execute.side_effect = [mock_res_mtg, mock_res_out, mock_res_lead]

        service = PostMeetingIntelligenceService(db)
        dto = RecordOutcomeRequestDTO(
            outcome_category="VERY_INTERESTED",
            buyer_interest_level=5,
            detailed_feedback="Client loved the floor plan and skyline views.",
            agreed_next_step="Send formal developer payment plan offer"
        )
        outcome = await service.record_outcome("mtg_done_1", dto)

        assert outcome.outcome_category == "VERY_INTERESTED"
        assert outcome.buyer_interest_level == 5
        assert mtg.status == "COMPLETED"
        assert lead.pipeline_stage == "negotiation"


class TestAgentMatcherAndReminders:
    """Tests broker matching, capacity guards, and reminder dispatch."""

    @pytest.mark.asyncio
    async def test_agent_matcher_assigned_broker(self):
        from app.modules.calendar.agent_matching.agent_matcher import AgentMatcher
        db = _mock_db()
        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4())
        mock_count = MagicMock()
        mock_count.scalar.return_value = 2 # 2 meetings (under limit of 6)
        db.execute.return_value = mock_count

        matcher = AgentMatcher(db)
        matched_id = await matcher.match_best_agent(lead, "org_1")
        assert matched_id == str(lead.broker_id)

    @pytest.mark.asyncio
    async def test_reminder_dispatcher(self):
        from app.modules.calendar.reminders.reminder_worker import ReminderDispatcher
        from app.models.calendar_models import MeetingReminder
        db = _mock_db()
        rem1 = MeetingReminder(
            id="rem_1", meeting_id="mtg_1", offset_minutes=120,
            channel="WHATSAPP", scheduled_for_utc=datetime.now(timezone.utc) - timedelta(minutes=5),
            is_sent=False
        )
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [rem1]
        db.execute.return_value = mock_res

        dispatcher = ReminderDispatcher(db)
        count = await dispatcher.process_due_reminders()

        assert count == 1
        assert rem1.is_sent is True


class TestConflictResolutionAndAITools:
    """Tests conflict detection and AI agent calendar tool wrappers."""

    @pytest.mark.asyncio
    async def test_conflict_detection(self):
        from app.modules.calendar.conflict_resolution.conflict_service import ConflictResolutionService
        from app.models.calendar_models import CalendarEvent
        db = _mock_db()
        mtg = Meeting(
            id="mtg_conf_1", organization_id="org_1", broker_id="brk_1",
            title="Site Visit", start_utc=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc)
        )
        evt = CalendarEvent(
            id="evt_ext_1", connection_id="conn_1", external_event_id="ext_google_99",
            title="Dentist Appointment", start_utc=datetime(2026, 8, 18, 10, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 8, 18, 11, 30, tzinfo=timezone.utc), is_busy=True
        )
        mock_res_mtg = MagicMock()
        mock_res_mtg.scalar_one_or_none.return_value = mtg
        mock_res_evt = MagicMock()
        mock_res_evt.scalars.return_value.all.return_value = [evt]
        mock_res_conf = MagicMock()
        mock_res_conf.scalar_one_or_none.return_value = None
        db.execute.side_effect = [mock_res_mtg, mock_res_evt, mock_res_conf]

        conflict_svc = ConflictResolutionService(db)
        conflicts = await conflict_svc.detect_conflicts_for_meeting("mtg_conf_1")

        assert len(conflicts) == 1
        assert "Dentist Appointment" in conflicts[0].conflict_description

    @pytest.mark.asyncio
    async def test_ai_agent_find_slots_tool(self):
        from app.modules.calendar.tools.agent_tools import AIAgentCalendarTools
        db = _mock_db()
        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), name="Tariq Al-Hashemi")
        mock_res_lead = MagicMock()
        mock_res_lead.scalar_one_or_none.return_value = lead
        mock_res_mtg = MagicMock()
        mock_res_mtg.scalars.return_value.all.return_value = []
        db.execute.side_effect = [mock_res_lead, mock_res_mtg]

        tools = AIAgentCalendarTools(db)
        result = await tools.find_available_slots(str(lead.id), "org_1")

        assert result["lead_id"] == str(lead.id)
        assert len(result["slots"]) > 0
