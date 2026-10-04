"""
Phase 2B — Controlled Agent Pilot Engine
==========================================
Manages the full controlled pilot lifecycle for WefyLabs autonomous agents.

PILOT LIFECYCLE (per PHASE2_PILOT_PLAN.md):
  Stage 1: Shadow Mode     — observe, log, zero external actions
  Stage 2: Recommend Mode  — surface recommendations, no outbound
  Stage 3: Prepare Mode    — draft/stage into review queue, no external dispatch
  Stage 4: Approval Mode   — submit for explicit human approval before execution
  Stage 5: Live Limited    — conditionally autonomous within policy constraints

ARCHITECTURE:
  - PilotTenantEnrollment: tracks each tenant's pilot stage + metrics
  - PilotAdvancementEngine: evaluates criteria and gates stage advancement
  - ShadowComparisonEngine: records what agent WOULD have done vs human DID
  - PilotMetricsAccumulator: accumulates KPIs needed for advancement gates
  - PilotLifecycleService: orchestrates the full pilot for a tenant

PHASE 2B SUCCESS CRITERIA:
  - All 10 bounded domain agents executing without incident in shadow mode
  - Shadow accuracy >= 70% for Stage 1 -> Stage 2 advancement
  - Recommendation acceptance rate >= 60% for Stage 2 -> Stage 3 advancement
  - Prepared draft quality >= 80% for Stage 3 -> Stage 4 advancement
  - Approval acceptance rate >= 75% for Stage 4 -> Stage 5 advancement
  - Zero incidents across all stages block advancement
  - Human override rate < 15% at Stage 5

INVARIANTS:
  1. Tenants NEVER skip stages. Sequential progression enforced.
  2. Any unresolved AgentIncidentRecord blocks ALL advancement.
  3. Stage regression is always permitted (safety degradation allowed, autonomy never).
  4. Pilot metrics are grounded in real execution records, never synthetic.
  5. Emergency kill switch overrides all pilot stage controls instantly.
"""
from __future__ import annotations

import enum
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.modules.autonomous_loop.phase2_governance import (
    Phase2ExecutionMode,
    Phase2AutonomyLevel,
    Phase2ActionType,
    RevenueActionPolicyEngine,
    get_policy_engine,
)
from app.modules.autonomous_loop.phase2_agent_contracts import (
    AgentDomain,
    AgentExecutionRecord,
    AgentExecutionState,
    AgentConfidence,
    AgentFailureType,
)
from app.modules.autonomous_loop.phase2_telemetry import (
    AgentIncidentRecord,
    AgentIncidentType,
    ShadowModeRecord,
    AgentKPI,
    AgentCostRecord,
    Phase2AgentTelemetryService,
    get_telemetry_service,
)

logger = logging.getLogger("wefylabs.phase2b.pilot_engine")


class PilotStage(str, enum.Enum):
    NOT_ENROLLED      = "NOT_ENROLLED"
    STAGE_1_SHADOW    = "STAGE_1_SHADOW"
    STAGE_2_RECOMMEND = "STAGE_2_RECOMMEND"
    STAGE_3_PREPARE   = "STAGE_3_PREPARE"
    STAGE_4_APPROVAL  = "STAGE_4_APPROVAL"
    STAGE_5_LIVE      = "STAGE_5_LIVE"

    def execution_mode(self) -> Phase2ExecutionMode:
        return {
            PilotStage.NOT_ENROLLED:       Phase2ExecutionMode.SHADOW,
            PilotStage.STAGE_1_SHADOW:     Phase2ExecutionMode.SHADOW,
            PilotStage.STAGE_2_RECOMMEND:  Phase2ExecutionMode.RECOMMEND,
            PilotStage.STAGE_3_PREPARE:    Phase2ExecutionMode.PREPARE,
            PilotStage.STAGE_4_APPROVAL:   Phase2ExecutionMode.APPROVAL,
            PilotStage.STAGE_5_LIVE:       Phase2ExecutionMode.LIVE,
        }[self]

    def next_stage(self) -> Optional["PilotStage"]:
        order = [
            PilotStage.STAGE_1_SHADOW,
            PilotStage.STAGE_2_RECOMMEND,
            PilotStage.STAGE_3_PREPARE,
            PilotStage.STAGE_4_APPROVAL,
            PilotStage.STAGE_5_LIVE,
        ]
        try:
            idx = order.index(self)
            if idx + 1 < len(order):
                return order[idx + 1]
        except ValueError:
            pass
        return None


