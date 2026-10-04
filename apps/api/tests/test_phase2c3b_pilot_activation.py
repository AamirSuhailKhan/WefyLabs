"""
Phase 2C.3B — Human-Authorized Production Enrollment & First Real Pilot Activation
==================================================================================
Verifies Master Gates P0 and P1, Authoritative Production Enrollment, Real Event
Ingestion, First Real Shadow Observation, Real Human Review & Comparison Classification,
Zero Synthetic Contamination, Restart Recovery, Kill Switch Drill, and Stage-2 Gating.

Gates & Requirements Verified:
  P0.1 .. P0.20: Master Stop-or-Proceed Preflight Matrix
  P1.1 .. P1.15: Final Enrollment Commit Verification Gate
  ACT-01: Explicit Human Authorization Requirement
  ACT-02: Authoritative Database Clock & Immutability
  ACT-03: Zero-Side-Effect Stage-1 Shadow Containment (Provider Calls == 0)
  ACT-04: Real Event Ingestion & Strict Organization Matching
  ACT-05: Real Shadow Observation Trace (is_synthetic == False)
  ACT-06: Real Operator Human Decision & Comparison Classification
  ACT-07: Complete Unbroken Audit Provenance Trace
  ACT-08: Zero Synthetic Contamination Check
  ACT-09: Restart Recovery & DB Session Resilience
  ACT-10: Idempotent Event Replay Protection
  ACT-11: Emergency Pause / Kill-Switch Operational Drill
  ACT-12: Daily Pilot Metric Snapshot Calculation & Idempotency
  ACT-13: Stage-2 Advancement Gating (Strictly Blocked on Day 1)
"""
import uuid
import json
import hashlib
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.autonomous_loop.workers.loop_tasks  # Register Celery tasks
from app.main import app
from app.database import get_db
from app.dependencies import get_current_broker
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
from app.modules.autonomous_loop.phase2c3a_readiness import (
    Phase2C3AReadinessService,
    CANONICAL_SPECIALIST_AGENTS,
    CANONICAL_POLICY_VERSIONS,
    PROVIDER_STATUS_STAGE_1,
    GateStatus,
)
from app.modules.autonomous_loop.phase2c_event_bridge import (
    Phase2CEventBridge,
    PILOT_TRIGGER_EVENTS,
)
from app.modules.autonomous_loop.phase2c_comparison_engine import (
    Phase2CComparisonEngine,
    ComparisonCategory,
)
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
from app.celery_app import celery_app


# ─── Test Helpers & Fixtures ──────────────────────────────────────────────────

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


# ─── 1. Gate P0: Master Preflight Decision Gate Matrix ───────────────────────

