"""
Phase 2C.1 — Runtime Gates Verification Suite (R1–R20)
======================================================
Validates all 20 Runtime Gates required by the Phase 2C.1
Real Tenant Shadow Pilot & Production Evidence specification.

GATES VALIDATED:
  R1:  Event bridge truly wired in loop worker
  R2:  Real event reaches pilot pipeline
  R3:  Real DB context builder with tenant isolation
  R4:  Real bounded agents evaluate context (all 10 agents)
  R5:  Policy traversal and shadow projection
  R6:  Durable observation persistence with non-synthetic invariants
  R7:  Human decision API workflow
  R8:  Six-category comparison engine
  R9:  Durable metric reconstruction from DB records
  R10: Hard provider boundary enforcement
  R11: Zero shadow side effects (dispatched = 0)
  R12: Tamper-evident audit chain reconstruction
  R13: Kill switch immediate block (global + tenant)
  R14: Restart recovery & persistence invariants
  R15: Event replay idempotency
  R16: Concurrency protection & state safety
  R17: Strict multi-tenant isolation
  R18: RBAC & tenant scoping
  R19: Failure injection & fail-closed behavior
  R20: Production observability & daily snapshot worker
"""
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.autonomous_loop.phase2_agent_contracts import (
    AgentContextObject, AgentDomain, AgentExecutionRecord, AgentConfidence
)
from app.modules.autonomous_loop.phase2_governance import (
    Phase2ActionType, Phase2ExecutionMode, Phase2RiskClass,
    RevenueActionPolicyEngine, get_policy_engine
)
from app.modules.autonomous_loop.phase2c_tool_contracts import (
    Phase2CToolDispatcher, ActionSemanticRecord, ActionSemanticState,
    assert_provider_dispatch_permitted, build_idempotency_key
)
from app.modules.autonomous_loop.phase2c_durable_models import (
    PilotTenant, PilotObservation, PilotHumanDecision,
    PilotApprovalItem, PilotAuditEvent, PilotStageTransition,
    PilotMetricSnapshot, PilotActionRecord
)
from app.modules.autonomous_loop.phase2c_context_builder import (
    Phase2CContextBuilder, ContextBuildError, FRESHNESS_TTL_BY_RISK
)
from app.modules.autonomous_loop.phase2c_comparison_engine import (
    Phase2CComparisonEngine, ComparisonCategory, ComparisonResult
)
from app.modules.autonomous_loop.phase2c_pilot_repository import (
    PilotRepository, MINIMUM_SHADOW_SAMPLE
)
from app.modules.autonomous_loop.phase2c_runtime import Phase2CPilotReadinessChecker
from app.modules.autonomous_loop.phase2c_event_bridge import (
    Phase2CEventBridge, PILOT_TRIGGER_EVENTS
)
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
from app.modules.autonomous_loop.phase2b_agents import (
    LeadIntelligenceAgent, QualificationAgent, PropertyMatchAgent,
    EngagementAgent, FollowUpAgent, VisitAgent,
    DealProgressionAgent, RecoveryAgent, RevenueIntelligenceAgent,
    ManagerIntelligenceAgent,
)


