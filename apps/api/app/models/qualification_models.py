"""
Part 21.4.1 — AI Lead Qualification Domain Foundation Models
============================================================
SQLAlchemy 2.0 models for deterministic, evidence-grounded lead qualification:
- QualificationFact: Atomic fact record with provenance, confidence, and supersession
- QualificationConflict: Explicit disagreement tracking between conflicting evidence
- QualificationRequirementPolicy: Versioned qualification criteria per country/market/type
- QualificationAuditEvent: Immutable audit trail for state transitions, overrides & facts
- QualificationSnapshotRecord: Point-in-time qualification evaluation snapshot
"""
import uuid
import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, BigInteger, Float,
    JSON, Index, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ─── Controlled Enums ─────────────────────────────────────────────────────────

class QualificationState(str, enum.Enum):
    """Deterministic lifecycle state for lead qualification."""
    NEW = "NEW"
    COLLECTING_INFORMATION = "COLLECTING_INFORMATION"
    PARTIALLY_QUALIFIED = "PARTIALLY_QUALIFIED"
    QUALIFIED = "QUALIFIED"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    NURTURE = "NURTURE"
    DISQUALIFIED = "DISQUALIFIED"


class QualificationIntent(str, enum.Enum):
    """Controlled buyer intent taxonomy."""
    BUY = "BUY"
    RENT = "RENT"
    INVEST = "INVEST"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"


class QualificationBuyerType(str, enum.Enum):
    """Controlled buyer classification."""
    END_USER = "END_USER"
    INVESTOR = "INVESTOR"
    LANDLORD = "LANDLORD"
    TENANT = "TENANT"
    COMPANY = "COMPANY"
    AGENT = "AGENT"
    UNKNOWN = "UNKNOWN"


class QualificationTimeline(str, enum.Enum):
    """Controlled transaction timeline representation."""
    IMMEDIATE = "IMMEDIATE"
    WITHIN_30_DAYS = "WITHIN_30_DAYS"
    WITHIN_3_MONTHS = "WITHIN_3_MONTHS"
    WITHIN_6_MONTHS = "WITHIN_6_MONTHS"
    WITHIN_12_MONTHS = "WITHIN_12_MONTHS"
    MORE_THAN_12_MONTHS = "MORE_THAN_12_MONTHS"
    UNKNOWN = "UNKNOWN"


class QualificationFinancing(str, enum.Enum):
    """Controlled financing method representation."""
    CASH = "CASH"
    MORTGAGE = "MORTGAGE"
    PAYMENT_PLAN = "PAYMENT_PLAN"
    UNKNOWN = "UNKNOWN"


class FactValueCategory(str, enum.Enum):
    """Epistemic category of a qualification fact."""
    FACT = "FACT"              # Explicitly confirmed by lead or verified CRM entry
    INFERENCE = "INFERENCE"    # Extracted by AI or heuristic
    UNKNOWN = "UNKNOWN"        # No reliable evidence
    CONFLICT = "CONFLICT"      # Contradictory evidence detected


class EvidenceSourceType(str, enum.Enum):
    """Explicit provenance origin of qualification evidence."""
    LEAD_FIELD = "LEAD_FIELD"
    CUSTOMER_MESSAGE = "CUSTOMER_MESSAGE"
    CRM_DATA = "CRM_DATA"
    PROSPECT_INTELLIGENCE = "PROSPECT_INTELLIGENCE"
    AI_EXTRACTION = "AI_EXTRACTION"
    HUMAN_VERIFICATION = "HUMAN_VERIFICATION"
    PROPERTY_RECOMMENDATION = "PROPERTY_RECOMMENDATION"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"


class FactStatus(str, enum.Enum):
    """Lifecycle status of an individual fact."""
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"


class ConflictStatus(str, enum.Enum):
    """Resolution status for conflicting evidence."""
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    SUPERSEDED = "SUPERSEDED"


class QualificationAuditActorType(str, enum.Enum):
    """Entity that caused a qualification action."""
    SYSTEM = "SYSTEM"
    AI = "AI"
    HUMAN = "HUMAN"