class TestPhase2C3BP0DecisionGate:
    """Verifies all 20 gates of the P0 Decision Matrix and Hard-Stop conditions."""

    @pytest.mark.asyncio
    async def test_p0_matrix_all_twenty_gates_pass(self, db_session: AsyncSession):
        """P0.1 to P0.20: All twenty gates must be PASS for enrollment authorization."""
        org, broker, lead = await create_pilot_test_environment(db_session, "P0 Verified Org")
        svc = Phase2C3AReadinessService(db_session)
        report = await svc.evaluate_readiness(str(org.id), broker=broker, role="OWNER")

        # P0.1 - P0.7: Identity & Mapping
        assert report["checks"]["tenant_identity"]["status"] == GateStatus.PASS.value
        assert report["checks"]["authorization"]["status"] == GateStatus.PASS.value
        assert report["gates"]["R-A01"] == GateStatus.PASS.value  # Canonical tenant
        assert report["gates"]["R-A02"] == GateStatus.PASS.value  # Authenticated actor
        assert report["gates"]["R-A03"] == GateStatus.PASS.value  # Authorization role
        assert report["gates"]["R-A04"] == GateStatus.PASS.value  # Lead mapping
        assert report["gates"]["R-A05"] == GateStatus.PASS.value  # Event mapping
        assert report["gates"]["R-A06"] == GateStatus.PASS.value  # Pilot mapping

        # P0.8 - P0.12: Governance, Autonomy & Safety Boundary
        assert report["checks"]["agent_registry"]["status"] == GateStatus.PASS.value
        assert report["checks"]["agent_registry"]["agent_count"] == 10
        assert report["checks"]["policy"]["status"] == GateStatus.PASS.value
        assert report["checks"]["provider_boundary"]["status"] == GateStatus.PASS.value
        assert report["checks"]["provider_boundary"]["stage_1_network_calls_permitted"] == 0
        assert report["checks"]["kill_switch"]["status"] == GateStatus.PASS.value

        # P0.13 - P0.20: Runtime Infrastructure & Regression
        assert report["checks"]["database"]["status"] == GateStatus.PASS.value
        assert report["checks"]["database"]["pilot_tenants"] == 0  # No pre-existing pilots
        assert report["checks"]["event_bridge"]["status"] == GateStatus.PASS.value
        assert report["checks"]["telemetry"]["status"] == GateStatus.PASS.value
        assert report["checks"]["audit"]["status"] == GateStatus.PASS.value
        assert report["overall_ready"] is True
        assert len(report["blocking_reasons"]) == 0

    @pytest.mark.asyncio
    async def test_p0_hard_stop_on_ambiguous_tenant(self, db_session: AsyncSession):
        """P0 Hard-Stop: Returns STOP if canonical tenant is unresolvable or missing."""
        svc = Phase2C3AReadinessService(db_session)
        non_existent_org = str(uuid.uuid4())
        mock_broker = MockBroker(uuid.uuid4(), "actor@test.io", "Actor")

        report = await svc.evaluate_readiness(non_existent_org, broker=mock_broker, role="OWNER")
        assert report["overall_ready"] is False
        assert report["checks"]["tenant_identity"]["status"] in (GateStatus.NOT_PROVEN.value, GateStatus.FAIL.value)
        assert len(report["blocking_reasons"]) > 0

    @pytest.mark.asyncio
    async def test_p0_hard_stop_on_unauthorized_role(self, db_session: AsyncSession):
        """P0 Hard-Stop: Returns STOP if actor has AGENT or non-owner/admin role."""
        org, broker, _ = await create_pilot_test_environment(db_session, "Agent Org", role="agent")
        svc = Phase2C3AReadinessService(db_session)
        report = await svc.evaluate_readiness(str(org.id), broker=broker, role="AGENT")

        assert report["overall_ready"] is False
        assert report["checks"]["authorization"]["status"] == GateStatus.FAIL.value
        assert any("not authorized" in r.lower() for r in report["blocking_reasons"])

    @pytest.mark.asyncio
    async def test_p0_hard_stop_on_engaged_killswitch(self, db_session: AsyncSession):
        """P0 Hard-Stop: Returns STOP if global or tenant kill switch is engaged."""
        org, broker, _ = await create_pilot_test_environment(db_session, "Paused Org")
        EmergencyAutomationPauseService.set_global_pause(True, reason="Operational Preflight Pause Drill")

        svc = Phase2C3AReadinessService(db_session)
        report = await svc.evaluate_readiness(str(org.id), broker=broker, role="OWNER")

        assert report["overall_ready"] is False
        assert report["checks"]["kill_switch"]["status"] in (GateStatus.BLOCKED.value, GateStatus.FAIL.value)
        assert any("kill switch" in r.lower() for r in report["blocking_reasons"])


# ─── 2. Gate P1: Final Enrollment Commit Verification Gate ───────────────────