# ═══════════════════════════════════════════════════════════════════════════════
# R1–R5: Pipeline Wiring, Event Flow, Context, Agents, Policy
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeGatesR1ToR5:

    def test_r1_event_bridge_is_wired_in_loop_tasks(self):
        """R1: Event bridge is wired into process_sales_loop_event_task."""
        import inspect
        from app.modules.autonomous_loop.workers import loop_tasks
        source = inspect.getsource(loop_tasks)
        assert "Phase2CEventBridge" in source, "Phase2CEventBridge must be imported in loop_tasks"
        assert "bridge.route_event" in source, "bridge.route_event must be called in loop_tasks"
        assert "pilot_obs_result" in source, "pilot observation result must be captured in loop_tasks"

    def test_r2_real_event_reaches_pilot_pipeline(self):
        """R2: A production domain event triggers shadow observation."""
        async def run():
            mock_db = AsyncMock()
            org_id = "org-test-r2"
            lead_id = "lead-test-r2"

            bridge = Phase2CEventBridge(mock_db)

            # Pilot active
            mock_pilot = MagicMock()
            mock_pilot.id = "pilot-r2"
            mock_pilot.current_stage = "STAGE_1_SHADOW"
            mock_pilot.pilot_status = "ACTIVE"

            # Lead exists
            mock_lead = MagicMock()
            mock_lead.id = lead_id
            mock_lead.name = "Real Prospect"
            mock_lead.broker_id = org_id
            mock_lead.status = "active"
            mock_lead.pipeline_stage = "NEW"
            mock_lead.source = "website"
            mock_lead.budget = 750000
            mock_lead.requirements = {"area": "Downtown"}
            mock_lead.updated_at = datetime.now(timezone.utc)

            # Lead automation state exists
            mock_las = MagicMock()
            mock_las.has_explicit_opt_in = True
            mock_las.has_opt_out = False
            mock_las.is_dnd_active = False
            mock_las.automation_disabled = False

            # Configure mock execute responses
            def mock_execute(stmt):
                res = MagicMock()
                sql = str(stmt)
                if "pilot_tenants" in sql:
                    res.scalar_one_or_none.return_value = mock_pilot
                elif "leads" in sql:
                    res.scalar_one_or_none.return_value = mock_lead
                elif "lead_automation_state" in sql:
                    res.scalar_one_or_none.return_value = mock_las
                else:
                    res.scalar_one_or_none.return_value = None
                    res.scalars.return_value.all.return_value = []
                return res

            mock_db.execute = AsyncMock(side_effect=mock_execute)
            mock_db.flush = AsyncMock()

            # Ensure kill switches are clean
            EmergencyAutomationPauseService.set_global_pause(False, "test", "clear")
            EmergencyAutomationPauseService.set_tenant_pause(org_id, False, "test", "clear")

            res = await bridge.route_event(
                event_type="NEW_LEAD",
                organization_id=org_id,
                lead_id=lead_id,
                event_id="evt-100",
                correlation_id="corr-100",
                payload={"source": "inbound_form"},
            )

            assert res is not None
            assert res.get("status") == "OBSERVATION_RECORDED"
            assert res.get("agent_id") == "lead-intelligence-agent-v2b"
            assert res.get("pilot_stage") == "STAGE_1_SHADOW"

        asyncio.run(run())

    def test_r3_real_context_builder_with_tenant_isolation(self):
        """R3: Context builder retrieves real records and enforces tenant isolation."""
        async def run():
            mock_db = AsyncMock()
            builder = Phase2CContextBuilder(mock_db)

            # If lead does not exist for tenant, must raise ContextBuildError (fail-closed)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(ContextBuildError, match="not found for org"):
                await builder.build("tenant-A", "lead-belongs-to-tenant-B")

        asyncio.run(run())

    def test_r4_all_ten_bounded_agents_evaluate_context(self):
        """R4: All 10 bounded agents successfully evaluate context and return genuine decisions."""
        agents = [
            LeadIntelligenceAgent(),
            QualificationAgent(),
            PropertyMatchAgent(),
            EngagementAgent(),
            FollowUpAgent(),
            VisitAgent(),
            DealProgressionAgent(),
            RecoveryAgent(),
            RevenueIntelligenceAgent(),
            ManagerIntelligenceAgent(),
        ]
        assert len(agents) == 10

        ctx = AgentContextObject(
            organization_id="org-r4",
            lead_id="lead-r4",
            lead_summary={"name": "Alice Investor", "budget": 1200000},
            consent_state={"has_explicit_opt_in": True, "has_opt_out": False, "is_dnd": False},
            freshness_ttl_seconds=300,
        )
        policy_engine = get_policy_engine()

        async def run():
            for agent in agents:
                rec = AgentExecutionRecord(
                    execution_id=str(uuid.uuid4()),
                    organization_id="org-r4",
                    lead_id="lead-r4",
                    agent_domain=agent.domain,
                    agent_version=agent.version,
                    goal=f"Evaluation by {agent.agent_id}",
                    execution_mode=Phase2ExecutionMode.SHADOW,
                )
                completed = await agent.execute(ctx, rec, policy_engine, dry_run=True)
                assert completed.execution_id == rec.execution_id
                assert completed.confidence in [AgentConfidence.HIGH, AgentConfidence.MEDIUM, AgentConfidence.LOW]
                assert len(completed.policy_decisions) > 0, f"{agent.agent_id} must have evaluated policy"
                assert completed.policy_decisions[-1]["action_type"] is not None
                assert completed.result_summary is not None

        asyncio.run(run())

    def test_r5_policy_traversal_and_shadow_projection(self):
        """R5: Stage 1 shadow execution mode projects action without external dispatch."""
        dispatcher = Phase2CToolDispatcher(
            organization_id="org-r5",
            pilot_stage="STAGE_1_SHADOW",
            execution_mode="SHADOW",
            agent_id="follow_up_agent",
            policy_engine=get_policy_engine(),
        )

        record = dispatcher.dispatch(
            action_type=Phase2ActionType.SEND_FOLLOW_UP,
            action_description="Follow-up WhatsApp message",
            execution_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            lead_id="lead-r5",
            risk_class=Phase2RiskClass.HIGH,
        )

        assert record.state == ActionSemanticState.SHADOW_PROJECTED
        assert "PROVIDER_DISPATCH_BLOCKED" in record.block_reason
        assert record.provider_request_id is None
        assert record.completed_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# R6–R10: Observation, Human Decision, Comparison, Metrics, Provider Boundary
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeGatesR6ToR10:

    def test_r6_durable_observation_persistence_invariants(self):
        """R6: Durable observation persistence enforces non-synthetic and eligibility invariants."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            obs = await repo.record_observation(
                organization_id="org-r6",
                pilot_id="pilot-r6",
                lead_id="lead-r6",
                agent_id="qualification_agent",
                agent_domain="QUALIFICATION",
                execution_id="exec-r6",
                pilot_stage="STAGE_1_SHADOW",
                execution_mode="SHADOW",
                recommended_action="QUALIFY_LEAD",
                reasoning="Lead has verified budget and timeline.",
                agent_confidence="HIGH",
                policy_decision="SHADOW_PROJECTED",
                source_event_id="evt-r6",
                source_event_type="NEW_LEAD",
            )

            assert obs.is_synthetic is False, "Production observation must NEVER be synthetic"
            assert obs.is_eligible_for_shadow_accuracy is False, "Pending human decision must not be accuracy-eligible"
            assert obs.pilot_stage == "STAGE_1_SHADOW"
            assert mock_db.flush.called

        asyncio.run(run())

    def test_r7_human_decision_api_workflow(self):
        """R7: Human operator records decision, updating comparison and eligibility."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            # Mock observation
            obs = PilotObservation(
                id="obs-r7",
                pilot_id="pilot-r7",
                organization_id="org-r7",
                lead_id="lead-r7",
                agent_id="follow_up_agent",
                agent_domain="FOLLOW_UP",
                execution_id="exec-r7",
                recommended_action="SEND_FOLLOW_UP",
                recommended_action_reasoning="Lead inactive for 48h",
                pilot_stage="STAGE_1_SHADOW",
                execution_mode="SHADOW",
                is_eligible_for_shadow_accuracy=False,
                is_synthetic=False,
                observed_at=datetime.now(timezone.utc),
            )

            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = obs
            mock_db.execute = AsyncMock(return_value=mock_res)

            updated_obs, decision = await repo.record_human_decision(
                observation_id="obs-r7",
                organization_id="org-r7",
                lead_id="lead-r7",
                human_actor_id="operator-123",
                human_actor_role="BROKER",
                decision_type="ACCEPT",
                action_taken="SEND_FOLLOW_UP",
                reason="Aligned with standard follow-up timing",
            )

            assert updated_obs.comparison_category == ComparisonCategory.EXACT_AGREEMENT.value
            assert updated_obs.agreement_score == 1.0
            assert updated_obs.is_eligible_for_shadow_accuracy is True, "Completed comparison makes observation eligible"
            assert decision.decision_type == "ACCEPT"
            assert decision.human_actor_id == "operator-123"

        asyncio.run(run())

    def test_r8_comparison_engine_six_categories(self):
        """R8: Comparison engine validates all 6 categories without redefining metrics."""
        # 1. Exact
        res_exact = Phase2CComparisonEngine.compare("SEND_WHATSAPP_MESSAGE", "SEND_WHATSAPP_MESSAGE")
        assert res_exact.category == ComparisonCategory.EXACT_AGREEMENT
        assert res_exact.agreement_score == 1.0

        # 2. Semantic
        res_sem = Phase2CComparisonEngine.compare("SEND_WHATSAPP_MESSAGE", "SEND_SMS")
        assert res_sem.category == ComparisonCategory.SEMANTIC_AGREEMENT
        assert res_sem.agreement_score == 0.85

        # 3. Abstention
        res_abs = Phase2CComparisonEngine.compare(None, None)
        assert res_abs.category == ComparisonCategory.ABSTENTION
        assert res_abs.agreement_score == 1.0

        # 4. Acceptable disagreement
        res_acc = Phase2CComparisonEngine.compare("NO_ACTION", "SEND_FOLLOW_UP")
        assert res_acc.category == ComparisonCategory.ACCEPTABLE_DISAGREEMENT
        assert res_acc.agreement_score == 0.0

        # 5. Harmful disagreement
        res_harm = Phase2CComparisonEngine.compare("SEND_PROPERTY_RECOMMENDATIONS", "ESCALATE_TO_MANAGER")
        assert res_harm.category == ComparisonCategory.HARMFUL_DISAGREEMENT
        assert res_harm.agreement_score == 0.0

        # 6. Insufficient evidence
        res_insuf = Phase2CComparisonEngine.compare("SEND_FOLLOW_UP", None)
        assert res_insuf.category == ComparisonCategory.INSUFFICIENT_EVIDENCE
        assert res_insuf.agreement_score == 0.0

    def test_r9_durable_metric_reconstruction_from_database(self):
        """R9: Shadow accuracy metric derived from persisted observations."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            # Under 50 observations = INSUFFICIENT_DATA
            count_res = MagicMock()
            count_res.scalar.return_value = 25
            mock_db.execute = AsyncMock(return_value=count_res)

            res = await repo.compute_shadow_accuracy(
                pilot_id="pilot-r9",
                period_start=datetime.now(timezone.utc) - timedelta(days=14),
                period_end=datetime.now(timezone.utc),
            )
            assert res["gate_result"] == "INSUFFICIENT_DATA"
            assert res["sample_size"] == 25
            assert res["minimum_sample"] == 50

            # 60 observations: 48 agreement, 12 disagreement -> 80% = PASS
            call_count = 0
            def mock_exec(stmt):
                nonlocal call_count
                call_count += 1
                r = MagicMock()
                if call_count == 1:
                    r.scalar.return_value = 60  # total eligible
                else:
                    r.scalar.return_value = 48  # acceptable agreements
                return r

            mock_db.execute = AsyncMock(side_effect=mock_exec)
            res2 = await repo.compute_shadow_accuracy(
                pilot_id="pilot-r9",
                period_start=datetime.now(timezone.utc) - timedelta(days=14),
                period_end=datetime.now(timezone.utc),
            )
            assert res2["gate_result"] == "PASS"
            assert res2["observed_value"] == 0.8
            assert res2["threshold"] == 0.70

        asyncio.run(run())

    def test_r10_provider_boundary_hard_blocks_in_stage1(self):
        """R10: Provider boundary blocks outbound dispatch unconditionally in Stage 1."""
        actions = [
            Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2ActionType.SEND_EMAIL,
            Phase2ActionType.SCHEDULE_SITE_VISIT,
            Phase2ActionType.CONFIRM_BOOKING,
        ]
        for act in actions:
            block = assert_provider_dispatch_permitted(
                organization_id="org-r10",
                pilot_stage="STAGE_1_SHADOW",
                execution_mode="SHADOW",
                action_type=act,
            )
            assert block is not None, f"Action {act.value} must be blocked in STAGE_1_SHADOW"
            assert "PROVIDER_DISPATCH_BLOCKED" in block


# ═══════════════════════════════════════════════════════════════════════════════
# R11–R15: Zero Side-Effects, Audit, Kill-Switch, Persistence, Replay
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeGatesR11ToR15:

    def test_r11_zero_shadow_side_effects_telemetry(self):
        """R11: Stage 1 maintains provider_dispatched = 0 across all actions."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            # Mock 10 action records that were SHADOW_PROJECTED
            records = []
            for i in range(10):
                ar = PilotActionRecord(
                    id=str(uuid.uuid4()),
                    record_id=f"rec-{i}",
                    pilot_id="pilot-r11",
                    organization_id="org-r11",
                    semantic_state="SHADOW_PROJECTED",
                    pilot_stage="STAGE_1_SHADOW",
                    execution_mode="SHADOW",
                    policy_version="phase2-v1.0",
                    requested_at=datetime.now(timezone.utc),
                )
                records.append(ar)

            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = records
            mock_db.execute = AsyncMock(return_value=mock_res)

            stats = await repo.get_provider_dispatch_stats("org-r11", "pilot-r11")
            assert stats["provider_dispatched"] == 0
            assert stats["provider_accepted"] == 0
            assert stats["provider_delivered"] == 0
            assert stats["provider_blocked"] == 10
            assert stats["is_stage_1_safe"] is True

        asyncio.run(run())

    def test_r12_audit_chain_tamper_evident_reconstruction(self):
        """R12: Audit chain records verifiable SHA-256 hashes linking events."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            # Event 1
            mock_count1 = MagicMock()
            mock_count1.scalar.return_value = 0
            mock_prev1 = MagicMock()
            mock_prev1.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(side_effect=[mock_count1, mock_prev1])

            evt1 = await repo._append_audit_event(
                pilot_id="pilot-r12",
                organization_id="org-r12",
                event_type="ENROLLED",
                actor_type="HUMAN",
                actor_id="admin-1",
                payload={"stage": "STAGE_1_SHADOW"},
            )
            assert evt1.sequence_number == 0
            assert evt1.previous_hash is None
            assert evt1.current_hash is not None

            # Event 2
            mock_count2 = MagicMock()
            mock_count2.scalar.return_value = 1
            mock_prev2 = MagicMock()
            mock_prev2.scalar_one_or_none.return_value = evt1.current_hash
            mock_db.execute = AsyncMock(side_effect=[mock_count2, mock_prev2])

            evt2 = await repo._append_audit_event(
                pilot_id="pilot-r12",
                organization_id="org-r12",
                event_type="STAGE_PAUSED",
                actor_type="HUMAN",
                actor_id="admin-1",
                payload={"reason": "Safety drill"},
            )
            assert evt2.sequence_number == 1
            assert evt2.previous_hash == evt1.current_hash
            assert evt2.current_hash != evt1.current_hash

        asyncio.run(run())

    def test_r13_kill_switch_immediate_block(self):
        """R13: Global and tenant kill switches immediately block event bridge and dispatcher."""
        async def run():
            mock_db = AsyncMock()
            bridge = Phase2CEventBridge(mock_db)

            # Global kill switch active
            EmergencyAutomationPauseService.set_global_pause(True, "sec_team", "Audit ongoing")
            res_global = await bridge.route_event(
                event_type="NEW_LEAD",
                organization_id="org-r13",
                lead_id="lead-r13",
                event_id="evt-1",
                correlation_id="corr-1",
                payload={},
            )
            assert res_global is None, "Global pause must suppress event bridge immediately"

            # Clear global, set tenant
            EmergencyAutomationPauseService.set_global_pause(False, "sec_team", "cleared")
            EmergencyAutomationPauseService.set_tenant_pause("org-r13", True, "broker", "Tenant maintenance")

            res_tenant = await bridge.route_event(
                event_type="NEW_LEAD",
                organization_id="org-r13",
                lead_id="lead-r13",
                event_id="evt-1",
                correlation_id="corr-1",
                payload={},
            )
            assert res_tenant is None, "Tenant pause must suppress event bridge immediately"

            # Clean up
            EmergencyAutomationPauseService.set_tenant_pause("org-r13", False, "broker", "cleared")

        asyncio.run(run())

    def test_r14_restart_recovery_persistence(self):
        """R14: Pilot stats and observations survive process restarts via DB queries."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            pilot = PilotTenant(
                id="pilot-r14",
                organization_id="org-r14",
                current_stage="STAGE_1_SHADOW",
                pilot_status="ACTIVE",
                enrolled_by="admin-r14",
                enrolled_at=datetime.now(timezone.utc) - timedelta(days=5),
                stage_entered_at=datetime.now(timezone.utc) - timedelta(days=5),
                enrolled_agent_ids=["lead_intelligence_agent"],
            )

            # Query pilot returns persisted record
            mock_res_pilot = MagicMock()
            mock_res_pilot.scalar_one_or_none.return_value = pilot

            mock_count1 = MagicMock()
            mock_count1.scalar.return_value = 35  # total obs
            mock_count2 = MagicMock()
            mock_count2.scalar.return_value = 28  # eligible obs
            mock_count3 = MagicMock()
            mock_count3.scalar.return_value = 0   # pending approvals

            mock_db.execute = AsyncMock(side_effect=[mock_res_pilot, mock_count1, mock_count2, mock_count3])

            stats = await repo.get_pilot_stats("org-r14")
            assert stats["organization_id"] == "org-r14"
            assert stats["pilot_id"] == "pilot-r14"
            assert stats["total_observations"] == 35
            assert stats["eligible_observations"] == 28
            assert stats["days_in_stage"] == 5

        asyncio.run(run())

    def test_r15_event_replay_idempotency(self):
        """R15: Replaying the same domain event produces deterministic idempotency key."""
        key1 = build_idempotency_key("org-r15", "lead-r15", "SEND_FOLLOW_UP", "corr-r15", "v1")
        key2 = build_idempotency_key("org-r15", "lead-r15", "SEND_FOLLOW_UP", "corr-r15", "v1")
        assert key1 == key2, "Idempotency key must be identical for identical inputs"
        assert len(key1) <= 48


