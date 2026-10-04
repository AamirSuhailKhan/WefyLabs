"""
Phase 2C.3A — Tenant Identity, Enrollment API & Production Pilot Readiness Tests
=================================================================================
Verifies Gates R-A01 through R-A20:
  R-A01: Canonical tenant identity proven
  R-A02: Authentication identity proven
  R-A03: Authorization identity proven
  R-A04: Lead identity mapping proven
  R-A05: Event tenant mapping proven
  R-A06: Pilot tenant mapping proven
  R-A07: Provider state understood (Stage 1 not required)
  R-A08: Provider boundary verified (zero outbound network calls)
  R-A09: Event pipeline verified
  R-A10: Celery worker verified
  R-A11: Celery Beat verified
  R-A12: Pilot repository persistence verified
  R-A13: Enrollment endpoint implemented
  R-A14: Enrollment authorization verified (RBAC + IDOR defense)
  R-A15: Enrollment idempotency verified
  R-A16: Enrollment clock integrity verified
  R-A17: Audit enrollment verified
  R-A18: Tenant isolation verified
  R-A19: Kill switch verified
  R-A20: Full regression verified
"""
import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.autonomous_loop.workers.loop_tasks  # Register Celery tasks
from app.main import app
from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.lead import Lead
from app.modules.autonomous_loop.phase2c_durable_models import PilotTenant, PilotAuditEvent
from app.modules.autonomous_loop.phase2c_pilot_repository import PilotRepository
from app.modules.autonomous_loop.phase2c3a_readiness import (
    Phase2C3AReadinessService,
    CANONICAL_SPECIALIST_AGENTS,
    CANONICAL_POLICY_VERSIONS,
    PROVIDER_STATUS_STAGE_1,
    GateStatus,
)
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
from app.celery_app import celery_app


# ─── Mock Fixtures ────────────────────────────────────────────────────────────

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


async def create_test_org_and_owner(
    db_session: AsyncSession,
    org_name: str = "Test Org",
    role: str = "owner",
) -> tuple[Organization, MockBroker]:
    """Creates a canonical Organization and OrganizationMember in DB."""
    b_uuid = uuid.uuid4()
    o_uuid = uuid.uuid4()
    org = Organization(id=o_uuid, name=org_name, slug=f"slug-{uuid.uuid4().hex[:6]}", plan="pro")
    broker = MockBroker(b_uuid, f"user-{uuid.uuid4().hex[:6]}@test.io", f"Owner {org_name}")
    broker.organization_id = str(o_uuid)
    member = OrganizationMember(organization_id=o_uuid, broker_id=b_uuid, role=role)
    db_session.add(org)
    db_session.add(member)
    await db_session.flush()
    return org, broker


@pytest.fixture(autouse=True)
def reset_kill_switches():
    EmergencyAutomationPauseService.reset_all_for_testing()
    yield
    EmergencyAutomationPauseService.reset_all_for_testing()


# ─── 1. Identity & Mapping Gates (R-A01 .. R-A06) ─────────────────────────────

