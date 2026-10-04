"""
Phase 2 — Agent Outcome Telemetry & Learning Extension
=======================================================
Extends Sprint 1E's Revenue Learning OS into agent performance measurement.

Per Phase 2 Sections 41, 42, 44, 47, 86, 87:
  - Every agent execution produces an AgentExecutionRecord
  - Agent KPIs: task_success, workflow_completion, human_override, revenue_effect
  - Agent cost accounting: AI cost, execution latency, business outcome
  - Agent failure taxonomy: all failure types are distinguishable
  - Agent quality dataset: built from real outcomes
  - Performance evaluation grounded in real business results

DOES NOT DUPLICATE:
  - Sprint 1E OutcomeEvent infrastructure (intelligence/outcome_recorder.py)
  - RecommendationEvaluation models (intelligence_models.py)
  - Existing telemetry infrastructure (infrastructure/middleware/observability_middleware.py)

INTEGRATES WITH:
  - phase2_agent_contracts.AgentExecutionRecord
  - Sprint 1E outcome_events (Spine B) — outcome linkage
  - intelligence_models.LossEvent — agent failure taxonomy linkage
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ─── 1. Agent KPI Enum (Section 42, 86) ──────────────────────────────────────

class AgentKPI(str, enum.Enum):
    """
    Canonical agent KPI registry.
    Per Section 42: optimize for business value, not execution volume.
    """
    TASK_SUCCESS = "TASK_SUCCESS"
    TASK_FAILURE = "TASK_FAILURE"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    CUSTOMER_RESPONDED = "CUSTOMER_RESPONDED"
    CUSTOMER_NO_RESPONSE = "CUSTOMER_NO_RESPONSE"
    VISIT_PROGRESSED = "VISIT_PROGRESSED"
    OFFER_PROGRESSED = "OFFER_PROGRESSED"
    BOOKING_PROGRESSED = "BOOKING_PROGRESSED"
    REVENUE_ATTRIBUTED = "REVENUE_ATTRIBUTED"
    RECOVERY_SUCCESSFUL = "RECOVERY_SUCCESSFUL"
    INCIDENT_TRIGGERED = "INCIDENT_TRIGGERED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    SHADOW_WOULD_HAVE = "SHADOW_WOULD_HAVE"   # Shadow mode captured projected action


# ─── 2. Agent Cost Record (Section 44, 45) ───────────────────────────────────

@dataclass
class AgentCostRecord:
    """
    Per-execution cost accounting.
    Per Section 44: measure per workflow — AI cost, execution latency, human review, business outcome.
    Goal: BUSINESS VALUE PER UNIT OF AUTOMATION.
    """
    execution_id: str
    organization_id: str
    agent_domain: str

    # AI costs
    ai_prompt_tokens: int = 0
    ai_completion_tokens: int = 0
    ai_calls: int = 0
    ai_cost_usd: float = 0.0

    # Execution costs
    tool_calls: int = 0
    execution_latency_ms: int = 0
    database_queries: int = 0

    # Human costs
    human_review_required: bool = False
    human_review_minutes: float = 0.0

    # Business outcome
    business_kpi: Optional[AgentKPI] = None
    revenue_outcome_linked: bool = False
    revenue_amount: Optional[float] = None

    # Manual effort metrics
    estimated_manual_effort_minutes: float = 0.0
    automation_effort_minutes: float = 0.0

    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_cost_usd(self) -> float:
        return self.ai_cost_usd

    @property
    def business_value_per_unit(self) -> Optional[str]:
        """
        Human-readable business value assessment.
        Per Section 45: only calculate when source data exists.
        """
        if self.revenue_amount and self.ai_cost_usd > 0:
            roi = self.revenue_amount / self.ai_cost_usd
            return f"${self.revenue_amount:.2f} revenue / ${self.ai_cost_usd:.4f} AI cost = {roi:.1f}x ROI"
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "organization_id": self.organization_id,
            "agent_domain": self.agent_domain,
            "ai_cost_usd": self.ai_cost_usd,
            "ai_calls": self.ai_calls,
            "tool_calls": self.tool_calls,
            "execution_latency_ms": self.execution_latency_ms,
            "human_review_required": self.human_review_required,
            "human_review_minutes": self.human_review_minutes,
            "business_kpi": self.business_kpi.value if self.business_kpi else None,
            "revenue_outcome_linked": self.revenue_outcome_linked,
            "revenue_amount": self.revenue_amount,
            "business_value_per_unit": self.business_value_per_unit,
            "recorded_at": self.recorded_at.isoformat(),
        }


# ─── 3. Shadow Mode Comparison Record (Section 56, 57) ───────────────────────

@dataclass
class ShadowModeRecord:
    """
    Shadow mode capture: what the agent would have done vs what the human actually did.
    Per Section 56: capture what it would have done, why, policy result, expected outcome.
    Per Section 57: compare human action vs agent recommendation vs agent-executed action.
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    lead_id: Optional[str] = None
    agent_domain: str = ""
    execution_id: str = ""

    # What agent would have done
    proposed_action: Optional[str] = None
    proposed_action_reasoning: Optional[str] = None
    policy_result: Optional[str] = None
    expected_outcome: Optional[str] = None

    # What human actually did (for comparison)
    human_action_taken: Optional[str] = None
    human_action_at: Optional[datetime] = None

    # Comparison
    action_aligned: Optional[bool] = None  # Did human take same action?
    alignment_notes: Optional[str] = None

    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "agent_domain": self.agent_domain,
            "proposed_action": self.proposed_action,
            "proposed_action_reasoning": self.proposed_action_reasoning,
            "policy_result": self.policy_result,
            "expected_outcome": self.expected_outcome,
            "human_action_taken": self.human_action_taken,
            "action_aligned": self.action_aligned,
            "recorded_at": self.recorded_at.isoformat(),
        }