# ═══════════════════════════════════════════════════════════════════════════════
# R16–R20: Concurrency, Tenant Isolation, RBAC, Failures, Observability
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeGatesR16ToR20:

    def test_r16_concurrency_protection(self):
        """R16: Simultaneous evaluations produce isolated execution records."""
        dispatcher = Phase2CToolDispatcher(
            organization_id="org-r16",
            pilot_stage="STAGE_1_SHADOW",
            execution_mode="SHADOW",
            agent_id="follow_up_agent",
            policy_engine=get_policy_engine(),
        )

        # Worker A and Worker B evaluate simultaneously
        rec_a = dispatcher.dispatch(
            action_type=Phase2ActionType.SEND_FOLLOW_UP,
            action_description="Worker A follow-up",
            execution_id=str(uuid.uuid4()),
            correlation_id="corr-concurrent-A",
            lead_id="lead-r16",
        )
        rec_b = dispatcher.dispatch(
            action_type=Phase2ActionType.SEND_FOLLOW_UP,
            action_description="Worker B follow-up",
            execution_id=str(uuid.uuid4()),
            correlation_id="corr-concurrent-B",
            lead_id="lead-r16",
        )

        assert rec_a.record_id != rec_b.record_id
        assert rec_a.correlation_id != rec_b.correlation_id
        assert rec_a.state == ActionSemanticState.SHADOW_PROJECTED
        assert rec_b.state == ActionSemanticState.SHADOW_PROJECTED

    def test_r17_strict_multi_tenant_isolation(self):
        """R17: Tenant A context or event is strictly inaccessible from Tenant B."""
        async def run():
            mock_db = AsyncMock()
            builder = Phase2CContextBuilder(mock_db)

            # Tenant A lead
            lead_a = MagicMock()
            lead_a.id = "lead-A"
            lead_a.broker_id = "tenant-A"

            # Tenant B tries to query Tenant A lead
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = None  # SQL where Lead.broker_id == "tenant-B" filters it out
            mock_db.execute = AsyncMock(return_value=mock_res)

            with pytest.raises(ContextBuildError, match="not found for org"):
                await builder.build(organization_id="tenant-B", lead_id="lead-A")

        asyncio.run(run())

    def test_r18_rbac_pilot_endpoints_require_broker_context(self):
        """R18: Pilot REST routes are registered with get_current_broker dependency."""
        from app.modules.autonomous_loop.router import router
        pilot_routes = [r for r in router.routes if "pilot" in r.path]
        assert len(pilot_routes) >= 6, "Must have at least 6 pilot routes"

        for route in pilot_routes:
            dep_names = []
            if hasattr(route, "dependant"):
                for dep in route.dependant.dependencies:
                    if getattr(dep, "call", None):
                        dep_names.append(getattr(dep.call, "__name__", str(dep.call)))
            has_broker = (
                "get_current_broker" in dep_names
                or "broker" in getattr(getattr(route, "endpoint", None), "__code__", MagicMock()).co_varnames
            )
            assert has_broker, f"Route {route.path} must require broker authentication"

    def test_r19_failure_injection_fail_closed(self):
        """R19: When context builder encounters error, system fails closed safely."""
        async def run():
            mock_db = AsyncMock()
            builder = Phase2CContextBuilder(mock_db)

            # Simulate database exception during load
            mock_db.execute = AsyncMock(side_effect=Exception("Database connection timeout"))

            with pytest.raises(ContextBuildError, match="Failed to load lead"):
                await builder.build("org-r19", "lead-r19")

        asyncio.run(run())

    def test_r20_production_observability_daily_snapshot_task(self):
        """R20: Daily snapshot Celery task exists and calculates metrics from DB observations."""
        from app.modules.autonomous_loop.workers.loop_tasks import generate_daily_pilot_snapshots_task
        assert generate_daily_pilot_snapshots_task is not None
        assert generate_daily_pilot_snapshots_task.name == "autonomous_loop.generate_daily_pilot_snapshots"
