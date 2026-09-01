"""
PART 7 — Enterprise Search Platform Models
==========================================
SQLAlchemy models for: SearchHistory, SavedSearch,
SearchIndexMetadata, SearchRanking.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class SearchHistory(Base):
    """
    Immutable record of every user search query.
    Drives: Recent Searches, Popular Searches, AI Personalization, Search Analytics.
    """
    __tablename__ = "search_history"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    user_id = mapped_column(String(36), nullable=False, index=True)
    query = mapped_column(String(500), nullable=False)
    entity_types = mapped_column(JSONBType, default=list, nullable=False)   # ["lead", "property", "contact"]
    filters_applied = mapped_column(JSONBType, default=dict, nullable=False)
    result_count = mapped_column(Integer, default=0, nullable=False)
    latency_ms = mapped_column(Integer, nullable=True)
    was_successful = mapped_column(Boolean, default=True, nullable=False)
    search_provider = mapped_column(String(30), default="postgresql", nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_search_history_org_user", "organization_id", "user_id"),
        Index("ix_search_history_org_created", "organization_id", "created_at"),
        Index("ix_search_history_query", "query"),
    )


class SavedSearch(Base):
    """
    User-saved filter/query configurations.
    Supports: personal saves, org-level sharing, workspace scoping.
    """
    __tablename__ = "saved_searches"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    workspace_id = mapped_column(String(36), nullable=True, index=True)
    user_id = mapped_column(String(36), nullable=False, index=True)
    name = mapped_column(String(150), nullable=False)
    description = mapped_column(Text, nullable=True)
    entity_type = mapped_column(String(30), nullable=False, index=True)     # lead | property | contact | global
    query = mapped_column(String(500), nullable=True)
    filters = mapped_column(JSONBType, default=dict, nullable=False)        # {status: "active", score: "hot"}
    sorting = mapped_column(JSONBType, default=dict, nullable=False)        # {field: "created_at", order: "desc"}
    columns = mapped_column(JSONBType, default=list, nullable=False)        # visible column config
    view_mode = mapped_column(String(20), default="list", nullable=False)   # list | kanban | grid | map
    is_shared = mapped_column(Boolean, default=False, nullable=False)
    share_scope = mapped_column(String(20), default="personal", nullable=False)  # personal | workspace | org
    is_default = mapped_column(Boolean, default=False, nullable=False)
    run_count = mapped_column(Integer, default=0, nullable=False)
    last_run_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_saved_search_org_entity", "organization_id", "entity_type"),
        Index("ix_saved_search_user", "user_id"),
    )


class SearchIndexMetadata(Base):
    """
    Tracks the indexing state of every entity in the search index.
    Drives: incremental reindex, stale detection, indexing health dashboards.
    """
    __tablename__ = "search_index_metadata"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    entity_type = mapped_column(String(30), nullable=False, index=True)     # lead | property | contact | task
    entity_id = mapped_column(String(36), nullable=False, index=True)
    index_provider = mapped_column(String(30), default="postgresql", nullable=False)
    index_status = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | indexed | failed | stale
    document_hash = mapped_column(String(64), nullable=True)               # SHA-256 of indexed document; detect staleness
    indexed_at = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count = mapped_column(Integer, default=0, nullable=False)
    error_message = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "index_provider", name="uq_search_idx_entity_provider"),
        Index("ix_search_idx_org_type_status", "organization_id", "entity_type", "index_status"),
    )


class SearchRanking(Base):
    """
    Configurable per-entity-type ranking weight table.
    Admins tune result ordering without code changes.
    """
    __tablename__ = "search_rankings"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=True, index=True)  # NULL = global default
    entity_type = mapped_column(String(30), nullable=False, index=True)
    base_weight = mapped_column(Float, default=1.0, nullable=False)         # Type-level base weight
    exact_match_boost = mapped_column(Float, default=2.0, nullable=False)
    recent_activity_boost = mapped_column(Float, default=0.3, nullable=False)
    lead_score_boost = mapped_column(Float, default=0.2, nullable=False)
    popularity_boost = mapped_column(Float, default=0.1, nullable=False)
    custom_signals = mapped_column(JSONBType, default=dict, nullable=True)   # Extensible signal overrides
    is_active = mapped_column(Boolean, default=True, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("entity_type", "organization_id", name="uq_search_ranking_entity_org"),
    )
