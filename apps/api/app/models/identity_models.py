"""
Volume 2 PART 3 — Enterprise Identity Resolution Engine Models
==============================================================
SQLAlchemy 2.0 models for:
1. Identity             — Permanent identity node per unique person
2. IdentityLink         — Many-to-one: Lead → Identity association
3. IdentityAlias        — Historical contact data (old phones, emails, names)
4. IdentityHistory      — Immutable timeline of identity lifecycle events
5. IdentityConflict     — Field-level conflicts pending resolution
6. DuplicateCandidate   — Pending match evaluations with similarity breakdown
7. MergeOperation       — Each merge with full pre-merge snapshot + undo support
8. MergeHistory         — Immutable audit log of all merge decisions
9. SimilarityScore      — Per-field similarity scores per candidate pair
10. ManualReview        — Manual review queue with AI explanation
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, BigInteger, Float,
    JSON, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class Identity(Base):
    """
    Permanent identity node representing a unique real-world person.
    Never deleted — only merged, split, or enriched.
    All leads from all sources (website, whatsapp, facebook, csv, etc.) resolve to one Identity.
    """
    __tablename__ = "identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Primary contact data (normalized)
    primary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    primary_phone_e164: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    primary_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_whatsapp: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    primary_telegram: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Enriched profile snapshot
    location_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    financial_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    intent_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Identity Health Score
    health_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified", nullable=False)

    # Source tracking
    first_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lead_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Merge state
    is_merged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    merged_into_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # AI behavior vector (extension point for future ML memory)
    behavior_vector: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_identity_org_health", "organization_id", "health_score"),
        Index("ix_identity_org_source", "organization_id", "first_source"),
        Index("ix_identity_phone_org", "primary_phone_e164", "organization_id"),
        Index("ix_identity_email_org", "primary_email", "organization_id"),
    )


class IdentityLink(Base):
    """
    Associates a CRM Lead with a permanent Identity node.
    One identity can have many links (one per lead source ingestion).
    """
    __tablename__ = "identity_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    link_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    link_method: Mapped[str] = mapped_column(String(30), nullable=False)  # auto_merge | manual_merge | initial_assignment | import
    matched_fields: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("lead_id", "identity_id", name="uq_lead_identity_link"),
        Index("ix_identity_link_identity", "identity_id", "is_active"),
        Index("ix_identity_link_lead", "lead_id"),
    )


class IdentityAlias(Base):
    """
    Historical contact data for an identity.
    Enables searching by past phone, email, name even after profile updates.
    """
    __tablename__ = "identity_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    alias_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # phone | email | name | whatsapp | telegram | company
    alias_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alias_value_normalized: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_alias_type_value", "alias_type", "alias_value_normalized"),
        Index("ix_alias_identity", "identity_id", "alias_type"),
    )


class IdentityHistory(Base):
    """
    Immutable chronological history of every identity lifecycle event.
    Append-only. Supports: Created, Merged, Split, Restored, Enriched, Reviewed, Edited.
    """
    __tablename__ = "identity_histories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # created | merged | split | restored | enriched | reviewed | edited | linked
    event_data: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="system", nullable=False)  # system | user

    related_identity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    related_lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_identity_history_id_created", "identity_id", "created_at"),
        Index("ix_identity_history_org_event", "organization_id", "event_type", "created_at"),
    )


class IdentityConflict(Base):
    """
    Field-level conflicts that arose during a merge.
    Stores Original, Incoming, Winner, Reason, Confidence, Reviewer.
    Never silently overwritten.
    """
    __tablename__ = "identity_conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    merge_operation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    original_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    incoming_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    winner_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    winner_source: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # original | incoming | manual

    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | resolved | deferred

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_conflict_identity_status", "identity_id", "status"),
    )


class DuplicateCandidate(Base):
    """
    A pending match evaluation between an incoming lead and an existing identity.
    Full similarity breakdown, algorithm details, and decision rationale stored.
    Explainable AI: every field shows its score, weight, and algorithm used.
    """
    __tablename__ = "duplicate_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # auto_merge | manual_review | new_identity | ignored
    decision_threshold_used: Mapped[float] = mapped_column(Float, default=0.95, nullable=False)

    # Explainability
    matched_fields: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)
    per_field_scores: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    weights_used: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    algorithms_used: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | processed | merged | ignored | review_pending
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_candidate_lead_confidence", "lead_id", "overall_confidence"),
        Index("ix_candidate_org_status", "organization_id", "status"),
    )


class MergeOperation(Base):
    """
    Records every merge attempt with full pre-merge snapshots of both records.
    Enables complete undo: restoring both identities and all their links.
    """
    __tablename__ = "merge_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    source_identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Full pre-merge snapshots for undo
    source_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    target_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    source_links_snapshot: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)

    merge_type: Mapped[str] = mapped_column(String(20), nullable=False)  # auto | manual | batch
    merge_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    conflicts_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fields_merged: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False, index=True)  # completed | undone | failed
    undone_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    undone_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_merge_op_org_status", "organization_id", "status"),
    )


class MergeHistory(Base):
    """
    Immutable audit log for every merge-related action. Append-only.
    """
    __tablename__ = "merge_histories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    merge_operation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    action: Mapped[str] = mapped_column(String(30), nullable=False)  # merge_started | merge_completed | merge_undone | conflict_created | conflict_resolved
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="system", nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_merge_history_op", "merge_operation_id", "created_at"),
    )


class SimilarityScore(Base):
    """
    Per-field similarity scores computed during a candidate evaluation.
    Provides training data for future ML model fine-tuning.
    """
    __tablename__ = "similarity_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_b: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)  # exact | jaro_winkler | levenshtein | soundex | double_metaphone | token_set | token_sort | ngram
    weighted_contribution: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_similarity_candidate_field", "candidate_id", "field_name"),
    )


class ManualReview(Base):
    """
    Manual review queue for ambiguous duplicate candidates (85–94% confidence).
    Reviewer sees old record, new record, AI explanation, similarity breakdown.
    Reviewer decisions stored as ground truth labels for future supervised ML training.
    """
    __tablename__ = "manual_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_identity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # AI Explanation
    ai_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ai_recommendation: Mapped[str] = mapped_column(String(20), nullable=False)  # merge | ignore | defer
    ai_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    similarity_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Reviewer Decision — ML ground truth label
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reviewer_decision: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # merge | ignore | defer
    reviewer_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | completed | deferred | auto_resolved
    priority: Mapped[str] = mapped_column(String(10), default="normal", nullable=False)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_review_org_status", "organization_id", "status", "created_at"),
        Index("ix_review_assigned", "assigned_to", "status"),
    )