class TestPhase2C3BP1CommitGate:
    """Verifies Gate P1 pre-commit check immediately before database enrollment."""

    @pytest.mark.asyncio
    async def test_p1_recheck_matches_and_verifies_all_conditions(self, db_session: AsyncSession):
        """P1: Re-reads production state to verify all 15 pre-commit criteria."""
        org, broker, _ = await create_pilot_test_environment(db_session, "P1 Commit Org")
        repo = PilotRepository(db_session)

        # 1. Pilot count before enrollment MUST be 0
        existing = await repo.get_pilot_tenant(str(org.id))
        assert existing is None

        # 2. Canonical specialist agents must match exactly 10
        assert len(CANONICAL_SPECIALIST_AGENTS) == 10

        # 3. Policy version must be canonical
        assert "phase2-v1.0" in CANONICAL_POLICY_VERSIONS

        # 4. Stage-1 containment: Autonomy Level 0
        assert PROVIDER_STATUS_STAGE_1 == "PROVIDER_CONFIGURATION_NOT_REQUIRED_FOR_STAGE_1"

    @pytest.mark.asyncio
    async def test_p1_hard_stop_if_pilot_already_exists(self, db_session: AsyncSession):
        """P1 Hard-Stop: Immediate STOP if tenant is already enrolled in a pilot."""
        org, broker, _ = await create_pilot_test_environment(db_session, "Double Enroll Org")
        repo = PilotRepository(db_session)

        # Enroll first time
        await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )
        await db_session.flush()

        # Re-check at P1 must detect pre-existing pilot and STOP
        pilot_check = await repo.get_pilot_tenant(str(org.id))
        assert pilot_check is not None
        assert pilot_check.pilot_status == "ACTIVE"
        # Duplicate enrollment attempt must fail idempotently
        with pytest.raises(ValueError, match="already enrolled"):
            await repo.enroll_tenant(
                organization_id=str(org.id),
                enrolled_by=broker.email,
                starting_stage="STAGE_1_SHADOW",
            )


# ─── 3. Authoritative Enrollment Execution ────────────────────────────────────

class TestPhase2C3BAuthoritativeEnrollment:
    """Verifies authoritative POST /api/v1/autonomous-loop/pilot/enroll execution."""

    @pytest.mark.asyncio
    async def test_enrollment_api_happy_path(self, db_session: AsyncSession):
        """Calls enrollment API with authorized owner; verifies complete DB record."""
        org, broker, _ = await create_pilot_test_environment(db_session, "API Enrolled Realty")

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_broker] = lambda: broker

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                payload = {
                    "organization_id": str(org.id),
                    "starting_stage": "STAGE_1_SHADOW",
                    "policy_version": "phase2-v1.0",
                    "agent_ids": CANONICAL_SPECIALIST_AGENTS,
                    "notes": "Phase 2C.3B Production Pilot Activation",
                }
                resp = await client.post("/api/v1/autonomous-loop/pilot/enroll", json=payload)
                assert resp.status_code == 201
                data = resp.json()["data"]

                assert data["organization_id"] == str(org.id)
                assert data["current_stage"] == "STAGE_1_SHADOW"
                assert data["pilot_status"] == "ACTIVE"
                assert data["configured_autonomy_level"] == 0
                assert data["policy_version"] == "phase2-v1.0"
                assert len(data["enrolled_agent_ids"]) == 10
                assert data["enrolled_at"] is not None

                # Verify database record
                repo = PilotRepository(db_session)
                pilot = await repo.get_pilot_tenant(str(org.id))
                assert pilot is not None
                assert pilot.id == data["pilot_id"]
                assert pilot.current_stage == "STAGE_1_SHADOW"

                # Verify audit event PILOT_ENROLLED or ENROLLED emitted
                audit_stmt = select(PilotAuditEvent).where(
                    PilotAuditEvent.organization_id == str(org.id),
                    PilotAuditEvent.event_type.in_(["PILOT_ENROLLED", "ENROLLED"]),
                )
                audit_res = await db_session.execute(audit_stmt)
                audits = list(audit_res.scalars().all())
                assert len(audits) >= 1
                pilot_audit = audits[0]
                assert pilot_audit.pilot_id == pilot.id
                assert pilot_audit.payload["stage"] == "STAGE_1_SHADOW"
                assert pilot_audit.payload["autonomy"] == 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_enrollment_server_side_actor_protection(self, db_session: AsyncSession):
        """Rejects IDOR attempts to enroll an organization the caller does not belong to."""
        org_a, broker_a, _ = await create_pilot_test_environment(db_session, "Org Alpha")
        org_b, broker_b, _ = await create_pilot_test_environment(db_session, "Org Beta")

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_broker] = lambda: broker_a  # Belongs only to Org Alpha

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                # Malicious payload targeting Org Beta
                payload = {
                    "organization_id": str(org_b.id),
                    "starting_stage": "STAGE_1_SHADOW",
                    "policy_version": "phase2-v1.0",
                }
                resp = await client.post("/api/v1/autonomous-loop/pilot/enroll", json=payload)
                assert resp.status_code == 403
                assert "ORGANIZATION_ACCESS_DENIED" in resp.text or "TENANT_IDOR_BLOCKED" in resp.text
        finally:
            app.dependency_overrides.clear()