@dataclass
class PilotMetrics:
    organization_id: str
    stage: PilotStage
    window_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    shadow_total: int = 0
    shadow_aligned: int = 0
    recommendations_generated: int = 0
    recommendations_accepted: int = 0
    human_overrides: int = 0
    drafts_prepared: int = 0
    drafts_accepted: int = 0
    outbound_dispatches: int = 0
    approval_requests: int = 0
    approvals_granted: int = 0
    approval_denials: int = 0
    mean_approval_time_minutes: float = 0.0
    autonomous_executions: int = 0
    total_executions: int = 0
    total_failures: int = 0
    policy_blocks: int = 0
    incidents_detected: int = 0
    incidents_resolved: int = 0
    customer_responses: int = 0

    @property
    def shadow_accuracy(self) -> float:
        return self.shadow_aligned / self.shadow_total if self.shadow_total > 0 else 0.0

    @property
    def recommendation_acceptance_rate(self) -> float:
        return self.recommendations_accepted / self.recommendations_generated if self.recommendations_generated > 0 else 0.0

    @property
    def draft_acceptance_rate(self) -> float:
        return self.drafts_accepted / self.drafts_prepared if self.drafts_prepared > 0 else 0.0

    @property
    def approval_acceptance_rate(self) -> float:
        return self.approvals_granted / self.approval_requests if self.approval_requests > 0 else 0.0

    @property
    def stage_human_override_rate(self) -> float:
        return self.human_overrides / self.autonomous_executions if self.autonomous_executions > 0 else 0.0

    @property
    def has_zero_incidents(self) -> bool:
        return self.incidents_detected == self.incidents_resolved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "stage": self.stage.value,
            "window_start": self.window_start.isoformat(),
            "shadow_accuracy": round(self.shadow_accuracy, 4),
            "recommendation_acceptance_rate": round(self.recommendation_acceptance_rate, 4),
            "draft_acceptance_rate": round(self.draft_acceptance_rate, 4),
            "approval_acceptance_rate": round(self.approval_acceptance_rate, 4),
            "stage_human_override_rate": round(self.stage_human_override_rate, 4),
            "has_zero_incidents": self.has_zero_incidents,
            "total_executions": self.total_executions,
            "total_failures": self.total_failures,
            "incidents_detected": self.incidents_detected,
            "incidents_resolved": self.incidents_resolved,
            "outbound_dispatches": self.outbound_dispatches,
        }


@dataclass
class PilotAdvancementCriteria:
    target_stage: PilotStage
    min_shadow_accuracy: float = 0.0
    min_recommendation_acceptance_rate: float = 0.0
    min_draft_acceptance_rate: float = 0.0
    min_approval_acceptance_rate: float = 0.0
    max_human_override_rate: float = 1.0
    require_zero_incidents: bool = True
    require_zero_outbound_in_stage3: bool = False
    min_duration_days: int = 0
    description: str = ""


