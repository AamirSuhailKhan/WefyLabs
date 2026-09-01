"""
Knowledge API Data Transfer Objects
======================================
Pydantic v2 schemas for all Knowledge Engine API endpoints.
Follows existing BeetleLabs DTO conventions (snake_case, no ORM).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── Upload ──────────────────────────────────────────────────────────────────

class KnowledgeUploadResponse(BaseModel):
    """Response after successful document upload."""
    document_id: str
    version_id: str
    status: str
    job_id: Optional[str] = None
    message: str
    is_duplicate: bool = False


# ─── Document ─────────────────────────────────────────────────────────────────

class KnowledgeDocumentDTO(BaseModel):
    """Knowledge document summary for list and detail views."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    title: str
    description: Optional[str] = None
    file_name: Optional[str] = None
    file_size_bytes: int = 0
    mime_type: Optional[str] = None
    file_type: Optional[str] = None
    status: str
    knowledge_type: str
    language: str = "en"
    country: Optional[str] = None
    currency: Optional[str] = None
    visibility: str = "INTERNAL"
    ai_allowed: bool = True
    customer_facing_allowed: bool = False
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    total_pages: int = 0
    total_chunks: int = 0
    total_facts: int = 0
    total_conflicts: int = 0
    ocr_used: bool = False
    ocr_confidence: Optional[float] = None
    project_id: Optional[str] = None
    property_id: Optional[str] = None
    collection_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentUpdateRequest(BaseModel):
    """Update document metadata."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    knowledge_type: Optional[str] = None
    visibility: Optional[str] = None
    ai_allowed: Optional[bool] = None
    customer_facing_allowed: Optional[bool] = None
    language: Optional[str] = Field(None, min_length=2, max_length=10)
    country: Optional[str] = None
    currency: Optional[str] = None
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    project_id: Optional[str] = None
    property_id: Optional[str] = None
    collection_id: Optional[str] = None


class KnowledgeDocumentListResponse(BaseModel):
    documents: List[KnowledgeDocumentDTO]
    total: int
    page: int
    limit: int
    total_pages: int


# ─── Search ───────────────────────────────────────────────────────────────────

class KnowledgeSearchRequest(BaseModel):
    """Hybrid knowledge search request."""
    query: str = Field(..., min_length=1, max_length=2000)
    knowledge_types: Optional[List[str]] = None
    project_id: Optional[str] = None
    property_id: Optional[str] = None
    language: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=50)
    rerank_top_n: int = Field(default=5, ge=1, le=20)
    channel: str = "internal"


class KnowledgeSearchResultDTO(BaseModel):
    """A single search result."""
    chunk_id: str
    document_id: str
    text: str
    score: float
    rank_position: int
    retrieval_method: str
    metadata: Dict[str, Any] = {}


class KnowledgeSearchResponse(BaseModel):
    """Hybrid search response."""
    results: List[KnowledgeSearchResultDTO]
    query: str
    total_vector_hits: int
    total_keyword_hits: int
    total_results: int
    retrieval_latency_ms: int
    reranking_latency_ms: int


# ─── Facts ────────────────────────────────────────────────────────────────────

class KnowledgeFactDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_id: Optional[str] = None
    fact_type: str
    value_text: Optional[str] = None
    value_numeric: Optional[float] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    confidence: float
    extraction_method: str
    verification_status: str
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime


class FactVerificationRequest(BaseModel):
    decision: str = Field(..., pattern="^(VERIFIED|REJECTED)$")
    confidence_override: Optional[float] = Field(None, ge=0.0, le=1.0)
    notes: Optional[str] = None


# ─── Conflicts ────────────────────────────────────────────────────────────────

class KnowledgeConflictDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    fact_type: str
    fact_a_id: str
    fact_a_value: Optional[str] = None
    fact_a_document_id: Optional[str] = None
    fact_a_confidence: float = 0.0
    fact_b_id: str
    fact_b_value: Optional[str] = None
    fact_b_document_id: Optional[str] = None
    fact_b_confidence: float = 0.0
    project_id: Optional[str] = None
    property_id: Optional[str] = None
    resolution_status: str
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime


class ConflictResolutionRequest(BaseModel):
    winning_fact_id: str
    resolution_strategy: str = "manual"
    resolution_notes: Optional[str] = None


# ─── Collections ─────────────────────────────────────────────────────────────

class KnowledgeCollectionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    knowledge_type: Optional[str] = None
    project_id: Optional[str] = None
    language: str = "en"
    is_active: bool = True
    document_count: int = 0
    created_at: datetime


class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    knowledge_type: Optional[str] = None
    project_id: Optional[str] = None
    language: str = "en"
    visibility: str = "INTERNAL"
    ai_allowed: bool = True


# ─── Feedback ─────────────────────────────────────────────────────────────────

class KnowledgeFeedbackRequest(BaseModel):
    query_id: str
    feedback_type: str = Field(..., pattern="^(POSITIVE|NEGATIVE|HALLUCINATION|OUTDATED|INCOMPLETE|OFF_TOPIC)$")
    notes: Optional[str] = None
    document_ids_flagged: List[str] = []
    chunk_ids_flagged: List[str] = []


# ─── Freshness Policies ───────────────────────────────────────────────────────

class FreshnessPolicyDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    knowledge_type: str
    max_age_days: int
    warn_at_days: int
    auto_expire: bool
    auto_publish: bool
    is_active: bool
    created_at: datetime


class FreshnessPolicyRequest(BaseModel):
    knowledge_type: str
    max_age_days: int = Field(default=90, ge=1, le=3650)
    warn_at_days: int = Field(default=75, ge=1)
    auto_expire: bool = False
    auto_publish: bool = False


# ─── Processing Jobs ─────────────────────────────────────────────────────────

class ProcessingJobDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    job_type: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    last_error: Optional[str] = None
    result_summary: Dict[str, Any] = {}
    created_at: datetime


# ─── Chunks ───────────────────────────────────────────────────────────────────

class KnowledgeChunkDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_index: int
    chunk_type: str
    content: str
    heading: Optional[str] = None
    section: Optional[str] = None
    page_number: Optional[int] = None
    knowledge_type: str
    language: str
    token_count: int
    is_expired: bool = False
    created_at: datetime


# ─── Health ───────────────────────────────────────────────────────────────────

class KnowledgeHealthResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    total_documents: int
    published_documents: int
    indexed_chunks: int
    failed_documents: int
    open_conflicts: int
    embedding_provider: str
    vector_store_provider: str
    checked_at: datetime
