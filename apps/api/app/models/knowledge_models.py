"""
Enterprise Knowledge Intelligence Platform — Database Models
=============================================================
20 production-grade SQLAlchemy 2.0 models for the BeetleLabs Knowledge Engine.

Architecture principle:
  - Vector index = retrieval layer, NOT the source of truth
  - Live price/availability → always query transactional services
  - Only PUBLISHED knowledge serves customer-facing AI
  - Every knowledge item carries full provenance
  - Tenant isolation enforced at every layer via organization_id

Model list:
  1.  KnowledgeSource
  2.  KnowledgeDocument
  3.  KnowledgeDocumentVersion
  4.  KnowledgeChunk
  5.  KnowledgeEmbedding
  6.  KnowledgeFact
  7.  KnowledgeConflict
  8.  KnowledgeVerification
  9.  KnowledgePermission
  10. KnowledgeCollection
  11. KnowledgeCollectionDocument
  12. KnowledgeIndex
  13. KnowledgeQuery
  14. KnowledgeRetrieval
  15. KnowledgeCitation
  16. KnowledgeFeedback
  17. KnowledgeEvaluation
  18. KnowledgeProvider
  19. KnowledgeProcessingJob
  20. KnowledgeDeletionJob
  21. KnowledgeFreshnessPolicy
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, BigInteger,
    Float, JSON, Index, UniqueConstraint, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# SQLite-compatible JSONB fallback
JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── 1. KnowledgeSource ───────────────────────────────────────────────────────

class KnowledgeSource(Base):
    """
    Authorized knowledge source for an organization.
    Examples: project database, approved website, document library, CRM notes.
    Every document must originate from an authorized source.
    """
    __tablename__ = "knowledge_sources"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    name = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=True)
    source_type = mapped_column(String(50), nullable=False, index=True)
    # file | structured_db | approved_website | manual | crm | api | conversation
    base_url = mapped_column(String(512), nullable=True)
    credentials_encrypted = mapped_column(Text, nullable=True)
    # Configurable source authority rank (lower = higher authority)
    priority_rank = mapped_column(Integer, default=50, nullable=False)
    is_active = mapped_column(Boolean, default=True, nullable=False)
    robots_txt_respected = mapped_column(Boolean, default=True, nullable=False)
    config = mapped_column(JSONBType, default=dict, nullable=False)
    total_documents = mapped_column(Integer, default=0, nullable=False)
    created_by = mapped_column(String(36), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_ks_org_type", "organization_id", "source_type"),
        Index("ix_ks_org_active", "organization_id", "is_active"),
    )


# ─── 2. KnowledgeDocument ─────────────────────────────────────────────────────

class KnowledgeDocument(Base):
    """
    A document ingested into the knowledge system.
    Tracks the complete document lifecycle from UPLOADED → PUBLISHED.

    Document states:
      UPLOADED → PROCESSING → PARSED → EXTRACTED → INDEXING →
      INDEXED → PUBLISHED | PENDING_REVIEW | FAILED | ARCHIVED | EXPIRED | DELETED

    Only PUBLISHED documents are served to customer-facing AI.
    """
    __tablename__ = "knowledge_documents"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    source_id = mapped_column(String(36), nullable=True, index=True)
    project_id = mapped_column(String(36), nullable=True, index=True)
    property_id = mapped_column(String(36), nullable=True, index=True)
    collection_id = mapped_column(String(36), nullable=True, index=True)
    current_version_id = mapped_column(String(36), nullable=True)

    # Identity
    title = mapped_column(String(500), nullable=False)
    description = mapped_column(Text, nullable=True)

    # File metadata
    file_name = mapped_column(String(255), nullable=True)
    file_size_bytes = mapped_column(BigInteger, default=0, nullable=False)
    mime_type = mapped_column(String(100), nullable=True)
    file_type = mapped_column(String(30), nullable=True)
    # pdf | docx | txt | csv | xlsx | html | markdown | image | structured

    # Storage
    storage_key = mapped_column(String(512), nullable=True)
    storage_provider = mapped_column(String(30), default="mock", nullable=False)
    checksum_sha256 = mapped_column(String(64), nullable=True)

    # State machine
    status = mapped_column(String(30), default="UPLOADED", nullable=False, index=True)
    # UPLOADED|PROCESSING|PARSED|EXTRACTED|INDEXING|INDEXED|
    # PUBLISHED|PENDING_REVIEW|REJECTED|FAILED|ARCHIVED|EXPIRED|DELETED

    # Knowledge classification
    knowledge_type = mapped_column(String(50), nullable=False, index=True)
    # PROPERTY|PROJECT|DEVELOPER|UNIT|PRICE|AVAILABILITY|PAYMENT_PLAN|
    # AMENITY|LOCATION|FAQ|POLICY|LEGAL|SALES_GUIDE|MARKETING|
    # CUSTOMER_PROVIDED|INTERNAL|OTHER

    # Geographic & language context
    language = mapped_column(String(10), default="en", nullable=False, index=True)
    country = mapped_column(String(10), nullable=True, index=True)
    currency = mapped_column(String(10), nullable=True)

    # Access control
    visibility = mapped_column(String(30), default="INTERNAL", nullable=False, index=True)
    # PUBLIC|CUSTOMER|INTERNAL|MANAGER_ONLY|ADMIN_ONLY
    ai_allowed = mapped_column(Boolean, default=True, nullable=False)
    customer_facing_allowed = mapped_column(Boolean, default=False, nullable=False)

    # Lifecycle dates
    effective_at = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    published_at = mapped_column(DateTime(timezone=True), nullable=True)

    # Processing metrics
    total_pages = mapped_column(Integer, default=0, nullable=False)
    total_chunks = mapped_column(Integer, default=0, nullable=False)
    total_facts = mapped_column(Integer, default=0, nullable=False)
    total_conflicts = mapped_column(Integer, default=0, nullable=False)

    # OCR
    ocr_used = mapped_column(Boolean, default=False, nullable=False)
    ocr_provider = mapped_column(String(50), nullable=True)
    ocr_confidence = mapped_column(Float, nullable=True)

    # Provenance
    source_url = mapped_column(String(512), nullable=True)
    author = mapped_column(String(200), nullable=True)
    uploaded_by = mapped_column(String(36), nullable=True)
    reviewed_by = mapped_column(String(36), nullable=True)
    reviewed_at = mapped_column(DateTime(timezone=True), nullable=True)

    processing_error = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kd_org_status", "organization_id", "status"),
        Index("ix_kd_org_type", "organization_id", "knowledge_type"),
        Index("ix_kd_org_lang", "organization_id", "language"),
        Index("ix_kd_project_status", "project_id", "status"),
        Index("ix_kd_expires", "expires_at", "status"),
    )


# ─── 3. KnowledgeDocumentVersion ──────────────────────────────────────────────

class KnowledgeDocumentVersion(Base):
    """
    Immutable version history for every document.
    Historical versions are NEVER deleted — only archived.
    Only one version can be active (is_active=True) per document.
    """
    __tablename__ = "knowledge_document_versions"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    document_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    version_number = mapped_column(Integer, nullable=False)
    checksum_sha256 = mapped_column(String(64), nullable=True)
    storage_key = mapped_column(String(512), nullable=True)
    file_size_bytes = mapped_column(BigInteger, default=0, nullable=False)
    effective_at = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    change_summary = mapped_column(Text, nullable=True)
    source_url = mapped_column(String(512), nullable=True)
    created_by = mapped_column(String(36), nullable=True)
    is_active = mapped_column(Boolean, default=False, nullable=False, index=True)
    previous_version_id = mapped_column(String(36), nullable=True)
    status = mapped_column(String(20), default="active", nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kdv_doc_version", "document_id", "version_number"),
        Index("ix_kdv_doc_active", "document_id", "is_active"),
        UniqueConstraint("document_id", "version_number", name="uq_kdv_doc_version"),
    )


# ─── 4. KnowledgeChunk ────────────────────────────────────────────────────────

class KnowledgeChunk(Base):
    """
    Semantic chunk of a parsed document.
    Unit of retrieval for vector and keyword search.
    Every chunk carries full metadata for permission, freshness, and provenance checks.
    """
    __tablename__ = "knowledge_chunks"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    document_id = mapped_column(String(36), nullable=False, index=True)
    version_id = mapped_column(String(36), nullable=True, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    project_id = mapped_column(String(36), nullable=True, index=True)
    property_id = mapped_column(String(36), nullable=True)

    # Position
    chunk_index = mapped_column(Integer, nullable=False)
    page_number = mapped_column(Integer, nullable=True)
    section = mapped_column(String(300), nullable=True)
    heading = mapped_column(String(300), nullable=True)
    subheading = mapped_column(String(300), nullable=True)

    # Type
    chunk_type = mapped_column(String(30), nullable=False, index=True)
    # paragraph|heading|table|faq|payment_plan|policy|list|property|amenity|floor_plan

    # Content
    content = mapped_column(Text, nullable=False)
    content_hash = mapped_column(String(64), nullable=True, index=True)
    token_count = mapped_column(Integer, default=0, nullable=False)
    char_count = mapped_column(Integer, default=0, nullable=False)

    # Context metadata
    language = mapped_column(String(10), default="en", nullable=False)
    country = mapped_column(String(10), nullable=True)
    currency = mapped_column(String(10), nullable=True)
    knowledge_type = mapped_column(String(50), nullable=False, index=True)
    visibility = mapped_column(String(30), default="INTERNAL", nullable=False)
    ai_allowed = mapped_column(Boolean, default=True, nullable=False)

    # Lifecycle
    effective_at = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    is_expired = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Table metadata (if chunk_type == 'table')
    table_data = mapped_column(JSONBType, default=None, nullable=True)
    # {headers: [...], rows: [[...]], caption: "...", table_index: 0}

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kc_doc_idx", "document_id", "chunk_index"),
        Index("ix_kc_org_type", "organization_id", "knowledge_type"),
        Index("ix_kc_project", "project_id"),
        Index("ix_kc_org_expired", "organization_id", "is_expired"),
        Index("ix_kc_expires", "expires_at"),
    )


# ─── 5. KnowledgeEmbedding ────────────────────────────────────────────────────

class KnowledgeEmbedding(Base):
    """
    Embedding vector metadata for a knowledge chunk.
    The actual vector is stored in this table as a JSON array (pgvector in production).

    Dedup: if chunk content hash matches, reuse existing embedding (no regeneration).
    Supports provider migration: old embeddings marked inactive, new ones generated.
    """
    __tablename__ = "knowledge_embeddings"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    chunk_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)

    # Provider metadata
    provider = mapped_column(String(50), nullable=False)
    # openai | gemini | cohere | local | mock
    model_name = mapped_column(String(100), nullable=False)
    model_version = mapped_column(String(50), nullable=True)
    embedding_dim = mapped_column(Integer, nullable=False)

    # Dedup key
    text_hash = mapped_column(String(64), nullable=False, index=True)
    token_count = mapped_column(Integer, default=0, nullable=False)
    cost_tokens = mapped_column(Integer, default=0, nullable=False)

    # Vector stored as JSON array (pgvector column added via migration in production)
    # In SQLite tests: stored as JSON. In PostgreSQL: cast to vector type.
    embedding_json = mapped_column(JSONBType, nullable=True)
    # Production: ALTER TABLE knowledge_embeddings ADD COLUMN embedding vector(1536);

    is_active = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_ke_chunk_active", "chunk_id", "is_active"),
        Index("ix_ke_org_provider", "organization_id", "provider"),
        Index("ix_ke_text_hash", "text_hash", "provider"),
    )


# ─── 6. KnowledgeFact ─────────────────────────────────────────────────────────

class KnowledgeFact(Base):
    """
    Structured fact extracted from a document.
    Remains UNVERIFIED until explicitly validated by a human reviewer
    or auto-approved by organization policy.

    CRITICAL: Never use AI-extracted facts to override verified CRM data.
    Facts are evidence, not authoritative records.
    """
    __tablename__ = "knowledge_facts"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    document_id = mapped_column(String(36), nullable=False, index=True)
    chunk_id = mapped_column(String(36), nullable=True, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    project_id = mapped_column(String(36), nullable=True, index=True)
    property_id = mapped_column(String(36), nullable=True, index=True)

    # Fact type
    fact_type = mapped_column(String(50), nullable=False, index=True)
    # PRICE|BEDROOMS|AREA|PAYMENT_PLAN|AVAILABILITY|AMENITY|LOCATION|
    # CONTACT|DATE|POLICY|LEGAL|FLOOR_PLAN|SPECIFICATION|OTHER

    # Value (one of these will be set depending on fact type)
    value_text = mapped_column(Text, nullable=True)
    value_numeric = mapped_column(Float, nullable=True)
    value_json = mapped_column(JSONBType, nullable=True)

    # Units & context
    currency = mapped_column(String(10), nullable=True)
    unit = mapped_column(String(30), nullable=True)      # sqft | sqm | AED | %
    scope = mapped_column(String(30), nullable=True)      # UNIT | FLOOR | BUILDING | PROJECT | DEVELOPER

    # Extraction provenance
    confidence = mapped_column(Float, default=0.0, nullable=False)
    extraction_method = mapped_column(String(30), default="llm", nullable=False)
    # rule | llm | regex | table_parser | ocr
    ai_model = mapped_column(String(100), nullable=True)
    source_page = mapped_column(Integer, nullable=True)
    source_text = mapped_column(Text, nullable=True)    # Original text snippet

    # Lifecycle
    effective_at = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)

    # Verification
    verification_status = mapped_column(String(20), default="UNVERIFIED", nullable=False, index=True)
    # UNVERIFIED | VERIFIED | REJECTED | EXPIRED
    verified_by = mapped_column(String(36), nullable=True)
    verified_at = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason = mapped_column(Text, nullable=True)

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kf_org_type", "organization_id", "fact_type"),
        Index("ix_kf_org_verification", "organization_id", "verification_status"),
        Index("ix_kf_project_type", "project_id", "fact_type"),
        Index("ix_kf_doc", "document_id"),
    )


# ─── 7. KnowledgeConflict ─────────────────────────────────────────────────────

class KnowledgeConflict(Base):
    """
    Two facts with conflicting values from different sources.
    System NEVER silently chooses one — conflict must be reviewed.
    Configurable resolution strategy (prefer_newest, prefer_authority, manual).
    """
    __tablename__ = "knowledge_conflicts"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    fact_type = mapped_column(String(50), nullable=False, index=True)

    # The two conflicting facts
    fact_a_id = mapped_column(String(36), nullable=False)
    fact_a_value = mapped_column(Text, nullable=True)
    fact_a_source_id = mapped_column(String(36), nullable=True)
    fact_a_document_id = mapped_column(String(36), nullable=True)
    fact_a_date = mapped_column(DateTime(timezone=True), nullable=True)
    fact_a_confidence = mapped_column(Float, default=0.0, nullable=False)

    fact_b_id = mapped_column(String(36), nullable=False)
    fact_b_value = mapped_column(Text, nullable=True)
    fact_b_source_id = mapped_column(String(36), nullable=True)
    fact_b_document_id = mapped_column(String(36), nullable=True)
    fact_b_date = mapped_column(DateTime(timezone=True), nullable=True)
    fact_b_confidence = mapped_column(Float, default=0.0, nullable=False)

    # Entity context
    project_id = mapped_column(String(36), nullable=True, index=True)
    property_id = mapped_column(String(36), nullable=True)

    # Resolution
    resolution_status = mapped_column(String(20), default="OPEN", nullable=False, index=True)
    # OPEN | RESOLVED | DISMISSED
    resolution_strategy = mapped_column(String(30), nullable=True)
    # prefer_newest | prefer_higher_authority | manual
    winning_fact_id = mapped_column(String(36), nullable=True)
    resolved_by = mapped_column(String(36), nullable=True)
    resolved_at = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes = mapped_column(Text, nullable=True)

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kcon_org_status", "organization_id", "resolution_status"),
        Index("ix_kcon_project", "project_id"),
    )


# ─── 8. KnowledgeVerification ─────────────────────────────────────────────────

class KnowledgeVerification(Base):
    """
    Human verification record for facts, documents, or chunks.
    Immutable audit of every review decision.
    """
    __tablename__ = "knowledge_verifications"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    target_type = mapped_column(String(20), nullable=False)
    # fact | document | chunk
    target_id = mapped_column(String(36), nullable=False, index=True)
    reviewer_id = mapped_column(String(36), nullable=False, index=True)
    reviewer_name = mapped_column(String(200), nullable=True)
    decision = mapped_column(String(20), nullable=False)
    # APPROVED | REJECTED | NEEDS_REVIEW
    confidence_override = mapped_column(Float, nullable=True)
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kv_org_target", "organization_id", "target_type", "target_id"),
    )


# ─── 9. KnowledgePermission ───────────────────────────────────────────────────

class KnowledgePermission(Base):
    """
    Fine-grained access control for knowledge items.
    Enforced at retrieval layer — never relying solely on LLM prompt.

    Customer-facing AI must never retrieve INTERNAL documents.
    Organization A must never retrieve Organization B knowledge.
    """
    __tablename__ = "knowledge_permissions"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    knowledge_type = mapped_column(String(50), nullable=True)
    document_id = mapped_column(String(36), nullable=True, index=True)
    collection_id = mapped_column(String(36), nullable=True, index=True)

    # Principal
    principal_type = mapped_column(String(20), nullable=False)
    # org | workspace | team | role | user
    principal_id = mapped_column(String(36), nullable=False, index=True)

    # Permissions
    visibility_level = mapped_column(String(30), default="INTERNAL", nullable=False)
    # PUBLIC | CUSTOMER | INTERNAL | MANAGER_ONLY | ADMIN_ONLY
    ai_allowed = mapped_column(Boolean, default=True, nullable=False)
    customer_facing_allowed = mapped_column(Boolean, default=False, nullable=False)
    can_edit = mapped_column(Boolean, default=False, nullable=False)
    can_delete = mapped_column(Boolean, default=False, nullable=False)
    can_publish = mapped_column(Boolean, default=False, nullable=False)

    created_by = mapped_column(String(36), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_kp_org_principal", "organization_id", "principal_type", "principal_id"),
        Index("ix_kp_document", "document_id"),
    )


# ─── 10. KnowledgeCollection ──────────────────────────────────────────────────

class KnowledgeCollection(Base):
    """
    Logical grouping of knowledge documents.
    Examples: "DLF Phase 5 Marketing", "Q1 2025 Payment Plans", "FAQ - Dubai Marina"
    """
    __tablename__ = "knowledge_collections"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    name = mapped_column(String(300), nullable=False)
    description = mapped_column(Text, nullable=True)
    knowledge_type = mapped_column(String(50), nullable=True)
    project_id = mapped_column(String(36), nullable=True, index=True)
    property_id = mapped_column(String(36), nullable=True)
    country = mapped_column(String(10), nullable=True)
    language = mapped_column(String(10), default="en", nullable=False)
    is_active = mapped_column(Boolean, default=True, nullable=False)
    visibility = mapped_column(String(30), default="INTERNAL", nullable=False)
    ai_allowed = mapped_column(Boolean, default=True, nullable=False)
    document_count = mapped_column(Integer, default=0, nullable=False)
    created_by = mapped_column(String(36), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kcol_org_active", "organization_id", "is_active"),
    )


# ─── 11. KnowledgeCollectionDocument ──────────────────────────────────────────

class KnowledgeCollectionDocument(Base):
    """Junction table: many-to-many between KnowledgeCollection and KnowledgeDocument."""
    __tablename__ = "knowledge_collection_documents"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    collection_id = mapped_column(String(36), nullable=False, index=True)
    document_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    added_by = mapped_column(String(36), nullable=True)
    added_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("collection_id", "document_id", name="uq_kcol_doc"),
    )


# ─── 12. KnowledgeIndex ───────────────────────────────────────────────────────

class KnowledgeIndex(Base):
    """
    Tracks vector + keyword index health per chunk.
    Drives incremental reindex, stale detection, and index health dashboards.
    """
    __tablename__ = "knowledge_indexes"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    chunk_id = mapped_column(String(36), nullable=False, index=True)
    document_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)

    vector_index_status = mapped_column(String(20), default="pending", nullable=False, index=True)
    # pending | indexed | failed | stale | deleted
    keyword_index_status = mapped_column(String(20), default="pending", nullable=False)
    vector_indexed_at = mapped_column(DateTime(timezone=True), nullable=True)
    keyword_indexed_at = mapped_column(DateTime(timezone=True), nullable=True)
    index_provider = mapped_column(String(30), default="pgvector", nullable=False)
    vector_index_error = mapped_column(Text, nullable=True)
    keyword_index_error = mapped_column(Text, nullable=True)
    retry_count = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("chunk_id", "index_provider", name="uq_ki_chunk_provider"),
        Index("ix_ki_org_status", "organization_id", "vector_index_status"),
        Index("ix_ki_doc", "document_id"),
    )


# ─── 13. KnowledgeQuery ───────────────────────────────────────────────────────

class KnowledgeQuery(Base):
    """
    Immutable record of every knowledge retrieval query.
    Used for: analytics, evaluation, cost tracking, debugging, and feedback correlation.
    """
    __tablename__ = "knowledge_queries"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    session_id = mapped_column(String(36), nullable=True, index=True)
    lead_id = mapped_column(String(36), nullable=True, index=True)
    agent_id = mapped_column(String(36), nullable=True)
    channel = mapped_column(String(30), nullable=True)

    # Query
    query_text = mapped_column(Text, nullable=False)
    query_language = mapped_column(String(10), default="en", nullable=False)
    intent = mapped_column(String(50), nullable=True)
    entities_extracted = mapped_column(JSONBType, default=dict, nullable=False)
    # {project, developer, property_type, bedrooms, budget, location, ...}
    filters_applied = mapped_column(JSONBType, default=dict, nullable=False)
    knowledge_types_queried = mapped_column(JSONBType, default=list, nullable=False)
    top_k = mapped_column(Integer, default=10, nullable=False)

    # Results
    vector_hits = mapped_column(Integer, default=0, nullable=False)
    keyword_hits = mapped_column(Integer, default=0, nullable=False)
    reranked_hits = mapped_column(Integer, default=0, nullable=False)
    context_chunks_used = mapped_column(Integer, default=0, nullable=False)

    # Performance
    retrieval_latency_ms = mapped_column(Integer, nullable=True)
    reranking_latency_ms = mapped_column(Integer, nullable=True)
    llm_latency_ms = mapped_column(Integer, nullable=True)
    total_latency_ms = mapped_column(Integer, nullable=True)

    # Cost
    embedding_tokens = mapped_column(Integer, default=0, nullable=False)
    context_tokens = mapped_column(Integer, default=0, nullable=False)
    llm_tokens_input = mapped_column(Integer, default=0, nullable=False)
    llm_tokens_output = mapped_column(Integer, default=0, nullable=False)

    # Quality
    answer_confidence = mapped_column(Float, nullable=True)
    grounding_passed = mapped_column(Boolean, nullable=True)
    had_citation = mapped_column(Boolean, default=False, nullable=False)
    hallucination_flagged = mapped_column(Boolean, default=False, nullable=False)

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    __table_args__ = (
        Index("ix_kq_org_created", "organization_id", "created_at"),
        Index("ix_kq_session", "session_id"),
        Index("ix_kq_lead", "lead_id"),
    )


# ─── 14. KnowledgeRetrieval ───────────────────────────────────────────────────

class KnowledgeRetrieval(Base):
    """
    Per-chunk retrieval record for a knowledge query.
    Enables per-chunk analytics: which chunks are actually useful?
    """
    __tablename__ = "knowledge_retrievals"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    query_id = mapped_column(String(36), nullable=False, index=True)
    chunk_id = mapped_column(String(36), nullable=False, index=True)
    document_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)

    retrieval_method = mapped_column(String(20), nullable=False)
    # vector | keyword | hybrid | structured
    rank_position = mapped_column(Integer, nullable=False)
    vector_score = mapped_column(Float, nullable=True)
    keyword_score = mapped_column(Float, nullable=True)
    reranker_score = mapped_column(Float, nullable=True)
    final_score = mapped_column(Float, nullable=True)

    was_used_in_context = mapped_column(Boolean, default=False, nullable=False)
    was_cited = mapped_column(Boolean, default=False, nullable=False)

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kr_query", "query_id"),
        Index("ix_kr_chunk", "chunk_id"),
    )


# ─── 15. KnowledgeCitation ────────────────────────────────────────────────────

class KnowledgeCitation(Base):
    """
    Traceable citation for every factual claim in an AI answer.
    Internal citation metadata — display text is sanitized before customer exposure.
    Never expose raw document IDs or internal paths to customers.
    """
    __tablename__ = "knowledge_citations"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    query_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    document_id = mapped_column(String(36), nullable=False, index=True)
    document_version_id = mapped_column(String(36), nullable=True)
    chunk_id = mapped_column(String(36), nullable=True)
    fact_id = mapped_column(String(36), nullable=True)

    # Location
    page_number = mapped_column(Integer, nullable=True)
    section = mapped_column(String(300), nullable=True)
    heading = mapped_column(String(300), nullable=True)

    # Display
    cited_text = mapped_column(Text, nullable=True)          # Excerpt shown as evidence
    source_display_name = mapped_column(String(300), nullable=True)  # "Project Brochure v2"
    source_url = mapped_column(String(512), nullable=True)   # Signed URL if applicable
    citation_index = mapped_column(Integer, nullable=False)  # [1], [2], [3] in answer

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kcit_query", "query_id"),
        Index("ix_kcit_doc", "document_id"),
    )


# ─── 16. KnowledgeFeedback ────────────────────────────────────────────────────

class KnowledgeFeedback(Base):
    """
    User or agent feedback on AI knowledge answers.
    Drives: evaluation datasets, reranker training, knowledge quality improvement.
    """
    __tablename__ = "knowledge_feedback"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    query_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    given_by = mapped_column(String(36), nullable=True)
    given_by_type = mapped_column(String(20), nullable=False)
    # agent | customer | system
    feedback_type = mapped_column(String(30), nullable=False, index=True)
    # helpful | not_helpful | incorrect | outdated | missing | conflict | hallucination
    notes = mapped_column(Text, nullable=True)
    document_ids_flagged = mapped_column(JSONBType, default=list, nullable=False)
    chunk_ids_flagged = mapped_column(JSONBType, default=list, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kfb_org_type", "organization_id", "feedback_type"),
        Index("ix_kfb_query", "query_id"),
    )


# ─── 17. KnowledgeEvaluation ──────────────────────────────────────────────────

class KnowledgeEvaluation(Base):
    """
    Automated evaluation results.
    Run whenever: embedding model changes, chunking changes,
    reranker changes, LLM changes, or retrieval logic changes.
    """
    __tablename__ = "knowledge_evaluations"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    eval_dataset_id = mapped_column(String(36), nullable=True)
    eval_type = mapped_column(String(50), nullable=False)
    # retrieval | grounding | citation | freshness | permission | hallucination | regression

    # Retrieval metrics
    retrieval_precision = mapped_column(Float, nullable=True)
    retrieval_recall = mapped_column(Float, nullable=True)
    mrr = mapped_column(Float, nullable=True)       # Mean Reciprocal Rank
    ndcg = mapped_column(Float, nullable=True)      # Normalized Discounted Cumulative Gain

    # Quality metrics
    groundedness_score = mapped_column(Float, nullable=True)
    citation_accuracy = mapped_column(Float, nullable=True)
    answer_relevance = mapped_column(Float, nullable=True)
    freshness_accuracy = mapped_column(Float, nullable=True)
    hallucination_rate = mapped_column(Float, nullable=True)
    permission_leakage_rate = mapped_column(Float, nullable=True)

    # System context
    embedding_model = mapped_column(String(100), nullable=True)
    chunking_version = mapped_column(String(50), nullable=True)
    reranker_version = mapped_column(String(50), nullable=True)
    llm_model = mapped_column(String(100), nullable=True)

    # Counts
    total_queries = mapped_column(Integer, default=0, nullable=False)
    passed = mapped_column(Integer, default=0, nullable=False)
    failed = mapped_column(Integer, default=0, nullable=False)
    skipped = mapped_column(Integer, default=0, nullable=False)

    run_by = mapped_column(String(36), nullable=True)
    notes = mapped_column(Text, nullable=True)
    run_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_keval_org_type", "organization_id", "eval_type"),
    )


# ─── 18. KnowledgeProvider ────────────────────────────────────────────────────

class KnowledgeProvider(Base):
    """
    Configuration for AI providers: LLM, Embedding, Reranker, OCR, Parser.
    Provider can be replaced without changing business logic.
    One default provider per (org, provider_type) pair.
    """
    __tablename__ = "knowledge_providers"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=True, index=True)
    # NULL = global default

    provider_type = mapped_column(String(30), nullable=False, index=True)
    # llm | embedding | reranker | ocr | parser
    provider_name = mapped_column(String(50), nullable=False)
    # openai | gemini | cohere | aws_textract | google_doc_ai | azure_doc | local | mock
    model_name = mapped_column(String(100), nullable=True)
    api_key_encrypted = mapped_column(Text, nullable=True)
    base_url = mapped_column(String(512), nullable=True)
    config = mapped_column(JSONBType, default=dict, nullable=False)

    is_active = mapped_column(Boolean, default=True, nullable=False)
    is_default = mapped_column(Boolean, default=False, nullable=False)
    cost_per_1k_tokens = mapped_column(Float, nullable=True)
    rate_limit_rpm = mapped_column(Integer, nullable=True)

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kprov_type", "provider_type", "is_active"),
        UniqueConstraint("organization_id", "provider_type", "provider_name",
                         name="uq_kprov_org_type_name"),
    )


# ─── 19. KnowledgeProcessingJob ───────────────────────────────────────────────

class KnowledgeProcessingJob(Base):
    """
    Background job tracking for every step of the ingestion pipeline.
    Every job: idempotent, retryable, observable, tenant-aware.
    Dead-letter after max_retries exceeded.
    """
    __tablename__ = "knowledge_processing_jobs"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    document_id = mapped_column(String(36), nullable=False, index=True)
    chunk_id = mapped_column(String(36), nullable=True, index=True)

    job_type = mapped_column(String(30), nullable=False, index=True)
    # parse | ocr | extract | chunk | embed | index | reindex | delete | evaluate

    status = mapped_column(String(20), default="pending", nullable=False, index=True)
    # pending | running | completed | failed | dead_letter

    worker_id = mapped_column(String(100), nullable=True)
    started_at = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)

    retry_count = mapped_column(Integer, default=0, nullable=False)
    max_retries = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_error = mapped_column(Text, nullable=True)

    result_summary = mapped_column(JSONBType, default=dict, nullable=False)
    idempotency_key = mapped_column(String(128), nullable=True, unique=True)
    priority = mapped_column(Integer, default=5, nullable=False)

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    __table_args__ = (
        Index("ix_kpj_org_status", "organization_id", "status"),
        Index("ix_kpj_doc_type", "document_id", "job_type"),
        Index("ix_kpj_next_attempt", "next_attempt_at", "status"),
    )


# ─── 20. KnowledgeDeletionJob ─────────────────────────────────────────────────

class KnowledgeDeletionJob(Base):
    """
    GDPR-aware document deletion tracking.
    Deletion sequence:
    1. Mark source deleted → 2. Remove vector index → 3. Remove keyword index
    → 4. Invalidate cache → 5. Emit event → 6. Preserve audit metadata

    Knowledge is recoverable from original documents if needed.
    Vector index is never the only copy.
    """
    __tablename__ = "knowledge_deletion_jobs"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    document_id = mapped_column(String(36), nullable=False, index=True)
    requested_by = mapped_column(String(36), nullable=True)
    reason = mapped_column(String(100), nullable=True)
    # admin_delete | gdpr_request | expired | superseded

    status = mapped_column(String(30), default="pending", nullable=False, index=True)
    # pending | source_marked | vector_removed | keyword_removed | cache_invalidated | completed | failed

    started_at = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_error = mapped_column(Text, nullable=True)

    # Audit metadata preserved even after deletion
    audit_metadata = mapped_column(JSONBType, default=dict, nullable=False)
    # {document_title, knowledge_type, total_chunks_deleted, total_embeddings_deleted, ...}

    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_kdel_org_status", "organization_id", "status"),
    )


# ─── 21. KnowledgeFreshnessPolicy ─────────────────────────────────────────────

class KnowledgeFreshnessPolicy(Base):
    """
    Per-organization, per-knowledge-type freshness configuration.
    Determines when documents should be considered stale or auto-expired.
    AI must not answer "current price is..." from expired price documents.
    """
    __tablename__ = "knowledge_freshness_policies"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    knowledge_type = mapped_column(String(50), nullable=False)

    max_age_days = mapped_column(Integer, default=90, nullable=False)
    warn_at_days = mapped_column(Integer, default=75, nullable=False)
    auto_expire = mapped_column(Boolean, default=False, nullable=False)
    require_re_verification_after_days = mapped_column(Integer, nullable=True)
    auto_publish = mapped_column(Boolean, default=False, nullable=False)
    applies_to_ai = mapped_column(Boolean, default=True, nullable=False)
    applies_to_customer_facing = mapped_column(Boolean, default=True, nullable=False)

    is_active = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "knowledge_type", name="uq_kfp_org_type"),
        Index("ix_kfp_org", "organization_id"),
    )