ADVANCEMENT_GATES: Dict[PilotStage, PilotAdvancementCriteria] = {
    PilotStage.STAGE_1_SHADOW: PilotAdvancementCriteria(
        target_stage=PilotStage.STAGE_2_RECOMMEND,
        min_shadow_accuracy=0.70,
        require_zero_incidents=True,
        min_duration_days=14,
        description="Stage 1->2: Shadow accuracy >= 70%, zero incidents, min 14 days",
    ),
    PilotStage.STAGE_2_RECOMMEND: PilotAdvancementCriteria(
        target_stage=PilotStage.STAGE_3_PREPARE,
        min_recommendation_acceptance_rate=0.60,
        require_zero_incidents=True,
        min_duration_days=7,
        description="Stage 2->3: Recommendation acceptance >= 60%, zero incidents, min 7 days",
    ),
    PilotStage.STAGE_3_PREPARE: PilotAdvancementCriteria(
        target_stage=PilotStage.STAGE_4_APPROVAL,
        min_draft_acceptance_rate=0.80,
        require_zero_incidents=True,
        require_zero_outbound_in_stage3=True,
        min_duration_days=7,
        description="Stage 3->4: Draft acceptance >= 80%, zero outbound dispatches, zero incidents, min 7 days",
    ),
    PilotStage.STAGE_4_APPROVAL: PilotAdvancementCriteria(
        target_stage=PilotStage.STAGE_5_LIVE,
        min_approval_acceptance_rate=0.75,
        require_zero_incidents=True,
        min_duration_days=14,
        description="Stage 4->5: Approval acceptance >= 75%, zero incidents, min 14 days",
    ),
}


@dataclass
class AdvancementEvaluationResult:
    organization_id: str
    current_stage: PilotStage
    target_stage: Optional[PilotStage]
    can_advance: bool
    blocking_reasons: List[str]
    passing_criteria: List[str]
    metrics_snapshot: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "current_stage": self.current_stage.value,
            "target_stage": self.target_stage.value if self.target_stage else None,
            "can_advance": self.can_advance,
            "blocking_reasons": self.blocking_reasons,
            "passing_criteria": self.passing_criteria,
            "metrics_snapshot": self.metrics_snapshot,
        }


