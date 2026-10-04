"""
Phase 2B — Controlled Agent Pilots Test Suite
==============================================
Release gates GB1-GB70 for Phase 2B Controlled Agent Pilots.

GATE CATEGORIES:
  GB1-GB10:  Pilot Enrollment & Stage Configuration
  GB11-GB20: Shadow Mode Accuracy & Comparison Engine
  GB21-GB30: All 10 Bounded Domain Agents (Shadow Execution)
  GB31-GB40: Advancement Gate Criteria Enforcement
  GB41-GB50: Human Approval Queue Lifecycle
  GB51-GB60: Stage Progression (Shadow->Recommend->Prepare->Approval->Live)
  GB61-GB70: Pilot Safety Invariants & Regression Protection

INVARIANTS UNDER TEST:
  1. Tenants never skip stages
  2. Unresolved incidents block advancement
  3. Stage regression always permitted
  4. Stage 3 zero outbound dispatch
  5. Emergency kill-switch overrides pilot controls
  6. Financial actions never exceed REQUEST_APPROVAL
  7. All 10 agents produce audit records
  8. Shadow mode captures human-vs-agent comparison
"""
import asyncio
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.autonomous_loop.phase2_governance import (
    Phase2ActionType, Phase2ExecutionMode, Phase2AutonomyLevel,
    Phase2RiskClass, RevenueActionPolicyEngine, get_policy_engine,
)
from app.modules.autonomous_loop.phase2_agent_contracts import (
    AgentDomain, AgentContextObject, AgentExecutionRecord,
    AgentExecutionState, AgentConfidence,
)
from app.modules.autonomous_loop.phase2_telemetry import (
    AgentIncidentRecord, AgentIncidentType, Phase2AgentTelemetryService,
)
from app.modules.autonomous_loop.phase2b_pilot_engine import (
    PilotStage, PilotMetrics, PilotLifecycleService,
    PilotTenantEnrollment, ShadowComparisonEngine,
    PilotAdvancementEngine, ADVANCEMENT_GATES, AdvancementEvaluationResult,
)
from app.modules.autonomous_loop.phase2b_approval_queue import (
    HumanApprovalQueueService, ApprovalStatus, ApprovalUrgency,
    ApprovalQueueItem, get_approval_queue,
)
from app.modules.autonomous_loop.phase2b_agents import (
    LeadIntelligenceAgent, QualificationAgent, PropertyMatchAgent,
    EngagementAgent, FollowUpAgent, VisitAgent, DealProgressionAgent,
    RecoveryAgent, RevenueIntelligenceAgent, ManagerIntelligenceAgent,
    ALL_PHASE2B_AGENTS, AGENT_REGISTRY, get_all_agent_ids,
    build_conditions,
)
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService


# ─── Test Fixtures ────────────────────────────────────────────────────────────

def make_org() -> str:
    return f"org-{uuid.uuid4().hex[:8]}"


def make_engine() -> RevenueActionPolicyEngine:
    return RevenueActionPolicyEngine()


def make_telemetry() -> Phase2AgentTelemetryService:
    svc = Phase2AgentTelemetryService()
    svc.reset_for_testing()
    return svc


def make_pilot_service() -> PilotLifecycleService:
    engine = make_engine()
    telemetry = make_telemetry()
    svc = PilotLifecycleService(policy_engine=engine, telemetry=telemetry)
    return svc


def make_context(org_id: str, lead_id: str = None, fresh: bool = True) -> AgentContextObject:
    ctx = AgentContextObject(
        organization_id=org_id,
        lead_id=lead_id or f"lead-{uuid.uuid4().hex[:6]}",
        lead_summary={"name": "Test Lead", "budget": 500000},
        lead_requirements={"min_bedrooms": 2, "max_price": 500000},
        qualification_profile={"score": 0.82, "qualified": True},
        property_shortlist=[{"id": "prop-1", "name": "Green Villa", "price": 450000}],
        consent_state={"has_explicit_opt_in": True, "has_opt_out": False, "is_dnd": False},
        policy_summary={
            "quiet_hours_permitted": True,
            "fatigue_budget_available": True,
            "agent_confidence": "HIGH",
            "confidence_score": 0.90,
            "execution_mode": "SHADOW",
        },
    )
    if not fresh:
        # Set context as stale (beyond TTL)
        from datetime import timedelta
        ctx.retrieved_at = datetime.now(timezone.utc) - timedelta(seconds=400)
    return ctx