class QualificationAuditEventType(str, enum.Enum):
    """Event taxonomy for qualification audit history."""
    STATE_CHANGE = "STATE_CHANGE"
    FACT_RECORDED = "FACT_RECORDED"
    FACT_SUPERSEDED = "FACT_SUPERSEDED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
    SNAPSHOT_GENERATED = "SNAPSHOT_GENERATED"


# ─── SQLAlchemy Entities ──────────────────────────────────────────────────────

class QualificationFact(Base):
    """
    Atomic qualification evidence unit.
    Captures field value, confidence, origin, and supersession without raw PII duplication.
    """
    __tablename__ = "qualification_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    field_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    raw_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[Optional[Any]] = mapped_column(JSONBType, nullable=True)
    value_category: Mapped[str] = mapped_column(
        String(20), default=FactValueCategory.FACT.value, nullable=False
    )
    value_type: Mapped[str] = mapped_column(String(20), default="string", nullable=False)

    source_type: Mapped[str] = mapped_column(
        String(30), default=EvidenceSourceType.LEAD_FIELD.value, nullable=False, index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    extracted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evidence_text_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=FactStatus.ACTIVE.value, nullable=False, index=True
    )
    supersedes_fact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_qf_org_lead_field_status", "organization_id", "lead_id", "field_name", "status"),
        Index("ix_qf_org_lead_status", "organization_id", "lead_id", "status"),
    )


class QualificationConflict(Base):
    """
    Tracks conflicting pieces of evidence for a specific lead and qualification field.
    Prevents silent overwrites of customer statements.
    """
    __tablename__ = "qualification_conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    existing_fact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    conflicting_fact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=ConflictStatus.OPEN.value, nullable=False, index=True
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_fact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_qc_org_lead_status", "organization_id", "lead_id", "status"),
    )


class QualificationRequirementPolicy(Base):
    """
    Configurable, versioned qualification requirements per market/transaction_type.
    """
    __tablename__ = "qualification_requirement_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    policy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)

    country_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    market_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    transaction_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    required_fields: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    recommended_fields: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    optional_fields: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)

    min_completeness_for_qualified: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    min_confidence_for_qualified: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_qrp_org_version", "organization_id", "policy_version"),
    )


class QualificationAuditEvent(Base):
    """
    Immutable audit log of all qualification transitions, overrides, and fact additions.
    """
    __tablename__ = "qualification_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    actor_type: Mapped[str] = mapped_column(
        String(20), default=QualificationAuditActorType.SYSTEM.value, nullable=False
    )
    actor_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(40), default=QualificationAuditEventType.STATE_CHANGE.value, nullable=False, index=True
    )

    previous_state: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_qae_org_lead_created", "organization_id", "lead_id", "created_at"),
    )


class QualificationSnapshotRecord(Base):
    """
    Persisted evaluation snapshot separating computed state & metrics from raw evidence.
    """
    __tablename__ = "qualification_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    state: Mapped[str] = mapped_column(
        String(30), default=QualificationState.NEW.value, nullable=False, index=True
    )
    intent: Mapped[str] = mapped_column(String(20), default=QualificationIntent.UNKNOWN.value, nullable=False)
    buyer_type: Mapped[str] = mapped_column(String(20), default=QualificationBuyerType.UNKNOWN.value, nullable=False)

    budget_min: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    budget_max: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    budget_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    location: Mapped[str] = mapped_column(String(255), default="UNKNOWN", nullable=False)
    property_type: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    timeline: Mapped[str] = mapped_column(String(30), default=QualificationTimeline.UNKNOWN.value, nullable=False)
    financing: Mapped[str] = mapped_column(String(30), default=QualificationFinancing.UNKNOWN.value, nullable=False)

    completeness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    missing_fields: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    conflicting_fields: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)

    policy_version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)
    summary_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_qs_org_lead_latest", "organization_id", "lead_id", "is_latest"),
    )