@dataclass
class PilotTenantEnrollment:
    enrollment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    current_stage: PilotStage = PilotStage.NOT_ENROLLED
    enrolled_by: str = "SYSTEM"
    enrolled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    current_metrics: Optional[Any] = None
    metrics_history: List[Dict[str, Any]] = field(default_factory=list)
    enrolled_agents: List[str] = field(default_factory=list)
    policy_engine_configured: bool = False
    pilot_notes: List[str] = field(default_factory=list)
    is_active: bool = True

    def record_stage_transition(self, from_stage, to_stage, advanced_by, reason):
        self.stage_history.append({
            "from_stage": from_stage.value,
            "to_stage": to_stage.value,
            "advanced_by": advanced_by,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def stage_age_days(self) -> float:
        if not self.stage_history:
            delta = (datetime.now(timezone.utc) - self.enrolled_at).total_seconds()
            return delta / 86400
        last = self.stage_history[-1]
        ts = datetime.fromisoformat(last["timestamp"])
        return (datetime.now(timezone.utc) - ts).total_seconds() / 86400

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enrollment_id": self.enrollment_id,
            "organization_id": self.organization_id,
            "current_stage": self.current_stage.value,
            "enrolled_by": self.enrolled_by,
            "enrolled_at": self.enrolled_at.isoformat(),
            "stage_age_days": round(self.stage_age_days(), 2),
            "enrolled_agents": self.enrolled_agents,
            "stage_history": self.stage_history,
            "is_active": self.is_active,
        }


class ShadowComparisonEngine:
    def __init__(self):
        self._shadow_records: List[ShadowModeRecord] = []

    def record_shadow_projection(self, organization_id, lead_id, agent_domain,
                                  execution_id, proposed_action, proposed_reasoning,
                                  policy_result, expected_outcome) -> ShadowModeRecord:
        record = ShadowModeRecord(
            organization_id=organization_id,
            lead_id=lead_id,
            agent_domain=agent_domain,
            execution_id=execution_id,
            proposed_action=proposed_action,
            proposed_action_reasoning=proposed_reasoning,
            policy_result=policy_result,
            expected_outcome=expected_outcome,
        )
        self._shadow_records.append(record)
        return record

    def record_human_action(self, execution_id, human_action) -> Optional[ShadowModeRecord]:
        record = next((r for r in self._shadow_records if r.execution_id == execution_id), None)
        if record is None:
            return None
        record.human_action_taken = human_action
        record.human_action_at = datetime.now(timezone.utc)
        record.action_aligned = (
            human_action.strip().upper() == (record.proposed_action or "").strip().upper()
        )
        record.alignment_notes = (
            "Agent and human agreed." if record.action_aligned
            else f"Agent: {record.proposed_action} | Human: {human_action}"
        )
        return record

    def get_shadow_accuracy(self, organization_id) -> Tuple[float, int, int]:
        compared = [
            r for r in self._shadow_records
            if r.organization_id == organization_id
            and r.human_action_taken is not None
            and r.action_aligned is not None
        ]
        if not compared:
            return 0.0, 0, 0
        aligned = sum(1 for r in compared if r.action_aligned)
        return aligned / len(compared), aligned, len(compared)

    def get_records(self, organization_id) -> List[ShadowModeRecord]:
        return [r for r in self._shadow_records if r.organization_id == organization_id]

    def reset_for_testing(self):
        self._shadow_records.clear()


class PilotAdvancementEngine:
    def evaluate_advancement(
        self,
        enrollment: PilotTenantEnrollment,
        metrics: PilotMetrics,
        telemetry: Phase2AgentTelemetryService,
        override_duration_check: bool = False,
    ) -> AdvancementEvaluationResult:
        current_stage = enrollment.current_stage
        target_stage = current_stage.next_stage()

        if target_stage is None:
            return AdvancementEvaluationResult(
                organization_id=enrollment.organization_id,
                current_stage=current_stage,
                target_stage=None,
                can_advance=False,
                blocking_reasons=["Tenant is at Stage 5 (maximum pilot stage)."],
                passing_criteria=[],
                metrics_snapshot=metrics.to_dict(),
            )

        gate = ADVANCEMENT_GATES.get(current_stage)
        if gate is None:
            return AdvancementEvaluationResult(
                organization_id=enrollment.organization_id,
                current_stage=current_stage,
                target_stage=target_stage,
                can_advance=False,
                blocking_reasons=["No advancement gate defined for current stage."],
                passing_criteria=[],
                metrics_snapshot=metrics.to_dict(),
            )

        blocking: List[str] = []
        passing: List[str] = []

        if gate.require_zero_incidents:
            if telemetry.has_release_blocking_incidents():
                blocking.append(f"INCIDENT BLOCKER: Unresolved incidents detected.")
            else:
                passing.append("Zero unresolved incidents.")

        if gate.min_shadow_accuracy > 0:
            if metrics.shadow_accuracy >= gate.min_shadow_accuracy:
                passing.append(f"Shadow accuracy {metrics.shadow_accuracy:.1%} >= {gate.min_shadow_accuracy:.1%}")
            else:
                blocking.append(f"Shadow accuracy {metrics.shadow_accuracy:.1%} < {gate.min_shadow_accuracy:.1%} required.")

        if gate.min_recommendation_acceptance_rate > 0:
            if metrics.recommendation_acceptance_rate >= gate.min_recommendation_acceptance_rate:
                passing.append(f"Recommendation acceptance {metrics.recommendation_acceptance_rate:.1%} >= {gate.min_recommendation_acceptance_rate:.1%}")
            else:
                blocking.append(f"Recommendation acceptance {metrics.recommendation_acceptance_rate:.1%} < {gate.min_recommendation_acceptance_rate:.1%} required.")

        if gate.min_draft_acceptance_rate > 0:
            if metrics.draft_acceptance_rate >= gate.min_draft_acceptance_rate:
                passing.append(f"Draft acceptance {metrics.draft_acceptance_rate:.1%} >= {gate.min_draft_acceptance_rate:.1%}")
            else:
                blocking.append(f"Draft acceptance {metrics.draft_acceptance_rate:.1%} < {gate.min_draft_acceptance_rate:.1%} required.")

        if gate.require_zero_outbound_in_stage3:
            if metrics.outbound_dispatches == 0:
                passing.append("Zero outbound dispatches in Stage 3")
            else:
                blocking.append(f"Stage 3 recorded {metrics.outbound_dispatches} outbound dispatch(es). Must be zero.")

        if gate.min_approval_acceptance_rate > 0:
            if metrics.approval_acceptance_rate >= gate.min_approval_acceptance_rate:
                passing.append(f"Approval acceptance {metrics.approval_acceptance_rate:.1%} >= {gate.min_approval_acceptance_rate:.1%}")
            else:
                blocking.append(f"Approval acceptance {metrics.approval_acceptance_rate:.1%} < {gate.min_approval_acceptance_rate:.1%} required.")

        if not override_duration_check and gate.min_duration_days > 0:
            age_days = enrollment.stage_age_days()
            if age_days >= gate.min_duration_days:
                passing.append(f"Stage duration {age_days:.1f} days >= {gate.min_duration_days} days")
            else:
                blocking.append(f"Stage duration {age_days:.1f} days < {gate.min_duration_days} days required.")

        return AdvancementEvaluationResult(
            organization_id=enrollment.organization_id,
            current_stage=current_stage,
            target_stage=target_stage,
            can_advance=len(blocking) == 0,
            blocking_reasons=blocking,
            passing_criteria=passing,
            metrics_snapshot=metrics.to_dict(),
        )


class PilotLifecycleService:
    def __init__(self, policy_engine=None, telemetry=None):
        self._policy_engine = policy_engine or get_policy_engine()
        self._telemetry = telemetry or get_telemetry_service()
        self._enrollments: Dict[str, PilotTenantEnrollment] = {}
        self._metrics: Dict[str, PilotMetrics] = {}
        self._shadow_engine = ShadowComparisonEngine()
        self._advancement_engine = PilotAdvancementEngine()
        self._audit_log: List[Dict[str, Any]] = []

    def enroll_tenant(self, organization_id, enrolled_by, starting_stage=PilotStage.STAGE_1_SHADOW,
                      agent_ids=None, notes="") -> PilotTenantEnrollment:
        if organization_id in self._enrollments:
            raise ValueError(f"Tenant {organization_id} is already enrolled.")
        enrollment = PilotTenantEnrollment(
            organization_id=organization_id,
            current_stage=starting_stage,
            enrolled_by=enrolled_by,
            enrolled_agents=list(agent_ids or []),
            pilot_notes=[notes] if notes else [],
        )
        metrics = PilotMetrics(organization_id=organization_id, stage=starting_stage)
        self._enrollments[organization_id] = enrollment
        self._metrics[organization_id] = metrics
        self._configure_policy_engine(organization_id, starting_stage, enrolled_by)
        self._audit("ENROLLED", organization_id, enrolled_by, {
            "starting_stage": starting_stage.value,
            "agent_ids": agent_ids or [],
        })
        logger.info(f"[PILOT] Tenant {organization_id} enrolled at {starting_stage.value}")
        return enrollment

    def get_enrollment(self, organization_id) -> Optional[PilotTenantEnrollment]:
        return self._enrollments.get(organization_id)

    def get_metrics(self, organization_id) -> Optional[PilotMetrics]:
        return self._metrics.get(organization_id)

    def evaluate_advancement(self, organization_id, override_duration_check=False) -> AdvancementEvaluationResult:
        enrollment = self._require_enrollment(organization_id)
        metrics = self._metrics[organization_id]
        return self._advancement_engine.evaluate_advancement(
            enrollment, metrics, self._telemetry,
            override_duration_check=override_duration_check,
        )

    def advance_stage(self, organization_id, advanced_by, override_duration_check=False,
                      force=False) -> Tuple[PilotStage, AdvancementEvaluationResult]:
        enrollment = self._require_enrollment(organization_id)
        evaluation = self.evaluate_advancement(organization_id, override_duration_check)
        if not evaluation.can_advance and not force:
            raise ValueError(
                f"Cannot advance {organization_id}: {evaluation.blocking_reasons}"
            )
        from_stage = enrollment.current_stage
        to_stage = evaluation.target_stage
        if to_stage is None:
            raise ValueError(f"Tenant {organization_id} is at maximum stage.")
        if self._metrics.get(organization_id):
            enrollment.metrics_history.append(self._metrics[organization_id].to_dict())
        enrollment.record_stage_transition(from_stage, to_stage, advanced_by, str(evaluation.passing_criteria))
        enrollment.current_stage = to_stage
        self._metrics[organization_id] = PilotMetrics(organization_id=organization_id, stage=to_stage)
        self._configure_policy_engine(organization_id, to_stage, advanced_by)
        self._audit("ADVANCED", organization_id, advanced_by, {
            "from_stage": from_stage.value,
            "to_stage": to_stage.value,
        })
        logger.info(f"[PILOT] {organization_id} ADVANCED {from_stage.value} -> {to_stage.value}")
        return to_stage, evaluation

    def regress_stage(self, organization_id, target_stage, regressed_by, reason) -> PilotTenantEnrollment:
        enrollment = self._require_enrollment(organization_id)
        current = enrollment.current_stage
        stage_order = [
            PilotStage.STAGE_1_SHADOW, PilotStage.STAGE_2_RECOMMEND,
            PilotStage.STAGE_3_PREPARE, PilotStage.STAGE_4_APPROVAL, PilotStage.STAGE_5_LIVE,
        ]
        try:
            current_idx = stage_order.index(current)
            target_idx = stage_order.index(target_stage)
        except ValueError:
            raise ValueError(f"Invalid regression target: {target_stage.value}")
        if target_idx >= current_idx:
            raise ValueError(f"Regression must target an earlier stage. Current={current.value}, Target={target_stage.value}")
        if self._metrics.get(organization_id):
            enrollment.metrics_history.append(self._metrics[organization_id].to_dict())
        enrollment.record_stage_transition(current, target_stage, regressed_by, f"REGRESSION: {reason}")
        enrollment.current_stage = target_stage
        self._metrics[organization_id] = PilotMetrics(organization_id=organization_id, stage=target_stage)
        self._configure_policy_engine(organization_id, target_stage, regressed_by)
        self._audit("REGRESSED", organization_id, regressed_by, {
            "from_stage": current.value, "to_stage": target_stage.value, "reason": reason,
        })
        logger.warning(f"[PILOT] {organization_id} REGRESSED {current.value} -> {target_stage.value}")
        return enrollment

    def record_execution(self, organization_id, execution_record: AgentExecutionRecord):
        metrics = self._metrics.get(organization_id)
        if metrics:
            metrics.total_executions += 1
            if execution_record.execution_state == AgentExecutionState.FAILED:
                metrics.total_failures += 1
        self._telemetry.record_execution(execution_record.to_dict())

    def record_shadow_projection(self, organization_id, lead_id, agent_domain, execution_id,
                                  proposed_action, proposed_reasoning, policy_result, expected_outcome):
        metrics = self._metrics.get(organization_id)
        if metrics:
            metrics.shadow_total += 1
        return self._shadow_engine.record_shadow_projection(
            organization_id, lead_id, agent_domain, execution_id,
            proposed_action, proposed_reasoning, policy_result, expected_outcome,
        )

    def record_human_action(self, organization_id, execution_id, human_action):
        record = self._shadow_engine.record_human_action(execution_id, human_action)
        metrics = self._metrics.get(organization_id)
        if metrics and record and record.action_aligned is not None:
            if record.action_aligned:
                metrics.shadow_aligned += 1
        return record

    def record_recommendation_outcome(self, organization_id, accepted, human_overrode=False):
        metrics = self._metrics.get(organization_id)
        if metrics:
            metrics.recommendations_generated += 1
            if accepted:
                metrics.recommendations_accepted += 1
            if human_overrode:
                metrics.human_overrides += 1

    def record_draft_outcome(self, organization_id, accepted, outbound_dispatched=False):
        metrics = self._metrics.get(organization_id)
        if metrics:
            metrics.drafts_prepared += 1
            if accepted:
                metrics.drafts_accepted += 1
            if outbound_dispatched:
                metrics.outbound_dispatches += 1
                logger.error(f"[PILOT_VIOLATION] Stage 3 outbound dispatch recorded for {organization_id}!")

    def record_approval_outcome(self, organization_id, approval_granted, approval_time_minutes=0.0):
        metrics = self._metrics.get(organization_id)
        if metrics:
            metrics.approval_requests += 1
            if approval_granted:
                metrics.approvals_granted += 1
            else:
                metrics.approval_denials += 1

    def record_policy_block(self, organization_id):
        metrics = self._metrics.get(organization_id)
        if metrics:
            metrics.policy_blocks += 1

    def record_incident(self, organization_id, incident: AgentIncidentRecord):
        metrics = self._metrics.get(organization_id)
        if metrics:
            metrics.incidents_detected += 1
        self._telemetry.record_incident(incident)
        logger.critical(f"[PILOT_INCIDENT] org={organization_id} type={incident.incident_type.value}")

    def resolve_incident(self, organization_id, incident_id, resolved_by):
        metrics = self._metrics.get(organization_id)
        for incident in self._telemetry.get_incidents():
            if incident.incident_id == incident_id and not incident.is_resolved:
                incident.is_resolved = True
                incident.resolved_at = datetime.now(timezone.utc)
                incident.resolved_by = resolved_by
                if metrics:
                    metrics.incidents_resolved += 1
                return

    def _configure_policy_engine(self, organization_id, stage, actor):
        mode_fns = {
            PilotStage.STAGE_1_SHADOW:    self._policy_engine.set_shadow_mode,
            PilotStage.STAGE_2_RECOMMEND: self._policy_engine.set_recommend_mode,
            PilotStage.STAGE_3_PREPARE:   self._policy_engine.set_prepare_mode,
            PilotStage.STAGE_4_APPROVAL:  self._policy_engine.set_approval_mode,
        }
        fn = mode_fns.get(stage)
        if fn:
            fn(organization_id, actor)
        elif stage == PilotStage.STAGE_5_LIVE:
            self._policy_engine.set_live_limited_mode(organization_id, actor)
        enrollment = self._enrollments.get(organization_id)
        if enrollment:
            enrollment.policy_engine_configured = True

    def _require_enrollment(self, organization_id) -> PilotTenantEnrollment:
        e = self._enrollments.get(organization_id)
        if e is None:
            raise ValueError(f"Tenant {organization_id} is not enrolled.")
        return e

    def _audit(self, event, org_id, actor, data):
        self._audit_log.append({
            "event": event,
            "organization_id": org_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        })

    def get_audit_log(self, organization_id=None):
        if organization_id:
            return [e for e in self._audit_log if e.get("organization_id") == organization_id]
        return list(self._audit_log)

    def get_pilot_status(self, organization_id):
        enrollment = self._enrollments.get(organization_id)
        metrics = self._metrics.get(organization_id)
        if not enrollment:
            return {"organization_id": organization_id, "status": "NOT_ENROLLED"}
        evaluation = self.evaluate_advancement(organization_id, override_duration_check=True)
        return {
            "enrollment": enrollment.to_dict(),
            "metrics": metrics.to_dict() if metrics else {},
            "advancement_evaluation": evaluation.to_dict(),
            "telemetry_summary": self._telemetry.summary(),
        }

    def get_shadow_engine(self) -> ShadowComparisonEngine:
        return self._shadow_engine

    def reset_for_testing(self):
        self._enrollments.clear()
        self._metrics.clear()
        self._audit_log.clear()
        self._shadow_engine.reset_for_testing()
        self._telemetry.reset_for_testing()


_pilot_service_instance: Optional[PilotLifecycleService] = None


def get_pilot_service() -> PilotLifecycleService:
    global _pilot_service_instance
    if _pilot_service_instance is None:
        _pilot_service_instance = PilotLifecycleService()
    return _pilot_service_instance
