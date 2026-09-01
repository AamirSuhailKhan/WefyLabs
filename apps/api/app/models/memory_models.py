"""
Volume 2 PART 13 — AI Memory & Customer Intelligence Engine Models
===================================================================
SQLAlchemy 2.0 models for:
1. MemoryRecord            — Master memory item (fact, preference, constraint, intent, PII)
2. MemoryVersion           — Immutable historical snapshots of superseded/updated memories
3. MemoryEvidence          — Direct evidence linkage (message ID, viewing ID, form ID, CRM note)
4. MemoryObjection         — Structured objection lifecycle (category, status, recurring count)
5. MemoryPropertyFeedback  — Structured property view/rejection logs with reason codes
6. MemoryAuditLog          — Complete audit trail of memory lifecycle actions
7. MemoryRetentionPolicy   — Configurable retention and TTL rules per memory type
8. MemoryDeletionRequest   — GDPR/CCPA deletion requests tracking vector and database purge
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

def _gen_uuid() -> str:
    return str(uuid.uuid4())


class MemoryRecord(Base, TimestampMixin):
    """
    Master memory record representing a verified fact, preference, constraint, or behavioral insight.
    Status: ACTIVE | STALE | CONTRADICTED | EXPIRED | ARCHIVED | DELETED
    Source: CUSTOMER_STATED | AGENT_CONFIRMED | CRM_VERIFIED | BEHAVIORAL_SIGNAL | AI_INFERRED | EXTERNAL_VERIFIED
    """
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    memory_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # PREFERENCE | CONSTRAINT | NEGATIVE_PREFERENCE | INTENT | LOCATION | BUDGET | TIMELINE | IDENTITY | EPISODIC | AI_DECISION
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g. "budget_max", "bedrooms", "preferred_locality"
    value_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Provenance & Confidence
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="CUSTOMER_STATED")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # message_id, viewing_id, crm_id
    confidence: Mapped[float] = mapped_column(Float, default=0.95, nullable=False)  # 0.00 to 1.00
    importance: Mapped[float] = mapped_column(Float, default=0.80, nullable=False)  # 0.00 to 1.00

    # Lifecycle & Validity
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scoping & Privacy
    is_customer_safe: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # True = safe for AI to quote to customer, False = internal agent note
    is_pii: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), default="PUBLIC_TO_ORG", nullable=False)  # PUBLIC_TO_ORG | ASSIGNED_AGENT | MANAGER_ONLY | SYSTEM_ONLY
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    versions: Mapped[List["MemoryVersion"]] = relationship(
        "MemoryVersion", back_populates="memory_record", cascade="all, delete-orphan"
    )
    evidence: Mapped[List["MemoryEvidence"]] = relationship(
        "MemoryEvidence", back_populates="memory_record", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_mem_lead_key_status", "lead_id", "key", "status"),
        Index("ix_mem_org_type", "organization_id", "memory_type"),
    )


class MemoryVersion(Base, TimestampMixin):
    """
    Immutable historical snapshot of superseded, contradicted, or updated memory records.
    """
    __tablename__ = "memory_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    memory_record_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    value_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_for_change: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    superseded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    memory_record: Mapped["MemoryRecord"] = relationship("MemoryRecord", back_populates="versions")


class MemoryEvidence(Base, TimestampMixin):
    """
    Direct ground-truth evidence linkage supporting a memory record.
    """
    __tablename__ = "memory_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    memory_record_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False, index=True)

    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CONVERSATION_MESSAGE | VIEWING_RECORD | CRM_NOTE | FORM_SUBMISSION | API_EVENT
    evidence_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # ID in underlying system
    raw_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Text quote from message
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    memory_record: Mapped["MemoryRecord"] = relationship("MemoryRecord", back_populates="evidence")


class MemoryObjection(Base, TimestampMixin):
    """
    Customer objections tracker with lifecycle progression.
    Status: OPEN | PARTIALLY_RESOLVED | RESOLVED | RECURRED | STALE
    """
    __tablename__ = "memory_objections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # PRICE | LOCATION | FINANCING | DEVELOPER | SIZE | TIMING | TRUST
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False, index=True)

    recurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MemoryPropertyFeedback(Base, TimestampMixin):
    """
    Property view, save, comparison, and structured rejection feedback.
    """
    __tablename__ = "memory_property_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    property_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False)  # VIEWED | SAVED | REJECTED | BOOKED_VIEWING | OFFERED
    rejection_reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # TOO_EXPENSIVE | WRONG_LOCATION | TOO_SMALL | WRONG_LAYOUT | POOR_PAYMENT_PLAN
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interest_score: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)


class MemoryAuditLog(Base, TimestampMixin):
    """
    Immutable audit log of all memory lifecycle events.
    """
    __tablename__ = "memory_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    memory_record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False)  # CREATED | UPDATED | CONFIRMED | CONTRADICTED | ARCHIVED | DELETED | ACCESSED
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changes_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class MemoryRetentionPolicy(Base, TimestampMixin):
    """
    Configurable retention TTL rules per memory type.
    """
    __tablename__ = "memory_retention_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ttl_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)  # e.g. Temporary context = 30 days, Preferences = 730 days
    is_auto_purge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MemoryDeletionRequest(Base, TimestampMixin):
    """
    GDPR/CCPA privacy deletion request tracking.
    """
    __tablename__ = "memory_deletion_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING | COMPLETED | FAILED
    records_deleted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