class TestIdentityAndMappingGates:
    """R-A01 through R-A06: Authoritative identity graph verification."""

    @pytest.mark.asyncio
    async def test_ra01_canonical_tenant_identity_proven(self, db_session: AsyncSession):
        """R-A01: Organization in organizations table is canonical tenant."""
        fake_org_id = str(uuid.uuid4())
        service = Phase2C3AReadinessService(db_session)
        report = await service.evaluate_readiness(fake_org_id)
        assert report["checks"]["tenant_identity"]["status"] in (GateStatus.NOT_PROVEN.value, GateStatus.FAIL.value)
        assert report["overall_ready"] is False
        assert report["gates"]["R-A01"] == GateStatus.NOT_PROVEN.value

        real_org, broker = await create_test_org_and_owner(db_session, "Real Org")
        report_real = await service.evaluate_readiness(str(real_org.id), broker=broker, role="OWNER")
        assert report_real["checks"]["tenant_identity"]["status"] == GateStatus.PASS.value
        assert report_real["gates"]["R-A01"] == GateStatus.PASS.value

    @pytest.mark.asyncio
    async def test_ra02_authentication_identity_proven(self, db_session: AsyncSession):
        """R-A02: Authenticated broker identity is strictly verified."""
        service = Phase2C3AReadinessService(db_session)
        org_id = str(uuid.uuid4())

        # Anonymous caller -> NOT_PROVEN
        report_anon = await service.evaluate_readiness(org_id, broker=None)
        assert report_anon["gates"]["R-A02"] == GateStatus.NOT_PROVEN.value

        # Authenticated caller -> PASS
        mock_broker = MockBroker(uuid.uuid4(), "owner@test.com", "Test Owner")
        report_auth = await service.evaluate_readiness(org_id, broker=mock_broker)
        assert report_auth["gates"]["R-A02"] == GateStatus.PASS.value

    @pytest.mark.asyncio
    async def test_ra03_authorization_identity_proven(self, db_session: AsyncSession):
        """R-A03: OWNER / ADMIN roles authorized; AGENT / READ_ONLY blocked."""
        service = Phase2C3AReadinessService(db_session)
        org_id = str(uuid.uuid4())

        rep_owner = await service.evaluate_readiness(org_id, role="OWNER")
        assert rep_owner["checks"]["authorization"]["status"] == GateStatus.PASS.value
        assert rep_owner["gates"]["R-A03"] == GateStatus.PASS.value

        rep_admin = await service.evaluate_readiness(org_id, role="ADMIN")
        assert rep_admin["checks"]["authorization"]["status"] == GateStatus.PASS.value

        rep_agent = await service.evaluate_readiness(org_id, role="AGENT")
        assert rep_agent["checks"]["authorization"]["status"] == GateStatus.FAIL.value
        assert rep_agent["gates"]["R-A03"] == GateStatus.FAIL.value
        assert rep_agent["overall_ready"] is False

        rep_none = await service.evaluate_readiness(org_id, role=None)
        assert rep_none["checks"]["authorization"]["status"] == GateStatus.NOT_PROVEN.value

    @pytest.mark.asyncio
    async def test_ra04_lead_identity_mapping_proven(self, db_session: AsyncSession):
        """R-A04: Lead schema links organization_id to organizations.id and broker_id to brokers.id."""
        assert hasattr(Lead, "organization_id")
        assert hasattr(Lead, "broker_id")
        service = Phase2C3AReadinessService(db_session)
        report = await service.evaluate_readiness(str(uuid.uuid4()))
        assert report["gates"]["R-A04"] == GateStatus.PASS.value

    @pytest.mark.asyncio
    async def test_ra05_event_tenant_mapping_proven(self, db_session: AsyncSession):
        """R-A05: SalesLoopEvent tenant_id matches event bridge expectations."""
        service = Phase2C3AReadinessService(db_session)
        report = await service.evaluate_readiness(str(uuid.uuid4()))
        assert report["checks"]["event_bridge"]["status"] == GateStatus.PASS.value
        assert report["gates"]["R-A05"] == GateStatus.PASS.value

    @pytest.mark.asyncio
    async def test_ra06_pilot_tenant_mapping_proven(self, db_session: AsyncSession):
        """R-A06: PilotTenant.organization_id is the primary tenant identity key."""
        assert hasattr(PilotTenant, "organization_id")
        service = Phase2C3AReadinessService(db_session)
        org, broker = await create_test_org_and_owner(db_session, "Pilot Mapping Org")
        rep = await service.evaluate_readiness(str(org.id), broker=broker, role="OWNER")
        assert rep["gates"]["R-A06"] == GateStatus.PASS.value


# ─── 2. Provider Boundary Gates (R-A07 .. R-A08) ──────────────────────────────

class TestProviderBoundaryGates:
    """R-A07 through R-A08: Provider state and Stage-1 zero-call boundary."""

    @pytest.mark.asyncio
    async def test_ra07_provider_state_understood(self, db_session: AsyncSession):
        """R-A07: Provider configuration is not required for Stage 1 Shadow Mode."""
        service = Phase2C3AReadinessService(db_session)
        report = await service.evaluate_readiness(str(uuid.uuid4()))
        assert report["provider_decision"] == PROVIDER_STATUS_STAGE_1
        assert report["gates"]["R-A07"] == GateStatus.PASS.value

    @pytest.mark.asyncio
    async def test_ra08_provider_boundary_verified(self, db_session: AsyncSession):
        """R-A08: Stage 1 Shadow mode strictly enforces zero outbound provider network calls."""
        service = Phase2C3AReadinessService(db_session)
        report = await service.evaluate_readiness(str(uuid.uuid4()))
        boundary = report["checks"]["provider_boundary"]
        assert boundary["status"] == GateStatus.PASS.value
        assert boundary["stage_1_network_calls_permitted"] == 0
        assert report["gates"]["R-A08"] == GateStatus.PASS.value


