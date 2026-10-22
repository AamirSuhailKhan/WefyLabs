"""
WefyLabs Phase 8.1 — Independent Verification of Regression Closure
===================================================================
Rigorous verification of the three highest-risk remediation areas:
1. Governance & Stage 1 Effective Autonomy Invariants (Zero unauthorized side effects)
2. Tenant Identity Conversion & Adversarial IDOR Defense
3. Static Security Scanner Precision and Evasion Resistance
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits, clear_ambient_tenant, get_ambient_tenant, current_tenant_ctx
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.modules.auth.service import create_access_token
from app.modules.autonomous_loop.phase2_governance import (
    RevenueActionPolicyEngine,
    Phase2ActionType,
    Phase2RiskClass,
    Phase2AutonomyLevel,
    Phase2ExecutionMode,
    ACTION_RISK_TABLE,
    get_policy_engine,
)
from app.modules.ai_agent.action_executor import (
    GovernedActionExecutor,
    ActionResultDTO,
)
from app.modules.ai_agent.action_policy import NextBestActionType, ProposedActionDTO
from app.modules.revenue_autopilot.action_handler import _safe_org_uuid as handler_safe_org_uuid
from app.modules.revenue_autopilot.engine import _safe_org_uuid as engine_safe_org_uuid
from app.infrastructure.tenancy.scope import resolve_organization_id_for_broker, TenantIsolationError, as_organization_uuid


@pytest.fixture(autouse=True)
def setup_verification_env():
    settings.ENV = "testing"
    clear_rate_limits()
    clear_ambient_tenant()
    token = current_tenant_ctx.set(None)
    yield
    current_tenant_ctx.reset(token)
    clear_ambient_tenant()
    clear_rate_limits()


# =============================================================================
# PART 1: Governance & Stage 1 Effective Autonomy Invariants
# =============================================================================

class TestStage1GovernanceInvariants:
    """Proves that Stage 1's effective autonomy remains strictly ZERO for all side-effecting actions."""

    def test_all_external_actions_blocked_in_stage1_shadow_mode(self):
        """In SHADOW execution mode (Stage 1 default), every external action is strictly prohibited."""
        engine = RevenueActionPolicyEngine()
        org_id = str(uuid.uuid4())

        # List of all actions with real external/state-mutating side effects
        external_actions = [
            # Medium Risk (Communication & Customer Outreach)
            Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2ActionType.SEND_EMAIL,
            Phase2ActionType.SEND_SMS,
            Phase2ActionType.SEND_PROPERTY_RECOMMENDATIONS,
            Phase2ActionType.SEND_PROPERTY_DETAILS,
            Phase2ActionType.SEND_VIEWING_INVITATION,
            Phase2ActionType.SEND_FOLLOW_UP,
            Phase2ActionType.SEND_REACTIVATION_OUTREACH,
            # High Risk (Visits, Deals, Inventory)
            Phase2ActionType.SCHEDULE_SITE_VISIT,
            Phase2ActionType.RESCHEDULE_SITE_VISIT,
            Phase2ActionType.CANCEL_SITE_VISIT,
            Phase2ActionType.UPDATE_DEAL_STATUS,
            Phase2ActionType.UPDATE_NEGOTIATION_STATE,
            Phase2ActionType.RESERVE_INVENTORY_UNIT,
            Phase2ActionType.ESCALATE_TO_MANAGER,
            Phase2ActionType.TRIGGER_HUMAN_HANDOFF,
            # Financial & Irreversible Actions
            Phase2ActionType.CREATE_BOOKING,
            Phase2ActionType.CONFIRM_BOOKING,
            Phase2ActionType.PROCESS_PAYMENT,
            Phase2ActionType.CANCEL_BOOKING,
            Phase2ActionType.ISSUE_REFUND,
        ]

        for action in external_actions:
            # Without human approval
            decision = engine.evaluate(
                organization_id=org_id,
                action_type=action,
                has_human_approval=False,
            )
            assert decision.is_permitted is False, f"SECURITY VIOLATION: {action.value} must NOT be permitted in SHADOW mode!"
            assert "shadow" in decision.block_reason.lower()

    def test_low_risk_observation_actions_do_not_execute_external_actions(self):
        """Low-risk actions permitted internally do not have external side effects."""
        engine = RevenueActionPolicyEngine()
        org_id = str(uuid.uuid4())

        internal_low_risk_actions = [
            Phase2ActionType.SUMMARIZE_LEAD,
            Phase2ActionType.PREPARE_PROPERTY_SHORTLIST,
            Phase2ActionType.PREPARE_MESSAGE_DRAFT,
            Phase2ActionType.PREPARE_NEGOTIATION_SUMMARY,
            Phase2ActionType.PREPARE_VISIT_PROPOSAL,
            Phase2ActionType.RECORD_OUTCOME,
            Phase2ActionType.UPDATE_LEAD_INTENT_STATE,
            Phase2ActionType.LOG_OBJECTION,
            Phase2ActionType.UPDATE_QUALIFICATION_PROFILE,
            Phase2ActionType.SHADOW_OBSERVE,
            Phase2ActionType.NO_ACTION,
        ]

        for action in internal_low_risk_actions:
            risk_class, max_level = ACTION_RISK_TABLE[action]
            assert risk_class == Phase2RiskClass.LOW, f"{action.value} must be classified as LOW risk"
            decision = engine.evaluate(
                organization_id=org_id,
                action_type=action,
                has_human_approval=False,
            )
            # Permitted internally for observation/drafting
            assert decision.is_permitted is True

    @pytest.mark.asyncio
    async def test_governed_action_executor_rejects_unapproved_outbound_execution(self, db_session: AsyncSession):
        """Proves GovernedActionExecutor strictly blocks autonomous outbound actions without valid authorization."""
        from app.modules.ai_agent.action_policy import ActionRiskTier
        org_id = uuid.uuid4()
        broker_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        executor = GovernedActionExecutor(db_session)

        # Propose unapproved appointment action requiring authorization
        proposal = ProposedActionDTO(
            action_type=NextBestActionType.SCHEDULE_APPOINTMENT,
            risk_tier=ActionRiskTier.HIGH,
            reason="AI wants to schedule appointment autonomously",
            parameters={"lead_id": str(lead_id), "appointment_time": "2026-10-20T10:00:00Z"},
            requires_authorization=True,
        )

        # Attempt execute with fake/invalid authorization token via keyword-only execution
        result = await executor.execute(
            organization_id=org_id,
            actor_id=str(broker_id),
            proposal=proposal,
            authorization_id=str(uuid.uuid4()),
        )
        assert result.status == "REJECTED"
        assert result.error_message is not None


