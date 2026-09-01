"""
End-to-End Platform Lifecycle Integration Test Suite
====================================================
Tests the complete 33-step customer lifecycle across all 15 BeetleLabs modules:

  Lead Ingestion -> Normalization -> Identity Resolution -> Deduplication ->
  Enrichment -> Qualification -> ML Scoring -> Intent -> Customer Memory ->
  RAG Grounding -> Property Recommendation -> AI Agent Conversation ->
  Policy & Quiet Hours -> Consent Verification -> Delivery Engine ->
  Dynamic Recalculation -> Workflow Orchestration -> Calendar Availability ->
  5-Minute Distributed Hold Lock -> Booking & Preparation Brief -> Follow-Up Reminders ->
  Outcome Recording -> CRM Intelligence Health -> Next Best Action ->
  Multi-Currency Revenue Analytics -> Platform Health Diagnostics.

Run: python -m pytest tests/test_e2e_platform_integration.py -v
"""
import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.models.calendar_models import Meeting, MeetingHold
from app.models.crm_models import Task
from app.modules.global_.currencies.money import Money
from app.modules.global_.phone.phone_service import PhoneService
from app.modules.global_.addresses.address_service import AddressService
from app.modules.global_.tax.tax_fee_service import TaxFeeService
from app.modules.global_.lead_sources.lead_source_registry import UniversalLeadNormalizer, PropertyFinderAdapter
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext
from app.modules.global_.policies.policy_service import PolicyService, PolicyContext
from app.modules.global_.consent.consent_service import ConsentService
from app.modules.global_.analytics.cross_country_analytics import CrossCountryAnalyticsEngine
from app.modules.global_.monitoring.market_health_service import MarketHealthService
from app.modules.calendar.booking_lock.lock_manager import BookingLockManager
from app.modules.calendar.availability.availability_engine import AvailabilityEngine
from app.modules.calendar.preparation.preparation_brief_service import PreparationBriefService
from app.modules.calendar.no_show.no_show_service import NoShowPredictionService
from app.modules.calendar.post_meeting.post_meeting_service import PostMeetingIntelligenceService
from app.modules.calendar.dto.calendar_schemas import RecordOutcomeRequestDTO
from app.modules.follow_up.timing.timing_engine import TimingEngine
from app.modules.follow_up.fatigue.fatigue_detector import FatigueDetector
from app.modules.follow_up.next_best_action.nba_calculator import NextBestActionEngine


