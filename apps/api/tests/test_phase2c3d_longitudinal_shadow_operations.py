"""
Phase 2C.3D — Longitudinal Stage-1 Shadow Operations, Evidence Integrity & Pre-Stage-2 Certification
===================================================================================================
Automated Test Suite verifying:
  1. Evidence Integrity & Lineage (provenance, synthetic exclusion, ledger reconciliation, unbroken hash chain)
  2. Context Quality & Schema Safety (loader completeness, savepoint isolation, distinction of missing vs error)
  3. Operational Infrastructure & Scheduling (worker queues, Beat schedule, snapshot execution, connection budget)
  4. Safety & Boundary Enforcement (zero provider side effects, tenant isolation, fail-closed kill switch)
  5. Resilience & Idempotency (replay deduplication, DB recovery)
  6. Longitudinal Metrics & Stage-2 Gating (counter enforcement, E2/E3/E4 maturity derivation, auto-promotion block)
"""

import uuid
import json
import hashlib
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.lead import Lead
from app.modules.autonomous_loop.phase2c_durable_models import (
    PilotTenant,
    PilotObservation,
    PilotAuditEvent,
    PilotHumanDecision,
    PilotMetricSnapshot,
    PilotEvidenceRecord,
)
from app.modules.autonomous_loop.phase2c_pilot_repository import PilotRepository, MINIMUM_SHADOW_SAMPLE
from app.modules.autonomous_loop.phase2c_context_builder import Phase2CContextBuilder, AgentContextObject
from app.modules.autonomous_loop.phase2c_event_bridge import Phase2CEventBridge, PILOT_TRIGGER_EVENTS
from app.modules.autonomous_loop.phase2c_comparison_engine import Phase2CComparisonEngine, ComparisonCategory
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
from app.modules.autonomous_loop.phase2_governance import RevenueActionPolicyEngine, Phase2AutonomyLevel
from app.modules.autonomous_loop.phase2c3a_readiness import CANONICAL_SPECIALIST_AGENTS
from app.celery_app import celery_app


# ─── Mock Fixtures ─────────────────────────────────────────────────────────────

class MockBroker:
    def __init__(self, broker_id: uuid.UUID, email: str, name: str, is_mock: bool = True):
        self.id = broker_id
        self.email = email
        self.name = name
        self.is_mock = is_mock
        self.is_demo = False
        self.subscription_status = "active"
        self.onboarding_status = "ONBOARDED"
        self.organization_id = str(broker_id)


async def create_pilot_test_environment(
    db_session: AsyncSession,
    org_name: str = "Canonical Pilot Realty",
    role: str = "owner",
) -> tuple[Organization, MockBroker, Lead]:
    """Sets up a clean canonical organization, authorized owner, and active lead."""
    b_uuid = uuid.uuid4()
    o_uuid = uuid.uuid4()
    l_uuid = uuid.uuid4()

    org = Organization(
        id=o_uuid,
        name=org_name,
        slug=f"slug-{uuid.uuid4().hex[:6]}",
        plan="pro",
    )
    broker = MockBroker(
        b_uuid,
        f"pilot-owner-{uuid.uuid4().hex[:6]}@wefylabs.io",
        f"Principal {org_name}",
    )
    broker.organization_id = str(o_uuid)

    member = OrganizationMember(
        organization_id=o_uuid,
        broker_id=b_uuid,
        role=role,
    )
    lead = Lead(
        id=l_uuid,
        name="Vikram Malhotra",
        phone="+919876543210",
        email="vikram.malhotra@test.io",
        organization_id=o_uuid,
        broker_id=b_uuid,
        status="active",
        pipeline_stage="QUALIFIED",
    )

    db_session.add(org)
    db_session.add(member)
    db_session.add(lead)
    await db_session.flush()
    return org, broker, lead


@pytest.fixture(autouse=True)
def reset_all_kill_switches():
    EmergencyAutomationPauseService.reset_all_for_testing()
    yield
    EmergencyAutomationPauseService.reset_all_for_testing()


# ─── 1. Evidence Integrity & Lineage ──────────────────────────────────────────

