"""
Identity Resolution Events — Pydantic event DTOs for all identity lifecycle events.
Published via Redis Pub/Sub for downstream analytics, timeline, and AI modules.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class IdentityCreated(BaseModel):
    event_type: str = "IdentityCreated"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str
    organization_id: str
    lead_id: Optional[str] = None
    source: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    health_score: float = 0.0
    occurred_at: datetime = Field(default_factory=_now_utc)


class DuplicateDetected(BaseModel):
    event_type: str = "DuplicateDetected"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    candidate_identity_id: str
    organization_id: str
    confidence: float
    decision: str  # auto_merge | manual_review
    matched_fields: List[str] = []
    reason: Optional[str] = None
    occurred_at: datetime = Field(default_factory=_now_utc)


class MergeSuggested(BaseModel):
    event_type: str = "MergeSuggested"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    candidate_identity_id: str
    organization_id: str
    confidence: float
    review_id: str
    ai_recommendation: str
    occurred_at: datetime = Field(default_factory=_now_utc)


class MergeCompleted(BaseModel):
    event_type: str = "MergeCompleted"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    merge_operation_id: str
    source_identity_id: str
    target_identity_id: str
    organization_id: str
    merge_type: str  # auto | manual
    confidence: float
    conflicts_detected: int = 0
    fields_merged: List[str] = []
    actor_id: Optional[str] = None
    occurred_at: datetime = Field(default_factory=_now_utc)


class MergeReverted(BaseModel):
    event_type: str = "MergeReverted"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    merge_operation_id: str
    source_identity_id: str
    target_identity_id: str
    organization_id: str
    undone_by: Optional[str] = None
    occurred_at: datetime = Field(default_factory=_now_utc)


class ConflictDetected(BaseModel):
    event_type: str = "ConflictDetected"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str
    merge_operation_id: str
    organization_id: str
    conflicting_fields: List[str] = []
    occurred_at: datetime = Field(default_factory=_now_utc)


class ManualReviewCreated(BaseModel):
    event_type: str = "ManualReviewCreated"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    review_id: str
    lead_id: str
    candidate_identity_id: str
    organization_id: str
    confidence: float
    ai_recommendation: str
    occurred_at: datetime = Field(default_factory=_now_utc)


class IdentityUpdated(BaseModel):
    event_type: str = "IdentityUpdated"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str
    organization_id: str
    updated_fields: List[str] = []
    update_reason: Optional[str] = None
    occurred_at: datetime = Field(default_factory=_now_utc)