# ─── 4. Agent Incident Record (Section 61, 99) ───────────────────────────────

class AgentIncidentType(str, enum.Enum):
    """
    Agent incident taxonomy. Per Section 61: incidents must be immediately recorded.
    Any of these occurring blocks release (Section 99).
    """
    UNAUTHORIZED_ACTION = "UNAUTHORIZED_ACTION"
    REPEATED_FAILURE = "REPEATED_FAILURE"
    POLICY_BYPASS_DETECTED = "POLICY_BYPASS_DETECTED"
    HALLUCINATED_COMMERCIAL_CLAIM = "HALLUCINATED_COMMERCIAL_CLAIM"
    DUPLICATE_EXTERNAL_ACTION = "DUPLICATE_EXTERNAL_ACTION"
    WRONG_TENANT_CONTEXT = "WRONG_TENANT_CONTEXT"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    TOOL_INJECTION = "TOOL_INJECTION"
    PII_LEAKAGE = "PII_LEAKAGE"
    CROSS_TENANT_EXPOSURE = "CROSS_TENANT_EXPOSURE"
    INFINITE_LOOP_DETECTED = "INFINITE_LOOP_DETECTED"
    REVENUE_LEDGER_MUTATION = "REVENUE_LEDGER_MUTATION"
    PROPERTY_TRUTH_CORRUPTION = "PROPERTY_TRUTH_CORRUPTION"


@dataclass
class AgentIncidentRecord:
    """
    Incident record per Phase 2 Section 61.
    Every incident is an immediate RELEASE BLOCKER until resolved.
    """
    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident_type: AgentIncidentType = AgentIncidentType.UNAUTHORIZED_ACTION
    organization_id: str = ""
    lead_id: Optional[str] = None
    execution_id: Optional[str] = None
    agent_domain: Optional[str] = None

    # Evidence
    model_used: Optional[str] = None
    policy_version: Optional[str] = None
    tool_name: Optional[str] = None
    inputs_summary: Optional[str] = None  # Sanitized — no PII
    outputs_summary: Optional[str] = None  # Sanitized — no PII
    actions_taken: List[str] = field(default_factory=list)

    # Impact & containment
    impact_description: str = ""
    containment_action: str = ""
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "incident_type": self.incident_type.value,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "execution_id": self.execution_id,
            "impact_description": self.impact_description,
            "containment_action": self.containment_action,
            "is_resolved": self.is_resolved,
            "detected_at": self.detected_at.isoformat(),
        }


# ─── 5. Agent Telemetry Service ───────────────────────────────────────────────

class Phase2AgentTelemetryService:
    """
    In-process telemetry collection for Phase 2 agent executions.
    In production, this integrates with the existing observability infrastructure
    (infrastructure/middleware/observability_middleware.py).
    """

    def __init__(self):
        self._execution_records: List[Dict[str, Any]] = []
        self._cost_records: List[AgentCostRecord] = []
        self._shadow_records: List[ShadowModeRecord] = []
        self._incidents: List[AgentIncidentRecord] = []

    def record_execution(self, record_dict: Dict[str, Any]) -> None:
        """Records a completed agent execution."""
        self._execution_records.append(record_dict)

    def record_cost(self, cost_record: AgentCostRecord) -> None:
        """Records agent cost accounting for a single execution."""
        self._cost_records.append(cost_record)

    def record_shadow(self, shadow_record: ShadowModeRecord) -> None:
        """Records a shadow mode projection."""
        self._shadow_records.append(shadow_record)

    def record_incident(self, incident: AgentIncidentRecord) -> None:
        """Records an agent incident. These are release blockers."""
        self._incidents.append(incident)

    def get_execution_records(self) -> List[Dict[str, Any]]:
        return list(self._execution_records)

    def get_cost_records(self) -> List[AgentCostRecord]:
        return list(self._cost_records)

    def get_shadow_records(self) -> List[ShadowModeRecord]:
        return list(self._shadow_records)

    def get_incidents(self) -> List[AgentIncidentRecord]:
        return list(self._incidents)

    def get_incident_count(self) -> int:
        return len(self._incidents)

    def has_release_blocking_incidents(self) -> bool:
        """Returns True if any unresolved incidents exist (release blocker)."""
        return any(not i.is_resolved for i in self._incidents)

    def reset_for_testing(self) -> None:
        """Resets all in-memory state between test runs."""
        self._execution_records.clear()
        self._cost_records.clear()
        self._shadow_records.clear()
        self._incidents.clear()

    def summary(self) -> Dict[str, Any]:
        """Returns telemetry summary for dashboard / operations."""
        total_executions = len(self._execution_records)
        total_cost = sum(c.ai_cost_usd for c in self._cost_records)
        shadow_count = len(self._shadow_records)
        incident_count = len(self._incidents)
        unresolved_incidents = sum(1 for i in self._incidents if not i.is_resolved)

        return {
            "total_executions": total_executions,
            "total_ai_cost_usd": round(total_cost, 6),
            "shadow_mode_records": shadow_count,
            "total_incidents": incident_count,
            "unresolved_incidents": unresolved_incidents,
            "has_release_blocking_incidents": unresolved_incidents > 0,
        }


# ─── 6. Module-level telemetry singleton ─────────────────────────────────────

_telemetry_instance: Optional[Phase2AgentTelemetryService] = None


def get_telemetry_service() -> Phase2AgentTelemetryService:
    """Returns the singleton telemetry service instance."""
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = Phase2AgentTelemetryService()
    return _telemetry_instance