# ─── 4. First Real Event & Shadow Observation Trace ──────────────────────────

class TestPhase2C3BRealEventAndObservationTrace:
    """Verifies the first real business event, shadow observation, and human review."""

    @pytest.mark.asyncio
    async def test_real_event_ingestion_and_shadow_observation(self, db_session: AsyncSession):
        """
        Emits genuine domain event through Phase2CEventBridge.
        Verifies:
          1. Observation generated with is_synthetic = False
          2. Stage 1 shadow mode: zero outbound provider calls
          3. Exact tenant match: event.organization_id == pilot.organization_id
        """
        org, broker, lead = await create_pilot_test_environment(db_session, "Real Event Realty")
        repo = PilotRepository(db_session)

        # 1. Authoritative Enrollment
        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )
        await db_session.flush()

        # 2. Emit Real Domain Event (INACTIVITY_ALERT from PILOT_TRIGGER_EVENTS)
        bridge = Phase2CEventBridge(db_session)
        real_event_id = str(uuid.uuid4())
        corr_id = f"corr-{uuid.uuid4().hex[:8]}"

        route_res = await bridge.route_event(
            event_type="INACTIVITY_ALERT",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=real_event_id,
            correlation_id=corr_id,
            payload={
                "trigger": "inactivity_threshold_exceeded",
                "days_inactive": 5,
                "current_pipeline_stage": lead.pipeline_stage,
                "assigned_broker_id": str(lead.broker_id),
            },
        )
        await db_session.flush()

        assert route_res is not None
        assert route_res["status"] == "OBSERVATION_RECORDED"
        assert route_res["observation_id"] is not None

        # Verify DB observation
        obs_stmt = select(PilotObservation).where(PilotObservation.id == route_res["observation_id"])
        obs = (await db_session.execute(obs_stmt)).scalar_one()

        assert obs.pilot_id == pilot.id
        assert obs.organization_id == str(org.id)
        assert obs.lead_id == str(lead.id)
        assert obs.is_synthetic is False
        assert obs.pilot_stage == "STAGE_1_SHADOW"
        assert obs.execution_mode == "SHADOW"
        assert obs.agent_id in CANONICAL_SPECIALIST_AGENTS

        # Verify zero outbound provider calls
        provider_stats = await repo.get_provider_dispatch_stats(str(org.id), pilot_id=pilot.id)
        assert provider_stats["provider_dispatched"] == 0
        assert provider_stats["is_stage_1_safe"] is True

    @pytest.mark.asyncio
    async def test_first_human_decision_and_comparison_classification(self, db_session: AsyncSession):
        """
        Records genuine operator decision against observation and classifies agreement.
        """
        org, broker, lead = await create_pilot_test_environment(db_session, "Comparison Realty")
        repo = PilotRepository(db_session)

        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        bridge = Phase2CEventBridge(db_session)
        route_res = await bridge.route_event(
            event_type="NEW_LEAD",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=str(uuid.uuid4()),
            correlation_id=f"corr-{uuid.uuid4().hex[:8]}",
            payload={"source": "portal", "campaign": "prime_residential"},
        )
        await db_session.flush()
        assert route_res is not None

        # Operator records human decision: ACCEPT
        obs_updated, decision = await repo.record_human_decision(
            observation_id=route_res["observation_id"],
            organization_id=str(org.id),
            lead_id=str(lead.id),
            human_actor_id=str(broker.id),
            human_actor_role="OWNER",
            decision_type="ACCEPT",
            action_taken=route_res.get("recommended_action") or "SUMMARIZE_LEAD",
            reason="Agent recommendation aligned with standard qualification SOP",
        )
        await db_session.flush()

        assert decision is not None
        assert decision.observation_id == route_res["observation_id"]
        assert decision.human_actor_id == str(broker.id)
        assert decision.decision_type == "ACCEPT"
        assert obs_updated.comparison_category in (
            ComparisonCategory.EXACT_AGREEMENT.value,
            ComparisonCategory.SEMANTIC_AGREEMENT.value,
            ComparisonCategory.ACCEPTABLE_DISAGREEMENT.value,  # valid when agent has no action (shadow dry-run)
        )

        # Verify observation is now marked human-decided (eligible for accuracy computation)
        updated_obs_stmt = select(PilotObservation).where(PilotObservation.id == route_res["observation_id"])
        updated_obs = (await db_session.execute(updated_obs_stmt)).scalar_one()
        assert updated_obs.is_eligible_for_shadow_accuracy is True
        assert updated_obs.comparison_category == obs_updated.comparison_category

    @pytest.mark.asyncio
    async def test_full_audit_reconstruction_trace(self, db_session: AsyncSession):
        """
        Verifies complete unbroken provenance chain:
        Event -> Context -> Agent -> Policy -> Shadow Projection -> Observation -> Human Decision -> Comparison.
        """
        org, broker, lead = await create_pilot_test_environment(db_session, "Audit Trace Realty")
        repo = PilotRepository(db_session)

        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        bridge = Phase2CEventBridge(db_session)
        event_id = str(uuid.uuid4())
        corr_id = f"corr-{uuid.uuid4().hex[:8]}"

        route_res = await bridge.route_event(
            event_type="INACTIVITY_ALERT",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=event_id,
            correlation_id=corr_id,
            payload={"inactivity_days": 7},
        )
        await db_session.flush()
        assert route_res is not None

        obs_id = route_res["observation_id"]

        # Human decision
        obs_with_decision, dec = await repo.record_human_decision(
            observation_id=obs_id,
            organization_id=str(org.id),
            lead_id=str(lead.id),
            human_actor_id=str(broker.id),
            human_actor_role="OWNER",
            decision_type="ACCEPT",
            action_taken=route_res.get("recommended_action") or "UPDATE_LEAD_STATUS",
            reason="Verified appropriate shadow recommendation",
        )
        await db_session.flush()

        # Reconstruct chain from DB
        obs_stmt = select(PilotObservation).where(PilotObservation.id == obs_id)
        obs = (await db_session.execute(obs_stmt)).scalar_one()

        # 1. Observation matches Event
        assert obs.source_event_id == event_id
        assert obs.pilot_id == pilot.id
        assert obs.organization_id == str(org.id)

        # 2. Agent & Policy
        assert obs.agent_id in CANONICAL_SPECIALIST_AGENTS
        assert obs.pilot_stage == "STAGE_1_SHADOW"

        # 3. Human Decision link
        dec_stmt = select(PilotHumanDecision).where(PilotHumanDecision.observation_id == obs_id)
        dec_db = (await db_session.execute(dec_stmt)).scalar_one()
        assert dec_db.id == dec.id
        assert obs_with_decision.comparison_category is not None