def make_execution_record(domain: AgentDomain, org_id: str) -> AgentExecutionRecord:
    return AgentExecutionRecord(
        organization_id=org_id,
        agent_domain=domain,
        agent_version="v2b.1.0",
        goal="Test execution",
        execution_mode="SHADOW",
    )


@pytest.fixture(autouse=True)
def reset_emergency_pause():
    EmergencyAutomationPauseService.reset_all_for_testing()
    yield
    EmergencyAutomationPauseService.reset_all_for_testing()


# ═══════════════════════════════════════════════════════════════════════════════
# GB1-GB10: Pilot Enrollment & Stage Configuration
# ═══════════════════════════════════════════════════════════════════════════════

class TestPilotEnrollment:
    """GB1-GB10: Enrollment and initial stage configuration."""

    def test_gb1_enroll_tenant_shadow_mode(self):
        """GB1: Enrolling a tenant starts in STAGE_1_SHADOW by default."""
        pilot = make_pilot_service()
        org = make_org()
        enrollment = pilot.enroll_tenant(org, "pilot_admin", agent_ids=["agent-1"])
        assert enrollment.current_stage == PilotStage.STAGE_1_SHADOW
        assert enrollment.organization_id == org
        assert enrollment.is_active is True

    def test_gb2_enroll_configures_policy_engine(self):
        """GB2: Enrollment configures the policy engine to SHADOW mode."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "pilot_admin")
        config = pilot._policy_engine.get_tenant_config(org)
        assert config.execution_mode == Phase2ExecutionMode.SHADOW

    def test_gb3_duplicate_enrollment_raises(self):
        """GB3: Re-enrolling same tenant raises ValueError."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "pilot_admin")
        with pytest.raises(ValueError, match="already enrolled"):
            pilot.enroll_tenant(org, "pilot_admin")

    def test_gb4_pilot_stage_maps_to_execution_mode(self):
        """GB4: Each PilotStage maps to the correct Phase2ExecutionMode."""
        assert PilotStage.STAGE_1_SHADOW.execution_mode() == Phase2ExecutionMode.SHADOW
        assert PilotStage.STAGE_2_RECOMMEND.execution_mode() == Phase2ExecutionMode.RECOMMEND
        assert PilotStage.STAGE_3_PREPARE.execution_mode() == Phase2ExecutionMode.PREPARE
        assert PilotStage.STAGE_4_APPROVAL.execution_mode() == Phase2ExecutionMode.APPROVAL
        assert PilotStage.STAGE_5_LIVE.execution_mode() == Phase2ExecutionMode.LIVE

    def test_gb5_stage_next_stage_sequence(self):
        """GB5: Stage.next_stage() follows strict sequential order."""
        assert PilotStage.STAGE_1_SHADOW.next_stage() == PilotStage.STAGE_2_RECOMMEND
        assert PilotStage.STAGE_2_RECOMMEND.next_stage() == PilotStage.STAGE_3_PREPARE
        assert PilotStage.STAGE_3_PREPARE.next_stage() == PilotStage.STAGE_4_APPROVAL
        assert PilotStage.STAGE_4_APPROVAL.next_stage() == PilotStage.STAGE_5_LIVE
        assert PilotStage.STAGE_5_LIVE.next_stage() is None

    def test_gb6_get_enrollment_returns_correct_record(self):
        """GB6: get_enrollment() returns the correct tenant enrollment."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        result = pilot.get_enrollment(org)
        assert result is not None
        assert result.organization_id == org

    def test_gb7_unenrolled_tenant_returns_none(self):
        """GB7: get_enrollment() returns None for unenrolled tenants."""
        pilot = make_pilot_service()
        result = pilot.get_enrollment("nonexistent-org")
        assert result is None

    def test_gb8_enrollment_audit_logged(self):
        """GB8: Enrollment creates an audit log entry."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "pilot_admin")
        audit = pilot.get_audit_log(org)
        assert any(e["event"] == "ENROLLED" for e in audit)

    def test_gb9_metrics_initialized_on_enrollment(self):
        """GB9: Pilot metrics are initialized to zero on enrollment."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        metrics = pilot.get_metrics(org)
        assert metrics is not None
        assert metrics.total_executions == 0
        assert metrics.shadow_total == 0
        assert metrics.incidents_detected == 0

    def test_gb10_enrolled_agents_tracked(self):
        """GB10: Agent IDs provided at enrollment are tracked in the enrollment."""
        pilot = make_pilot_service()
        org = make_org()
        agent_ids = ["agent-lead-intel", "agent-qualification", "agent-property-match"]
        enrollment = pilot.enroll_tenant(org, "admin", agent_ids=agent_ids)
        assert set(enrollment.enrolled_agents) == set(agent_ids)


# ═══════════════════════════════════════════════════════════════════════════════
# GB11-GB20: Shadow Mode Accuracy & Comparison Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestShadowModeAccuracy:
    """GB11-GB20: Shadow mode recording and accuracy computation."""

    def test_gb11_shadow_projection_recorded(self):
        """GB11: Shadow projections are recorded in the shadow engine."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        exec_id = str(uuid.uuid4())
        record = pilot.record_shadow_projection(
            org, "lead-1", "LEAD_INTELLIGENCE", exec_id,
            "SEND_WHATSAPP_MESSAGE", "Lead responded positively",
            "BLOCKED_SHADOW", "Lead would engage",
        )
        assert record is not None
        assert record.proposed_action == "SEND_WHATSAPP_MESSAGE"
        assert record.organization_id == org

    def test_gb12_shadow_total_increments(self):
        """GB12: shadow_total metric increments on each projection."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        for i in range(5):
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTELLIGENCE",
                                            str(uuid.uuid4()), "SEND_FOLLOW_UP",
                                            "reason", "BLOCKED", "outcome")
        metrics = pilot.get_metrics(org)
        assert metrics.shadow_total == 5

    def test_gb13_human_action_aligned_increments_shadow_aligned(self):
        """GB13: When human takes same action as agent, shadow_aligned increments."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        exec_id = str(uuid.uuid4())
        pilot.record_shadow_projection(org, "lead-1", "LEAD_INTELLIGENCE", exec_id,
                                        "SEND_FOLLOW_UP", "reason", "BLOCKED", "outcome")
        pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        metrics = pilot.get_metrics(org)
        assert metrics.shadow_aligned == 1
        assert metrics.shadow_total == 1

    def test_gb14_human_action_misaligned_does_not_increment(self):
        """GB14: When human takes different action, shadow_aligned does NOT increment."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        exec_id = str(uuid.uuid4())
        pilot.record_shadow_projection(org, "lead-1", "LEAD_INTELLIGENCE", exec_id,
                                        "SEND_FOLLOW_UP", "reason", "BLOCKED", "outcome")
        pilot.record_human_action(org, exec_id, "NO_ACTION")
        metrics = pilot.get_metrics(org)
        assert metrics.shadow_aligned == 0

    def test_gb15_shadow_accuracy_70_percent(self):
        """GB15: Shadow accuracy is computed correctly from aligned/total ratio."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # 7 aligned, 3 not aligned = 70%
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTELLIGENCE", exec_id,
                                            "SEND_FOLLOW_UP", "reason", "BLOCKED", "outcome")
            human_action = "SEND_FOLLOW_UP" if i < 7 else "NO_ACTION"
            pilot.record_human_action(org, exec_id, human_action)
        metrics = pilot.get_metrics(org)
        assert abs(metrics.shadow_accuracy - 0.70) < 0.01

    def test_gb16_shadow_accuracy_zero_when_no_comparisons(self):
        """GB16: Shadow accuracy is 0.0 when no comparisons have been recorded."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        metrics = pilot.get_metrics(org)
        assert metrics.shadow_accuracy == 0.0

    def test_gb17_shadow_records_scoped_to_tenant(self):
        """GB17: Shadow records from tenant A are not visible to tenant B's engine."""
        engine = ShadowComparisonEngine()
        exec_id = str(uuid.uuid4())
        engine.record_shadow_projection("org-A", "lead-1", "LEAD_INTEL", exec_id,
                                         "SEND_FOLLOW_UP", "r", "B", "o")
        records_a = engine.get_records("org-A")
        records_b = engine.get_records("org-B")
        assert len(records_a) == 1
        assert len(records_b) == 0

    def test_gb18_shadow_accuracy_100_percent(self):
        """GB18: Shadow accuracy reaches 100% when all comparisons align."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        for i in range(5):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTELLIGENCE", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        metrics = pilot.get_metrics(org)
        assert metrics.shadow_accuracy == 1.0

    def test_gb19_unknown_execution_id_returns_none(self):
        """GB19: Recording a human action for unknown exec_id returns None."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        result = pilot.record_human_action(org, "nonexistent-exec-id", "SEND_FOLLOW_UP")
        assert result is None

    def test_gb20_shadow_engine_reset_clears_records(self):
        """GB20: reset_for_testing() clears all shadow records."""
        engine = ShadowComparisonEngine()
        engine.record_shadow_projection("org-1", "lead-1", "LEAD_INTEL", str(uuid.uuid4()),
                                         "SEND_FOLLOW_UP", "r", "B", "o")
        engine.reset_for_testing()
        assert len(engine.get_records("org-1")) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# GB21-GB30: All 10 Bounded Domain Agents (Shadow Execution)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllTenAgentsShadow:
    """GB21-GB30: All 10 agents execute cleanly in shadow mode."""

    @pytest.mark.asyncio
    async def test_gb21_lead_intelligence_agent_shadow(self):
        """GB21: LeadIntelligenceAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = LeadIntelligenceAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED
        assert "SHADOW" in result.result_summary or result.result_summary

    @pytest.mark.asyncio
    async def test_gb22_qualification_agent_shadow(self):
        """GB22: QualificationAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = QualificationAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_gb23_property_match_agent_shadow(self):
        """GB23: PropertyMatchAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = PropertyMatchAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED
        assert result.result_summary is not None

    @pytest.mark.asyncio
    async def test_gb24_engagement_agent_shadow(self):
        """GB24: EngagementAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = EngagementAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_gb25_followup_agent_shadow(self):
        """GB25: FollowUpAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = FollowUpAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_gb26_visit_agent_shadow(self):
        """GB26: VisitAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = VisitAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_gb27_deal_progression_agent_shadow(self):
        """GB27: DealProgressionAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = DealProgressionAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_gb28_recovery_agent_shadow(self):
        """GB28: RecoveryAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = RecoveryAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_gb29_revenue_intelligence_agent_shadow(self):
        """GB29: RevenueIntelligenceAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = RevenueIntelligenceAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_gb30_manager_intelligence_agent_shadow(self):
        """GB30: ManagerIntelligenceAgent executes in shadow mode, produces record."""
        engine = make_engine()
        org = make_org()
        ctx = make_context(org)
        agent = ManagerIntelligenceAgent()
        record = make_execution_record(agent.domain, org)
        result = await agent.execute(ctx, record, engine, dry_run=True)
        assert result.execution_state == AgentExecutionState.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# GB31-GB40: Advancement Gate Criteria Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdvancementGates:
    """GB31-GB40: Advancement gate criteria are properly enforced."""

    def test_gb31_stage1_insufficient_shadow_accuracy_blocks(self):
        """GB31: Insufficient shadow accuracy blocks Stage 1 -> Stage 2 advancement."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # 50% accuracy — below 70% gate
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id, "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP" if i < 5 else "NO_ACTION")
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        assert not evaluation.can_advance
        assert any("Shadow accuracy" in r for r in evaluation.blocking_reasons)

    def test_gb32_stage1_sufficient_shadow_accuracy_passes(self):
        """GB32: 70%+ shadow accuracy passes the Stage 1 shadow accuracy gate."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # 80% accuracy — above 70% gate
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id, "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP" if i < 8 else "NO_ACTION")
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        assert not any("Shadow accuracy" in r for r in evaluation.blocking_reasons)

    def test_gb33_unresolved_incident_blocks_all_advancement(self):
        """GB33: Any unresolved incident is an absolute advancement blocker."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # Simulate perfect shadow accuracy
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id, "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        # Add an unresolved incident
        incident = AgentIncidentRecord(
            incident_id=str(uuid.uuid4()),
            incident_type=AgentIncidentType.UNAUTHORIZED_ACTION,
            organization_id=org,
        )
        pilot.record_incident(org, incident)
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        assert not evaluation.can_advance
        assert any("INCIDENT BLOCKER" in r for r in evaluation.blocking_reasons)

    def test_gb34_resolved_incident_unblocks_advancement(self):
        """GB34: Resolving an incident removes the advancement block."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # Perfect shadow accuracy
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id, "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        # Add then resolve an incident
        incident_id = str(uuid.uuid4())
        incident = AgentIncidentRecord(
            incident_id=incident_id,
            incident_type=AgentIncidentType.UNAUTHORIZED_ACTION,
            organization_id=org,
        )
        pilot.record_incident(org, incident)
        pilot.resolve_incident(org, incident_id, "ops_engineer")
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        # Should not have incident blocker (may still have other blockers but not incident)
        assert not any("INCIDENT BLOCKER" in r for r in evaluation.blocking_reasons)

    def test_gb35_stage2_recommendation_acceptance_gate(self):
        """GB35: Stage 2 -> Stage 3 requires 60%+ recommendation acceptance."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin", starting_stage=PilotStage.STAGE_2_RECOMMEND)
        # 50% acceptance — below 60%
        for i in range(10):
            pilot.record_recommendation_outcome(org, accepted=(i < 5))
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        assert not evaluation.can_advance
        assert any("acceptance" in r.lower() for r in evaluation.blocking_reasons)

    def test_gb36_stage3_zero_outbound_gate(self):
        """GB36: Stage 3 blocks advancement if any outbound dispatch occurred."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin", starting_stage=PilotStage.STAGE_3_PREPARE)
        # 90%+ draft acceptance but one outbound dispatch
        for i in range(10):
            pilot.record_draft_outcome(org, accepted=True, outbound_dispatched=(i == 0))
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        assert not evaluation.can_advance
        assert any("outbound" in r.lower() for r in evaluation.blocking_reasons)

    def test_gb37_stage4_approval_acceptance_gate(self):
        """GB37: Stage 4 -> Stage 5 requires 75%+ approval acceptance."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin", starting_stage=PilotStage.STAGE_4_APPROVAL)
        # 60% acceptance — below 75%
        for i in range(10):
            pilot.record_approval_outcome(org, approval_granted=(i < 6))
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        assert not evaluation.can_advance

    def test_gb38_stage5_no_further_advancement(self):
        """GB38: At Stage 5 (maximum), evaluate_advancement reports no further advancement."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin", starting_stage=PilotStage.STAGE_5_LIVE)
        evaluation = pilot.evaluate_advancement(org, override_duration_check=True)
        assert not evaluation.can_advance
        assert evaluation.target_stage is None

    def test_gb39_advancement_requires_not_enrolled_raises(self):
        """GB39: Evaluating advancement for unenrolled tenant raises ValueError."""
        pilot = make_pilot_service()
        with pytest.raises(ValueError, match="not enrolled"):
            pilot.evaluate_advancement("nonexistent-org")

    def test_gb40_force_advance_bypasses_gate_criteria(self):
        """GB40: force=True allows advancement even if gate criteria not met (ops recovery)."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # Deliberately insufficient metrics
        new_stage, evaluation = pilot.advance_stage(org, "ops_lead", override_duration_check=True, force=True)
        assert new_stage == PilotStage.STAGE_2_RECOMMEND