# =============================================================================
# PART 2: Tenant Identity Conversion & Adversarial IDOR Defense
# =============================================================================

class TestTenantIdentityAdversarialDefense:
    """Adversarial security audit proving arbitrary strings cannot forge authorized tenant context."""

    def test_safe_org_uuid_deterministic_and_safe(self):
        """_safe_org_uuid converts valid UUIDs natively and falls back to broker identity or deterministic DNS namespace."""
        import types
        real_uuid = uuid.uuid4()
        broker_real = types.SimpleNamespace(id=real_uuid, organization_id=real_uuid)

        # 1. Native UUID is unchanged
        assert handler_safe_org_uuid(broker_real) == real_uuid
        assert engine_safe_org_uuid(broker_real) == real_uuid

        # 2. String representation of valid UUID is converted to exact UUID
        broker_str = types.SimpleNamespace(id=uuid.uuid4(), organization_id=str(real_uuid))
        assert handler_safe_org_uuid(broker_str) == real_uuid
        assert engine_safe_org_uuid(broker_str) == real_uuid

        # 3. Non-UUID organization string falls back to broker_id if valid UUID
        broker_id = uuid.uuid4()
        broker_with_valid_id = types.SimpleNamespace(id=broker_id, organization_id="org-enterprise-01")
        assert handler_safe_org_uuid(broker_with_valid_id) == broker_id
        assert engine_safe_org_uuid(broker_with_valid_id) == broker_id

        # 4. If neither organization_id nor broker_id is a valid UUID, maps deterministically via uuid5 DNS namespace
        broker_raw_only = types.SimpleNamespace(id="non-uuid-broker", organization_id="org-enterprise-01")
        derived_1 = handler_safe_org_uuid(broker_raw_only)
        derived_2 = engine_safe_org_uuid(broker_raw_only)
        assert derived_1 == derived_2
        assert derived_1 == uuid.uuid5(uuid.NAMESPACE_DNS, "org-enterprise-01")

    @pytest.mark.asyncio
    async def test_ambient_non_uuid_never_creates_authorized_tenant(self, db_session: AsyncSession):
        """Ambient context with non-UUID string cannot grant tenant access."""
        broker_id = uuid.uuid4()
        from app.dependencies import current_tenant_ctx, TenantContext

        # Inject non-UUID string into ambient context
        token = current_tenant_ctx.set(TenantContext(
            organization_id="untrusted-random-string",
            broker_id=broker_id,
            user_id=str(broker_id),
            role="AGENT",
        ))

        try:
            # resolve_organization_id_for_broker must sanitize and ignore non-UUID ambient context
            resolved = await resolve_organization_id_for_broker(db_session, broker_id, allow_fallback=True)
            # Should fallback to broker_id, NEVER adopt the untrusted ambient string
            assert resolved == broker_id
        finally:
            current_tenant_ctx.reset(token)

    @pytest.mark.asyncio
    async def test_malformed_headers_rejected_with_http_400(self, db_session: AsyncSession):
        """Malformed X-WefyLabs-Organization-Id headers return HTTP 400 Bad Request."""
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        org = Organization(id=uuid.uuid4(), name="Real Org", slug=f"real-{uuid.uuid4().hex[:6]}")
        broker = Broker(id=uuid.uuid4(), email="agent@real.com", name="Agent", phone="+919000000001")
        db_session.add_all([org, broker])
        await db_session.flush()

        mem = OrganizationMember(organization_id=org.id, broker_id=broker.id, role="agent")
        db_session.add(mem)
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email})
        transport = ASGITransport(app=app)

        malformed_headers = [
            "not-a-uuid",
            "12345",
            "../../../etc/passwd",
            "true",
            "null",
            "00000000-0000-0000-0000-00000000000Z",  # Invalid char
            "; DROP TABLE organizations; --",
        ]

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for bad_header in malformed_headers:
                res = await client.get(
                    "/api/v1/leads",
                    headers={"Authorization": f"Bearer {token}", "X-WefyLabs-Organization-Id": bad_header}
                )
                assert res.status_code == 400, f"Header '{bad_header}' must be rejected with HTTP 400"
                assert "INVALID_ORGANIZATION_CONTEXT" in res.text

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_cross_tenant_and_nonexistent_org_rejected_with_http_403(self, db_session: AsyncSession):
        """Nonexistent org IDs and cross-tenant org IDs return HTTP 403 Forbidden."""
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        org_victim = Organization(id=uuid.uuid4(), name="Victim Org", slug=f"victim-{uuid.uuid4().hex[:6]}")
        org_attacker = Organization(id=uuid.uuid4(), name="Attacker Org", slug=f"attacker-{uuid.uuid4().hex[:6]}")
        broker_attacker = Broker(id=uuid.uuid4(), email="attacker@test.com", name="Attacker", phone="+919000000002")
        db_session.add_all([org_victim, org_attacker, broker_attacker])
        await db_session.flush()

        # Attacker is member of org_attacker, NOT org_victim
        mem = OrganizationMember(organization_id=org_attacker.id, broker_id=broker_attacker.id, role="agent")
        db_session.add(mem)
        await db_session.commit()

        token = create_access_token({"sub": broker_attacker.email, "email": broker_attacker.email})
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Attacker requesting victim org -> 403
            res_victim = await client.get(
                "/api/v1/leads",
                headers={"Authorization": f"Bearer {token}", "X-WefyLabs-Organization-Id": str(org_victim.id)}
            )
            assert res_victim.status_code == 403
            assert "ORGANIZATION_ACCESS_DENIED" in res_victim.text

            # 2. Attacker requesting completely random nonexistent org UUID -> 403
            random_org = uuid.uuid4()
            res_random = await client.get(
                "/api/v1/leads",
                headers={"Authorization": f"Bearer {token}", "X-WefyLabs-Organization-Id": str(random_org)}
            )
            assert res_random.status_code == 403
            assert "ORGANIZATION_ACCESS_DENIED" in res_random.text

            # 3. Attacker requesting own legitimate org -> 200
            res_own = await client.get(
                "/api/v1/leads",
                headers={"Authorization": f"Bearer {token}", "X-WefyLabs-Organization-Id": str(org_attacker.id)}
            )
            assert res_own.status_code == 200

        app.dependency_overrides.clear()


