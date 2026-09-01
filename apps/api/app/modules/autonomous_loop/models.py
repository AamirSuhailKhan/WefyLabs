"""
Part 21.8 — AI Autonomous Sales Loop SQLAlchemy Models
=======================================================
Database models for the durable, auditable, idempotent autonomous sales loop.

Four tables added by migration 0015:
  1. sales_loop_events    — Durable event store with idempotency
  2. sales_loop_audit_entries — Explainability audit trail
  3. sales_loop_dead_letters  — Permanently failed events
  4. lead_automation_state    — Per-lead automation controls

CRITICAL: These are ADDITIVE-ONLY. No existing tables are modified.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class SalesLoopEvent(Base, TimestampMixin):
    """
    Durable, idempotent event record for the autonomous sales loop.

    Processing guarantees:
    - idempotency_key uniqueness prevents duplicate processing.
    - processing_state lifecycle: RECEIVED → PROCESSING → COMPLETED/FAILED/RETRYABLE/DEAD_LETTER
    - retry_count bounded by max_retries configuration.
    - correlation_id links all events in the same causal chain.
    - causation_id links this event to the event that caused it.
    """
    __tablename__ = "sales_loop_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)

    # Tenant & lead identity
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    broker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Causality chain
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    causation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Actor who triggered this event
    actor_type: Mapped[str] = mapped_column(String(30), default="SYSTEM", nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Event payload (stored as JSONB for auditability)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Processing lifecycle
    processing_state: Mapped[str] = mapped_column(
        String(30), default="RECEIVED", nullable=False, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_class: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # Timestamps
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Source context
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_sle_tenant_lead_type", "tenant_id", "lead_id", "event_type"),
        Index("ix_sle_state_occurred", "processing_state", "occurred_at"),
        Index("ix_sle_correlation", "correlation_id"),
    )


class SalesLoopAuditEntry(Base, TimestampMixin):
    """
    Immutable audit trail for every autonomous decision.
    Supports the 'Why did BeetleLabs do this?' explainability requirement.

    Records:
      event → state_before → intelligence_run → decision → guard_chain → action → provider_result → state_after
    """
    __tablename__ = "sales_loop_audit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    event_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sales_loop_events.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    causation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Tenant & lead
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # What happened
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    lifecycle_state_before: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lifecycle_state_after: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Intelligence summary (grounded facts only — no PII message bodies)
    qualification_completeness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    qualification_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    matched_properties_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buying_signal_level: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Decision
    action_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    automation_permission: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Guard chain results (structured)
    guard_results: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)

    # Execution result
    provider_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    provider_status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Decision rationale (safe, no PII)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Actor
    actor_type: Mapped[str] = mapped_column(String(30), default="SYSTEM", nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_slae_tenant_lead", "tenant_id", "lead_id"),
        Index("ix_slae_occurred", "occurred_at"),
    )


class SalesLoopDeadLetter(Base, TimestampMixin):
    """
    Permanently failed events that exhausted retry policy.
    Requires admin intervention for recovery.

    CRITICAL: Never stores secrets, credentials, or customer PII message bodies.
    """
    __tablename__ = "sales_loop_dead_letters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    original_event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Causality
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    causation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Failure information (no sensitive data)
    failure_class: Mapped[str] = mapped_column(String(60), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    safe_error_message: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timeline
    first_failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Admin recovery
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sldl_tenant_unresolved", "tenant_id", "is_resolved"),
    )


class LeadAutomationState(Base, TimestampMixin):
    """
    Per-lead automation controls enabling broker pause/resume/takeover.
    One row per lead (upserted on first event).
    """
    __tablename__ = "lead_automation_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Automation controls
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_broker_takeover: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pause_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Lifecycle tracking
    current_lifecycle_state: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False)
    previous_lifecycle_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    state_change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Loop protection counters
    daily_action_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_action_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    orchestration_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Last processed event (for replay protection)
    last_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Pending broker approval
    pending_action_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    pending_action_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pending_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