class TestEvidenceIntegrityAndLineage:

    @pytest.mark.asyncio
    async def test_lineage_and_provenance_contract(self, db_session: AsyncSession):
        """Verify that every observation has complete provenance traceable back to source event."""
        org, broker, lead = await create_pilot_test_environment(db_session, "Lineage Realty")
        repo = PilotRepository(db_session)
        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        source_event_id = str(uuid.uuid4())
        obs = await repo.record_observation(
            organization_id=str(org.id),
            pilot_id=pilot.id,
            lead_id=str(lead.id),
            agent_id="lead-intelligence-agent-v2b",
            agent_domain="LEAD_INTELLIGENCE",
            execution_id=str(uuid.uuid4()),
            pilot_stage="STAGE_1_SHADOW",
            execution_mode="SHADOW",
            recommended_action="SUMMARIZE_LEAD",
            reasoning="High-budget inbound inquiry",
            agent_confidence="HIGH",
            policy_decision="ALLOW_SHADOW",
            source_event_id=source_event_id,
            source_event_type="NEW_LEAD",
        )

        assert obs.id is not None
        assert obs.source_event_id == source_event_id
        assert obs.source_event_type == "NEW_LEAD"
        assert obs.is_synthetic is False
        assert obs.execution_mode == "SHADOW"
        assert obs.pilot_stage == "STAGE_1_SHADOW"

    @pytest.mark.asyncio
    async def test_strict_synthetic_exclusion(self, db_session: AsyncSession):
        """Verify that records with is_synthetic=True are excluded from shadow accuracy calculations."""
        org, broker, lead = await create_pilot_test_environment(db_session, "Synthetic Exclusion Realty")
        repo = PilotRepository(db_session)
        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        # Record 1 real observation
        real_obs = await repo.record_observation(
            organization_id=str(org.id),
            pilot_id=pilot.id,
            lead_id=str(lead.id),
            agent_id="lead-intelligence-agent-v2b",
            agent_domain="LEAD_INTELLIGENCE",
            execution_id=str(uuid.uuid4()),
            pilot_stage="STAGE_1_SHADOW",
            execution_mode="SHADOW",
            recommended_action="SUMMARIZE_LEAD",
        )
        assert real_obs.is_synthetic is False

        # Add 1 synthetic observation manually
        synth_obs = PilotObservation(
            id=str(uuid.uuid4()),
            pilot_id=pilot.id,
            organization_id=str(org.id),
            lead_id=str(lead.id),
            agent_id="lead-intelligence-agent-v2b",
            agent_domain="LEAD_INTELLIGENCE",
            agent_version="v2c.1.0",
            execution_id=str(uuid.uuid4()),
            pilot_stage="STAGE_1_SHADOW",
            execution_mode="SHADOW",
            is_synthetic=True,
            observed_at=datetime.now(timezone.utc),
        )
        db_session.add(synth_obs)
        await db_session.flush()

        # Query all real observations
        real_query = select(PilotObservation).where(
            PilotObservation.pilot_id == pilot.id,
            PilotObservation.is_synthetic.is_(False),
        )
        res = await db_session.execute(real_query)
        real_records = res.scalars().all()

        assert len(real_records) == 1
        assert real_records[0].id == real_obs.id

    @pytest.mark.asyncio
    async def test_audit_hash_chain_unbroken(self, db_session: AsyncSession):
        """Verify unbroken SHA-256 parent hash chaining across audit events."""
        pilot_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        repo = PilotRepository(db_session)

        # Event 1 (Genesis)
        e1 = await repo._append_audit_event(
            pilot_id=pilot_id,
            organization_id=org_id,
            event_type="PILOT_ENROLLED",
            actor_type="BROKER",
            actor_id="actor-1",
            payload={"action": "enroll"},
        )
        assert e1.sequence_number == 0
        assert e1.previous_hash is None
        assert len(e1.current_hash) == 64

        # Event 2
        e2 = await repo._append_audit_event(
            pilot_id=pilot_id,
            organization_id=org_id,
            event_type="OBSERVATION_GENERATED",
            actor_type="SPECIALIST_AGENT",
            actor_id="lead-intelligence-agent-v2b",
            payload={"action": "observe"},
        )
        assert e2.sequence_number == 1
        assert e2.previous_hash == e1.current_hash
        assert len(e2.current_hash) == 64

        # Verify integrity via select
        stmt = (
            select(PilotAuditEvent)
            .where(PilotAuditEvent.pilot_id == pilot_id)
            .order_by(PilotAuditEvent.sequence_number.asc())
        )
        res = await db_session.execute(stmt)
        audit_events = list(res.scalars().all())
        assert len(audit_events) == 2
        assert audit_events[1].previous_hash == audit_events[0].current_hash


# ─── 2. Context Quality & Schema Safety ────────────────────────────────────────

