"""
Volume 2 PART 8 — AI Follow-Up & Autonomous Lead Nurturing Engine Models
========================================================================
SQLAlchemy 2.0 models for lifecycle states, consent management, suppression rules,
adaptive sequences, quiet hours policies, grounded executions, fatigue, and Next Best Action.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

def _gen_uuid() -> str:
    return str(uuid.uuid4())


class FollowUpPolicy(Base, TimestampMixin):
    """
    Organization-level governance policy defining autonomy levels, quiet hours,
    channel allowances, and frequency limits.
    """
    __tablename__ = "follow_up_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    autonomy_level: Mapped[str] = mapped_column(String(30), default="LEVEL_3", nullable=False) # LEVEL_0 to LEVEL_5
    allowed_channels: Mapped[List[str]] = mapped_column(JSONBType, default=lambda: ["WHATSAPP", "EMAIL"], nullable=False)
    quiet_hours_start: Mapped[str] = mapped_column(String(10), default="21:00", nullable=False)
    quiet_hours_end: Mapped[str] = mapped_column(String(10), default="08:00", nullable=False)
    working_days: Mapped[List[int]] = mapped_column(JSONBType, default=lambda: [1, 2, 3, 4, 5, 6], nullable=False) # Mon-Sat
    max_messages_per_day: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_messages_per_week: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_consecutive_no_reply: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    min_hours_between_msgs: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    require_approval_high_value: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    high_value_threshold_aed: Mapped[float] = mapped_column(Float, default=5000000.0, nullable=False)

    # Part 27 — Organization Follow-Up Automation Configuration
    first_contact_sla_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    stale_lead_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    reengagement_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    escalation_delay_hours: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    manager_escalation_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    hot_lead_sla_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    working_hours_start: Mapped[str] = mapped_column(String(10), default="09:00", nullable=False)
    working_hours_end: Mapped[str] = mapped_column(String(10), default="18:00", nullable=False)
    timezone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    auto_send_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    automation_settings: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class FollowUpSequence(Base, TimestampMixin):
    """
    Reusable multi-step follow-up sequence definition for specific lifecycle states.
    """
    __tablename__ = "follow_up_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_lifecycle_state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    steps: Mapped[List["FollowUpSequenceStep"]] = relationship("FollowUpSequenceStep", back_populates="sequence", cascade="all, delete-orphan")
    enrollments: Mapped[List["FollowUpEnrollment"]] = relationship("FollowUpEnrollment", back_populates="sequence", cascade="all, delete-orphan")


class FollowUpSequenceStep(Base, TimestampMixin):
    """
    Individual step within an automated follow-up sequence.
    """
    __tablename__ = "follow_up_sequence_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    sequence_id: Mapped[str] = mapped_column(String(36), ForeignKey("follow_up_sequences.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    preferred_channel: Mapped[str] = mapped_column(String(30), default="WHATSAPP", nullable=False)
    reason_type: Mapped[str] = mapped_column(String(50), default="UNANSWERED_INQUIRY", nullable=False)
    message_goal: Mapped[str] = mapped_column(String(100), nullable=False)
    template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    require_human_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sequence: Mapped["FollowUpSequence"] = relationship("FollowUpSequence", back_populates="steps")


class FollowUpEnrollment(Base, TimestampMixin):
    """
    Tracks a lead's active enrollment inside a specific sequence.
    """
    __tablename__ = "follow_up_enrollments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence_id: Mapped[str] = mapped_column(String(36), ForeignKey("follow_up_sequences.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    current_step_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False) # ACTIVE | COMPLETED | HALTED_REPLY | CANCELLED
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sequence: Mapped["FollowUpSequence"] = relationship("FollowUpSequence", back_populates="enrollments")
    executions: Mapped[List["FollowUpExecution"]] = relationship("FollowUpExecution", back_populates="enrollment")


class FollowUpExecution(Base, TimestampMixin):
    """
    Represents a scheduled, pending, or sent outbound follow-up message record.
    """
    __tablename__ = "follow_up_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    enrollment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("follow_up_enrollments.id", ondelete="SET NULL"), nullable=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channel: Mapped[str] = mapped_column(String(30), default="WHATSAPP", nullable=False)
    reason_type: Mapped[str] = mapped_column(String(50), default="UNANSWERED_INQUIRY", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="SCHEDULED", nullable=False) # SCHEDULED | PENDING_APPROVAL | DISPATCHED | DELIVERED | READ | RESPONDED | SUPPRESSED | CANCELLED | FAILED
    scheduled_for_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recipient_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    message_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    grounded_facts: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    response_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    response_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    enrollment: Mapped[Optional["FollowUpEnrollment"]] = relationship("FollowUpEnrollment", back_populates="executions")
    decisions: Mapped[List["FollowUpDecision"]] = relationship("FollowUpDecision", back_populates="execution", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_exec_lead_status", "lead_id", "status"),
        Index("ix_exec_sched_status", "scheduled_for_utc", "status"),
    )


class FollowUpDecision(Base, TimestampMixin):
    """
    Audit log explaining why a follow-up was eligible, suppressed, or escalated.
    """
    __tablename__ = "follow_up_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    execution_id: Mapped[str] = mapped_column(String(36), ForeignKey("follow_up_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    decision_outcome: Mapped[str] = mapped_column(String(50), nullable=False) # ELIGIBLE | SUPPRESSED | ESCALATED
    fatigue_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    consecutive_no_replies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_channel_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rules_evaluated: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    execution: Mapped["FollowUpExecution"] = relationship("FollowUpExecution", back_populates="decisions")


class CommunicationConsent(Base, TimestampMixin):
    """
    Granular per-channel, per-purpose customer consent record.
    """
    __tablename__ = "communication_consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False) # WHATSAPP | SMS | EMAIL | TELEGRAM
    purpose: Mapped[str] = mapped_column(String(50), default="MARKETING_AND_FOLLOWUP", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPTED_IN", nullable=False) # OPTED_IN | OPTED_OUT | PENDING | EXPIRED
    source: Mapped[str] = mapped_column(String(50), default="WEBSITE_INQUIRY", nullable=False)
    consent_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    withdrawn_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        UniqueConstraint("lead_id", "channel", "purpose", name="uq_lead_channel_purpose"),
    )


class ContactFatigue(Base, TimestampMixin):
    """
    Maintains real-time fatigue score and consecutive unanswered message counts for a lead.
    """
    __tablename__ = "contact_fatigues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    total_messages_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_no_replies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_fatigue_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False) # 0.0 (fresh) to 1.0 (exhausted)
    is_suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suppressed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class NextBestAction(Base, TimestampMixin):
    """
    Determines and caches the highest-value next action for a lead.
    """
    __tablename__ = "next_best_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommended_action: Mapped[str] = mapped_column(String(100), nullable=False) # Call, Send WhatsApp, Schedule Viewing, Human Handoff, Wait
    action_reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False) # 0 to 100
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    expected_outcome: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_property_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class FollowUpAttribution(Base, TimestampMixin):
    """
    Attribution tracking linking follow-up messages to key downstream conversion milestones.
    """
    __tablename__ = "follow_up_attributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    milestone_type: Mapped[str] = mapped_column(String(50), nullable=False) # VIEWING_BOOKED | MEETING_HELD | DEAL_WON
    attributed_revenue_aed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    attribution_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class FollowUpRule(Base, TimestampMixin):
    """
    Organization-specific follow-up automation rule.
    Maps lifecycle triggers to deterministic CRM actions.
    """
    __tablename__ = "follow_up_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # lead_created, lead_assigned, first_contact_sla_breach, lead_no_response, followup_overdue, meeting_scheduled, meeting_missed, pipeline_stage_changed, lead_stale, lead_reengagement, manual
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False) # create_task, send_notification, escalate, create_reengagement_task, suggest_next_action, send_email
    action_config: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    conditions: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False) # low, normal, high, urgent
    max_runs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_fu_rules_org_trigger", "organization_id", "trigger", "enabled"),
    )


class FollowUpAutomationEvent(Base, TimestampMixin):
    """
    Deterministic Idempotency Ledger for follow-up automation.
    Guarantees that a periodic worker or retry cannot create duplicate tasks/notifications
    for the same lead, rule, and evaluation target window.
    """
    __tablename__ = "follow_up_automation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("follow_up_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    notification_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED", nullable=False) # PENDING | COMPLETED | SKIPPED | FAILED
    execution_details: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rule: Mapped[Optional["FollowUpRule"]] = relationship("FollowUpRule")

    __table_args__ = (
        Index("ix_fu_auto_lead_created", "lead_id", "created_at"),
        Index("ix_fu_auto_org_status", "organization_id", "status"),
    )
