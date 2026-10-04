"""
Phase 2 — Bounded Domain Agent Contracts
==========================================
Canonical, typed agent interface contracts for the WefyLabs Autonomous Revenue
Execution OS. Every agent must implement this interface.

PHASE 2 SPECIFICATION REQUIREMENTS:
  - Every agent has strict interface: agent_id, version, purpose, inputs,
    allowed_tools, allowed_actions, forbidden_actions, required_context,
    decision_schema, confidence semantics, fallback, audit requirements.
  - Agents NEVER have unrestricted database access.
  - Agent → Tool → Domain Service → Database (not Agent → Database).
  - Context objects are bounded — not entire database exports.
  - Every agent execution must produce a structured AgentExecutionRecord.

EXISTING INFRASTRUCTURE REUSED:
  - ActionPolicyEngine (ai_agent/action_policy.py)
  - RevenueActionPolicyEngine (phase2_governance.py)
  - SalesLoopAuditService (autonomous_loop/audit_service.py)
  - EmergencyAutomationPauseService (autonomous_loop/emergency_pause.py)
  - LoopProtectionService (autonomous_loop/loop_protection.py)
"""
from __future__ import annotations

import abc
import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.modules.autonomous_loop.phase2_governance import (
    Phase2ActionType,
    Phase2RiskClass,
    Phase2AutonomyLevel,
    Phase2PolicyDecision,
    Phase2ExecutionMode,
    AutonomyReadinessCondition,
    RevenueActionPolicyEngine,
)


# ─── 1. Agent Domain Classification (Section 6) ──────────────────────────────

class AgentDomain(str, enum.Enum):
    """
    Bounded domain agent registry. Each agent has a single, focused purpose.
    An agent must not span multiple domains. Complexity is managed by the orchestrator.
    """
    LEAD_INTELLIGENCE = "LEAD_INTELLIGENCE"
    QUALIFICATION = "QUALIFICATION"
    PROPERTY_MATCH = "PROPERTY_MATCH"
    ENGAGEMENT = "ENGAGEMENT"
    FOLLOW_UP = "FOLLOW_UP"
    VISIT = "VISIT"
    DEAL = "DEAL"
    RECOVERY = "RECOVERY"
    REVENUE_INTELLIGENCE = "REVENUE_INTELLIGENCE"
    MANAGER_INTELLIGENCE = "MANAGER_INTELLIGENCE"


# ─── 2. Agent Confidence Semantics (Section 40) ──────────────────────────────

class AgentConfidence(str, enum.Enum):
    """
    Categorical confidence states for agent outputs.
    Per Section 40: do not generate fake confidence numbers.
    Use categorical states only when objectively supported.
    """
    HIGH = "HIGH"       # Strong evidence from multiple verified sources
    MEDIUM = "MEDIUM"   # Reasonable evidence with some uncertainty
    LOW = "LOW"         # Limited or conflicting evidence
    UNKNOWN = "UNKNOWN" # Insufficient evidence to make any determination


# ─── 3. Agent Execution State (Section 31) ───────────────────────────────────

class AgentExecutionState(str, enum.Enum):
    """
    Explicit state machine states for long-running agent workflows.
    No hidden state in model context.
    """
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    EXECUTING = "EXECUTING"
    WAITING_FOR_EXTERNAL = "WAITING_FOR_EXTERNAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# ─── 4. Agent Failure Taxonomy (Section 43) ──────────────────────────────────

class AgentFailureType(str, enum.Enum):
    """Structured agent failure taxonomy. Every failure must be distinguishable."""
    PLANNING_FAILURE = "PLANNING_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"
    GROUNDING_FAILURE = "GROUNDING_FAILURE"
    POLICY_FAILURE = "POLICY_FAILURE"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    EXTERNAL_FAILURE = "EXTERNAL_FAILURE"
    TIMEOUT = "TIMEOUT"
    CUSTOMER_REJECTION = "CUSTOMER_REJECTION"
    HUMAN_REJECTION = "HUMAN_REJECTION"
    BUSINESS_OUTCOME_FAILURE = "BUSINESS_OUTCOME_FAILURE"
    TENANT_ISOLATION_VIOLATION = "TENANT_ISOLATION_VIOLATION"
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
    LOOP_PROTECTION_TRIGGERED = "LOOP_PROTECTION_TRIGGERED"
    UNKNOWN = "UNKNOWN"


# ─── 5. Bounded Agent Context (Section 10, 11) ───────────────────────────────