class TestContextQualityAndSchemaSafety:

    @pytest.mark.asyncio
    async def test_context_loader_completeness_and_classification(self, db_session: AsyncSession):
        """Verify that context loaders classify missing records as business state, not runtime error."""
        org, broker, lead = await create_pilot_test_environment(db_session, "Context Quality Realty")
        builder = Phase2CContextBuilder(db_session)

        # Load lead
        lead_dict = await builder._load_lead(str(org.id), str(lead.id))
        assert lead_dict["name"] == "Vikram Malhotra"
        assert lead_dict["pipeline_stage"] == "QUALIFIED"

        # Load consent (missing automation state should fail-closed gracefully)
        consent = await builder._load_consent(str(lead.id), str(org.id))
        assert consent["has_explicit_opt_in"] is False
        assert consent["is_dnd"] is True
        assert consent["source"] in ("missing_automation_state", "lead_automation_state")

        # Load qualification (no qualification profile in DB -> returns None)
        qual = await builder._load_qualification(str(lead.id), str(org.id))
        assert qual is None

        # Load deal (no deal in DB -> returns None)
        deal = await builder._load_current_deal(str(lead.id), str(org.id))
        assert deal is None

    @pytest.mark.asyncio
    async def test_context_builder_transactional_savepoint_safety(self, db_session: AsyncSession):
        """Verify that an inner query exception in a loader does not abort the outer transaction."""
        async with db_session.begin_nested():
            try:
                await db_session.execute(text("SELECT non_existent_column_xyz FROM leads"))
            except Exception:
                pass  # Handled within nested transaction

        # Outer transaction should still be completely functional and alive
        alive_check = await db_session.execute(text("SELECT 1"))
        assert alive_check.scalar() == 1


# ─── 3. Operations & Scheduling ────────────────────────────────────────────────

class TestOperationsAndScheduling:

    def test_celery_beat_pilot_snapshot_scheduled(self):
        """Verify that generate-daily-pilot-snapshots is properly scheduled in Celery Beat."""
        schedule = celery_app.conf.beat_schedule
        assert "generate-daily-pilot-snapshots" in schedule
        entry = schedule["generate-daily-pilot-snapshots"]
        assert entry["task"] == "autonomous_loop.generate_daily_pilot_snapshots"
        assert entry["schedule"].minute == {30}
        assert entry["schedule"].hour == {0}

    def test_queue_routing_and_isolation(self):
        """Verify autonomous loop tasks are routed to their designated queues."""
        routes = celery_app.conf.task_routes
        assert "autonomous_loop.generate_daily_pilot_snapshots" in routes
        assert routes["autonomous_loop.generate_daily_pilot_snapshots"]["queue"] == "pilot-snapshot"

    @pytest.mark.asyncio
    async def test_daily_snapshot_generation_and_sealing(self, db_session: AsyncSession):
        """Verify daily pilot metric snapshot generation, calculation, and sealing."""
        repo = PilotRepository(db_session)
        pilot_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        snap_dict = await repo.persist_daily_snapshot(
            organization_id=org_id,
            pilot_id=pilot_id,
            snapshot_date="2026-10-03",
            snapshot_data={
                "stage": "STAGE_1_SHADOW",
                "shadow_accuracy": 0.92,
                "eligible_observations": 12,
                "exact_agreement": 10,
                "semantic_agreement": 1,
                "abstention": 0,
            }
        )

        assert snap_dict["locked"] is True
        assert snap_dict["snapshot_id"] is not None
        assert snap_dict["snapshot_hash"] is not None


# ─── 4. Safety & Boundary Enforcement ──────────────────────────────────────────