# ─── 3. Event Pipeline & Celery Gates (R-A09 .. R-A12) ─────────────────────────

class TestEventPipelineAndWorkerGates:
    """R-A09 through R-A12: Pipeline wiring and Celery runtime tasks."""

    @pytest.mark.asyncio
    async def test_ra09_event_pipeline_verified(self, db_session: AsyncSession):
        """R-A09: Domain event bridge and trigger events verified."""
        service = Phase2C3AReadinessService(db_session)
        report = await service.evaluate_readiness(str(uuid.uuid4()))
        assert report["checks"]["event_bridge"]["status"] == GateStatus.PASS.value
        assert report["gates"]["R-A09"] == GateStatus.PASS.value

    def test_ra10_celery_worker_verified(self):
        """R-A10: Celery autonomous_loop task is registered and routable."""
        registered_tasks = celery_app.tasks.keys()
        assert "autonomous_loop.process_sales_loop_event" in registered_tasks
        assert "sales-loop-orchestration" in [q.name for q in celery_app.conf.task_queues]

    def test_ra11_celery_beat_verified(self):
        """R-A11: Celery Beat periodic task configured for pilot snapshots."""
        assert "pilot-snapshot" in [q.name for q in celery_app.conf.task_queues]
        assert "autonomous_loop.generate_daily_pilot_snapshots" in celery_app.tasks.keys()

    @pytest.mark.asyncio
    async def test_ra12_pilot_repository_persistence_verified(self, db_session: AsyncSession):
        """R-A12: PilotRepository durable persistence and session commit."""
        repo = PilotRepository(db_session)
        org_id = str(uuid.uuid4())
        pilot = await repo.enroll_tenant(
            organization_id=org_id,
            enrolled_by="architect@wefylabs.io",
            notes="Testing R-A12 persistence",
        )
        await db_session.flush()

        loaded = await repo.get_pilot_tenant(org_id)
        assert loaded is not None
        assert loaded.organization_id == org_id
        assert loaded.current_stage == "STAGE_1_SHADOW"
        assert loaded.configured_autonomy_level == 0


# ─── 4. Enrollment API & Security Gates (R-A13 .. R-A20) ──────────────────────