@dataclass
class AgentContextObject:
    """
    Bounded, freshness-aware context object passed to every agent execution.
    
    Per Phase 2 spec:
      - Context is bounded — not entire database exports
      - Every field indicates source, retrieved_at, freshness
      - Critical truth (price, availability, booking) must be revalidated before use
      - No hidden memory — all context is explicit and auditable
    """
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    lead_id: Optional[str] = None

    # Lead identity
    lead_summary: Optional[Dict[str, Any]] = None
    lead_requirements: Optional[Dict[str, Any]] = None
    recent_conversation: Optional[List[Dict[str, Any]]] = None

    # Qualification
    qualification_profile: Optional[Dict[str, Any]] = None

    # Property context
    property_shortlist: Optional[List[Dict[str, Any]]] = None

    # Commercial truth
    current_deal: Optional[Dict[str, Any]] = None
    current_tasks: Optional[List[Dict[str, Any]]] = None
    recent_actions: Optional[List[Dict[str, Any]]] = None
    recent_outcomes: Optional[List[Dict[str, Any]]] = None

    # SLA & policy
    sla_state: Optional[Dict[str, Any]] = None
    policy_summary: Optional[Dict[str, Any]] = None
    consent_state: Optional[Dict[str, Any]] = None

    # Freshness metadata
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    freshness_ttl_seconds: int = 300  # 5 minutes

    # Fields requiring revalidation before consequential actions
    stale_fields: List[str] = field(default_factory=list)

    def is_fresh(self) -> bool:
        """Returns True if context is within freshness window."""
        age_seconds = (datetime.now(timezone.utc) - self.retrieved_at).total_seconds()
        return age_seconds <= self.freshness_ttl_seconds

    def requires_revalidation(self, field_name: str) -> bool:
        """
        Returns True if this field must be revalidated before use.
        Critical commercial truth fields always require revalidation.
        """
        always_revalidate = {"price", "availability", "booking_state", "deal_value", "inventory_status"}
        return field_name in always_revalidate or field_name in self.stale_fields


# ─── 6. Agent Plan (Section 13, 14) ──────────────────────────────────────────

@dataclass
class AgentPlanStep:
    """One step in an agent execution plan."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_index: int = 0
    description: str = ""
    action_type: Optional[Phase2ActionType] = None
    tool_name: Optional[str] = None
    tool_inputs: Dict[str, Any] = field(default_factory=dict)
    expected_output_schema: Optional[Dict[str, Any]] = None
    is_conditional: bool = False
    condition_description: Optional[str] = None
    on_success_step: Optional[str] = None
    on_failure_step: Optional[str] = None
    max_retry: int = 1


@dataclass
class AgentPlan:
    """
    Structured agent execution plan. Plans are validated before any execution.
    
    Per Section 13: Observe → Plan → Validate → Authorize → Execute → Verify
    Per Section 15: Maximum execution budgets enforced on every plan.
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_domain: AgentDomain = AgentDomain.LEAD_INTELLIGENCE
    goal: str = ""
    steps: List[AgentPlanStep] = field(default_factory=list)
    required_resources: List[str] = field(default_factory=list)
    expected_outcome: str = ""
    risk_level: Phase2RiskClass = Phase2RiskClass.LOW
    authorization_requirement: Phase2AutonomyLevel = Phase2AutonomyLevel.AUTONOMOUS_GOVERNED
    expiry: Optional[datetime] = None

    # Execution budgets (Section 15)
    max_steps: int = 10
    max_retries_per_step: int = 2
    max_external_messages: int = 1
    max_execution_seconds: int = 60
    max_tool_calls: int = 20

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self) -> bool:
        if self.expiry is None:
            return False
        return datetime.now(timezone.utc) > self.expiry


# ─── 7. Agent Execution Record (Section 41, 44) ──────────────────────────────

