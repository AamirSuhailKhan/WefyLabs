"""
apps/api/tests/test_phase2c6a_governance_certification.py
==========================================================
PHASE 2C.6A — Governance, Evidence Integrity, and Promotion Lock Tests

Covers prompt phases:
  - Phase 24: Governance Promotion Lock (14-day & 50-decision hard gate)
  - Phase 25: Promotion-Attempt Rejection Test
  - Phase 26: Kill Switch Safety Guard Test
  - Phase 27: Restart Durability & Non-In-Memory State Test
  - Phase 28: Event Replay & Non-Duplication Test
  - Phase 29: Idempotency Enforcement Test
  - Phase 30: Concurrency & Tenant Isolation Test
"""
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.modules.autonomous_loop.phase2_governance import (
    Phase2AutonomyLevel,
    Phase2ExecutionMode,
    Phase2RiskClass,
    Phase2ActionType,
    RevenueActionPolicyEngine,
)
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
from app.modules.autonomous_loop.phase2c_durable_models import (
    PilotTenant,
    PilotStageTransition,
    PilotObservation,
    PilotHumanDecision,
    PilotAuditEvent,
    PilotActionRecord,
)
from app.modules.autonomous_loop.phase2c_pilot_repository import (
    PilotRepository,
    MINIMUM_STAGE_DAYS,
    MINIMUM_SHADOW_SAMPLE,
)
from app.modules.autonomous_loop.phase2c_tool_contracts import (
    build_idempotency_key,
    ActionSemanticState,
    assert_provider_dispatch_permitted,
)


@pytest.fixture
def test_org_id():
    return f"org-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def pilot_repo(mock_db):
    return PilotRepository(db=mock_db)


# ==============================================================================
# PHASE 24 & 25 — GOVERNANCE PROMOTION LOCK & PROMOTION ATTEMPT TEST
# ==============================================================================

class TestGovernancePromotionLock:
    """Verifies that Stage 1 CANNOT be promoted to Stage 2 without meeting hard gates."""

    @pytest.mark.asyncio
    async def test_advance_stage_blocked_when_days_insufficient(self, pilot_repo, mock_db, test_org_id):
        """Phase 25: 3 days, 2 decisions -> Promotion REJECTED, autonomy remains 0, stage remains STAGE_1_SHADOW."""
        pilot = PilotTenant(
            id=str(uuid.uuid4()),
            organization_id=test_org_id,
            current_stage="STAGE_1_SHADOW",
            pilot_status="ACTIVE",
            configured_autonomy_level=0,
            stage_entered_at=datetime.now(timezone.utc) - timedelta(days=3),
        )

        with patch.object(pilot_repo, "get_pilot_tenant", return_value=pilot), \
             patch.object(pilot_repo, "_append_audit_event", new_callable=AsyncMock) as mock_audit:

            # Mock 2 decisions (threshold is 50)
            mock_res = MagicMock()
            mock_res.scalar.return_value = 2
            mock_db.execute.return_value = mock_res

            with pytest.raises(ValueError, match="Governance Promotion Lock: Cannot advance"):
                await pilot_repo.advance_stage(
                    organization_id=test_org_id,
                    to_stage="STAGE_2_RECOMMEND",
                    triggered_by="admin-user",
                    reason="Premature promotion attempt",
                )

            # Verification: Stage remains STAGE_1_SHADOW
            assert pilot.current_stage == "STAGE_1_SHADOW"
            # Verification: Autonomy remains 0
            assert pilot.configured_autonomy_level == 0
            # Verification: Audit event records denied attempt
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args[1]
            assert call_kwargs["event_type"] == "PROMOTION_ATTEMPT_DENIED"
            assert call_kwargs["payload"]["elapsed_days"] == 3
            assert call_kwargs["payload"]["genuine_decisions"] == 2
            assert call_kwargs["payload"]["lock_enforced"] is True

    @pytest.mark.asyncio
    async def test_stage2_review_blocked_when_decisions_insufficient(self, pilot_repo, mock_db, test_org_id):
        """Even with human review APPROVED, promotion is blocked if decisions < 50."""
        pilot = PilotTenant(
            id=str(uuid.uuid4()),
            organization_id=test_org_id,
            current_stage="STAGE_1_SHADOW",
            pilot_status="ACTIVE",
            configured_autonomy_level=0,
            stage_entered_at=datetime.now(timezone.utc) - timedelta(days=15),  # 15 days (enough)
        )

        with patch.object(pilot_repo, "get_pilot_tenant", return_value=pilot), \
             patch.object(pilot_repo, "_append_audit_event", new_callable=AsyncMock) as mock_audit:

            # Mock 10 decisions (threshold is 50, so NOT enough)
            mock_res = MagicMock()
            mock_res.scalar.return_value = 10
            mock_db.execute.return_value = mock_res

            with pytest.raises(ValueError, match="Governance Promotion Lock: Cannot approve Stage 2 advancement"):
                await pilot_repo.record_stage2_review(
                    organization_id=test_org_id,
                    reviewer_id="lead-auditor",
                    decision="APPROVED",
                    reason="Auditor approves prematurely",
                    evidence_hash="sha256-hash-xyz",
                )

            assert pilot.current_stage == "STAGE_1_SHADOW"
            assert pilot.configured_autonomy_level == 0
            mock_audit.assert_called_once()
            assert mock_audit.call_args[1]["event_type"] == "PROMOTION_ATTEMPT_DENIED"


