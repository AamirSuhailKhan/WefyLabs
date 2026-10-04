"""
Phase 2C — Durable Pilot State SQLAlchemy Models
=================================================
PostgreSQL-backed persistence for all Phase 2C pilot state.

REPLACES (as authoritative source of truth):
  - PilotLifecycleService._enrollments (in-memory)
  - PilotLifecycleService._metrics (in-memory)
  - PilotLifecycleService._audit_log (in-memory)
  - ShadowComparisonEngine._shadow_records (in-memory)
  - Phase2AgentTelemetryService._execution_records (in-memory)
  - HumanApprovalQueueService._queue (in-memory)

The in-memory structures may remain as L1 caches (per-request),
but all authoritative writes go to these tables via migration 0042.

TABLES:
  pilot_tenants              — Enrollment + stage tracking
  pilot_stage_transitions    — Immutable stage history
  pilot_observations         — Per-lead shadow observations
  pilot_metric_snapshots     — Computed metrics snapshots (periodic)
  pilot_evidence_records     — Advancement gate evidence
  pilot_audit_events         — Tamper-evident audit chain
  pilot_action_records       — ActionSemanticRecord persistence
  pilot_human_decisions      — Human-vs-agent comparison records
  pilot_approval_items       — Durable approval queue items
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON,
    Index, UniqueConstraint, ForeignKey, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _uid() -> str:
    return str(uuid.uuid4())


class PilotTenant(Base, TimestampMixin):
    """
    Authoritative enrollment record for a pilot tenant.
    Replaces PilotTenantEnrollment in-memory dataclass as production source.
    """
    __tablename__ = "pilot_tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)

    # Pilot state
    current_stage: Mapped[str] = mapped_column(String(40), nullable=False, default="STAGE_1_SHADOW")
    pilot_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, PAUSED, STOPPED, COMPLETED

    # Enrollment metadata
    enrolled_by: Mapped[str] = mapped_column(String(120), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=lambda: datetime.now(timezone.utc))
    stage_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                        default=lambda: datetime.now(timezone.utc))

    # Configuration
    configured_autonomy_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), default="phase2-v1.0", nullable=False)
    enrolled_agent_ids: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=list, nullable=False)

    # Pilot notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_pt_stage_status", "current_stage", "pilot_status"),
    )


class PilotStageTransition(Base, TimestampMixin):
    """
    Immutable record of every stage transition.
    Never updated — append-only.
    """
    __tablename__ = "pilot_stage_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    pilot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    from_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    transition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ADVANCE")  # ADVANCE, REGRESS, ENROLL
    triggered_by: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Evidence snapshot reference
    evidence_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    evidence_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_pst_pilot_at", "pilot_id", "transitioned_at"),
    )


class PilotObservation(Base, TimestampMixin):
    """
    Per-lead, per-agent shadow observation record.
    Records what the agent WOULD have done + what the human actually did.
    This is the fundamental unit of Phase 2C evidence.
    """
    __tablename__ = "pilot_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    pilot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Agent context
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_domain: Mapped[str] = mapped_column(String(60), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(40), nullable=False, default="v2c.1.0")
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Source event that triggered this observation
    source_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source_event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Agent decision (the shadow projection)
    recommended_action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recommended_action_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # HIGH, MEDIUM, LOW, UNKNOWN
    policy_decision: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # PERMITTED, BLOCKED, SHADOW_PROJECTED

    # Human decision (captured later)
    human_action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    human_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    human_actor_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    human_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Comparison result (computed after human decision captured)
    comparison_category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    # EXACT_AGREEMENT, SEMANTIC_AGREEMENT, ACCEPTABLE_DISAGREEMENT,
    # HARMFUL_DISAGREEMENT, ABSTENTION, INSUFFICIENT_EVIDENCE
    agreement_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.0-1.0
    comparison_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Business outcome linkage
    customer_response: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    outcome_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    revenue_linked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Pilot state at observation time
    pilot_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False, default="phase2-v1.0")

    # Data quality flags
    is_eligible_for_shadow_accuracy: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )  # Must NEVER be true in prod — server_default enforces this at DB level

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_po_pilot_lead_agent", "pilot_id", "lead_id", "agent_domain"),
        Index("ix_po_observed_at", "pilot_id", "observed_at"),
        Index("ix_po_comparison", "pilot_id", "comparison_category", "is_eligible_for_shadow_accuracy"),
    )


class PilotMetricSnapshot(Base, TimestampMixin):
    """
    Periodic computed metric snapshots for dashboard + advancement gates.
    Metrics are calculated FROM pilot_observations — never incremented directly.
    """
    __tablename__ = "pilot_metric_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    pilot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_sample: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Formula metadata
    numerator: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    denominator: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Evidence quality
    source: Mapped[str] = mapped_column(String(60), nullable=False, default="pilot_observations")
    calculation_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v2c.1.0")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_pms_pilot_metric", "pilot_id", "metric_name", "period_start"),
        UniqueConstraint("pilot_id", "metric_name", "period_start", "calculation_version",
                         name="uq_pms_metric_period"),
    )


class PilotEvidenceRecord(Base, TimestampMixin):
    """
    Advancement gate evidence record — one row per gate per evaluation.
    Immutable once written (append-only for advancement decisions).
    """
    __tablename__ = "pilot_evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    pilot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(40), nullable=False)

    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_sample: Mapped[int] = mapped_column(Integer, nullable=False)

    # Gate result
    gate_result: Mapped[str] = mapped_column(String(20), nullable=False)
    # PASS, FAIL, INSUFFICIENT_DATA — never boolean
    blocking_reasons: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    passing_criteria: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)

    # Snapshot integrity
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v2c.1.0")
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False, default="phase2-v1.0")

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_per_pilot_stage", "pilot_id", "from_stage", "generated_at"),
    )


class PilotAuditEvent(Base, TimestampMixin):
    """
    Tamper-evident audit chain for consequential pilot actions.
    Uses linked hashes for append-only integrity verification.
    """
    __tablename__ = "pilot_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    pilot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # ENROLLED, STAGE_ADVANCED, STAGE_REGRESSED, OBSERVATION_RECORDED,
    # APPROVAL_SUBMITTED, APPROVAL_GRANTED, APPROVAL_DENIED, KILL_SWITCH_ACTIVATED,
    # INCIDENT_DETECTED, INCIDENT_RESOLVED, EVIDENCE_GENERATED

    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)  # SYSTEM, HUMAN, AGENT
    actor_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Payload (sanitized — no PII beyond lead_id reference)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Linked hash chain
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_pae_pilot_seq", "pilot_id", "sequence_number"),
        Index("ix_pae_event_type", "pilot_id", "event_type", "occurred_at"),
        UniqueConstraint("pilot_id", "sequence_number", name="uq_pae_pilot_seq"),
    )


class PilotActionRecord(Base, TimestampMixin):
    """
    Durable persistence of ActionSemanticRecord from phase2c_tool_contracts.
    Every agent tool dispatch attempt is persisted here.
    """
    __tablename__ = "pilot_action_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    pilot_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("pilot_tenants.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Correlation
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Agent identity
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(40), nullable=False)

    # Action
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(40), nullable=False)
    action_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Semantic state (final)
    semantic_state: Mapped[str] = mapped_column(String(40), nullable=False)
    state_history: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False, default=list)

    # Pilot context
    pilot_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)

    # Provider result
    provider_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    provider_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    provider_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Block reason (when blocked)
    block_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_par_org_action_state", "organization_id", "action_type", "semantic_state"),
        Index("ix_par_execution", "execution_id"),
        Index("ix_par_completed", "completed_at"),
    )


class PilotHumanDecision(Base, TimestampMixin):
    """
    Explicit human decision record — NOT inferred from any automated signal.
    Human operators record their actual decisions here against shadow observations.
    """
    __tablename__ = "pilot_human_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    observation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_observations.id", ondelete="CASCADE"),
        nullable=False, index=True, unique=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Who decided
    human_actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    human_actor_role: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # What they decided
    decision_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # ACCEPT, REJECT, MODIFY, IGNORE, CHOOSE_ALTERNATIVE
    action_taken: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modified_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_phd_org_decided", "organization_id", "decided_at"),
    )


class PilotApprovalItem(Base, TimestampMixin):
    """
    Durable approval queue item — replaces HumanApprovalQueueService in-memory dict.
    Every approval state transition is persisted. Approval survives process restart.
    """
    __tablename__ = "pilot_approval_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    approval_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    pilot_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("pilot_tenants.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # What needs approval
    agent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_domain: Mapped[str] = mapped_column(String(60), nullable=False)
    execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(40), nullable=False)
    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Evidence for reviewer
    lead_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Integrity
    resource_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False, default="phase2-v1.0")
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")

    # Lifecycle
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Resolution
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hash_matched_at_review: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    __table_args__ = (
        Index("ix_pai_org_status", "organization_id", "approval_status"),
        Index("ix_pai_expires", "approval_status", "expires_at"),
    )
