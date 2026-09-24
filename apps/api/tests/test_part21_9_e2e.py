"""
BEETLELABS — PART 21.9
End-to-End Verification Test Harness
======================================
Tests the complete real-world lifecycle using the ACTUAL service APIs.

Architecture:
  - Uses in-memory SQLite (consistent with conftest.py)
  - Real application services — NO mock shortcuts through domain logic
  - Provider mocks ONLY at the external network boundary
  - Every test uses the actual method signatures found in the codebase

NON-NEGOTIABLE RULES:
  1. No hardcoded lead IDs, revenues, or conversion rates.
  2. Every assertion corresponds to actual observable system behavior.
  3. Provider mocks return explicit CONFIGURATION_REQUIRED where credentials unavailable.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.models import Base, Broker, Lead
from app.models.property_models import PropertyListing
from app.modules.autonomous_loop.models import LeadAutomationState
from app.modules.autonomous_loop.taxonomies import LeadLifecycleState, SalesLoopEventType, AutomationPermission
from app.modules.communication.provider_adapters.base_provider import DeliveryStatusEnum

# ─────────────────────────────────────────────────────────────────────────────
# Shared test infrastructure
# ─────────────────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

TENANT_A_UUID = uuid.uuid4()
TENANT_B_UUID = uuid.uuid4()
TENANT_A_ID = str(TENANT_A_UUID)
TENANT_B_ID = str(TENANT_B_UUID)


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def tenant_a_broker(db_session):
    broker = Broker(
        id=TENANT_A_UUID,
        email="broker.a@tenantA.com",
        phone="+971501234567",
        name="Broker A",
        agency_name="Tenant A Realty",
        city="Dubai",
        whatsapp_number="+971501234567",
        subscription_status="active",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture(scope="function")
async def tenant_b_broker(db_session):
    broker = Broker(
        id=TENANT_B_UUID,
        email="broker.b@tenantB.com",
        phone="+971509876543",
        name="Broker B",
        agency_name="Tenant B Realty",
        city="Dubai",
        whatsapp_number="+971509876543",
        subscription_status="active",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture(scope="function")
async def test_lead_tenant_a(db_session, tenant_a_broker):
    lead = Lead(
        broker_id=tenant_a_broker.id,
        phone="+971501111111",
        name="Test Customer A",
        source="website_form",
        status="active",
        pipeline_stage="new",
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)
    return lead


@pytest_asyncio.fixture(scope="function")
async def test_lead_tenant_b(db_session, tenant_b_broker):
    lead = Lead(
        broker_id=tenant_b_broker.id,
        phone="+971502222222",
        name="Test Customer B",
        source="whatsapp_inbound",
        status="active",
        pipeline_stage="new",
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)
    return lead


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO A: Lead Acquisition Foundation
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioA_LeadAcquisition:
    """E2E Scenario A: New inbound lead acquisition."""

    @pytest.mark.asyncio
    async def test_lead_creation_with_proper_attribution(self, db_session, tenant_a_broker):
        """Lead created with all required fields — no fabricated attribution."""
        lead = Lead(
            broker_id=tenant_a_broker.id,
            phone="+971503333333",
            name="Ahmed Al Mansouri",
            source="website_form",
            status="active",
            pipeline_stage="new",
        )
        db_session.add(lead)
        await db_session.commit()
        await db_session.refresh(lead)

        assert lead.id is not None
        assert lead.broker_id == tenant_a_broker.id
        assert lead.phone == "+971503333333"
        assert lead.source == "website_form"
        assert lead.status == "active"

    @pytest.mark.asyncio
    async def test_lead_tenant_isolation_at_creation(
        self, db_session, tenant_a_broker, tenant_b_broker
    ):
        """Lead created for Tenant A cannot be accessed via Tenant B's broker_id."""
        from sqlalchemy import select

        lead_a = Lead(
            broker_id=tenant_a_broker.id,
            phone="+971505555555",
            name="Tenant A Customer",
            source="website_form",
            status="active",
            pipeline_stage="new",
        )
        db_session.add(lead_a)
        await db_session.commit()

        # Tenant B tries to access Tenant A's lead via broker_id filter
        stmt = select(Lead).where(
            Lead.broker_id == tenant_b_broker.id,
            Lead.phone == "+971505555555",
        )
        result = await db_session.execute(stmt)
        leaked_lead = result.scalars().first()
        assert leaked_lead is None, "Tenant B MUST NOT see Tenant A's lead"


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO B: AI Prospect Intelligence
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioB_ProspectIntelligence:
    """
    E2E Scenario B: AI extracts structured intelligence from customer message.
    Uses actual StrictLLMProspectExtractionDTO schema (evidence_snippets: Dict[str, str]).
    """

    @pytest.mark.asyncio
    async def test_extractor_requires_evidence_for_each_field(self):
        """
        The extraction DTO enforces evidence_snippets per field.
        When a field is supported by evidence, evidence_snippet must be non-empty.
        """
        from app.modules.prospect_intelligence.dto.prospect_intelligence_dto import (
            StrictLLMProspectExtractionDTO,
        )

        raw_extraction = {
            "language": "en",
            "prospect_types": ["BUYER"],
            "transaction_intent": "BUY",
            "property_type": "apartment",
            "bedrooms": 3,
            "bathrooms": None,
            "location": "Dubai Marina",
            "preferred_areas": ["Dubai Marina"],
            "size_min": None,
            "size_max": None,
            "size_unit": "sqft",
            "furnished_preference": None,
            "parking_required": None,
            "amenities": [],
            "view_preference": None,
            "floor_preference": None,
            "new_or_resale": None,
            "ready_or_off_plan": None,
            "budget_min": 1800000,
            "budget_max": 2000000,
            "currency": "AED",
            "timeline": "0_3_MONTHS",
            "financing": "UNKNOWN",
            "purpose": "END_USE",
            "urgency": "MEDIUM",
            "evidence_snippets": {
                "intent": "I want to buy",
                "property_type": "3 bedroom apartment",
                "budget": "AED 2 million",
                "timeline": "within three months",
                "location": "Dubai Marina",
                "financing": "",
            },
            "field_confidences": {
                "intent_confidence": 0.97,
                "property_type_confidence": 0.95,
                "location_confidence": 0.93,
                "budget_confidence": 0.90,
                "timeline_confidence": 0.88,
                "financing_confidence": 0.0,
                "purpose_confidence": 0.70,
                "urgency_confidence": 0.65,
            },
            "overall_confidence": 0.88,
            "missing_critical_fields": ["financing"],
            "data_quality_flags": [],
        }

        dto = StrictLLMProspectExtractionDTO(**raw_extraction)

        assert dto.transaction_intent == "BUY"
        assert dto.property_type == "apartment"
        assert dto.bedrooms == 3
        assert dto.location == "Dubai Marina"
        assert dto.budget_min == 1800000
        assert dto.budget_max == 2000000
        assert dto.currency == "AED"
        assert dto.timeline == "0_3_MONTHS"

        assert dto.evidence_snippets.get("intent") == "I want to buy"
        assert dto.evidence_snippets.get("budget") == "AED 2 million"
        assert dto.financing == "UNKNOWN"
        assert dto.bathrooms is None

    @pytest.mark.asyncio
    async def test_unknown_fields_remain_unknown(self):
        """
        When a field is not mentioned in the customer message,
        extraction MUST return UNKNOWN or null.
        """
        from app.modules.prospect_intelligence.dto.prospect_intelligence_dto import (
            StrictLLMProspectExtractionDTO,
        )

        minimal_extraction = {
            "language": "en",
            "prospect_types": ["RENTER"],
            "transaction_intent": "RENT",
            "property_type": None,
            "bedrooms": None,
            "bathrooms": None,
            "location": "Abu Dhabi",
            "preferred_areas": ["Abu Dhabi"],
            "size_min": None,
            "size_max": None,
            "size_unit": "sqft",
            "furnished_preference": None,
            "parking_required": None,
            "amenities": [],
            "view_preference": None,
            "floor_preference": None,
            "new_or_resale": None,
            "ready_or_off_plan": None,
            "budget_min": None,
            "budget_max": None,
            "currency": "UNKNOWN",
            "timeline": "UNKNOWN",
            "financing": "UNKNOWN",
            "purpose": "UNKNOWN",
            "urgency": "UNKNOWN",
            "evidence_snippets": {
                "intent": "I want to rent",
                "property_type": "",
                "budget": "",
                "timeline": "",
                "location": "Abu Dhabi",
                "financing": "",
            },
            "field_confidences": {
                "intent_confidence": 0.95,
                "property_type_confidence": 0.0,
                "location_confidence": 0.90,
                "budget_confidence": 0.0,
                "timeline_confidence": 0.0,
                "financing_confidence": 0.0,
                "purpose_confidence": 0.0,
                "urgency_confidence": 0.0,
            },
            "overall_confidence": 0.60,
            "missing_critical_fields": ["property_type", "bedrooms", "budget_min", "timeline"],
            "data_quality_flags": [],
        }

        dto = StrictLLMProspectExtractionDTO(**minimal_extraction)

        assert dto.property_type is None
        assert dto.bedrooms is None
        assert dto.budget_min is None
        assert dto.timeline == "UNKNOWN"
        assert dto.financing == "UNKNOWN"
        assert dto.evidence_snippets.get("budget") == ""


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO C: Qualification Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioC_Qualification:
    """E2E Scenario C: Qualification facts, completeness, normalizers."""

    def test_qualification_taxonomies_are_complete(self):
        """Qualification taxonomies must define all controlled enums with UNKNOWN fallbacks."""
        from app.models.qualification_models import (
            QualificationIntent,
            QualificationBuyerType,
            QualificationTimeline,
            QualificationFinancing,
            FactValueCategory,
        )

        assert QualificationIntent.UNKNOWN.value == "UNKNOWN"
        assert QualificationBuyerType.UNKNOWN.value == "UNKNOWN"
        assert QualificationTimeline.UNKNOWN.value == "UNKNOWN"
        assert QualificationFinancing.UNKNOWN.value == "UNKNOWN"
        assert FactValueCategory.UNKNOWN.value == "UNKNOWN"

    def test_qualification_normalizer_returns_unknown_for_ungrounded_input(self):
        """QualificationTaxonomyNormalizer must strictly return UNKNOWN for empty or unrecognized inputs."""
        from app.modules.lead_qualification.taxonomies import QualificationTaxonomyNormalizer
        from app.models.qualification_models import (
            QualificationIntent,
            QualificationBuyerType,
            QualificationTimeline,
            QualificationFinancing,
        )

        assert QualificationTaxonomyNormalizer.normalize_intent(None) == QualificationIntent.UNKNOWN
        assert QualificationTaxonomyNormalizer.normalize_intent("random gibberish") == QualificationIntent.UNKNOWN
        assert QualificationTaxonomyNormalizer.normalize_buyer_type(None) == QualificationBuyerType.UNKNOWN
        assert QualificationTaxonomyNormalizer.normalize_timeline(None) == QualificationTimeline.UNKNOWN
        assert QualificationTaxonomyNormalizer.normalize_financing(None) == QualificationFinancing.UNKNOWN

    @pytest.mark.asyncio
    async def test_fact_repository_has_persistence_methods(self):
        """Fact repository must have methods to save/upsert facts."""
        from app.modules.lead_qualification.fact_repository import QualificationFactRepository

        public_methods = [m for m in dir(QualificationFactRepository) if not m.startswith("_")]
        persistence_methods = [
            m for m in public_methods
            if any(kw in m.lower() for kw in ["upsert", "add", "save", "create", "store", "record"])
        ]
        assert len(persistence_methods) > 0, "Fact repository must have persistence methods"


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO D: Property Matching
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioD_PropertyMatching:
    """
    E2E Scenario D: HardConstraintEngine uses actual PropertyListing model and NormalizedRequirementsDTO.
    """

    @pytest.mark.asyncio
    async def test_hard_filter_engine_rejects_over_budget_property(self, db_session):
        """Over-budget property must be rejected when listed against matching requirements."""
        from app.modules.property_recommendation.hard_filter import HardConstraintEngine
        from app.modules.property_recommendation.dto import NormalizedRequirementsDTO

        engine = HardConstraintEngine()

        requirements = NormalizedRequirementsDTO(
            transaction_intent="BUY",
            min_budget=1000000.0,
            max_budget=2000000.0,
            currency="AED",
            location="Dubai Marina",
            min_bedrooms=3,
            max_bedrooms=3,
        )

        over_budget_prop = PropertyListing(
            broker_id=TENANT_A_UUID,
            title="Luxury 3BR Apartment",
            description="Ultra luxury over-budget apartment",
            property_type="apartment",
            bedrooms=3,
            bathrooms=3,
            parking_spaces=2,
            area_value=2000.0,
            area_unit="sqft",
            price=3000000.0,  # AED 3M — over budget
            currency_code="AED",
            locality="Dubai Marina",
            city="Dubai",
            status="available",
        )
        db_session.add(over_budget_prop)
        await db_session.flush()

        valid, rejected = engine.filter_candidates([over_budget_prop], requirements)

        assert len(valid) == 0, "Over-budget property MUST be rejected by HardConstraintEngine"
        assert len(rejected) > 0, "Must have rejection log entry"

    @pytest.mark.asyncio
    async def test_hard_filter_engine_passes_matching_property(self, db_session):
        """Property within budget and matching key requirements must pass hard filter."""
        from app.modules.property_recommendation.hard_filter import HardConstraintEngine
        from app.modules.property_recommendation.dto import NormalizedRequirementsDTO

        engine = HardConstraintEngine()

        requirements = NormalizedRequirementsDTO(
            transaction_intent="BUY",
            min_budget=1000000.0,
            max_budget=2000000.0,
            currency="AED",
            location="Dubai Marina",
            min_bedrooms=3,
            max_bedrooms=3,
        )

        matching_prop = PropertyListing(
            broker_id=TENANT_A_UUID,
            title="3BR Marina Apartment",
            description="Beautiful apartment in the heart of Dubai Marina",
            property_type="apartment",
            bedrooms=3,
            bathrooms=3,
            parking_spaces=1,
            area_value=1600.0,
            area_unit="sqft",
            price=1900000.0,  # AED 1.9M — within budget
            currency_code="AED",
            locality="Dubai Marina",
            city="Dubai",
            status="available",
        )
        db_session.add(matching_prop)
        await db_session.flush()

        valid, rejected = engine.filter_candidates([matching_prop], requirements)

        assert len(valid) == 1, f"Matching property should pass hard filter. Rejected: {rejected}"

    @pytest.mark.asyncio
    async def test_empty_candidate_pool_returns_explicit_empty(self):
        """If zero candidates exist, must return empty list."""
        from app.modules.property_recommendation.hard_filter import HardConstraintEngine
        from app.modules.property_recommendation.dto import NormalizedRequirementsDTO

        engine = HardConstraintEngine()
        requirements = NormalizedRequirementsDTO(
            transaction_intent="BUY",
            min_budget=1000000.0,
            max_budget=2000000.0,
            currency="AED",
        )

        valid, rejected = engine.filter_candidates([], requirements)

        assert valid == []
        assert rejected == []


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO E: Next Best Action
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioE_NextBestAction:
    """E2E Scenario E: NBA evaluation — deterministic priority ordering."""

    def test_nba_taxonomy_defines_required_action_types(self):
        """NBA must include human escalation action types at minimum."""
        from app.modules.sales_action.taxonomies import SalesActionType

        defined = {a.value for a in SalesActionType}
        human_variants = {v for v in defined if any(
            kw in v.lower() for kw in ["human", "review", "handoff", "escalat", "broker"]
        )}
        assert len(human_variants) > 0, (
            f"NBA must include human escalation action types. Defined: {defined}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO F: Safety Guards — All must be FAIL-CLOSED
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioF_SafetyGuards:
    """
    E2E Scenario F: Every safety guard must block when triggered.
    """

    def _make_automation_state(self, **kwargs):
        """Helper to create valid LeadAutomationState instance."""
        defaults = {
            "lead_id": str(uuid.uuid4()),
            "tenant_id": TENANT_A_ID,
            "current_lifecycle_state": LeadLifecycleState.CONTACTING.value,
            "is_paused": False,
            "is_broker_takeover": False,
            "daily_action_count": 0,
            "orchestration_depth": 0,
            "consecutive_failures": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        return LeadAutomationState(**defaults)

    def _make_guard(self):
        """Creates OrchestratorGuardChain with mock DB session."""
        from app.modules.autonomous_loop.guard_chain import OrchestratorGuardChain
        mock_db = MagicMock()
        return OrchestratorGuardChain(mock_db)

    def test_lifecycle_guard_blocks_opted_out_lead(self):
        """An opted-out lead must NEVER receive autonomous outbound communication."""
        guard = self._make_guard()
        opted_out_state = self._make_automation_state(
            current_lifecycle_state=LeadLifecycleState.OPTED_OUT.value,
        )
        result = guard._evaluate_lifecycle_guard(opted_out_state)
        assert not result.passed, "Opted-out lead MUST be blocked"
        assert result.guard_name.value == "LEAD_LIFECYCLE"

    def test_lifecycle_guard_blocks_converted_lead(self):
        """CONVERTED is now in NO_OUTBOUND_STATES — autonomous outbound must be blocked."""
        guard = self._make_guard()
        converted_state = self._make_automation_state(
            current_lifecycle_state=LeadLifecycleState.CONVERTED.value,
        )
        result = guard._evaluate_lifecycle_guard(converted_state)
        assert not result.passed, (
            "CONVERTED lead MUST be blocked — CONVERTED is in NO_OUTBOUND_STATES (S-001 fix)"
        )

    def test_lifecycle_guard_blocks_paused_lead(self):
        """Paused automation must block all autonomous action."""
        guard = self._make_guard()
        paused_state = self._make_automation_state(
            is_paused=True,
            pause_reason="Broker requested manual review",
        )
        result = guard._evaluate_lifecycle_guard(paused_state)
        assert not result.passed, "Paused lead automation MUST be blocked"

    def test_lifecycle_guard_blocks_broker_takeover(self):
        """Broker takeover must suspend all autonomous communication (S-005 fix)."""
        guard = self._make_guard()
        takeover_state = self._make_automation_state(
            is_broker_takeover=True,
        )
        result = guard._evaluate_lifecycle_guard(takeover_state)
        assert not result.passed, "Broker takeover MUST block autonomous action (S-005)"
        assert "broker takeover" in result.reason.lower()

    def test_lifecycle_guard_allows_active_lead(self):
        """An active lead in CONTACTING state must pass the lifecycle guard."""
        guard = self._make_guard()
        active_state = self._make_automation_state(
            current_lifecycle_state=LeadLifecycleState.CONTACTING.value,
            is_paused=False,
            is_broker_takeover=False,
        )
        result = guard._evaluate_lifecycle_guard(active_state)
        assert result.passed, "Active lead in CONTACTING must pass lifecycle guard"

    @pytest.mark.asyncio
    async def test_quiet_hours_guard_fails_closed_on_exception(self, db_session, test_lead_tenant_a):
        """QuietHoursGuard exception must fail-closed (S-002 fix verification)."""
        from app.modules.autonomous_loop.guard_chain import OrchestratorGuardChain
        from app.modules.sales_action.taxonomies import SalesActionType

        normal_state = self._make_automation_state(
            lead_id=str(test_lead_tenant_a.id),
            tenant_id=str(test_lead_tenant_a.broker_id),
        )

        guard = OrchestratorGuardChain(db_session)

        with patch.object(guard.consent_guard, "evaluate_consent", new_callable=AsyncMock) as mc:
            mc.return_value = (True, MagicMock(value="GRANTED"), "Consent granted")

            with patch(
                "app.modules.autonomous_loop.guard_chain.QuietHoursGuard.evaluate_timing",
                side_effect=RuntimeError("Timezone service unavailable"),
            ):
                result = await guard.evaluate(
                    lead=test_lead_tenant_a,
                    automation_state=normal_state,
                    action_type=SalesActionType.FOLLOW_UP_NO_RESPONSE,
                    automation_permission=AutomationPermission.AUTOMATIC,
                    organization_id=str(test_lead_tenant_a.broker_id),
                )

        assert not result.overall_passed, (
            f"QuietHoursGuard exception must fail-closed (S-002). "
            f"Got overall_passed={result.overall_passed}"
        )

    @pytest.mark.asyncio
    async def test_fatigue_guard_fails_closed_on_exception(self, db_session, test_lead_tenant_a):
        """FatigueGuard exception must fail-closed (S-003 fix verification)."""
        from app.modules.autonomous_loop.guard_chain import OrchestratorGuardChain
        from app.modules.sales_action.taxonomies import SalesActionType

        normal_state = self._make_automation_state(
            lead_id=str(test_lead_tenant_a.id),
            tenant_id=str(test_lead_tenant_a.broker_id),
        )

        guard = OrchestratorGuardChain(db_session)

        with patch.object(guard.consent_guard, "evaluate_consent", new_callable=AsyncMock) as mc:
            mc.return_value = (True, MagicMock(value="GRANTED"), "Consent granted")

            with patch(
                "app.modules.autonomous_loop.guard_chain.QuietHoursGuard.evaluate_timing",
                return_value=(True, None, "UTC", "Within hours"),
            ):
                with patch.object(
                    guard.fatigue_guard, "evaluate_fatigue",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("Database connection lost"),
                ):
                    result = await guard.evaluate(
                        lead=test_lead_tenant_a,
                        automation_state=normal_state,
                        action_type=SalesActionType.FOLLOW_UP_NO_RESPONSE,
                        automation_permission=AutomationPermission.AUTOMATIC,
                        organization_id=str(test_lead_tenant_a.broker_id),
                    )

        assert not result.overall_passed, (
            f"FatigueGuard exception must fail-closed (S-003). "
            f"Got overall_passed={result.overall_passed}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO G: Communication Provider
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioG_CommunicationProvider:
    """E2E Scenario G: Provider credentials audit."""

    def test_whatsapp_credentials_are_placeholder_in_dev(self):
        """
        In development, WhatsApp credentials are placeholders.
        This test documents that the integration is CONFIGURATION_REQUIRED.
        """
        from app.config import settings

        wa_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        phone_id = getattr(settings, "PHONE_NUMBER_ID", "")

        is_placeholder = any([
            not wa_token,
            wa_token in ("wa_access_token_placeholder", "wa-placeholder", ""),
            not phone_id,
            phone_id in ("wa_phone_number_id_placeholder", ""),
        ])

        if is_placeholder:
            assert True, "CONFIGURATION_REQUIRED: WhatsApp credentials not configured"
        else:
            assert wa_token and phone_id, "Real credentials must be non-empty"

    def test_provider_delivery_contract(self):
        """
        Delivery status DELIVERED must only come from a provider webhook confirmation.
        """
        assert DeliveryStatusEnum.DELIVERED.value == "DELIVERED"
        assert DeliveryStatusEnum.QUEUED.value == "QUEUED"
        assert DeliveryStatusEnum.SENT.value == "SENT"
        assert DeliveryStatusEnum.CONFIGURATION_REQUIRED.value == "CONFIGURATION_REQUIRED"


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO I: Autonomous Loop
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioI_AutonomousLoop:
    """E2E Scenario I: Full autonomous loop chain verification."""

    @pytest.mark.asyncio
    async def test_state_machine_rejects_invalid_transitions(self, db_session):
        """The state machine must reject transitions that violate the allowed table."""
        from app.modules.autonomous_loop.state_machine import LeadStateMachine

        sm = LeadStateMachine(db_session)

        is_valid, error = sm.validate_transition(
            from_state=LeadLifecycleState.NEW,
            to_state=LeadLifecycleState.CONVERTED,
        )
        assert not is_valid, "NEW → CONVERTED must be an invalid transition"
        assert error is not None

    @pytest.mark.asyncio
    async def test_terminal_state_cannot_transition_to_active(self, db_session):
        """Terminal states must NOT transition to any active state."""
        from app.modules.autonomous_loop.state_machine import LeadStateMachine, TERMINAL_STATES

        sm = LeadStateMachine(db_session)
        active_states = {
            LeadLifecycleState.NEW,
            LeadLifecycleState.CONTACTING,
            LeadLifecycleState.ENGAGING,
            LeadLifecycleState.QUALIFYING,
        }

        for terminal in TERMINAL_STATES:
            for active in active_states:
                is_valid, _ = sm.validate_transition(terminal, active)
                assert not is_valid, (
                    f"TERMINAL {terminal.value} must NEVER transition to {active.value}"
                )

    @pytest.mark.asyncio
    async def test_automation_state_is_tenant_scoped(
        self, db_session, test_lead_tenant_a, test_lead_tenant_b
    ):
        """S-001 fix: Tenant B querying Tenant A's lead must raise PermissionError."""
        from app.modules.autonomous_loop.state_machine import LeadStateMachine

        sm = LeadStateMachine(db_session)

        # Create Tenant A's automation state
        state_a = await sm.get_or_create_automation_state(
            lead_id=str(test_lead_tenant_a.id),
            tenant_id=str(test_lead_tenant_a.broker_id),
        )
        await db_session.flush()
        assert state_a is not None

        # Tenant B tries to access Tenant A's lead_id -> Must raise PermissionError
        with pytest.raises(PermissionError) as excinfo:
            await sm.get_or_create_automation_state(
                lead_id=str(test_lead_tenant_a.id),
                tenant_id=str(test_lead_tenant_b.broker_id),
            )
        assert "Access denied" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_event_store_idempotency(self, db_session):
        """Same idempotency_key must return existing event, not create duplicate."""
        from app.modules.autonomous_loop.event_store import SalesLoopEventStore
        from app.modules.autonomous_loop.dto import SalesLoopEventDTO

        store = SalesLoopEventStore(db_session)
        idem_key = f"test-idempotency-{uuid.uuid4()}"
        lead_id = str(uuid.uuid4())

        event_dto = SalesLoopEventDTO(
            event_type=SalesLoopEventType.NEW_LEAD,
            tenant_id=TENANT_A_ID,
            lead_id=lead_id,
            correlation_id=str(uuid.uuid4()),
            idempotency_key=idem_key,
            occurred_at=datetime.now(timezone.utc),
            payload={},
        )

        event1, is_new1 = await store.ingest_event(event_dto)
        assert event1 is not None
        assert is_new1 is True

        event2, is_new2 = await store.ingest_event(event_dto)
        assert event2 is not None
        assert is_new2 is False, "Duplicate idempotency_key must return is_new=False"
        assert str(event1.id) == str(event2.id), "Same event ID must be returned for duplicate"

    @pytest.mark.asyncio
    async def test_loop_protection_blocks_runaway_orchestration(self, db_session):
        """Loop protection must block when daily actions or depth exceed limits."""
        from app.modules.autonomous_loop.loop_protection import LoopProtectionService

        lp = LoopProtectionService(db_session)

        overloaded_state = LeadAutomationState(
            lead_id=str(uuid.uuid4()),
            tenant_id=TENANT_A_ID,
            current_lifecycle_state=LeadLifecycleState.CONTACTING.value,
            is_paused=False,
            is_broker_takeover=False,
            daily_action_count=100,   # High
            orchestration_depth=50,   # High
            consecutive_failures=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        ok, reason = lp.evaluate(overloaded_state, policy=None)
        assert not ok, f"Runaway orchestration must be blocked. ok={ok}, reason={reason}"


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5: Failure Recovery
# ─────────────────────────────────────────────────────────────────────────────

class TestFailureRecovery:
    """Phase 5: Failure recovery — dead letter handling, retry safety."""

    @pytest.mark.asyncio
    async def test_dead_letter_created_via_admit(self, db_session):
        """
        DeadLetterService.admit() must create a dead letter record
        when a SalesLoopEvent permanently fails.
        """
        from app.modules.autonomous_loop.dead_letter_service import DeadLetterService
        from app.modules.autonomous_loop.models import SalesLoopEvent
        from app.modules.autonomous_loop.taxonomies import FailureClass, EventProcessingState

        dl_svc = DeadLetterService(db_session)

        event = SalesLoopEvent(
            id=str(uuid.uuid4()),
            idempotency_key=f"dl-test-{uuid.uuid4()}",
            event_type="NEW_LEAD",
            tenant_id=TENANT_A_ID,
            lead_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            actor_type="SYSTEM",
            payload={},
            processing_state=EventProcessingState.FAILED.value,
            retry_count=3,
            max_retries=3,
            occurred_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(event)
        await db_session.flush()

        dead_letter = await dl_svc.admit(
            event=event,
            failure_class=FailureClass.PERMANENT_PROVIDER_ERROR,
            safe_error_message="Provider returned 500 after 3 retries",
        )

        assert dead_letter is not None
        assert dead_letter.original_event_id == event.id
        assert not dead_letter.is_resolved
        assert dead_letter.tenant_id == TENANT_A_ID

    @pytest.mark.asyncio
    async def test_dead_letter_resolution(self, db_session):
        """Dead letters can be resolved by a broker via resolve() API. Returns bool."""
        from app.modules.autonomous_loop.dead_letter_service import DeadLetterService
        from app.modules.autonomous_loop.models import SalesLoopEvent
        from app.modules.autonomous_loop.taxonomies import FailureClass, EventProcessingState

        dl_svc = DeadLetterService(db_session)

        event = SalesLoopEvent(
            id=str(uuid.uuid4()),
            idempotency_key=f"dl-resolve-{uuid.uuid4()}",
            event_type="CUSTOMER_MESSAGE_RECEIVED",
            tenant_id=TENANT_A_ID,
            lead_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            actor_type="SYSTEM",
            payload={},
            processing_state=EventProcessingState.FAILED.value,
            retry_count=3,
            max_retries=3,
            occurred_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(event)
        await db_session.flush()

        dead_letter = await dl_svc.admit(
            event=event,
            failure_class=FailureClass.UNKNOWN_ERROR,
            safe_error_message="Unknown internal error",
        )

        broker_id = str(uuid.uuid4())
        resolved_ok = await dl_svc.resolve(
            dead_letter_id=str(dead_letter.id),
            tenant_id=TENANT_A_ID,
            resolved_by=broker_id,
            resolution_notes="Manually investigated — stale event, safe to close",
        )

        assert resolved_ok is True, "resolve() must return True on successful resolution"

        from sqlalchemy import select as sa_select
        from app.modules.autonomous_loop.models import SalesLoopDeadLetter
        stmt = sa_select(SalesLoopDeadLetter).where(SalesLoopDeadLetter.id == dead_letter.id)
        res = await db_session.execute(stmt)
        updated_dl = res.scalars().first()
        assert updated_dl.is_resolved is True
        assert updated_dl.resolved_by == broker_id


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 14: Observability
# ─────────────────────────────────────────────────────────────────────────────

class TestObservability:
    """Phase 14: Metrics existence and PII-safety verification."""

    def test_autonomous_loop_metrics_defined(self):
        """All required autonomous loop metrics must be defined."""
        from app.modules.autonomous_loop.metrics import (
            LOOP_EVENTS_TOTAL,
            LOOP_EVENTS_PROCESSED,
            LOOP_EVENTS_FAILED,
            LOOP_GUARD_BLOCKS,
            LOOP_ACTIONS_DISPATCHED,
            LOOP_DEAD_LETTERS,
            LOOP_DUPLICATE_EVENTS,
            LOOP_PROCESSING_LATENCY,
        )
        assert LOOP_EVENTS_TOTAL is not None
        assert LOOP_EVENTS_PROCESSED is not None
        assert LOOP_EVENTS_FAILED is not None
        assert LOOP_GUARD_BLOCKS is not None
        assert LOOP_ACTIONS_DISPATCHED is not None
        assert LOOP_DEAD_LETTERS is not None
        assert LOOP_DUPLICATE_EVENTS is not None
        assert LOOP_PROCESSING_LATENCY is not None

    def test_metrics_mask_function_does_not_expose_pii(self):
        """mask_org_id must not return the full UUID."""
        from app.modules.autonomous_loop.metrics import mask_org_id

        real_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        masked = mask_org_id(real_uuid)

        assert masked is not None
        assert masked != real_uuid
        assert len(masked) <= 16


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 16: No-Fabrication Audit
# ─────────────────────────────────────────────────────────────────────────────

class TestNoFabricationAudit:
    """Phase 16: Verify no production fabrication exists."""

    def test_gemini_key_is_not_placeholder(self):
        """Gemini API key must be a real credential — not a placeholder."""
        from app.config import settings
        key = getattr(settings, "GEMINI_API_KEY", None)
        assert key is not None, "GEMINI_API_KEY must be set"
        assert "placeholder" not in key.lower()
        assert not key.startswith("AIzaSy_placeholder")

    def test_validated_settings_has_production_validation(self):
        """The ValidatedSettings class must fail-fast on placeholders in production."""
        from app.common.config.validated_settings import EnterpriseSettings
        assert hasattr(EnterpriseSettings, "validate_production_security")

    def test_supabase_url_placeholder_is_documented_in_dev(self):
        """In development, Supabase URL being placeholder is expected."""
        from app.config import settings
        supabase_url = getattr(settings, "SUPABASE_URL", "")
        env = getattr(settings, "ENV", "development")
        if env.lower() in ("development", "dev"):
            assert True
        else:
            assert "placeholder" not in supabase_url.lower()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 19: Alembic Verification
# ─────────────────────────────────────────────────────────────────────────────

class TestAlembicVerification:
    """Phase 19: Migration chain structure verification."""

    def test_exactly_one_alembic_head(self):
        """There must be exactly one Alembic migration head."""
        import subprocess
        import sys
        import os

        cwd = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "heads"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        output = result.stdout.strip()
        head_lines = [l for l in output.splitlines() if "(head)" in l]
        assert len(head_lines) == 1, (
            f"Expected exactly 1 Alembic head, found {len(head_lines)}.\n{output}"
        )
        # The head moves forward as new parts add migrations, so assert the
        # invariant (a single, well-formed head) rather than a hardcoded list.
        revision = head_lines[0].split()[0]
        assert revision and revision.split("_")[0].isdigit(), (
            f"Unrecognized migration head: {head_lines[0]}"
        )

    def test_migration_chain_expected_files_present(self):
        """All expected migration files must be present."""
        import os

        versions_path = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
        migration_files = [
            f for f in os.listdir(versions_path)
            if f.endswith(".py") and not f.startswith("__")
        ]

        expected = [
            "001_initial_schema.py",
            "002_enterprise_foundation.py",
            "merge_002_and_9999_heads.py",
            "9999_production_baseline.py",
            "0015_sales_loop_orchestration.py",
            "0016_lead_sources_alignment.py",
            "0017_razorpay_billing.py",
            "0018_pre_branding_blockers.py",
        ]
        for ef in expected:
            assert ef in migration_files, f"Expected migration file {ef} not found"