@dataclass
class AgentExecutionRecord:
    """
    Complete record of a single agent execution.
    Every agent execution MUST produce one of these.
    This extends Sprint 1E learning models into agent performance.
    """
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    lead_id: Optional[str] = None
    agent_domain: AgentDomain = AgentDomain.LEAD_INTELLIGENCE
    agent_version: str = "v1.0"
    goal: str = ""
    execution_state: AgentExecutionState = AgentExecutionState.CREATED
    execution_mode: Phase2ExecutionMode = Phase2ExecutionMode.SHADOW
    plan_id: Optional[str] = None

    # Inputs
    context_id: Optional[str] = None
    input_summary: Dict[str, Any] = field(default_factory=dict)

    # Tools & actions
    tools_invoked: List[Dict[str, Any]] = field(default_factory=list)
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    policy_decisions: List[Dict[str, Any]] = field(default_factory=list)

    # Outcomes
    result_summary: Optional[str] = None
    confidence: AgentConfidence = AgentConfidence.UNKNOWN
    human_intervention_required: bool = False
    human_intervention_reason: Optional[str] = None
    business_effect: Optional[str] = None
    revenue_effect: Optional[str] = None

    # Failure
    failure_type: Optional[AgentFailureType] = None
    failure_message: Optional[str] = None

    # Telemetry (Section 44, 69)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    total_tool_calls: int = 0
    total_ai_calls: int = 0
    estimated_cost_usd: float = 0.0

    # Tracing
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_execution_id: Optional[str] = None

    def mark_complete(self, result_summary: str, confidence: AgentConfidence) -> None:
        self.execution_state = AgentExecutionState.COMPLETED
        self.result_summary = result_summary
        self.confidence = confidence
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)

    def mark_failed(self, failure_type: AgentFailureType, message: str) -> None:
        self.execution_state = AgentExecutionState.FAILED
        self.failure_type = failure_type
        self.failure_message = message
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "agent_domain": self.agent_domain.value,
            "agent_version": self.agent_version,
            "goal": self.goal,
            "execution_state": self.execution_state.value,
            "execution_mode": self.execution_mode.value,
            "confidence": self.confidence.value,
            "human_intervention_required": self.human_intervention_required,
            "business_effect": self.business_effect,
            "revenue_effect": self.revenue_effect,
            "failure_type": self.failure_type.value if self.failure_type else None,
            "failure_message": self.failure_message,
            "duration_ms": self.duration_ms,
            "total_tool_calls": self.total_tool_calls,
            "estimated_cost_usd": self.estimated_cost_usd,
            "trace_id": self.trace_id,
        }


# ─── 8. Abstract Agent Contract (Section 7) ──────────────────────────────────