# ═══════════════════════════════════════════════════════════════════════════════
# GB41-GB50: Human Approval Queue Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovalQueueLifecycle:
    """GB41-GB50: Human approval queue operations."""

    def test_gb41_submit_creates_pending_item(self):
        """GB41: Submitting an action creates a PENDING approval item."""
        queue = HumanApprovalQueueService()
        org = make_org()
        item = queue.submit_for_approval(
            organization_id=org,
            action_type=Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            risk_class=Phase2RiskClass.MEDIUM,
            agent_domain=AgentDomain.ENGAGEMENT,
            action_description="Send WhatsApp follow-up to lead",
        )
        assert item.status == ApprovalStatus.PENDING
        assert item.organization_id == org

    def test_gb42_approve_grants_approval(self):
        """GB42: approve() grants approval and marks item as APPROVED."""
        queue = HumanApprovalQueueService()
        org = make_org()
        item = queue.submit_for_approval(
            org, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT,
            "Send WhatsApp follow-up",
        )
        decision, success = queue.approve(item.approval_id, "broker_alice", "Looks good.")
        assert success is True
        assert decision.is_approved is True
        approved = queue.get_item(item.approval_id)
        assert approved.status == ApprovalStatus.APPROVED

    def test_gb43_deny_rejects_approval(self):
        """GB43: deny() marks item as DENIED."""
        queue = HumanApprovalQueueService()
        org = make_org()
        item = queue.submit_for_approval(
            org, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT,
            "Send WhatsApp follow-up",
        )
        decision = queue.deny(item.approval_id, "broker_bob", "Not appropriate now.")
        assert decision.is_approved is False
        denied = queue.get_item(item.approval_id)
        assert denied.status == ApprovalStatus.DENIED

    def test_gb44_expired_item_auto_denied(self):
        """GB44: Approving an expired item returns failure with EXPIRED status."""
        queue = HumanApprovalQueueService()
        org = make_org()
        item = queue.submit_for_approval(
            org, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT,
            "Send follow-up",
            custom_expiry_minutes=0,  # Already expired
        )
        # Force expiry
        from datetime import timedelta
        item.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        decision, success = queue.approve(item.approval_id, "broker_alice")
        assert success is False
        assert not decision.is_approved

    def test_gb45_resource_hash_mismatch_rejects(self):
        """GB45: Approval is rejected if resource state changed (hash mismatch)."""
        queue = HumanApprovalQueueService()
        org = make_org()
        resource_data = {"lead_id": "lead-1", "status": "ACTIVE", "budget": 500000}
        item = queue.submit_for_approval(
            org, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT,
            "Send follow-up",
            resource_data=resource_data,
        )
        # Changed resource data
        changed_resource = {"lead_id": "lead-1", "status": "CLOSED", "budget": 0}
        decision, success = queue.approve(item.approval_id, "broker_alice",
                                           current_resource_data=changed_resource)
        assert success is False
        assert not decision.hash_matches

    def test_gb46_financial_actions_get_shorter_expiry(self):
        """GB46: FINANCIAL_IRREVERSIBLE actions have shorter expiry (15 min)."""
        queue = HumanApprovalQueueService()
        org = make_org()
        item = queue.submit_for_approval(
            org, Phase2ActionType.CREATE_BOOKING,
            Phase2RiskClass.FINANCIAL_IRREVERSIBLE, AgentDomain.DEAL,
            "Book unit for customer",
        )
        expiry_minutes = (item.expires_at - item.created_at).total_seconds() / 60
        assert expiry_minutes <= 16  # 15 min + small buffer

    def test_gb47_pending_items_scoped_to_tenant(self):
        """GB47: get_pending_items() returns only items for the specified tenant."""
        queue = HumanApprovalQueueService()
        org_a, org_b = make_org(), make_org()
        queue.submit_for_approval(org_a, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
                                   Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT, "For A")
        queue.submit_for_approval(org_b, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
                                   Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT, "For B")
        items_a = queue.get_pending_items(org_a)
        items_b = queue.get_pending_items(org_b)
        assert len(items_a) == 1 and items_a[0].organization_id == org_a
        assert len(items_b) == 1 and items_b[0].organization_id == org_b

    def test_gb48_cancel_removes_from_pending(self):
        """GB48: Cancelling an item removes it from the pending queue."""
        queue = HumanApprovalQueueService()
        org = make_org()
        item = queue.submit_for_approval(
            org, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT, "Follow-up",
        )
        queue.cancel(item.approval_id, "agent_system")
        pending = queue.get_pending_items(org)
        assert len(pending) == 0

    def test_gb49_queue_stats_accurate(self):
        """GB49: Queue stats accurately reflect approved/denied/pending counts."""
        queue = HumanApprovalQueueService()
        org = make_org()
        for _ in range(3):
            item = queue.submit_for_approval(
                org, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
                Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT, "Follow-up",
            )
        all_items = queue.get_pending_items(org)
        queue.approve(all_items[0].approval_id, "broker")
        queue.deny(all_items[1].approval_id, "broker")
        stats = queue.get_queue_stats(org)
        assert stats["approved"] == 1
        assert stats["denied"] == 1
        assert stats["pending"] == 1

    def test_gb50_audit_trail_for_all_decisions(self):
        """GB50: All approval decisions are audit-logged with actor identity."""
        queue = HumanApprovalQueueService()
        org = make_org()
        item = queue.submit_for_approval(
            org, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2RiskClass.MEDIUM, AgentDomain.ENGAGEMENT, "Follow-up",
        )
        queue.approve(item.approval_id, "broker_alice", "Approved.")
        audit = queue.get_audit_log(org)
        actors = [e["actor"] for e in audit]
        assert "broker_alice" in actors