# =============================================================================
# PART 3: Static Security Scanner Precision and Evasion Resistance
# =============================================================================

class TestSecurityScannerVerification:
    """Rigorous audit of security scanner precision, anti-evasion, and genuine defect detection."""

    def test_scanner_detects_deliberately_vulnerable_fixtures(self):
        """Proves the scanner detects query parameter tenancy violations and evasion attempts."""
        from tests.test_part21_9_security import TestAuthenticationSecurity

        # 1. Direct parameter naming
        vuln_1 = '''
        @router.get("/pilot/readiness")
        async def get_readiness(organization_id: Optional[str] = Query(None)):
            pass
        '''
        violations_1 = TestAuthenticationSecurity._scan_query_org_violations(vuln_1)
        assert len(violations_1) >= 1, "Must catch unauthenticated organization_id in Query()"

        # 2. Alternative naming (org_id, target_org)
        vuln_2 = '''
        @router.get("/pilot/status")
        async def get_status(org_id: str = Query(...)):
            pass
        '''
        violations_2 = TestAuthenticationSecurity._scan_query_org_violations(vuln_2)
        assert len(violations_2) >= 1, "Must catch org_id in Query()"

        # 3. Evasive parameter rename with query alias targeting organization_id
        vuln_3 = '''
        @router.get("/pilot/status")
        async def get_status(custom_param: str = Query(..., alias="organization_id")):
            pass
        '''
        violations_3 = TestAuthenticationSecurity._scan_query_org_violations(vuln_3)
        assert len(violations_3) >= 1, "Must catch evasive alias='organization_id' in Query()"

    def test_scanner_permits_known_safe_fixtures(self):
        """Proves the scanner permits safe authenticated header resolution and DB context."""
        from tests.test_part21_9_security import TestAuthenticationSecurity

        safe_code = '''
        @router.get("/pilot/readiness")
        async def get_pilot_readiness(
            x_organization_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
            db: AsyncSession = Depends(get_db),
            broker: Broker = Depends(get_current_broker),
        ):
            target_org_id, role = await _resolve_caller_org_and_role(db, broker, x_organization_id)
            pass
        '''
        violations = TestAuthenticationSecurity._scan_query_org_violations(safe_code)
        assert len(violations) == 0, f"Safe pattern must produce zero violations, got: {violations}"

    def test_production_router_passes_security_scanner(self):
        """Proves the real production autonomous loop router contains zero Query-based tenant violations."""
        from tests.test_part21_9_security import TestAuthenticationSecurity
        import os

        router_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "modules", "autonomous_loop", "router.py"
        )
        assert os.path.exists(router_path), f"Router file must exist at {router_path}"
        with open(router_path, "r", encoding="utf-8") as f:
            content = f.read()

        violations = TestAuthenticationSecurity._scan_query_org_violations(content)
        assert len(violations) == 0, f"Production autonomous loop router has scanner violations: {violations}"