class Phase2AgentContract(abc.ABC):
    """
    Abstract base class enforcing the Phase 2 agent interface contract.
    Every bounded domain agent MUST implement this interface.

    CONTRACT:
      - Agent has explicit agent_id, domain, version, purpose.
      - Agent declares allowed_tools and allowed_actions.
      - Agent declares forbidden_actions — these are blocked at this layer.
      - Agent may NOT access the database directly.
        Flow: Agent → Tool → Domain Service → Database
      - Agent produces AgentExecutionRecord on every invocation.
      - Agent evaluates Phase2PolicyDecision before any external action.
      - Agent supports dry_run mode for simulation (shadow/shadow_observe).
    """

    @property
    @abc.abstractmethod
    def agent_id(self) -> str:
        """Unique agent identifier."""

    @property
    @abc.abstractmethod
    def domain(self) -> AgentDomain:
        """Agent domain classification."""

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Agent version string."""

    @property
    @abc.abstractmethod
    def purpose(self) -> str:
        """Plain-language description of agent purpose."""

    @property
    @abc.abstractmethod
    def allowed_tools(self) -> Set[str]:
        """Set of tool names this agent is permitted to invoke."""

    @property
    @abc.abstractmethod
    def allowed_actions(self) -> Set[Phase2ActionType]:
        """Set of Phase2ActionTypes this agent may propose or execute."""

    @property
    def forbidden_actions(self) -> Set[Phase2ActionType]:
        """
        Actions explicitly forbidden for this agent, regardless of policy.
        Override in subclasses to declare agent-specific prohibitions.
        Default: all financial/irreversible actions.
        """
        return {
            Phase2ActionType.CREATE_BOOKING,
            Phase2ActionType.CONFIRM_BOOKING,
            Phase2ActionType.PROCESS_PAYMENT,
            Phase2ActionType.CANCEL_BOOKING,
            Phase2ActionType.ISSUE_REFUND,
        }

    def is_action_permitted_for_agent(self, action_type: Phase2ActionType) -> Tuple[bool, str]:
        """
        Checks if this action is in the agent's allowed set and not forbidden.
        Returns (is_permitted, reason).
        """
        if action_type in self.forbidden_actions:
            return False, f"Action {action_type.value} is in agent {self.agent_id} forbidden list."
        if action_type not in self.allowed_actions:
            return False, f"Action {action_type.value} is not in agent {self.agent_id} allowed_actions."
        return True, ""

    def validate_tool_access(self, tool_name: str) -> bool:
        """Returns True if this agent is permitted to invoke the specified tool."""
        return tool_name in self.allowed_tools

    @abc.abstractmethod
    async def execute(
        self,
        context: AgentContextObject,
        execution_record: AgentExecutionRecord,
        policy_engine: RevenueActionPolicyEngine,
        dry_run: bool = False,
    ) -> AgentExecutionRecord:
        """
        Execute the agent's core reasoning + action logic.

        Args:
            context: Bounded context object — revalidate critical fields before use.
            execution_record: Mutable execution record — update as execution progresses.
            policy_engine: Revenue Action Policy Engine — evaluate every action before execution.
            dry_run: If True, simulate execution (shadow mode) — no external actions.

        Returns:
            Completed AgentExecutionRecord with full audit trail.
        """


# ─── 9. Human Handoff Contract (Section 17, 33) ──────────────────────────────

@dataclass
class HumanHandoffRequest:
    """
    Structured human handoff when the agent reaches its limits.
    Per Section 17: never just display 'AI failed.'
    """
    handoff_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    lead_id: Optional[str] = None
    agent_domain: AgentDomain = AgentDomain.LEAD_INTELLIGENCE
    execution_id: Optional[str] = None

    # Context for human
    what_happened: str = ""
    what_was_attempted: str = ""
    what_remains_unresolved: str = ""
    recommended_next_step: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    # Classification
    trigger_reason: str = ""   # uncertain_intent | high_risk_action | low_confidence | tool_failure | etc.
    urgency: str = "medium"    # low | medium | high | critical

    # Approval queue info (Section 33)
    risk_level: Phase2RiskClass = Phase2RiskClass.MEDIUM
    revenue_impact: Optional[str] = None
    expiry: Optional[datetime] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "agent_domain": self.agent_domain.value,
            "what_happened": self.what_happened,
            "what_was_attempted": self.what_was_attempted,
            "what_remains_unresolved": self.what_remains_unresolved,
            "recommended_next_step": self.recommended_next_step,
            "trigger_reason": self.trigger_reason,
            "urgency": self.urgency,
            "risk_level": self.risk_level.value,
            "revenue_impact": self.revenue_impact,
            "created_at": self.created_at.isoformat(),
        }


# ─── 10. Stop Conditions Registry (Section 74) ───────────────────────────────

CANONICAL_STOP_CONDITIONS = {
    "CUSTOMER_RESPONDED": "Customer provided a response — human takes over or follow-up paused.",
    "DEAL_CHANGED": "Deal state changed — re-evaluation required before next action.",
    "LEAD_CONVERTED": "Lead has been converted — workflow terminates.",
    "LEAD_LOST": "Lead is marked lost — workflow terminates.",
    "CUSTOMER_OPTED_OUT": "Customer opted out of communications — immediate halt.",
    "MAX_ATTEMPTS_REACHED": "Maximum follow-up attempts reached — escalate to human.",
    "POLICY_EXPIRED": "Automation policy has expired — re-authorization required.",
    "HUMAN_TAKEOVER": "Human agent has taken over the conversation.",
    "AGENT_INCIDENT": "Agent detected an anomaly requiring human review.",
    "KILL_SWITCH_ACTIVATED": "Global or tenant kill switch activated — all automation halted.",
}


# ─── 11. Communication Frequency Protection (Section 75) ─────────────────────

@dataclass
class CommunicationFrequencyPolicy:
    """
    Per-tenant, per-lead communication frequency protection.
    Prevents agents from endlessly re-engaging customers.
    """
    organization_id: str
    daily_message_limit: int = 3
    weekly_message_limit: int = 10
    sequence_limit: int = 5           # Max consecutive messages without response
    cooldown_hours_after_response: int = 4
    stop_on_response: bool = True      # Pause automation when customer responds
    stop_on_opt_out: bool = True       # Immediately halt on opt-out signal
    minimum_gap_minutes: int = 60     # Minimum time between messages to same lead

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "daily_message_limit": self.daily_message_limit,
            "weekly_message_limit": self.weekly_message_limit,
            "sequence_limit": self.sequence_limit,
            "cooldown_hours_after_response": self.cooldown_hours_after_response,
            "stop_on_response": self.stop_on_response,
            "stop_on_opt_out": self.stop_on_opt_out,
            "minimum_gap_minutes": self.minimum_gap_minutes,
        }


# Avoid circular import — import Tuple after dataclass definitions
from typing import Tuple
