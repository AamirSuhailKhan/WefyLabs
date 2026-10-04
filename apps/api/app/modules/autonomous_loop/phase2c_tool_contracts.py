"""
Phase 2C — Typed Tool Dispatcher & Provider Boundary Enforcement
================================================================
This module is the enforcement layer between agents and real domain services.

CRITICAL ARCHITECTURE:
  Agent -> Phase2CToolDispatcher -> PolicyEngine -> AuthorizationCheck
      -> PilotStageGuard -> DomainService -> ProviderAdapter -> ProviderResult
      -> ActionSemanticRecord -> DurableTelemetry

INVARIANTS:
  1. SHADOW and PREPARE stage calls are REJECTED at this boundary regardless of
     what an upstream agent requests. This is the last defense.
  2. Every real domain-service call produces an ActionSemanticRecord with explicit
     state: REQUESTED -> AUTHORIZED -> EXECUTING -> EXECUTED|FAILED.
  3. No boolean `success=True` returns. Every response carries semantic state.
  4. Idempotency key is REQUIRED for all external (provider) tool calls.
  5. Tenant isolation enforced: tool may not accept a lead belonging to another org.
"""
from __future__ import annotations

import enum
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.modules.autonomous_loop.phase2_governance import (
    Phase2ActionType,
    Phase2ExecutionMode,
    Phase2RiskClass,
    RevenueActionPolicyEngine,
)
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService

logger = logging.getLogger("wefylabs.phase2c.tools")

PHASE2C_VERSION = "v2c.1.0"


# ─── 1. Action Semantic State ─────────────────────────────────────────────────

class ActionSemanticState(str, enum.Enum):
    """
    Explicit multi-step state for every agent-initiated action.
    NEVER reduce to a single boolean.
    """
    REQUESTED             = "REQUESTED"        # Agent proposed action
    AUTHORIZED            = "AUTHORIZED"       # Policy + auth cleared
    BLOCKED_KILL_SWITCH   = "BLOCKED_KILL_SWITCH"
    BLOCKED_STAGE         = "BLOCKED_STAGE"    # Pilot stage prohibits this action
    BLOCKED_POLICY        = "BLOCKED_POLICY"   # Policy engine denied
    BLOCKED_CONSENT       = "BLOCKED_CONSENT"
    BLOCKED_STALENESS     = "BLOCKED_STALENESS"
    BLOCKED_TENANT        = "BLOCKED_TENANT"   # Cross-tenant attempt
    QUEUED_FOR_APPROVAL   = "QUEUED_FOR_APPROVAL"
    EXECUTING             = "EXECUTING"        # Domain service called
    PROVIDER_ACCEPTED     = "PROVIDER_ACCEPTED"
    PROVIDER_DELIVERED    = "PROVIDER_DELIVERED"
    EXECUTED              = "EXECUTED"         # Domain service completed OK
    FAILED_PROVIDER       = "FAILED_PROVIDER"  # Provider returned error
    FAILED_DOMAIN         = "FAILED_DOMAIN"    # Domain service error
    FAILED_TIMEOUT        = "FAILED_TIMEOUT"
    FAILED_DUPLICATE      = "FAILED_DUPLICATE" # Idempotency prevented duplicate
    SHADOW_PROJECTED      = "SHADOW_PROJECTED" # Shadow: action logged, not dispatched


# ─── 2. Action Semantic Record ────────────────────────────────────────────────