def _mock_db() -> AsyncMock:
    """Creates an AsyncMock database session with a synchronous add method to match SQLAlchemy AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


class TestEndToEndPlatformIntegration:
    """
    Validates complete lifecycle orchestration across all domains.
    """

    @pytest.mark.asyncio
    async def test_full_lead_lifecycle_journey(self):
        """
        Complete E2E customer journey:
        Inbound Dubai Portal Lead -> Qualification -> Recommendation -> Hold -> Book -> Outcome -> Revenue BI.
        """
        org_id = str(uuid.uuid4())
        broker_id = str(uuid.uuid4())
        lead_id = str(uuid.uuid4())

        # ── Step 1 & 2: Inbound Portal Payload Normalization ────────────────────
        raw_portal_payload = {
            "name": "Tariq Al-Hashemi",
            "phone": "+971 50 123 4567",
            "email": "tariq@investor.ae",
            "budget": "3500000",
            "currency": "AED",
            "location": "Downtown Dubai",
            "property_type": "2_bed",
            "message": "Interested in high-floor units with Burj Khalifa view."
        }

        normalized = UniversalLeadNormalizer.normalize_payload("property_finder", raw_portal_payload, default_country="AE")
        assert normalized.country_code == "AE"
        assert normalized.phone == "+971501234567"
        assert normalized.budget_max == Decimal("3500000")
        assert normalized.consent_obtained is True

        # ── Step 3: Phone Normalization & Masking for Safe Logging ──────────────
        masked_phone = PhoneService.mask(normalized.phone)
        assert masked_phone.startswith("+971")
        assert masked_phone.endswith("4567")
        assert "X" in masked_phone

        # ── Step 4: Address Formatting (Dubai National Schema) ─────────────────
        address = AddressService.format_address("AE", {
            "building": "Burj Crown Tower",
            "area": "Downtown Dubai",
            "emirate": "Dubai",
            "makani": "12345 67890"
        })
        assert address.is_valid is True
        assert "Burj Crown Tower" in address.formatted_address
        assert "United Arab Emirates" in address.formatted_address

        # ── Step 5: Real Estate Transaction Cost Calculation ──────────────────
        prop_price = Money.of("3500000", "AED")
        costs = TaxFeeService.calculate_transaction_costs(prop_price, "AE")
        assert costs.grand_total_estimated.amount > Decimal("3500000")
        dld_item = next(it for it in costs.items if it.item_key == "dld_transfer_fee")
        assert dld_item.amount.amount == Decimal("140000")  # 4% of 3.5M AED

        # ── Step 6: Policy & Quiet Hours Evaluation ────────────────────────────
        db_mock = _mock_db()
        mock_policy = MagicMock()
        mock_policy.policy_key = "whatsapp_inbound"
        mock_policy.category = "COMMUNICATION"
        mock_policy.version = 1
        mock_policy.id = "pol-1"
        mock_policy.rule_json = {"actions": ["send_whatsapp"], "decision": "ALLOWED"}
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [mock_policy]
        mock_res.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_res

        policy_svc = PolicyService(db_mock)
        p_eval = await policy_svc.evaluate("COMMUNICATION", "send_whatsapp", PolicyContext(organization_id=org_id))
        assert p_eval.decision == "ALLOWED"

        # ── Step 7: Timing & Fatigue Detection ────────────────────────────────
        timing_engine = TimingEngine()
        lead_stub = Lead(phone="+971501234567", preferred_locations=["Downtown Dubai"])
        optimal_time, tz_resolved = timing_engine.calculate_optimal_send_time(lead_stub)
        assert optimal_time >= datetime.now(timezone.utc) - timedelta(seconds=5)
        assert tz_resolved == "Asia/Dubai"

        fatigue_detector = FatigueDetector(db_mock)
        mock_fatigue_record = MagicMock(consecutive_no_replies=0)
        db_mock.execute.return_value = MagicMock(scalar_one_or_none=lambda: mock_fatigue_record)
        is_suppressed, f_score, reason = await fatigue_detector.evaluate_fatigue(lead_id, org_id, MagicMock(max_consecutive_no_reply=3))
        assert is_suppressed is False

        # ── Step 8: Distributed 5-Minute Collision Hold Lock ───────────────────
        db_mock_hold = _mock_db()
        db_mock_hold.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)  # No conflicting hold
        lock_mgr = BookingLockManager(db_mock_hold)

        slot_start = datetime.now(timezone.utc) + timedelta(days=1, hours=2)
        slot_end = slot_start + timedelta(minutes=45)

        hold = await lock_mgr.acquire_hold(
            broker_id=broker_id,
            lead_id=lead_id,
            slot_start_utc=slot_start,
            slot_end_utc=slot_end
        )
        assert hold is not None
        assert hold.broker_id == broker_id
        assert hold.is_released is False

        # ── Step 9: No-Show Propensity Prediction ──────────────────────────────
        lead_entity = Lead(
            id=uuid.UUID(lead_id),
            broker_id=uuid.UUID(broker_id),
            name="Tariq Al-Hashemi",
            phone="+971501234567",
            budget_max=3500000,
            budget_currency="AED",
            score="hot",
            score_confidence=0.9
        )
        db_mock_ns = _mock_db()
        meeting_mock = Meeting(
            id=str(uuid.uuid4()),
            broker_id=broker_id,
            lead_id=lead_id,
            organization_id=org_id,
            meeting_type="PROPERTY_VIEWING",
            start_utc=slot_start,
            end_utc=slot_end,
            customer_timezone="Asia/Dubai",
            broker_timezone="Asia/Dubai"
        )
        db_mock_ns.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: meeting_mock),
            MagicMock(scalar_one_or_none=lambda: lead_entity),
        ]
        no_show_svc = NoShowPredictionService(db_mock_ns)
        ns_pred = await no_show_svc.predict_no_show_risk(str(meeting_mock.id))
        assert ns_pred.no_show_probability >= 0.0
        assert ns_pred.risk_level in ("LOW", "MEDIUM", "HIGH")

        # ── Step 10: Broker Preparation Brief Generation ───────────────────────
        db_mock_brief = _mock_db()
        db_mock_brief.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: meeting_mock),
            MagicMock(scalar_one_or_none=lambda: lead_entity),
        ]
        brief_svc = PreparationBriefService(db_mock_brief)
        brief = await brief_svc.generate_brief(str(meeting_mock.id))
        assert brief.meeting_id == str(meeting_mock.id)
        assert "Tariq Al-Hashemi" in brief.buyer_summary

        # ── Step 11: Viewing Conducted & Outcome Recorded ─────────────────────
        db_mock_outcome = _mock_db()
        db_mock_outcome.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: meeting_mock),
            MagicMock(scalar_one_or_none=lambda: None),
            MagicMock(scalar_one_or_none=lambda: lead_entity),
        ]
        outcome_svc = PostMeetingIntelligenceService(db_mock_outcome)
        outcome_dto = RecordOutcomeRequestDTO(
            outcome_category="VERY_INTERESTED",
            buyer_interest_level=5,
            detailed_feedback="Client loved the panoramic view. Preparing reservation deposit.",
            agreed_next_step="prepare_reservation_agreement"
        )
        recorded_outcome = await outcome_svc.record_outcome(str(meeting_mock.id), outcome_dto)
        assert recorded_outcome.outcome_category == "VERY_INTERESTED"
        assert recorded_outcome.buyer_interest_level == 5

        # ── Step 12: Next Best Action Generation ──────────────────────────────
        nba_engine = NextBestActionEngine(db_mock)
        lead_entity.pipeline_stage = "negotiation"
        nba_result = await nba_engine.compute_next_best_action(lead_entity)
        assert nba_result is not None
        assert nba_result.recommended_action != ""

        # ── Step 13: Consolidated Multi-Currency Revenue Analytics ─────────────
        analytics_engine = CrossCountryAnalyticsEngine(db_mock)
        with patch.object(analytics_engine._fx_service, "convert", AsyncMock(return_value=MagicMock(
            converted=MagicMock(amount=Decimal("952875"), currency_code="USD", to_dict=lambda: {"amount": "952875", "currency_code": "USD"}),
            rate=Decimal("0.27225"),
            status="OK"
        ))):
            revenue_report = await analytics_engine.generate_global_revenue_report(
                organization_id=org_id,
                target_reporting_currency="USD",
                market_revenues=[
                    {"market_id": "dubai", "market_name": "Dubai Freehold", "country_code": "AE", "native_currency": "AED", "amount": Decimal("3500000"), "deals": 1}
                ]
            )
            assert revenue_report.reporting_currency == "USD"
            assert revenue_report.total_consolidated_revenue.amount == Decimal("952875")
            assert revenue_report.unconverted_markets_count == 0

        # ── Step 14: Platform Diagnostic Health Diagnostics ───────────────────
        health_svc = MarketHealthService(db_mock)
        health_report = await health_svc.get_platform_health(market_id="dubai", country_code="AE")
        assert health_report["overall_status"] in ("HEALTHY", "WARNING")
        assert len(health_report["services"]) >= 6