# ═══════════════════════════════════════════════════════════════════════════════
# GB51-GB60: Stage Progression (Shadow -> Recommend -> Prepare -> Approval -> Live)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStageProgression:
    """GB51-GB60: Stage progression, regression, and policy engine updates."""

    def test_gb51_advance_stage1_to_stage2(self):
        """GB51: Tenant advances from Stage 1 to Stage 2 when gate criteria met."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # Satisfy shadow accuracy gate
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        new_stage, _ = pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        assert new_stage == PilotStage.STAGE_2_RECOMMEND

    def test_gb52_advance_updates_policy_engine_mode(self):
        """GB52: After advancement, policy engine reflects new stage's execution mode."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        config = pilot._policy_engine.get_tenant_config(org)
        assert config.execution_mode == Phase2ExecutionMode.RECOMMEND

    def test_gb53_advance_records_transition_in_history(self):
        """GB53: Stage advancement is recorded in the enrollment stage history."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        enrollment = pilot.get_enrollment(org)
        assert len(enrollment.stage_history) == 1
        assert enrollment.stage_history[0]["from_stage"] == PilotStage.STAGE_1_SHADOW.value
        assert enrollment.stage_history[0]["to_stage"] == PilotStage.STAGE_2_RECOMMEND.value

    def test_gb54_advance_resets_metrics_window(self):
        """GB54: Stage advancement resets the metrics window for the new stage."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        metrics = pilot.get_metrics(org)
        # Metrics should be reset for Stage 2
        assert metrics.stage == PilotStage.STAGE_2_RECOMMEND
        assert metrics.total_executions == 0

    def test_gb55_advance_snapshots_old_metrics(self):
        """GB55: Old stage metrics are preserved in the enrollment metrics history."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        enrollment = pilot.get_enrollment(org)
        assert len(enrollment.metrics_history) == 1
        assert enrollment.metrics_history[0]["stage"] == PilotStage.STAGE_1_SHADOW.value

    def test_gb56_stage_skip_not_allowed(self):
        """GB56: Cannot skip stages — advancement always moves exactly one stage forward."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        new_stage, _ = pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        # Can only advance to Stage 2, not Stage 3+
        assert new_stage == PilotStage.STAGE_2_RECOMMEND
        enrollment = pilot.get_enrollment(org)
        assert enrollment.current_stage == PilotStage.STAGE_2_RECOMMEND

    def test_gb57_regress_stage_allowed(self):
        """GB57: Emergency stage regression is always permitted."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin", starting_stage=PilotStage.STAGE_3_PREPARE)
        enrollment = pilot.regress_stage(org, PilotStage.STAGE_1_SHADOW, "sre_lead", "Incident detected")
        assert enrollment.current_stage == PilotStage.STAGE_1_SHADOW

    def test_gb58_regress_forward_raises(self):
        """GB58: Regressing to a later stage raises ValueError."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin", starting_stage=PilotStage.STAGE_2_RECOMMEND)
        with pytest.raises(ValueError, match="Regression must target an earlier stage"):
            pilot.regress_stage(org, PilotStage.STAGE_3_PREPARE, "admin", "test")

    def test_gb59_advance_without_gate_criteria_raises(self):
        """GB59: advance_stage() raises ValueError when gate criteria are not met."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")
        # No shadow data — will not meet gate criteria
        with pytest.raises(ValueError, match="Cannot advance"):
            pilot.advance_stage(org, "pilot_lead", override_duration_check=True)

    def test_gb60_full_stage_progression_lifecycle(self):
        """GB60: Full lifecycle simulation through Stage 1 -> Stage 2 -> Stage 3."""
        pilot = make_pilot_service()
        org = make_org()
        pilot.enroll_tenant(org, "admin")

        # Stage 1 -> 2: shadow accuracy
        for i in range(10):
            exec_id = str(uuid.uuid4())
            pilot.record_shadow_projection(org, f"lead-{i}", "LEAD_INTEL", exec_id,
                                            "SEND_FOLLOW_UP", "r", "B", "o")
            pilot.record_human_action(org, exec_id, "SEND_FOLLOW_UP")
        stage, _ = pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        assert stage == PilotStage.STAGE_2_RECOMMEND

        # Stage 2 -> 3: recommendation acceptance
        for i in range(10):
            pilot.record_recommendation_outcome(org, accepted=(i < 7))  # 70% >= 60%
        stage, _ = pilot.advance_stage(org, "pilot_lead", override_duration_check=True)
        assert stage == PilotStage.STAGE_3_PREPARE


# ═══════════════════════════════════════════════════════════════════════════════
# GB61-GB70: Pilot Safety Invariants & Kill-Switch Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestPilotSafetyInvariants:
    """GB61-GB70: Safety invariants, kill-switch integration, and agent boundaries."""

    def test_gb61_global_kill_switch_blocks_all_agent_actions(self):
        """GB61: Global kill-switch causes all governance evaluations to BLOCK."""
        engine = make_engine()
        org = make_org()
        engine.set_shadow_mode(org, "admin")
        EmergencyAutomationPauseService.set_global_pause(True, "SRE", "Test kill-switch")
        decision = engine.evaluate(org, Phase2ActionType.SEND_WHATSAPP_MESSAGE)
        assert not decision.is_permitted
        assert "kill switch" in decision.block_reason.lower()

    def test_gb62_tenant_kill_switch_blocks_tenant_actions(self):
        """GB62: Tenant kill-switch blocks actions for that tenant only."""
        engine = make_engine()
        org_a, org_b = make_org(), make_org()
        engine.set_live_limited_mode(org_a, "admin")
        engine.set_live_limited_mode(org_b, "admin")
        EmergencyAutomationPauseService.set_tenant_pause(org_a, True, "SRE", "Incident")
        decision_a = engine.evaluate(org_a, Phase2ActionType.SEND_FOLLOW_UP)
        decision_b = engine.evaluate(org_b, Phase2ActionType.SEND_FOLLOW_UP)
        assert not decision_a.is_permitted
        # org_b in LIVE mode with conditions may or may not permit — the key is it's not kill-switch blocked
        assert "kill switch" not in (decision_b.block_reason or "").lower()

    def test_gb63_financial_actions_never_exceed_level3(self):
        """GB63: Financial actions never exceed REQUEST_APPROVAL (Level 3) regardless of config."""
        engine = make_engine()
        org = make_org()
        # Try to set financial to AUTONOMOUS_GOVERNED (6)
        engine.configure_tenant(
            org,
            execution_mode=Phase2ExecutionMode.LIVE,
            default_level_financial=Phase2AutonomyLevel.AUTONOMOUS_GOVERNED,
        )
        config = engine.get_tenant_config(org)
        assert config.default_level_financial.value <= Phase2AutonomyLevel.REQUEST_APPROVAL.value

    def test_gb64_revenue_intelligence_agent_cannot_send_messages(self):
        """GB64: RevenueIntelligenceAgent has SEND_WHATSAPP_MESSAGE in forbidden_actions."""
        agent = RevenueIntelligenceAgent()
        permitted, reason = agent.is_action_permitted_for_agent(Phase2ActionType.SEND_WHATSAPP_MESSAGE)
        assert not permitted
        assert "forbidden" in reason.lower()

    def test_gb65_manager_intelligence_agent_cannot_schedule_visits(self):
        """GB65: ManagerIntelligenceAgent has SCHEDULE_SITE_VISIT in forbidden_actions."""
        agent = ManagerIntelligenceAgent()
        permitted, reason = agent.is_action_permitted_for_agent(Phase2ActionType.SCHEDULE_SITE_VISIT)
        assert not permitted
        assert "forbidden" in reason.lower()

    def test_gb66_agent_registry_contains_all_10_agents(self):
        """GB66: Agent registry contains exactly 10 agents."""
        ids = get_all_agent_ids()
        assert len(ids) == 10
        assert len(ALL_PHASE2B_AGENTS) == 10

    def test_gb67_all_agents_have_unique_agent_ids(self):
        """GB67: All 10 agents have unique agent_id values."""
        ids = [agent.agent_id for agent in ALL_PHASE2B_AGENTS]
        assert len(ids) == len(set(ids))

    def test_gb68_all_agents_have_forbidden_financial_actions(self):
        """GB68: All agents forbid at least CREATE_BOOKING and PROCESS_PAYMENT."""
        for agent in ALL_PHASE2B_AGENTS:
            assert Phase2ActionType.CREATE_BOOKING in agent.forbidden_actions, (
                f"Agent {agent.agent_id} does not forbid CREATE_BOOKING"
            )
            assert Phase2ActionType.PROCESS_PAYMENT in agent.forbidden_actions, (
                f"Agent {agent.agent_id} does not forbid PROCESS_PAYMENT"
            )

    def test_gb69_conditions_built_correctly_from_context(self):
        """GB69: build_conditions() returns 5 canonical conditions from context."""
        org = make_org()
        ctx = make_context(org)
        conditions = build_conditions(ctx)
        assert len(conditions) == 5
        cond_ids = {c.condition_id for c in conditions}
        from app.modules.autonomous_loop.phase2_governance import (
            CANONICAL_CONDITION_1, CANONICAL_CONDITION_2, CANONICAL_CONDITION_3,
            CANONICAL_CONDITION_4, CANONICAL_CONDITION_5,
        )
        assert {CANONICAL_CONDITION_1, CANONICAL_CONDITION_2, CANONICAL_CONDITION_3,
                CANONICAL_CONDITION_4, CANONICAL_CONDITION_5} == cond_ids

    def test_gb70_stale_context_fails_freshness_condition(self):
        """GB70: Stale context (beyond TTL) fails the FRESHNESS_VERIFIED condition."""
        from app.modules.autonomous_loop.phase2_governance import CANONICAL_CONDITION_1
        org = make_org()
        ctx = make_context(org, fresh=False)  # Stale context
        assert not ctx.is_fresh()
        conditions = build_conditions(ctx)
        freshness_cond = next(c for c in conditions if c.condition_id == CANONICAL_CONDITION_1)
        assert freshness_cond.is_met is False