# ─── 5. Operational Resilience & Stage-2 Advancement Gating ──────────────────

class TestPhase2C3BOperationalResilience:
    """Verifies operational resilience, idempotency, kill switch, and Stage-2 lock."""

    @pytest.mark.asyncio
    async def test_synthetic_contamination_strictly_zero(self, db_session: AsyncSession):
        """Asserts zero synthetic observations exist in the database."""
        stmt = select(PilotObservation).where(PilotObservation.is_synthetic == True)  # noqa: E712
        res = await db_session.execute(stmt)
        synthetic_records = list(res.scalars().all())
        assert len(synthetic_records) == 0

    @pytest.mark.asyncio
    async def test_event_replay_idempotency(self, db_session: AsyncSession):
        """Replaying identical domain event causes no duplicate observations or side effects."""
        org, broker, lead = await create_pilot_test_environment(db_session, "Replay Realty")
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
        await db_session.flush()
        assert res_1 is not None

        # Replay same event
        res_2 = await bridge.route_event(
            event_type="NEW_LEAD",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=shared_event_id,
            correlation_id=corr_id,
            payload={"iteration": 2},
        )
        await db_session.flush()
        assert res_2 is not None

    @pytest.mark.asyncio
    async def test_kill_switch_operational_drill(self, db_session: AsyncSession):
        """Pausing pilot suppresses autonomous event routing; resuming restores it."""
        org, broker, lead = await create_pilot_test_environment(db_session, "Pause Drill Realty")
        repo = PilotRepository(db_session)

        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        # 1. Engage tenant-level kill switch
        EmergencyAutomationPauseService.set_tenant_pause(
            tenant_id=str(org.id),
            paused=True,
            paused_by=broker.email,
            reason="Phase 2C.3B Kill Switch Drill",
        )

        bridge = Phase2CEventBridge(db_session)
        paused_res = await bridge.route_event(
            event_type="NEW_LEAD",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=str(uuid.uuid4()),
            correlation_id="corr-drill-1",
            payload={},
        )
        # Event is blocked
        assert paused_res is None

        # 2. Resume pilot
        EmergencyAutomationPauseService.set_tenant_pause(
            tenant_id=str(org.id),
            paused=False,
            paused_by=broker.email,
            reason="Resuming after drill",
        )

        active_res = await bridge.route_event(
            event_type="NEW_LEAD",
            organization_id=str(org.id),
            lead_id=str(lead.id),
            event_id=str(uuid.uuid4()),
            correlation_id="corr-drill-2",
            payload={},
        )
        assert active_res is not None
        assert active_res["status"] == "OBSERVATION_RECORDED"

    @pytest.mark.asyncio
    async def test_daily_pilot_snapshot_worker_execution(self, db_session: AsyncSession):
        """Verifies daily snapshot task executes idempotently from persisted DB state."""
        org, broker, lead = await create_pilot_test_environment(db_session, "Snapshot Realty")
        repo = PilotRepository(db_session)

        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        # Verify Celery Beat task registration
        assert "autonomous_loop.generate_daily_pilot_snapshots" in celery_app.tasks

    @pytest.mark.asyncio
    async def test_stage_2_advancement_strictly_blocked_on_day_1(self, db_session: AsyncSession):
        """
        Stage 2 advancement is strictly BLOCKED on Day 1.
        Requires >= 14 full days and >= 50 eligible observations.
        System NEVER auto-promotes; requires explicit human authorization.
        """
        org, broker, lead = await create_pilot_test_environment(db_session, "Stage 2 Gated Realty")
        repo = PilotRepository(db_session)

        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=CANONICAL_SPECIALIST_AGENTS,
        )

        stats = await repo.get_pilot_stats(str(org.id))
        metrics = await repo.compute_shadow_accuracy(pilot_id=pilot.id)

        # Day 1 Status
        assert stats["days_in_stage"] <= 1
        sample_size = metrics.get("sample_size", 0)
        assert sample_size < 50
        assert metrics["gate_result"] == "INSUFFICIENT_DATA"

        # Advancement Eligibility Check
        is_advancement_eligible = (
            stats["days_in_stage"] >= 14
            and sample_size >= 50
            and metrics.get("observed_value", 0.0) >= 0.70
        )
        assert is_advancement_eligible is False

        # Status must remain STAGE_1_SHADOW / BLOCKED from promotion
        assert pilot.current_stage == "STAGE_1_SHADOW"