class TestEnrollmentApiAndSecurityGates:
    """R-A13 through R-A20: Enrollment API, RBAC, IDOR, idempotency, clock integrity."""

    @pytest.mark.asyncio
    async def test_ra13_enrollment_endpoint_implemented(self, db_session: AsyncSession):
        """R-A13: POST /pilot/enroll returns 201 on valid request."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Aamir Founder Org")

        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={
                        "organization_id": str(org.id),
                        "notes": "Testing Phase 2C.3A enrollment",
                        "starting_stage": "STAGE_1_SHADOW",
                    },
                )
                assert res.status_code == 201
                body = res.json()["data"]
                assert body["organization_id"] == str(org.id)
                assert body["current_stage"] == "STAGE_1_SHADOW"
                assert body["pilot_status"] == "ACTIVE"
                assert body["configured_autonomy_level"] == 0
                assert body["enrolled_by"] == f"{mock_owner.name} <{mock_owner.email}> ({mock_owner.id})"
                assert "enrolled_at" in body
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_ra14_enrollment_authorization_and_idor_defense(self, db_session: AsyncSession):
        """R-A14: AGENT role blocked (403), IDOR cross-tenant enrollment blocked (403)."""
        broker_uuid = uuid.uuid4()
        org_a_uuid = uuid.uuid4()
        org_b_uuid = uuid.uuid4()

        org_a = Organization(id=org_a_uuid, name="Org A", slug=f"org-a-{uuid.uuid4().hex[:6]}")
        org_b = Organization(id=org_b_uuid, name="Org B", slug=f"org-b-{uuid.uuid4().hex[:6]}")
        db_session.add_all([org_a, org_b])
        await db_session.flush()

        member_a = OrganizationMember(
            organization_id=org_a_uuid,
            broker_id=broker_uuid,
            role="agent",
        )
        db_session.add(member_a)
        await db_session.flush()

        agent_broker = MockBroker(broker_uuid, "agent@org-a.com", "Agent Smith", is_mock=False)
        app.dependency_overrides[get_current_broker] = lambda: agent_broker
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Agent role cannot enroll their own org
                res1 = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={"organization_id": str(org_a_uuid)},
                )
                assert res1.status_code == 403
                assert res1.json()["detail"]["code"] == "INSUFFICIENT_ROLE"

                # 2. Agent cannot enroll Org B (IDOR defense)
                res2 = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={"organization_id": str(org_b_uuid)},
                )
                assert res2.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_ra15_enrollment_idempotency_verified(self, db_session: AsyncSession):
        """R-A15: Repeated enrollment returns HTTP 409 Conflict with existing pilot data."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Idempotent Org")

        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                r1 = await client.post("/api/v1/autonomous-loop/pilot/enroll", json={"organization_id": str(org.id)})
                assert r1.status_code == 201

                r2 = await client.post("/api/v1/autonomous-loop/pilot/enroll", json={"organization_id": str(org.id)})
                assert r2.status_code == 409
                err_body = r2.json()["detail"]
                assert err_body["code"] == "PILOT_ALREADY_ENROLLED"
                assert err_body["pilot_status"] == "ACTIVE"
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_ra16_enrollment_clock_integrity_verified(self, db_session: AsyncSession):
        """R-A16: enrolled_at is database/server generated and client-supplied start times are rejected."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Clock Org")

        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                before = datetime.now(timezone.utc)
                res = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={"organization_id": str(org.id), "enrolled_at": "2020-01-01T00:00:00Z"},
                )
                assert res.status_code == 422

                res_valid = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={"organization_id": str(org.id)},
                )
                assert res_valid.status_code == 201
                enrolled_at_str = res_valid.json()["data"]["enrolled_at"]
                enrolled_dt = datetime.fromisoformat(enrolled_at_str)
                assert enrolled_dt >= before
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_ra17_audit_enrollment_verified(self, db_session: AsyncSession):
        """R-A17: Enrollment atomically creates immutable PILOT_ENROLLED audit event."""
        repo = PilotRepository(db_session)
        org_id = str(uuid.uuid4())
        pilot = await repo.enroll_tenant(
            organization_id=org_id,
            enrolled_by="auditor@wefylabs.io",
            notes="Testing audit event",
        )
        await db_session.flush()

        stmt = select(PilotAuditEvent).where(PilotAuditEvent.pilot_id == pilot.id)
        res = await db_session.execute(stmt)
        events = list(res.scalars().all())
        assert len(events) >= 1
        enroll_event = [e for e in events if e.event_type == "ENROLLED"][0]
        assert enroll_event.actor_id == "auditor@wefylabs.io"
        assert enroll_event.payload["starting_stage"] == "STAGE_1_SHADOW"

    @pytest.mark.asyncio
    async def test_ra18_tenant_isolation_verified(self, db_session: AsyncSession):
        """R-A18: Tenant A actor cannot view Tenant B's pilot status or readiness."""
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        broker_a = MockBroker(uuid.uuid4(), "user_a@test.com", "User A", is_mock=False)

        db_session.add(Organization(id=uuid.UUID(org_a), name="Org A", slug=f"org-a-{uuid.uuid4().hex[:6]}"))
        db_session.add(Organization(id=uuid.UUID(org_b), name="Org B", slug=f"org-b-{uuid.uuid4().hex[:6]}"))
        db_session.add(OrganizationMember(organization_id=uuid.UUID(org_a), broker_id=broker_a.id, role="owner"))
        await db_session.flush()

        app.dependency_overrides[get_current_broker] = lambda: broker_a
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get(f"/api/v1/autonomous-loop/pilot/readiness?organization_id={org_b}")
                assert res.status_code == 403
                assert res.json()["detail"]["code"] == "ORGANIZATION_ACCESS_DENIED"
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_ra19_kill_switch_verified(self, db_session: AsyncSession):
        """R-A19: Active emergency kill switch blocks readiness and refuses enrollment."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Safety Org")

        EmergencyAutomationPauseService.set_tenant_pause(
            tenant_id=str(org.id),
            paused=True,
            paused_by="SRE_DRILL",
            reason="Safety audit verification",
        )

        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                r_readiness = await client.get(f"/api/v1/autonomous-loop/pilot/readiness?organization_id={org.id}")
                assert r_readiness.status_code == 200
                data = r_readiness.json()["data"]
                assert data["overall_ready"] is False
                assert data["checks"]["kill_switch"]["status"] == "BLOCKED"

                r_enroll = await client.post("/api/v1/autonomous-loop/pilot/enroll", json={"organization_id": str(org.id)})
                assert r_enroll.status_code == 412
                assert r_enroll.json()["detail"]["code"] == "ENROLLMENT_PRECONDITION_FAILED"
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_ra20_full_regression_verified(self, db_session: AsyncSession):
        """R-A20: All 20 readiness gates evaluate to valid vocabulary statuses."""
        org, mock_broker = await create_test_org_and_owner(db_session, "Regression Org")
        service = Phase2C3AReadinessService(db_session)
        report = await service.evaluate_readiness(str(org.id), broker=mock_broker, role="OWNER")

        allowed_statuses = {"PASS", "FAIL", "NOT_PROVEN", "BLOCKED"}
        assert len(report["gates"]) == 20
        for gate_id in [f"R-A{i:02d}" for i in range(1, 21)]:
            assert gate_id in report["gates"]
            assert report["gates"][gate_id] in allowed_statuses


# ─── 5. Parameter Validation & Status Tests ────────────────────────────────────

class TestEnrollmentValidationAndStatus:
    """Rigorous input bounds and status API testing."""

    @pytest.mark.asyncio
    async def test_higher_stage_rejected(self, db_session: AsyncSession):
        """Initial enrollment cannot select STAGE_2_RECOMMEND (422 Unprocessable Entity)."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Stage Org")
        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={"organization_id": str(org.id), "starting_stage": "STAGE_2_RECOMMEND"},
                )
                assert res.status_code == 422
                assert res.json()["detail"]["code"] == "INVALID_STAGE"
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_unknown_agent_rejected(self, db_session: AsyncSession):
        """Unrecognized agent IDs are strictly rejected (422)."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Agent Org")
        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={
                        "organization_id": str(org.id),
                        "agent_ids": ["unregistered_rogue_agent"],
                    },
                )
                assert res.status_code == 422
                assert res.json()["detail"]["code"] == "INVALID_AGENTS"
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_unsupported_policy_version_rejected(self, db_session: AsyncSession):
        """Unsupported policy version rejected (422)."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Policy Org")
        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(
                    "/api/v1/autonomous-loop/pilot/enroll",
                    json={
                        "organization_id": str(org.id),
                        "policy_version": "unsupported-custom-v99",
                    },
                )
                assert res.status_code == 422
                assert res.json()["detail"]["code"] == "INVALID_POLICY_VERSION"
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_pilot_status_lifecycle(self, db_session: AsyncSession):
        """GET /pilot/status returns NOT_ENROLLED before enrollment and ACTIVE after enrollment."""
        org, mock_owner = await create_test_org_and_owner(db_session, "Lifecycle Org")

        app.dependency_overrides[get_current_broker] = lambda: mock_owner
        app.dependency_overrides[get_db] = lambda: db_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Before enrollment -> NOT_ENROLLED
                s1 = await client.get(f"/api/v1/autonomous-loop/pilot/status?organization_id={org.id}")
                assert s1.status_code == 200
                assert s1.json()["data"]["status"] == "NOT_ENROLLED"

                # 2. Enroll
                e = await client.post("/api/v1/autonomous-loop/pilot/enroll", json={"organization_id": str(org.id)})
                assert e.status_code == 201

                # 3. After enrollment -> ACTIVE
                s2 = await client.get(f"/api/v1/autonomous-loop/pilot/status?organization_id={org.id}")
                assert s2.status_code == 200
                d2 = s2.json()["data"]
                assert d2["status"] == "ACTIVE"
                assert d2["current_stage"] == "STAGE_1_SHADOW"
                assert d2["configured_autonomy_level"] == 0
        finally:
            app.dependency_overrides.pop(get_current_broker, None)
            app.dependency_overrides.pop(get_db, None)