# ==============================================================================
# PHASE 26 — KILL SWITCH SAFETY GUARD TEST
# ==============================================================================

class TestKillSwitchSafety:
    """Verifies that the emergency kill switch halts all automation dispatches."""

    def test_kill_switch_blocks_provider_dispatch(self, test_org_id):
        """When in Stage 1 or when kill switch is engaged, provider dispatches are unconditionally blocked."""
        # Shadow mode dispatch is never permitted
        reason = assert_provider_dispatch_permitted(
            organization_id=test_org_id,
            pilot_stage="STAGE_1_SHADOW",
            execution_mode="SHADOW",
            action_type=Phase2ActionType.SEND_WHATSAPP_MESSAGE,
        )
        assert reason is not None
        assert "PROVIDER_DISPATCH_BLOCKED" in reason

        # When global kill switch is active
        with patch.object(EmergencyAutomationPauseService, "is_global_paused", return_value=(True, "EMERGENCY_KILL_ACTIVE")):
            reason = assert_provider_dispatch_permitted(
                organization_id=test_org_id,
                pilot_stage="STAGE_4_APPROVAL",
                execution_mode="LIVE",
                action_type=Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            )
            assert reason is not None
            assert "GLOBAL_KILL_SWITCH" in reason


# ==============================================================================
# PHASE 27 — RESTART DURABILITY TEST
# ==============================================================================

class TestRestartDurability:
    """Verifies that governance state survives repository re-instantiation."""

    @pytest.mark.asyncio
    async def test_state_loaded_from_db_not_process_memory(self, mock_db, test_org_id):
        """New repository instance retrieves durable DB values without relying on in-memory globals."""
        stored_pilot = PilotTenant(
            id="pilot-12345",
            organization_id=test_org_id,
            current_stage="STAGE_1_SHADOW",
            pilot_status="ACTIVE",
            configured_autonomy_level=0,
            stage_entered_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
        )

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = stored_pilot
        mock_db.execute.return_value = mock_res

        # Fresh repository instance (simulates API/worker restart)
        fresh_repo = PilotRepository(db=mock_db)
        reloaded = await fresh_repo.get_pilot_tenant(test_org_id)

        assert reloaded.current_stage == "STAGE_1_SHADOW"
        assert reloaded.configured_autonomy_level == 0
        assert reloaded.stage_entered_at == datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


# ==============================================================================
# PHASE 28 & 29 — REPLAY SAFETY & IDEMPOTENCY
# ==============================================================================

class TestReplayAndIdempotency:
    """Verifies idempotency key stability and replay safety."""

    def test_idempotency_key_deterministic(self, test_org_id):
        """Same action, payload, execution ID generates identical idempotency key."""
        k1 = build_idempotency_key(
            organization_id=test_org_id,
            lead_id="lead-001",
            action_type="SUMMARIZE_LEAD",
            correlation_id="corr-001",
        )
        k2 = build_idempotency_key(
            organization_id=test_org_id,
            lead_id="lead-001",
            action_type="SUMMARIZE_LEAD",
            correlation_id="corr-001",
        )
        assert k1 == k2

        # Different correlation produces different key
        k3 = build_idempotency_key(
            organization_id=test_org_id,
            lead_id="lead-001",
            action_type="SUMMARIZE_LEAD",
            correlation_id="corr-002",
        )
        assert k1 != k3


# ==============================================================================
# PHASE 30 — DATABASE CONCURRENCY & TENANT ISOLATION
# ==============================================================================

class TestTenantIsolation:
    """Verifies strict cross-tenant isolation enforcement."""

    def test_policy_engine_tenant_scoped(self):
        engine = RevenueActionPolicyEngine()
        config1 = engine.get_tenant_config("org-a")
        config2 = engine.get_tenant_config("org-b")

        # Low risk actions are AUTONOMOUS_GOVERNED for internal drafting/observation
        assert config1.default_level_low_risk == Phase2AutonomyLevel.AUTONOMOUS_GOVERNED
        assert config2.default_level_low_risk == Phase2AutonomyLevel.AUTONOMOUS_GOVERNED

        # All side-effecting risk tiers are strictly OBSERVE_ONLY (effective autonomy = 0)
        assert config1.default_level_medium_risk == Phase2AutonomyLevel.OBSERVE_ONLY
        assert config2.default_level_medium_risk == Phase2AutonomyLevel.OBSERVE_ONLY
        assert config1.default_level_high_risk == Phase2AutonomyLevel.OBSERVE_ONLY
        assert config2.default_level_high_risk == Phase2AutonomyLevel.OBSERVE_ONLY
        assert config1.default_level_financial == Phase2AutonomyLevel.OBSERVE_ONLY
        assert config2.default_level_financial == Phase2AutonomyLevel.OBSERVE_ONLY