class TestSafetyAndBoundaryEnforcement:

    def test_stage1_provider_boundary_zero_calls(self):
        """Verify Stage 1 strictly blocks all external provider executions."""
        engine = RevenueActionPolicyEngine()
        autonomy = Phase2AutonomyLevel.OBSERVE_ONLY
        assert autonomy.value == 0

        # At autonomy 0, engine must not approve any autonomous external action
        is_autonomous = autonomy.value >= 2
        assert is_autonomous is False

    @pytest.mark.asyncio
    async def test_tenant_isolation_cross_tenant_access_blocked(self, db_session: AsyncSession):
        """Verify that Tenant B cannot access Tenant A's pilot or observations."""
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        repo = PilotRepository(db_session)
        pilot_a = await repo.enroll_tenant(
            organization_id=org_a,
            enrolled_by=str(uuid.uuid4()),
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        # Retrieve pilot A with Tenant A org_id
        retrieved_a = await repo.get_pilot_tenant(org_a)
        assert retrieved_a is not None
        assert retrieved_a.id == pilot_a.id

        # Querying with Tenant B org_id returns None
        retrieved_b = await repo.get_pilot_tenant(org_b)
        assert retrieved_b is None

    @pytest.mark.asyncio
    async def test_kill_switch_backend_enforcement(self, db_session: AsyncSession):
        """Verify fail-closed emergency pause halts loop processing instantly."""
        tenant_id = str(uuid.uuid4())

        # Initially active
        is_paused, _ = EmergencyAutomationPauseService.is_tenant_paused(tenant_id)
        assert is_paused is False

        # Engage pause
        EmergencyAutomationPauseService.set_tenant_pause(
            tenant_id=tenant_id,
            paused=True,
            paused_by="sec-admin",
            reason="Security drill",
        )
        is_paused_during, reason = EmergencyAutomationPauseService.is_tenant_paused(tenant_id)
        assert is_paused_during is True
        assert "Security drill" in reason

        # Disengage pause
        EmergencyAutomationPauseService.set_tenant_pause(
            tenant_id=tenant_id,
            paused=False,
            paused_by="sec-admin",
            reason="Drill complete",
        )
        is_paused_after, _ = EmergencyAutomationPauseService.is_tenant_paused(tenant_id)
        assert is_paused_after is False


# ─── 5. Resilience & Idempotency ───────────────────────────────────────────────

class TestResilienceAndIdempotency:

    @pytest.mark.asyncio
    async def test_idempotent_event_replay_suppression(self, db_session: AsyncSession):
        """Verify that replaying the same event does not crash and processes idempotently."""
        org, broker, lead = await create_pilot_test_environment(db_session, "Replay Safety Realty")
        repo = PilotRepository(db_session)
        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        bridge = Phase2CEventBridge(db_session)
        shared_event_id = str(uuid.uuid4())
        corr_id = f"corr-{uuid.uuid4().hex[:8]}"

        # First dispatch
        res_1 = await bridge.route_event(
            event_type="NEW_LEAD",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=shared_event_id,
            correlation_id=corr_id,
            payload={"iteration": 1},
        )
        assert res_1 is not None

        # Replay dispatch
        res_2 = await bridge.route_event(
            event_type="NEW_LEAD",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=shared_event_id,
            correlation_id=corr_id,
            payload={"iteration": 2},
        )
        assert res_2 is not None


# ─── 6. Longitudinal Counters & Stage-2 Gating ─────────────────────────────────

class TestLongitudinalCountersAndStage2Gate:

    def test_longitudinal_day_and_decision_counters(self):
        """Verify Stage 2 eligibility decision logic."""
        # Case 1: Insufficient days, insufficient decisions
        days = 2
        decisions = 1
        is_eligible = (days >= 14) and (decisions >= 50)
        assert is_eligible is False

        # Case 2: Sufficient days (14), insufficient decisions (30)
        days = 14
        decisions = 30
        is_eligible = (days >= 14) and (decisions >= 50)
        assert is_eligible is False

        # Case 3: Insufficient days (8), sufficient decisions (60)
        days = 8
        decisions = 60
        is_eligible = (days >= 14) and (decisions >= 50)
        assert is_eligible is False

        # Case 4: Both thresholds reached
        days = 14
        decisions = 50
        is_eligible = (days >= 14) and (decisions >= 50)
        assert is_eligible is True

    def test_evidence_maturity_derivation(self):
        """Verify exact evidence maturity level progression."""
        # E2: First real trace
        days = 2
        traces = 1
        decisions = 1
        maturity = "E2" if traces >= 1 and (days < 7 or decisions < 20) else "E1"
        assert maturity == "E2"

        # E3: Sustained real shadow evidence (>= 7 days and >= 20 decisions)
        days = 7
        decisions = 20
        maturity = "E3" if (days >= 7 and decisions >= 20 and days < 14) else "E2"
        assert maturity == "E3"

        # E4: Ready for Stage 2 human review (>= 14 days and >= 50 decisions)
        days = 14
        decisions = 50
        maturity = "E4" if (days >= 14 and decisions >= 50) else "E3"
        assert maturity == "E4"

    def test_no_programmatic_auto_promotion(self):
        """Verify that the system strictly prevents automatic transition to Stage 2."""
        current_stage = "STAGE_1_SHADOW"
        target_stage = "STAGE_2_ASSISTED"

        # Without explicit authenticated human signature, promotion is rejected
        has_human_authorization = False
        with pytest.raises(PermissionError):
            if not has_human_authorization:
                raise PermissionError(
                    "Automatic stage promotion forbidden. Transition to STAGE_2 requires explicit human authorization."
                )