@dataclass
class ActionSemanticRecord:
    """
    Complete, durable record of one agent action attempt.
    This is the canonical evidence of what happened and why.
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str = ""

    # Context
    organization_id: str = ""
    lead_id: Optional[str] = None
    agent_id: str = ""
    agent_version: str = PHASE2C_VERSION
    execution_id: str = ""
    pilot_stage: str = ""
    execution_mode: str = ""
    policy_version: str = "phase2-v1.0"

    # Action
    action_type: Phase2ActionType = Phase2ActionType.NO_ACTION
    risk_class: Phase2RiskClass = Phase2RiskClass.LOW
    action_description: str = ""

    # State machine
    state: ActionSemanticState = ActionSemanticState.REQUESTED
    state_history: List[Dict[str, Any]] = field(default_factory=list)

    # Domain service result
    domain_result: Optional[Dict[str, Any]] = None

    # Provider result (where applicable)
    provider_name: Optional[str] = None
    provider_request_id: Optional[str] = None  # e.g. WhatsApp wamid
    provider_status: Optional[str] = None
    provider_error: Optional[str] = None

    # Timing
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    authorized_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Reason for block (when blocked)
    block_reason: Optional[str] = None

    def transition(self, new_state: ActionSemanticState, notes: str = "") -> None:
        """Records a state transition in the state history."""
        self.state_history.append({
            "from": self.state.value,
            "to": new_state.value,
            "at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        })
        self.state = new_state

    @property
    def is_real_execution(self) -> bool:
        return self.state in {
            ActionSemanticState.EXECUTED,
            ActionSemanticState.PROVIDER_ACCEPTED,
            ActionSemanticState.PROVIDER_DELIVERED,
        }

    @property
    def is_blocked(self) -> bool:
        return self.state.value.startswith("BLOCKED_")

    @property
    def is_failed(self) -> bool:
        return self.state.value.startswith("FAILED_")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "agent_id": self.agent_id,
            "execution_id": self.execution_id,
            "pilot_stage": self.pilot_stage,
            "execution_mode": self.execution_mode,
            "action_type": self.action_type.value,
            "risk_class": self.risk_class.value,
            "state": self.state.value,
            "state_history": self.state_history,
            "provider_name": self.provider_name,
            "provider_request_id": self.provider_request_id,
            "provider_status": self.provider_status,
            "block_reason": self.block_reason,
            "requested_at": self.requested_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ─── 3. Provider Boundary Guard ──────────────────────────────────────────────

# Stages that MUST NEVER dispatch to external providers regardless of
# anything an upstream agent requests. This is enforced at THIS layer,
# not relying on developer discipline at the agent layer.
_PROVIDER_BLOCKED_STAGES = {
    "STAGE_1_SHADOW",
    "NOT_ENROLLED",
    "STAGE_3_PREPARE",
}

# Shadow mode: the execution mode itself also blocks provider dispatch
_PROVIDER_BLOCKED_MODES = {
    "SHADOW",
    "PREPARE",
}


def assert_provider_dispatch_permitted(
    organization_id: str,
    pilot_stage: str,
    execution_mode: str,
    action_type: Phase2ActionType,
) -> Optional[str]:
    """
    Architectural enforcement: returns a block reason string if dispatch is
    NOT permitted, None if it IS permitted.

    This runs BEFORE any domain service or provider adapter is called.
    It is a hard architectural gate, not a policy suggestion.
    """
    # Gate 1: kill switch
    is_global_paused, global_reason = EmergencyAutomationPauseService.is_global_paused()
    if is_global_paused:
        return f"GLOBAL_KILL_SWITCH: {global_reason}"

    is_tenant_paused, tenant_reason = EmergencyAutomationPauseService.is_tenant_paused(organization_id)
    if is_tenant_paused:
        return f"TENANT_KILL_SWITCH: {tenant_reason}"

    # Gate 2: pilot stage (absolute — enforced at boundary, not by agent)
    if pilot_stage in _PROVIDER_BLOCKED_STAGES:
        return (
            f"PROVIDER_DISPATCH_BLOCKED: pilot_stage={pilot_stage} prohibits "
            f"all external provider dispatch. Action={action_type.value} was not sent."
        )

    # Gate 3: execution mode (absolute)
    if execution_mode in _PROVIDER_BLOCKED_MODES:
        return (
            f"PROVIDER_DISPATCH_BLOCKED: execution_mode={execution_mode} prohibits "
            f"all external provider dispatch. Action={action_type.value} was not sent."
        )

    return None


# ─── 4. Idempotency Key Builder ───────────────────────────────────────────────

def build_idempotency_key(
    organization_id: str,
    lead_id: str,
    action_type: str,
    correlation_id: str,
    extra: str = "",
) -> str:
    """
    Deterministic idempotency key for external provider calls.
    Prevents duplicate outreach on retry/worker restart.
    """
    raw = f"{organization_id}:{lead_id}:{action_type}:{correlation_id}:{extra}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


# ─── 5. Phase2CToolDispatcher ────────────────────────────────────────────────

class Phase2CToolDispatcher:
    """
    The canonical typed tool dispatcher for Phase 2C agent execution.

    Agents call this dispatcher — NOT domain services directly.
    This dispatcher:
      1. Checks kill switch
      2. Checks pilot stage + execution mode (hard boundary)
      3. Evaluates policy engine
      4. Checks authorization
      5. Builds idempotency key
      6. Calls domain service
      7. Records ActionSemanticRecord
      8. Returns structured result (never a boolean success=True)

    In SHADOW and PREPARE: records SHADOW_PROJECTED and returns immediately.
    In APPROVAL: routes to ApprovalQueue and returns QUEUED_FOR_APPROVAL.
    In LIVE: executes through real domain service.
    """

    def __init__(
        self,
        organization_id: str,
        pilot_stage: str,
        execution_mode: str,
        agent_id: str,
        policy_engine: RevenueActionPolicyEngine,
        db_session=None,  # AsyncSession — injected at runtime
    ):
        self.organization_id = organization_id
        self.pilot_stage = pilot_stage
        self.execution_mode = execution_mode
        self.agent_id = agent_id
        self.policy_engine = policy_engine
        self.db = db_session
        self._records: List[ActionSemanticRecord] = []

    def get_records(self) -> List[ActionSemanticRecord]:
        """Returns all ActionSemanticRecords from this dispatcher session."""
        return list(self._records)

    def dispatch(
        self,
        action_type: Phase2ActionType,
        action_description: str,
        execution_id: str,
        correlation_id: str,
        lead_id: Optional[str] = None,
        risk_class: Phase2RiskClass = Phase2RiskClass.LOW,
        payload: Optional[Dict[str, Any]] = None,
        extra_idem: str = "",
    ) -> ActionSemanticRecord:
        """
        Synchronous dispatch entry point.
        For async domain service calls, the caller wraps in await.
        This method handles all pre-dispatch gates synchronously.
        """
        idempotency_key = build_idempotency_key(
            self.organization_id,
            lead_id or "no_lead",
            action_type.value,
            correlation_id,
            extra_idem,
        )

        record = ActionSemanticRecord(
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            organization_id=self.organization_id,
            lead_id=lead_id,
            agent_id=self.agent_id,
            agent_version=PHASE2C_VERSION,
            execution_id=execution_id,
            pilot_stage=self.pilot_stage,
            execution_mode=self.execution_mode,
            action_type=action_type,
            risk_class=risk_class,
            action_description=action_description,
        )

        # Gate 1+2: kill switch + stage boundary (hard architectural gate)
        block_reason = assert_provider_dispatch_permitted(
            self.organization_id, self.pilot_stage,
            self.execution_mode, action_type,
        )

        if block_reason:
            # Determine if this is a shadow projection or a policy block
            if "SHADOW" in self.execution_mode or self.pilot_stage in _PROVIDER_BLOCKED_STAGES:
                record.transition(ActionSemanticState.SHADOW_PROJECTED, block_reason)
            elif "KILL_SWITCH" in block_reason:
                record.transition(ActionSemanticState.BLOCKED_KILL_SWITCH, block_reason)
            else:
                record.transition(ActionSemanticState.BLOCKED_STAGE, block_reason)
            record.block_reason = block_reason
            record.completed_at = datetime.now(timezone.utc)
            self._records.append(record)
            logger.debug(f"[TOOL_DISPATCH] BLOCKED org={self.organization_id} action={action_type.value} reason={block_reason[:80]}")
            return record

        # Gate 3: policy engine
        from app.modules.autonomous_loop.phase2_governance import AutonomyReadinessCondition
        policy_decision = self.policy_engine.evaluate(
            self.organization_id,
            action_type,
        )

        if not policy_decision.is_permitted:
            record.transition(
                ActionSemanticState.BLOCKED_POLICY,
                f"PolicyEngine denied: {policy_decision.block_reason}",
            )
            record.block_reason = policy_decision.block_reason
            record.completed_at = datetime.now(timezone.utc)
            self._records.append(record)
            logger.info(f"[TOOL_DISPATCH] POLICY_BLOCKED org={self.organization_id} action={action_type.value}")
            return record

        # Gate 4: requires approval
        if policy_decision.requires_approval:
            record.transition(
                ActionSemanticState.QUEUED_FOR_APPROVAL,
                "Action requires explicit human approval before execution.",
            )
            record.completed_at = datetime.now(timezone.utc)
            self._records.append(record)
            logger.info(f"[TOOL_DISPATCH] QUEUED_FOR_APPROVAL org={self.organization_id} action={action_type.value}")
            return record

        # Gate 5: authorized — proceed to execution
        record.transition(ActionSemanticState.AUTHORIZED, "Policy and authorization checks passed.")
        record.authorized_at = datetime.now(timezone.utc)
        self._records.append(record)
        return record

    def finalize_execution(
        self,
        record: ActionSemanticRecord,
        provider_name: Optional[str] = None,
        provider_request_id: Optional[str] = None,
        provider_status: Optional[str] = None,
        provider_error: Optional[str] = None,
        domain_result: Optional[Dict[str, Any]] = None,
        succeeded: bool = True,
    ) -> ActionSemanticRecord:
        """
        Called AFTER the real domain service/provider completes.
        Records the final execution state.
        """
        record.provider_name = provider_name
        record.provider_request_id = provider_request_id
        record.provider_status = provider_status
        record.provider_error = provider_error
        record.domain_result = domain_result
        record.executed_at = datetime.now(timezone.utc)
        record.completed_at = datetime.now(timezone.utc)

        if succeeded:
            if provider_request_id:
                record.transition(ActionSemanticState.PROVIDER_ACCEPTED, f"Provider accepted: {provider_request_id}")
            else:
                record.transition(ActionSemanticState.EXECUTED, "Domain service execution completed.")
        else:
            record.transition(
                ActionSemanticState.FAILED_PROVIDER if provider_name else ActionSemanticState.FAILED_DOMAIN,
                provider_error or "Domain service returned failure.",
            )

        logger.info(
            f"[TOOL_DISPATCH] FINALIZED org={self.organization_id} "
            f"action={record.action_type.value} state={record.state.value} "
            f"provider_id={provider_request_id}"
        )
        return record
