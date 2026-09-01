"""
Part 21.8 — Autonomous Sales Loop Pydantic DTOs
================================================
Strongly-typed schemas for event ingestion, orchestration results,
guard chain decisions, explainability, and broker controls.

ZERO FABRICATION POLICY:
  All fields are Optional with explicit UNKNOWN/None defaults.
  No field is invented or defaulted to false positive values.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.modules.autonomous_loop.taxonomies import (
    SalesLoopEventType,
    EventProcessingState,
    AutomationPermission,
    FailureClass,
    LeadLifecycleState,
    GuardName,
    ActorType,
)


class SalesLoopEventDTO(BaseModel):
    """Canonical input for an autonomous sales loop event."""
    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: SalesLoopEventType
    schema_version: str = "1.0"

    # Tenant & lead identity (tenant_id always from authenticated context, never from body)
    tenant_id: str
    lead_id: Optional[str] = None
    broker_id: Optional[str] = None

    # Causality
    correlation_id: str = Field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}")
    causation_id: Optional[str] = None

    # Actor
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: Optional[str] = None

    # Event content
    payload: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None

    # Idempotency
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GuardResultDTO(BaseModel):
    """Result of one guard evaluation in the guard chain."""
    guard_name: GuardName
    passed: bool
    reason: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)


class GuardChainResultDTO(BaseModel):
    """Aggregate result of running all guards in the orchestrator guard chain."""
    overall_passed: bool
    blocking_guard: Optional[GuardName] = None
    blocking_reason: Optional[str] = None
    guard_results: List[GuardResultDTO] = Field(default_factory=list)
    human_approval_required: bool = False
    scheduled_for_utc: Optional[datetime] = None
    customer_timezone: Optional[str] = None


class IntelligenceSummaryDTO(BaseModel):
    """Summary of intelligence state at the time of decision (no PII)."""
    qualification_state: str = "UNKNOWN"
    qualification_completeness: float = 0.0
    qualification_confidence: float = 0.0
    buying_signal_level: str = "UNKNOWN"
    matched_properties_count: int = 0
    has_blocking_objections: bool = False
    has_negotiation_signal: bool = False
    has_appointment_intent: bool = False
    has_opt_out_signal: bool = False


class OrchestratorResultDTO(BaseModel):
    """Result of processing one event through the autonomous orchestrator."""
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    lead_id: Optional[str] = None
    tenant_id: str
    correlation_id: str
    causation_id: Optional[str] = None

    # Outcome
    processing_state: EventProcessingState = EventProcessingState.COMPLETED
    action_type: Optional[str] = None
    automation_permission: Optional[AutomationPermission] = None

    # Guard results
    guard_chain: Optional[GuardChainResultDTO] = None

    # Intelligence summary
    intelligence: Optional[IntelligenceSummaryDTO] = None

    # Lifecycle state change
    lifecycle_state_before: Optional[LeadLifecycleState] = None
    lifecycle_state_after: Optional[LeadLifecycleState] = None

    # Execution
    provider_name: Optional[str] = None
    provider_status: Optional[str] = None
    provider_message_id: Optional[str] = None

    # Next step
    follow_up_event_type: Optional[SalesLoopEventType] = None
    follow_up_scheduled_at: Optional[datetime] = None

    # Failure
    failure_class: Optional[FailureClass] = None
    error_code: Optional[str] = None
    safe_error_message: Optional[str] = None

    # Reason
    decision_reason: str = ""
    policy_version: str = "v1.0"

    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExplainabilityDTO(BaseModel):
    """
    Human-readable structured explanation of an autonomous decision.
    Answers: 'Why did BeetleLabs do this?'

    Derived strictly from persisted audit facts — never invented.
    """
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    lead_id: str
    tenant_id: str
    event_type: str
    occurred_at: datetime

    # Causality
    correlation_id: str
    causation_id: Optional[str] = None

    # Decision context (grounded facts only)
    qualification_state: str = "UNKNOWN"
    qualification_completeness: float = 0.0
    matched_properties_count: int = 0
    buying_signal_level: str = "UNKNOWN"

    # Action taken
    action_type: Optional[str] = None
    automation_permission: Optional[str] = None

    # Guard chain results
    guard_results: List[Dict[str, Any]] = Field(default_factory=list)

    # Outcome
    provider_name: Optional[str] = None
    provider_status: Optional[str] = None

    # Rationale (safe, no raw customer message text)
    decision_reason: str = ""
    policy_version: str = "v1.0"

    # Lifecycle
    lifecycle_state_before: Optional[str] = None
    lifecycle_state_after: Optional[str] = None

    # Actor
    actor_type: str = "SYSTEM"


class BrokerControlDTO(BaseModel):
    """Broker control request for pause/resume/takeover."""
    action: str  # "pause" | "resume" | "handoff" | "approve" | "reject"
    reason: Optional[str] = None
    broker_notes: Optional[str] = None


class AutomationStateDTO(BaseModel):
    """Current automation state for a lead."""
    lead_id: str
    tenant_id: str
    is_paused: bool = False
    is_broker_takeover: bool = False
    current_lifecycle_state: str = "NEW"
    daily_action_count: int = 0
    consecutive_failures: int = 0
    pending_action_type: Optional[str] = None
    pending_since: Optional[datetime] = None
    last_event_type: Optional[str] = None
    last_event_at: Optional[datetime] = None


class DeadLetterDTO(BaseModel):
    """Dead-letter event summary for admin review."""
    id: str
    original_event_id: str
    event_type: str
    tenant_id: str
    lead_id: Optional[str] = None
    failure_class: str
    safe_error_message: str
    retry_count: int = 0
    first_failed_at: datetime
    last_failed_at: datetime
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None


class TimelineEntryDTO(BaseModel):
    """Single entry in the autonomous sales timeline for frontend rendering."""
    audit_id: str
    event_type: str
    action_type: Optional[str] = None
    automation_permission: Optional[str] = None
    lifecycle_state_before: Optional[str] = None
    lifecycle_state_after: Optional[str] = None
    guard_passed: bool = True
    blocking_guard: Optional[str] = None
    blocking_reason: Optional[str] = None
    provider_status: Optional[str] = None
    decision_reason: str = ""
    occurred_at: datetime
    actor_type: str = "SYSTEM"
