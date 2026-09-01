"""
Volume 2 PART 2 — AI Lead Enrichment Engine Models
==================================================
SQLAlchemy 2.0 models for:
1. LeadEnrichment: Aggregated enriched profile snapshot per lead
2. ConfidenceScore: Field-level confidence scores & data provenance
3. EnrichmentHistory: Immutable audit trail of enrichment runs
4. EnrichmentSource: Tracking source metadata
5. EnrichmentProvider: External provider registry & health tracking
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, BigInteger, Float, JSON, Index, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class LeadEnrichment(Base):
    """
    Unified enriched profile for a Lead.
    Stores multi-dimensional profiles: Identity, Location, Financial, Intent, Property, Communication, AI Insights.
    """
    __tablename__ = "lead_enrichments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Multi-dimensional Profiles (JSONB with SQLite fallback)
    identity_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    location_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    financial_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    intent_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    property_interest: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    communication_profile: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Derived Quality & AI Synthesis
    overall_quality_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0 - 100
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)     # 0.0 - 1.0
    quality_tier: Mapped[str] = mapped_column(String(20), default="cold", nullable=False, index=True) # hot | warm | cold | unqualified
    
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_recommendations: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)
    
    field_completion_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False, index=True) # pending | processing | completed | failed

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_lead_enrichment_org_tier", "organization_id", "quality_tier"),
    )


class ConfidenceScore(Base):
    """
    Granular field-level confidence and data provenance.
    Enforces strict distinction between:
    - observed (directly provided by user)
    - inferred (derived via AI/Rules/Regex)
    - verified (confirmed by external source/3rd party provider)
    """
    __tablename__ = "confidence_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    field_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False) # 0.0 - 1.0
    
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True) # observed | inferred | verified
    method: Mapped[str] = mapped_column(String(50), nullable=False) # Direct | Regex | PhoneNER | GeoIP | RuleEngine | LLM_GPT4o | ExternalProvider
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("lead_id", "field_name", name="uq_lead_field_confidence"),
        Index("ix_confidence_lead_field", "lead_id", "field_name"),
    )


class EnrichmentHistory(Base):
    """
    Immutable audit trail for lead enrichment passes.
    Supports replay safety analysis and debugging.
    """
    __tablename__ = "enrichment_histories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    trigger_event: Mapped[str] = mapped_column(String(50), nullable=False) # LeadNormalized | ReEnrichRequested | ManualUpdate | WebhookUpdate
    fields_modified: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=list, nullable=False)
    previous_values: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    new_values: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_token_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False) # success | partial | failed

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class EnrichmentSource(Base):
    """
    Registry of data sources used for enrichment (e.g. Ingestion Canonical, Regex Rule Engine, Open FX API, LLM Service).
    """
    __tablename__ = "enrichment_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    source_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class EnrichmentProvider(Base):
    """
    External provider registry tracking credentials, rate limits, latency, and operational health.
    """
    __tablename__ = "enrichment_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # phone_lookup | geo_ip | email_verify | business_registry
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    failure_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_calls: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    failed_calls: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    
    settings_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
