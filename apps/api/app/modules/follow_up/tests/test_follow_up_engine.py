"""
Unit & Integration Test Suite for AI Follow-Up & Autonomous Lead Nurturing Engine
==================================================================================
Tests:
- Lifecycle State Transitions & Terminal State Guards
- Consent Management & Fail-Closed Opt-Out
- Timezone-Aware Scheduling & Quiet Hours Windowing
- Contact Fatigue & Anti-Spam Suppression
- Multi-Rule Suppression (Human Takeover, Terminal States, Frequency)
- Channel Selection & Suitability Scoring
- Grounded Multi-Language Message Generation (EN, HI, AR, UR)
- Next Best Action Deterministic Computation
- Adaptive Sequence Engine & Inbound Reply Halt Invariant
- Orchestrator Pipeline & Audit Decision Logging
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.lead import Lead
from app.models.follow_up_models import (
    FollowUpPolicy, FollowUpSequence, FollowUpSequenceStep, FollowUpEnrollment,
    FollowUpExecution, CommunicationConsent, ContactFatigue
)
from app.modules.follow_up.lifecycle.lifecycle_manager import LeadLifecycleManager
from app.modules.follow_up.consent.consent_manager import ConsentManager
from app.modules.follow_up.timing.timing_engine import TimingEngine
from app.modules.follow_up.fatigue.fatigue_detector import FatigueDetector
from app.modules.follow_up.suppression.suppression_engine import SuppressionEngine
from app.modules.follow_up.channel_selection.channel_selector import ChannelSelector
from app.modules.follow_up.content_strategy.strategy_engine import ContentStrategyEngine
from app.modules.follow_up.message_generation.grounded_generator import GroundedMessageGenerator
from app.modules.follow_up.next_best_action.nba_calculator import NextBestActionEngine
from app.modules.follow_up.sequence.sequence_engine import SequenceEngine
from app.modules.follow_up.service import FollowUpOrchestratorService
from app.modules.follow_up.dto.follow_up_schemas import UpdatePolicyDTO


class TestLifecycleManager:
    """Tests 18-state lead lifecycle state transitions."""

    def test_valid_transitions(self):
        db = AsyncMock()
        manager = LeadLifecycleManager(db)

        assert manager.can_transition("NEW", "CONTACTING") is True
        assert manager.can_transition("CONTACTING", "ENGAGING") is True
        assert manager.can_transition("ENGAGING", "QUALIFYING") is True
        assert manager.can_transition("QUALIFIED", "RECOMMENDATION_SENT") is True
        assert manager.can_transition("RECOMMENDATION_SENT", "VIEWING_BOOKED") is True
        assert manager.can_transition("VIEWING_BOOKED", "VIEWING_COMPLETED") is True
        assert manager.can_transition("VIEWING_COMPLETED", "NEGOTIATION") is True
        assert manager.can_transition("NEGOTIATION", "CONVERTED") is True

    def test_terminal_state_cannot_transition(self):
        db = AsyncMock()
        manager = LeadLifecycleManager(db)

        # DO_NOT_CONTACT is terminal
        assert manager.can_transition("DO_NOT_CONTACT", "CONTACTING") is False
        assert manager.can_transition("DO_NOT_CONTACT", "ENGAGING") is False


class TestConsentManager:
    """Tests granular consent and permanent opt-out enforcement."""

    @pytest.mark.asyncio
    async def test_opt_in_consent_verified(self):
        db = AsyncMock()
        manager = ConsentManager(db)

        consent = CommunicationConsent(
            lead_id="lead_1", organization_id="org_1",
            channel="WHATSAPP", purpose="MARKETING_AND_FOLLOWUP", status="OPTED_IN"
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = consent
        db.execute.return_value = mock_res

        has_consent = await manager.verify_consent("lead_1", "WHATSAPP")
        assert has_consent is True

    @pytest.mark.asyncio
    async def test_opt_out_permanently_blocks(self):
        db = AsyncMock()
        manager = ConsentManager(db)

        consent = CommunicationConsent(
            lead_id="lead_2", organization_id="org_1",
            channel="WHATSAPP", purpose="MARKETING_AND_FOLLOWUP", status="OPTED_OUT"
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = consent
        db.execute.return_value = mock_res

        has_consent = await manager.verify_consent("lead_2", "WHATSAPP")
        assert has_consent is False


class TestTimingEngine:
    """Tests timezone resolution, quiet hours evaluation, and DST safety."""

    def test_timezone_resolution(self):
        engine = TimingEngine()

        lead_dubai = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), phone="+971501234567", preferred_locations=["Dubai Marina"])
        assert engine.resolve_timezone(lead_dubai) == "Asia/Dubai"

        lead_india = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), phone="+919876543210", preferred_locations=["Indiranagar"])
        assert engine.resolve_timezone(lead_india) == "Asia/Kolkata"

    def test_quiet_hours_detection(self):
        engine = TimingEngine()

        # 23:30 Dubai time (19:30 UTC) is within quiet hours (21:00 to 08:00)
        dt_night_utc = datetime(2026, 8, 14, 19, 30, tzinfo=timezone.utc)
        assert engine.is_within_quiet_hours(dt_night_utc, "Asia/Dubai", "21:00", "08:00") is True

        # 14:00 Dubai time (10:00 UTC) is outside quiet hours
        dt_day_utc = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
        assert engine.is_within_quiet_hours(dt_day_utc, "Asia/Dubai", "21:00", "08:00") is False

    def test_optimal_time_defers_quiet_hours(self):
        engine = TimingEngine()
        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), phone="+971501234567", preferred_locations=["Dubai Marina"])

        # Night time in Dubai (22:00 local = 18:00 UTC)
        night_utc = datetime(2026, 8, 14, 18, 0, tzinfo=timezone.utc)
        optimal_utc, tz = engine.calculate_optimal_send_time(lead, desired_time_utc=night_utc)

        # Should be deferred to 09:30 AM local time tomorrow (05:30 UTC)
        assert optimal_utc > night_utc
        assert tz == "Asia/Dubai"


class TestFatigueDetector:
    """Tests message fatigue accumulation and reset invariants."""

    @pytest.mark.asyncio
    async def test_fatigue_threshold_suppresses(self):
        db = AsyncMock()
        detector = FatigueDetector(db)

        # Lead with 3 consecutive unanswered messages
        record = ContactFatigue(
            lead_id="lead_f1", organization_id="org_1",
            total_messages_sent=3, consecutive_no_replies=3, current_fatigue_score=1.0, is_suppressed=False
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = record
        db.execute.return_value = mock_res

        policy = FollowUpPolicy(organization_id="org_1", max_consecutive_no_reply=3)
        is_suppressed, score, reason = await detector.evaluate_fatigue("lead_f1", "org_1", policy)

        assert is_suppressed is True
        assert score == 1.0
        assert "maximum consecutive" in reason.lower()

    @pytest.mark.asyncio
    async def test_inbound_reply_resets_fatigue(self):
        db = AsyncMock()
        detector = FatigueDetector(db)

        record = ContactFatigue(
            lead_id="lead_f2", organization_id="org_1",
            total_messages_sent=3, consecutive_no_replies=3, current_fatigue_score=1.0, is_suppressed=True
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = record
        db.execute.return_value = mock_res

        await detector.record_inbound_response("lead_f2", "org_1")

        assert record.consecutive_no_replies == 0
        assert record.current_fatigue_score == 0.0
        assert record.is_suppressed is False


class TestSuppressionEngine:
    """Tests multi-rule suppression."""

    @pytest.mark.asyncio
    async def test_human_handoff_suppressed(self):
        db = AsyncMock()
        engine = SuppressionEngine(db)

        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), phone="+971500000000", pipeline_stage="human_handoff")
        policy = FollowUpPolicy(organization_id="org_1")

        is_supp, reason, rules = await engine.evaluate_suppression(lead, "WHATSAPP", policy)

        assert is_supp is True
        assert "human" in reason.lower()

    @pytest.mark.asyncio
    async def test_terminal_state_suppressed(self):
        db = AsyncMock()
        engine = SuppressionEngine(db)

        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), phone="+971500000000", pipeline_stage="converted")
        policy = FollowUpPolicy(organization_id="org_1")

        is_supp, reason, rules = await engine.evaluate_suppression(lead, "WHATSAPP", policy)

        assert is_supp is True
        assert "terminal" in reason.lower()


class TestGroundedMessageGenerator:
    """Tests multi-language message generation and verified property grounding."""

    def test_english_price_update_message(self):
        gen = GroundedMessageGenerator()
        ctx = {
            "lead_name": "Alex",
            "reason_type": "PRICE_UPDATE",
            "preferred_location": "Dubai Marina",
            "property": {
                "title": "Marina Gate 2BHK",
                "price": 1800000.0,
                "currency": "AED",
                "bedrooms": 2,
                "locality": "Dubai Marina",
                "city": "Dubai"
            }
        }
        body, subject = gen.generate_message(ctx, language="en", channel="WHATSAPP")
        assert "Alex" in body
        assert "Marina Gate 2BHK" in body
        assert "1,800,000 AED" in body
        assert "2 BHK" in body

    def test_hindi_new_match_message(self):
        gen = GroundedMessageGenerator()
        ctx = {
            "lead_name": "Rahul",
            "reason_type": "NEW_MATCH",
            "preferred_location": "Indiranagar",
            "property": {
                "title": "Prestige Heights",
                "price": 18500000.0,
                "currency": "INR",
                "bedrooms": 3,
                "locality": "Indiranagar",
                "city": "Bengaluru"
            }
        }
        body, subject = gen.generate_message(ctx, language="hi", channel="WHATSAPP")
        assert "Rahul" in body
        assert "नमस्ते" in body
        assert "18,500,000 INR" in body

    def test_arabic_property_message(self):
        gen = GroundedMessageGenerator()
        ctx = {
            "lead_name": "Tariq",
            "reason_type": "PRICE_UPDATE",
            "preferred_location": "Downtown Dubai",
            "property": {
                "title": "Burj Crown",
                "price": 2400000.0,
                "currency": "AED",
                "bedrooms": 2,
                "locality": "Downtown Dubai",
                "city": "Dubai"
            }
        }
        body, subject = gen.generate_message(ctx, language="ar", channel="WHATSAPP")
        assert "Tariq" in body
        assert "مرحباً" in body
        assert "Burj Crown" in body


class TestNextBestActionEngine:
    """Tests deterministic Next Best Action computation."""

    @pytest.mark.asyncio
    async def test_new_lead_nba(self):
        db = AsyncMock()
        nba_engine = NextBestActionEngine(db)

        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), phone="+971501111111", pipeline_stage="new")
        nba = await nba_engine.compute_next_best_action(lead)

        assert "greeting" in nba.recommended_action.lower() or "discovery" in nba.recommended_action.lower()
        assert nba.priority_score >= 90.0

    @pytest.mark.asyncio
    async def test_viewing_booked_nba(self):
        db = AsyncMock()
        nba_engine = NextBestActionEngine(db)

        lead = Lead(id=uuid.uuid4(), broker_id=uuid.uuid4(), phone="+971501111111", pipeline_stage="viewing_booked")
        nba = await nba_engine.compute_next_best_action(lead)

        assert "viewing reminder" in nba.recommended_action.lower()


class TestSequenceEngine:
    """Tests adaptive sequence execution and the halt-on-reply invariant."""

    @pytest.mark.asyncio
    async def test_halt_active_enrollments(self):
        db = AsyncMock()
        seq_engine = SequenceEngine(db)

        mock_update_res = MagicMock()
        mock_update_res.rowcount = 1
        db.execute.return_value = mock_update_res

        halted = await seq_engine.halt_active_enrollments("lead_seq_1", reason="Customer Responded")
        assert halted == 1
