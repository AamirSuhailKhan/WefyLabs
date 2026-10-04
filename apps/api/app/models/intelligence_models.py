"""
WefyLabs Master Build 14 - Intelligence Graph, Outcome Model and Learning Loop
=============================================================================
Canonical models for the Revenue Intelligence Graph, Learning Loop, and
Competitive Moat Layer.

ABSOLUTE PRINCIPLES enforced in this module:
- Every OutcomeEvent is tenant-isolated via organization_id.
- LearningEvent is immutable and append-only (no UPDATE operations).
- Benchmark data is aggregated with minimum cohort enforcement.
- No identifiable customer data in global benchmarks.
- No causality claims - only association and sequence.
- All AI learning signals have provenance (source_event_id + signal_type).
- Model/prompt/policy versions are always referenced, never inferred.

Build on: 01-13
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)
PctType = Numeric(precision=7, scale=4)


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# Phase 1: Canonical Outcome Event Taxonomy

class OutcomeEventType(str, Enum):
    # Core Revenue Milestones (Sprint 1E Taxonomy)
    LEAD_CREATED = "LEAD_CREATED"
    LEAD_IDENTIFIED = "LEAD_IDENTIFIED"
    LEAD_CONTACTED = "LEAD_CONTACTED"
    LEAD_RESPONDED = "LEAD_RESPONDED"
    LEAD_QUALIFIED = "LEAD_QUALIFIED"
    LEAD_DISQUALIFIED = "LEAD_DISQUALIFIED"
    LEAD_REACTIVATED = "LEAD_REACTIVATED"
    LEAD_RECOVERED = "LEAD_RECOVERED"
    LEAD_CHURNED = "LEAD_CHURNED"
    
    # Property Match Outcomes
    PROPERTY_MATCHED = "PROPERTY_MATCHED"
    PROPERTY_SHARED = "PROPERTY_SHARED"
    PROPERTY_MATCH_ACCEPTED = "PROPERTY_MATCH_ACCEPTED"
    PROPERTY_MATCH_REJECTED = "PROPERTY_MATCH_REJECTED"
    PROPERTY_SHORTLISTED = "PROPERTY_SHORTLISTED"
    PROPERTY_REVISITED = "PROPERTY_REVISITED"
    PROPERTY_DISCUSSED = "PROPERTY_DISCUSSED"
    PROPERTY_VISITED = "PROPERTY_VISITED"
    PROPERTY_BOOKED = "PROPERTY_BOOKED"
    
    # Message & Follow-up Execution
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_REPLIED = "MESSAGE_REPLIED"
    MESSAGE_IGNORED = "MESSAGE_IGNORED"
    FOLLOWUP_SCHEDULED = "FOLLOWUP_SCHEDULED"
    FOLLOWUP_EXECUTED = "FOLLOWUP_EXECUTED"
    FOLLOWUP_COMPLETED = "FOLLOWUP_COMPLETED"
    FOLLOWUP_IGNORED = "FOLLOWUP_IGNORED"
    FOLLOWUP_OVERDUE = "FOLLOWUP_OVERDUE"
    
    # Appointments & Site Visits
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_NO_SHOW = "APPOINTMENT_NO_SHOW"
    SITE_VISIT_SCHEDULED = "SITE_VISIT_SCHEDULED"
    SITE_VISIT_ATTENDED = "SITE_VISIT_ATTENDED"
    SITE_VISIT_COMPLETED = "SITE_VISIT_COMPLETED"
    SITE_VISIT_NO_SHOW = "SITE_VISIT_NO_SHOW"
    SITE_VISIT_RESCHEDULED = "SITE_VISIT_RESCHEDULED"
    SITE_VISIT_CANCELLED = "SITE_VISIT_CANCELLED"
    
    # Opportunity & Offer Lifecycles
    OPPORTUNITY_CREATED = "OPPORTUNITY_CREATED"
    OPPORTUNITY_ADVANCED = "OPPORTUNITY_ADVANCED"
    OPPORTUNITY_STALLED = "OPPORTUNITY_STALLED"
    OPPORTUNITY_LOST = "OPPORTUNITY_LOST"
    OFFER_CREATED = "OFFER_CREATED"
    OFFER_NEGOTIATED = "OFFER_NEGOTIATED"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    OFFER_REJECTED = "OFFER_REJECTED"
    
    # Booking & Revenue Attainment
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_INTENT_CREATED = "BOOKING_INTENT_CREATED"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    DEAL_WON = "DEAL_WON"
    DEAL_LOST = "DEAL_LOST"
    DEAL_RECOVERED = "DEAL_RECOVERED"
    REVENUE_RECORDED = "REVENUE_RECORDED"
    REVENUE_REALIZED = "REVENUE_REALIZED"
    REFUND = "REFUND"
    CHURN = "CHURN"
    UPSELL = "UPSELL"
    DOWNSELL = "DOWNSELL"
    
    # AI Action Outcomes
    AI_ACTION_ACCEPTED = "AI_ACTION_ACCEPTED"
    AI_ACTION_REJECTED = "AI_ACTION_REJECTED"
    AI_ACTION_OVERRIDDEN = "AI_ACTION_OVERRIDDEN"
    AI_ACTION_IGNORED = "AI_ACTION_IGNORED"
    
    # Objections
    OBJECTION_RAISED = "OBJECTION_RAISED"
    OBJECTION_RESOLVED = "OBJECTION_RESOLVED"
    OBJECTION_UNRESOLVED = "OBJECTION_UNRESOLVED"


class OutcomeEntityType(str, Enum):
    LEAD = "LEAD"
    OPPORTUNITY = "OPPORTUNITY"
    PROPERTY = "PROPERTY"
    APPOINTMENT = "APPOINTMENT"
    SITE_VISIT = "SITE_VISIT"
    OFFER = "OFFER"
    BOOKING = "BOOKING"
    CONVERSATION = "CONVERSATION"
    FOLLOW_UP = "FOLLOW_UP"
    AI_ACTION = "AI_ACTION"
    MESSAGE = "MESSAGE"


class OutcomeSource(str, Enum):
    HUMAN = "HUMAN"
    AI_AGENT = "AI_AGENT"
    AUTOMATION = "AUTOMATION"
    SYSTEM = "SYSTEM"
    WEBHOOK = "WEBHOOK"
    IMPORT = "IMPORT"


class OutcomeEvent(Base):
    """
    CANONICAL OUTCOME EVENT - immutable append-only record.
    Tenant isolation: organization_id is ALWAYS required.
    INVARIANT: Records are never deleted or updated.
    """
    __tablename__ = "outcome_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(30), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_human_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overrode_ai_recommendation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    correction_of: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    property_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    channel: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    outcome_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    outcome_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    revenue_impact: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    metadata_json: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_outcome_org_type_entity", "organization_id", "event_type", "entity_id"),
        Index("ix_outcome_org_occurred", "organization_id", "occurred_at"),
        Index("ix_outcome_lead_type", "lead_id", "event_type"),
        Index("ix_outcome_org_entity_type", "organization_id", "entity_type"),
    )


# Phase 2: Learning Event Model

class LearningSignalType(str, Enum):
    HUMAN_ACCEPT = "HUMAN_ACCEPT"
    HUMAN_REJECT = "HUMAN_REJECT"
    HUMAN_EDIT = "HUMAN_EDIT"
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
    HUMAN_DISMISS = "HUMAN_DISMISS"
    HUMAN_SNOOZE = "HUMAN_SNOOZE"
    HUMAN_IGNORE = "HUMAN_IGNORE"
    RECOMMENDATION_ACCEPTED = "RECOMMENDATION_ACCEPTED"
    RECOMMENDATION_REJECTED = "RECOMMENDATION_REJECTED"
    RECOMMENDATION_EXECUTED = "RECOMMENDATION_EXECUTED"
    RECOMMENDATION_SUCCEEDED = "RECOMMENDATION_SUCCEEDED"
    RECOMMENDATION_FAILED = "RECOMMENDATION_FAILED"
    PREDICTION_CORRECT = "PREDICTION_CORRECT"
    PREDICTION_INCORRECT = "PREDICTION_INCORRECT"
    PREDICTION_CALIBRATION = "PREDICTION_CALIBRATION"
    AI_RESPONSE_HELPFUL = "AI_RESPONSE_HELPFUL"
    AI_RESPONSE_UNHELPFUL = "AI_RESPONSE_UNHELPFUL"
    AI_HALLUCINATION_DETECTED = "AI_HALLUCINATION_DETECTED"
    AI_SAFETY_VIOLATION = "AI_SAFETY_VIOLATION"
    PROPERTY_MATCH_POSITIVE = "PROPERTY_MATCH_POSITIVE"
    PROPERTY_MATCH_NEGATIVE = "PROPERTY_MATCH_NEGATIVE"
    NBA_EXECUTED = "NBA_EXECUTED"
    NBA_IGNORED = "NBA_IGNORED"
    NBA_OUTCOME_POSITIVE = "NBA_OUTCOME_POSITIVE"
    NBA_OUTCOME_NEGATIVE = "NBA_OUTCOME_NEGATIVE"
    DUPLICATE_DETECTED = "DUPLICATE_DETECTED"
    MISSING_ATTRIBUTION = "MISSING_ATTRIBUTION"
    INVALID_STAGE_TRANSITION = "INVALID_STAGE_TRANSITION"


class LearningEvent(Base):
    """
    LEARNING EVENT - immutable append-only signal record.
    MUST NOT be used as a general-purpose event log.
    source_event_id MUST point to a real OutcomeEvent or domain event.
    A user clicking helpful creates a LearningEvent.
    That signal requires evaluation before changing production behavior.
    """
    __tablename__ = "learning_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    signal_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    metadata_json: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_learning_org_signal", "organization_id", "signal_type"),
        Index("ix_learning_org_occurred", "organization_id", "occurred_at"),
        Index("ix_learning_entity", "entity_type", "entity_id"),
        Index("ix_learning_source_event", "source_event_id"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_learning_confidence_range"
        ),
    )


# Phase 3: Sales Outcome Graph

class SalesOutcomeEdge(Base):
    """
    SALES OUTCOME GRAPH EDGE - records transitions in the sales graph.
    Queryable: What happened after this recommendation?
    INVARIANT: append-only. Source truth = OutcomeEvent records.
    """
    __tablename__ = "sales_outcome_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_stage: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    to_entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    to_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    to_stage: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transition_type: Mapped[str] = mapped_column(String(60), nullable=False)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    outcome_event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    transition_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    was_successful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    revenue_realized: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_edge_org_transition", "organization_id", "transition_type"),
        Index("ix_edge_lead", "lead_id", "transition_at"),
        Index("ix_edge_from_entity", "from_entity_type", "from_entity_id"),
        Index("ix_edge_to_entity", "to_entity_type", "to_entity_id"),
    )


class HumanOverrideCategory(str, Enum):
    INCORRECT = "INCORRECT"
    NOT_TIMELY = "NOT_TIMELY"
    NOT_USEFUL = "NOT_USEFUL"
    ALREADY_HANDLED = "ALREADY_HANDLED"
    CUSTOMER_CONTEXT_MISSING = "CUSTOMER_CONTEXT_MISSING"
    WRONG_PROPERTY = "WRONG_PROPERTY"
    WRONG_CHANNEL = "WRONG_CHANNEL"
    WRONG_PRIORITY = "WRONG_PRIORITY"
    OTHER = "OTHER"


# Phase 4: AI Action Outcome Loop

class AIActionOutcome(Base):
    """
    AI ACTION OUTCOME RECORD - tracks the full lifecycle of an AI recommendation.
    INVARIANT: AI recommends. Human or Build 06 policy gates execution.
    """
    __tablename__ = "ai_action_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    ai_model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    recommended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    human_decision: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    human_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    override_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    override_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    business_result: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    revenue_attributed: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)
    outcome_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_ai_outcome_org_type", "organization_id", "recommendation_type"),
        Index("ix_ai_outcome_org_result", "organization_id", "business_result"),
        Index("ix_ai_outcome_lead", "lead_id", "recommended_at"),
        Index("ix_ai_outcome_override_cat", "organization_id", "override_category"),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_ai_confidence_range"
        ),
    )


# Phase 6: Recommendation Quality Metrics

class RecommendationQualitySnapshot(Base):
    """
    RECOMMENDATION QUALITY SNAPSHOT - periodic aggregated quality metrics.
    INVARIANT: Historical snapshots are immutable.
    CAUTION: Rates require minimum sample size before being meaningful.
    """
    __tablename__ = "recommendation_quality_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    lead_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    total_recommendations: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_size_sufficient: Mapped[bool] = mapped_column(Boolean, nullable=False)
    acceptance_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    execution_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    override_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    rejection_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    ignore_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    methodology: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "recommendation_type", "period_start", "period_end",
            "role", "channel", name="uq_rec_quality_snapshot"
        ),
        Index("ix_rec_quality_org_type", "organization_id", "recommendation_type"),
        CheckConstraint("total_recommendations >= 0", name="ck_rec_quality_sample_positive"),
    )


# Phase 10: Objection Intelligence

class ObjectionType(str, Enum):
    PRICE = "PRICE"
    LOCATION = "LOCATION"
    TRUST = "TRUST"
    TIMING = "TIMING"
    FINANCING = "FINANCING"
    AVAILABILITY = "AVAILABILITY"
    LAYOUT = "LAYOUT"
    AMENITIES = "AMENITIES"
    DEVELOPER = "DEVELOPER"
    LEGAL = "LEGAL"
    POSSESSION = "POSSESSION"
    NEGOTIATION = "NEGOTIATION"
    OTHER = "OTHER"


class ObjectionRecord(Base):
    """
    OBJECTION RECORD - structured capture of sales objections.
    Every objection requires provenance (source_conversation_id).
    NEVER infer causality from resolution rate alone.
    """
    __tablename__ = "objection_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    objection_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    objection_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_from: Mapped[str] = mapped_column(String(30), nullable=False)
    source_conversation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    extraction_model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extraction_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    resolution_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conversion_after_resolution: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_objection_org_type", "organization_id", "objection_type"),
        Index("ix_objection_org_resolved", "organization_id", "is_resolved"),
        CheckConstraint(
            "extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)",
            name="ck_objection_confidence_range"
        ),
    )


# Phase 12: Funnel Intelligence

class FunnelTransitionRecord(Base):
    """
    FUNNEL TRANSITION RECORD - canonical funnel stage transition log.
    INVARIANT: Computed from real OutcomeEvent records, never fabricated.
    """
    __tablename__ = "funnel_transition_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_stage: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    to_stage: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_stage_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transition_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    lead_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_funnel_org_stages", "organization_id", "from_stage", "to_stage"),
        Index("ix_funnel_lead", "lead_id", "transition_at"),
        Index("ix_funnel_org_channel", "organization_id", "channel"),
    )


# Phase 19: Experimentation Engine

class ExperimentStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class Experiment(Base):
    """
    EXPERIMENT - controlled experimentation definition.
    SAFETY RULE: Experiments MUST NOT automatically activate in production.
    Status DRAFT -> REVIEW -> APPROVED is required before RUNNING.
    """
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    secondary_metrics: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    population_definition: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    expected_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rollback_condition: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ExperimentStatus.DRAFT, nullable=False, index=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_experiment_status", "status"),
        CheckConstraint("expected_sample_size > 0", name="ck_experiment_sample_positive"),
    )


class ExperimentVariant(Base):
    """Variant definition within an experiment."""
    __tablename__ = "experiment_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    experiment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_control: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    traffic_allocation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("experiment_id", "name", name="uq_variant_experiment_name"),
        CheckConstraint(
            "traffic_allocation_pct > 0 AND traffic_allocation_pct <= 100",
            name="ck_variant_allocation_range"
        ),
    )


class ExperimentAssignment(Base):
    """
    EXPERIMENT ASSIGNMENT - immutable record of subject assignment to variant.
    INVARIANT: Once assigned, the assignment never changes.
    """
    __tablename__ = "experiment_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    first_exposure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("experiment_id", "subject_id", name="uq_experiment_assignment"),
        Index("ix_assignment_experiment_variant", "experiment_id", "variant_id"),
        Index("ix_assignment_org_experiment", "organization_id", "experiment_id"),
    )


class ExperimentConversion(Base):
    """Records a conversion event for an experiment subject."""
    __tablename__ = "experiment_conversions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assignment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    outcome_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    converted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_conversion_experiment_variant", "experiment_id", "variant_id"),
        Index("ix_conversion_org", "organization_id", "converted_at"),
    )


# Phase 22-25: Benchmarking Engine

class BenchmarkType(str, Enum):
    ORGANIZATION = "ORGANIZATION"
    TEAM = "TEAM"
    HISTORICAL = "HISTORICAL"
    ANONYMIZED_COHORT = "ANONYMIZED_COHORT"


class BenchmarkDefinition(Base):
    """
    BENCHMARK DEFINITION - what is being measured and how.
    PRIVACY RULE: Minimum cohort size >= 5 enforced at DB level.
    INTEGRITY RULE: Never call internally calculated metric an industry benchmark.
    """
    __tablename__ = "benchmark_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    benchmark_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    methodology: Mapped[str] = mapped_column(Text, nullable=False)
    minimum_cohort_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    external_source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    external_source_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    external_license_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint("minimum_cohort_size >= 5", name="ck_benchmark_min_cohort"),
    )


class BenchmarkSnapshot(Base):
    """
    BENCHMARK SNAPSHOT - computed benchmark value at a point in time.
    INVARIANT: Historical snapshots are immutable once created.
    PRIVACY: organization_id = NULL for anonymized cohort benchmarks.
    """
    __tablename__ = "benchmark_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_definitions.id"),
        nullable=False, index=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    value_p50: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    value_p75: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    value_p90: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    value_p95: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    confidence_interval_low: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    confidence_interval_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    actual_cohort_size: Mapped[int] = mapped_column(Integer, nullable=False)
    is_privacy_safe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_statistically_meaningful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "definition_id", "organization_id", "period_start", "period_end",
            name="uq_benchmark_snapshot"
        ),
        Index("ix_benchmark_def_period", "definition_id", "period_start"),
        CheckConstraint("actual_cohort_size >= 0", name="ck_benchmark_cohort_nonneg"),
    )


# Phase 34-35: Data Quality Engine

class DataQualityIssueType(str, Enum):
    DUPLICATE_LEAD = "DUPLICATE_LEAD"
    MISSING_IDENTITY = "MISSING_IDENTITY"
    INVALID_PROPERTY = "INVALID_PROPERTY"
    STALE_AVAILABILITY = "STALE_AVAILABILITY"
    MISSING_SOURCE_ATTRIBUTION = "MISSING_SOURCE_ATTRIBUTION"
    ORPHAN_EVENT = "ORPHAN_EVENT"
    INCONSISTENT_STAGE_TRANSITION = "INCONSISTENT_STAGE_TRANSITION"
    MISSING_OUTCOME_EVENT = "MISSING_OUTCOME_EVENT"
    INVALID_REVENUE_LINK = "INVALID_REVENUE_LINK"
    DUPLICATE_OUTCOME_EVENT = "DUPLICATE_OUTCOME_EVENT"
    MISSING_EXPERIMENT_ASSIGNMENT = "MISSING_EXPERIMENT_ASSIGNMENT"
    STALE_LEARNING_SIGNAL = "STALE_LEARNING_SIGNAL"


class DataQualityIssueStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"
    REOPENED = "REOPENED"


class DataQualityIssue(Base):
    """DATA QUALITY ISSUE - append-only record of detected data quality problems."""
    __tablename__ = "data_quality_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=DataQualityIssueStatus.OPEN, nullable=False, index=True)
    owner: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    suggested_remediation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    in_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    in_review_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    ignored_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("ix_dq_org_type", "organization_id", "issue_type"),
        Index("ix_dq_org_resolved", "organization_id", "is_resolved"),
        Index("ix_dq_org_status", "organization_id", "status"),
    )


# Phase 44: Model/Policy Registry

class RegistryEntityType(str, Enum):
    MODEL = "MODEL"
    PROMPT = "PROMPT"
    POLICY = "POLICY"
    DATASET = "DATASET"
    FEATURE = "FEATURE"
    EVALUATION = "EVALUATION"


class RegistryEntryStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    EVALUATION = "EVALUATION"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ROLLED_BACK = "ROLLED_BACK"


class PolicyRegistryEntry(Base):
    """
    MODEL/POLICY REGISTRY ENTRY - tracks versions of models, prompts, policies.
    INVARIANT: No direct production mutation without evaluation gate.
    """
    __tablename__ = "policy_registry_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RegistryEntryStatus.CANDIDATE,
                                         nullable=False, index=True)
    previous_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    rollback_of_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    artifact_uri: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    evaluation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    hallucination_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    safety_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    latency_p95_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    promoted_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deprecation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deprecation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_key", "version", name="uq_registry_entity_version"),
        Index("ix_registry_type_key", "entity_type", "entity_key"),
        Index("ix_registry_status", "status"),
    )


# Phase 46: Drift Detection

class DriftType(str, Enum):
    INPUT_DISTRIBUTION = "INPUT_DISTRIBUTION"
    LEAD_SOURCE = "LEAD_SOURCE"
    PROPERTY_INVENTORY = "PROPERTY_INVENTORY"
    CONVERSATION = "CONVERSATION"
    MODEL_QUALITY = "MODEL_QUALITY"
    CONVERSION = "CONVERSION"
    COST = "COST"


class DriftAlertRecord(Base):
    """
    DRIFT ALERT RECORD - append-only record of detected drift events.
    CAUTION: Do not automatically declare model failure from one noisy period.
    """
    __tablename__ = "drift_alert_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    drift_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(200), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    baseline_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    drift_score: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    is_significant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    baseline_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    current_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("ix_drift_type_entity", "drift_type", "entity_key"),
        Index("ix_drift_detected", "detected_at"),
    )


# Phase 26: Intelligence Snapshot

class IntelligenceSnapshot(Base):
    """
    INTELLIGENCE SNAPSHOT - periodic immutable snapshot of org intelligence metrics.
    INVARIANT: Historical snapshots are NEVER mutated.
    """
    __tablename__ = "intelligence_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    funnel_metrics: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    channel_metrics: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    ai_metrics: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    revenue_metrics: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    data_quality_metrics: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    trend_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_event_min_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_event_max_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "period_type", "period_start",
            name="uq_intel_snapshot_org_period"
        ),
        Index("ix_intel_snapshot_org_period", "organization_id", "period_start"),
    )


# Phase 39: Insight Engine

class InsightType(str, Enum):
    TREND = "TREND"
    ANOMALY = "ANOMALY"
    OPPORTUNITY = "OPPORTUNITY"
    RISK = "RISK"
    BOTTLENECK = "BOTTLENECK"
    COST = "COST"
    REVENUE = "REVENUE"
    QUALITY = "QUALITY"
    AI = "AI"
    FOLLOWUP = "FOLLOWUP"
    PROPERTY = "PROPERTY"


class InsightRecord(Base):
    """
    INSIGHT RECORD - actionable insight with explicit provenance.
    Every insight requires: source, metric, period, confidence, explanation.
    Ranking uses explicit dimensions: impact, urgency, confidence, actionability.
    No opaque AI score without explanation.
    """
    __tablename__ = "insight_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    insight_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    source_event_ids: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    impact_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    urgency_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    actionability_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_benefit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_evidence: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("ix_insight_org_type", "organization_id", "insight_type"),
        Index("ix_insight_org_generated", "organization_id", "generated_at"),
        CheckConstraint("impact_score >= 0 AND impact_score <= 10", name="ck_insight_impact"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 10",
                        name="ck_insight_confidence"),
    )


# Phase 53-54: Organization Learning Profile

class OrganizationLearningProfile(Base):
    """
    ORGANIZATION LEARNING PROFILE - tenant-scoped learning context.
    NEVER derived from other organizations data.
    NEVER contains identifiable individual customer information.
    Customer-specific learning MUST remain tenant scoped.
    """
    __tablename__ = "organization_learning_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    preferred_channels: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    response_patterns: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    property_preferences: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    sales_cadence: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    conversion_patterns: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    ai_usage_patterns: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    workflow_patterns: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    objection_patterns: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    data_coverage_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    outcome_density_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    learning_loop_maturity: Mapped[str] = mapped_column(String(20), default="INITIAL", nullable=False)
    total_outcomes_sampled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_learning_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    derived_from_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    derived_from_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_computed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


# ─── Sprint 1F: Governed Adaptive Policy Pipeline ──────────────────────────────


class PolicyAuditLog(Base):
    """
    POLICY AUDIT LOG — immutable, append-only record of every state transition
    for a PolicyRegistryEntry.

    INVARIANT: Records are NEVER updated or deleted.
    INVARIANT: Every status change on a PolicyRegistryEntry MUST create a row here.
    INVARIANT: actor_id is REQUIRED for human-driven transitions.

    Sprint 1F Gate: G-13, G-15 — Human Approval + Audit Trail
    """
    __tablename__ = "policy_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    policy_entry_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)  # HUMAN | SYSTEM | CELERY
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eval_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("ix_pol_audit_entry_at", "policy_entry_id", "occurred_at"),
        Index("ix_pol_audit_org_status", "organization_id", "to_status"),
    )


class AdaptivePolicyRollout(Base):
    """
    ADAPTIVE POLICY ROLLOUT — progressive rollout configuration for an approved
    policy.  Controls the percentage of traffic exposed to the new policy and
    the guardrails that must pass before each increment.

    INVARIANT: A rollout row is created only AFTER status=APPROVED.
    INVARIANT: traffic_pct starts at 0 and only increases via the Celery controller.
    INVARIANT: emergency_pause immediately halts the controller without changing
               the policy's status in PolicyRegistryEntry.

    Sprint 1F Gate: G-02, G-07 — Progressive Rollout + Rollback Controller
    """
    __tablename__ = "adaptive_policy_rollouts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    policy_entry_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    traffic_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_traffic_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    increment_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    increment_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    # Guardrail thresholds — rollout controller halts if metrics breach these
    min_conversion_rate_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    max_error_rate_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    min_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # Tenant filtering — None means all tenants
    tenant_allowlist: Mapped[Optional[list]] = mapped_column(JSONBType, nullable=True)
    emergency_pause: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_rolled_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_triggered_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_increment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fully_deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint("traffic_pct >= 0 AND traffic_pct <= 100", name="ck_rollout_traffic_range"),
        CheckConstraint("increment_pct > 0 AND increment_pct <= 100", name="ck_rollout_increment_positive"),
        CheckConstraint("min_sample_size >= 1", name="ck_rollout_min_sample_positive"),
        Index("ix_rollout_org_pause", "organization_id", "emergency_pause"),
    )


class PilotCohortGuard(Base):
    """
    PILOT COHORT GUARD — records the automated readiness check performed before a
    policy is allowed to transition from APPROVED → ACTIVE.

    Checks enforced by the service layer:
      - organization has >= min_lead_count leads with recorded outcomes
      - observation window is >= min_observation_days old
      - no open DataQualityIssue with severity=HIGH for the org

    INVARIANT: A cleared guard row is REQUIRED before promote_policy_entry can
               set status=ACTIVE.
    INVARIANT: is_cleared can only be set True after all checks pass.

    Sprint 1F Gate: G-08 — Pilot Cohort Guard (N≥30)
    """
    __tablename__ = "pilot_cohort_guards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    policy_entry_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    min_lead_count: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    actual_lead_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_observation_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    actual_observation_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_high_severity_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("ix_pilot_guard_policy", "policy_entry_id", "is_cleared"),
        Index("ix_pilot_guard_org", "organization_id", "checked_at"),
        CheckConstraint("actual_lead_count >= 0", name="ck_guard_lead_count_positive"),
    )


# ─── Sprint 1F: Revenue Leakage & Recovery Engine (Sections 21 & 22) ───────────


class RevenueLeakageType(str, Enum):
    UNCONTACTED_LEAD = "UNCONTACTED_LEAD"
    SLOW_RESPONSE_LEAD = "SLOW_RESPONSE_LEAD"
    UNWORKED_QUALIFIED_LEAD = "UNWORKED_QUALIFIED_LEAD"
    STALE_QUALIFIED_LEAD = "STALE_QUALIFIED_LEAD"
    UNMATCHED_DEMAND = "UNMATCHED_DEMAND"
    POOR_PROPERTY_MATCH = "POOR_PROPERTY_MATCH"
    MISSED_FOLLOWUP = "MISSED_FOLLOWUP"
    NO_SHOW = "NO_SHOW"
    ABANDONED_OFFER = "ABANDONED_OFFER"
    EXPIRED_HOLD = "EXPIRED_HOLD"
    STALLED_NEGOTIATION = "STALLED_NEGOTIATION"
    LOST_DEAL = "LOST_DEAL"
    UNATTRIBUTED_REVENUE = "UNATTRIBUTED_REVENUE"


class RevenueLeakageStatus(str, Enum):
    DETECTED = "DETECTED"
    ENGAGED = "ENGAGED"
    RECOVERED = "RECOVERED"
    EXPIRED = "EXPIRED"
    DISMISSED = "DISMISSED"


class RevenueLeakageRecord(Base):
    """
    REVENUE LEAKAGE RECORD — identifies uncaptured or stalling commercial value
    across the commercial lifecycle.

    Every leakage candidate has:
      - evidence (JSON with metrics, timestamps, reasons)
      - stage (commercial pipeline stage)
      - value (estimated leakage value in AED/currency)
      - owner (assigned agent or desk)
      - recommended intervention (actionable operational next step)
      - expiry (time limit for recovery window)
      - status (DETECTED | ENGAGED | RECOVERED | EXPIRED | DISMISSED)
      - outcome (commercial recovery result)
      - experiment_id (optional, for Section 22 recovery experiments)

    Sprint 1F Section 21 & 22
    """
    __tablename__ = "revenue_leakage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    leakage_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    deal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    property_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    estimated_leakage_value: Mapped[Decimal] = mapped_column(MoneyType, nullable=False, default=Decimal("0.0000"))
    currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
    recommended_intervention: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=RevenueLeakageStatus.DETECTED, nullable=False, index=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    recovered_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    experiment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    experiment_variant: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expiry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    engaged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    engaged_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_rev_leakage_rec_org_status", "organization_id", "status"),
        Index("ix_rev_leakage_rec_org_type", "organization_id", "leakage_type"),
        Index("ix_rev_leakage_rec_org_stage", "organization_id", "stage"),
    )
