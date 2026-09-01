"""
Part 21.2 — Real-Estate Lead Discovery Domain Models
=====================================================
Entities supporting autonomous AI lead discovery from authorized sources.

Core Principles:
  1. Zero Fabrication: AI never generates imaginary prospects. Candidates are
     only created from real source signals with verifiable evidence.
  2. Authorized Data Only: Ingestion strictly via official APIs, webhooks,
     customer databases, and authorized partner integrations.
  3. Real Estate Domain: Prospects, buyers, sellers, tenants, landlords, investors.
     Zero recruitment or job portal logic.

Domain Objects:
  DiscoverySource      — Authorized source registry (META, GOOGLE, PARTNER_API, etc.)
  DiscoveryCampaign    — AI discovery objective definition with multi-country criteria
  DiscoveryRun         — Individual execution tracking with pagination cursors and usage metrics
  DiscoveryCandidate   — Discovered prospect undergoing validation and qualification state machine
  DiscoveryEvidence    — Immutable factual provenance linking candidate to concrete source records
  DiscoverySignal      — Structured real buying and transaction intent signals
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, Float,
    JSON, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")
NumericType = Numeric(precision=20, scale=4)  # Decimal-safe — NEVER use Float for budget
UUIDType = UUID(as_uuid=True).with_variant(String(36), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# TAXONOMY & ENUM CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

class DiscoverySourceType:
    META = "META"
    GOOGLE = "GOOGLE"
    PARTNER_API = "PARTNER_API"
    CUSTOMER_API = "CUSTOMER_API"
    CUSTOMER_DATABASE = "CUSTOMER_DATABASE"
    WEBSITE_SIGNAL = "WEBSITE_SIGNAL"
    LICENSED_PROVIDER = "LICENSED_PROVIDER"
    CRM = "CRM"
    OTHER_AUTHORIZED_PROVIDER = "OTHER_AUTHORIZED_PROVIDER"


class ProviderStatus:
    CONNECTED = "CONNECTED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    DISABLED = "DISABLED"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class DiscoveryCampaignStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DiscoveryRunStatus:
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CandidateStatus:
    DISCOVERED = "DISCOVERED"
    EVIDENCE_VALIDATION = "EVIDENCE_VALIDATION"
    NORMALIZING = "NORMALIZING"
    IDENTITY_MATCH = "IDENTITY_MATCH"
    DUPLICATE = "DUPLICATE"
    RELEVANT = "RELEVANT"
    IRRELEVANT = "IRRELEVANT"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY = "READY"
    IMPORTED = "IMPORTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ComplianceStatus:
    ALLOWED = "ALLOWED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class SignalType:
    PROPERTY_INQUIRY = "PROPERTY_INQUIRY"
    BROCHURE_REQUEST = "BROCHURE_REQUEST"
    VIEWING_REQUEST = "VIEWING_REQUEST"
    PRICE_INQUIRY = "PRICE_INQUIRY"
    FINANCING_INQUIRY = "FINANCING_INQUIRY"
    REPEAT_VISIT = "REPEAT_VISIT"
    HIGH_INTENT_MESSAGE = "HIGH_INTENT_MESSAGE"
    CAMPAIGN_RESPONSE = "CAMPAIGN_RESPONSE"
    CONTACT_FORM = "CONTACT_FORM"
    WHATSAPP_INQUIRY = "WHATSAPP_INQUIRY"
    PROPERTY_PAGE_INTERACTION = "PROPERTY_PAGE_INTERACTION"
    INVESTMENT_QUERY = "INVESTMENT_QUERY"
    SELLING_INQUIRY = "SELLING_INQUIRY"
    RENTAL_INQUIRY = "RENTAL_INQUIRY"


# ─────────────────────────────────────────────────────────────────────────────
# DISCOVERY SOURCE
# ─────────────────────────────────────────────────────────────────────────────

class DiscoverySource(Base):
    """
    Authorized source from which real estate leads can be discovered.
    Includes rate limits, daily/monthly quotas, error tracking, and market scoping.
    """
    __tablename__ = "discovery_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default=ProviderStatus.CONFIGURATION_REQUIRED, nullable=False, index=True)

    # Provider Configuration (Secrets stored encrypted or reference to SecretsManager)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # Geographic and Market Scoping
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    market_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Rate Limiting & Quotas
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    monthly_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    usage_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Health & Error Tracking
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_discovery_sources_org_provider", "organization_id", "provider"),
        Index("ix_discovery_sources_org_status", "organization_id", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DISCOVERY CAMPAIGN
# ─────────────────────────────────────────────────────────────────────────────

class DiscoveryCampaign(Base):
    """
    AI discovery objective (e.g. "Find high-intent Dubai Marina apartment buyers").
    Distinct from LeadCampaign (which is for marketing attribution).
    """
    __tablename__ = "discovery_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Geographic Scope
    market_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    cities: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    # Real Estate Criteria
    property_types: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)  # ["apartment", "villa"]
    transaction_types: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True) # ["BUY", "RENT", "INVEST"]
    lead_types: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)        # ["BUYER", "INVESTOR", "TENANT"]

    # Budget & Currency (Explicit Decimal bounds)
    budget_min: Mapped[Optional[Decimal]] = mapped_column(NumericType, nullable=True)
    budget_max: Mapped[Optional[Decimal]] = mapped_column(NumericType, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # ISO 4217

    timeline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    languages: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    # AI Discovery Thresholds
    intent_threshold: Mapped[float] = mapped_column(Float, default=0.70, nullable=False)
    minimum_confidence: Mapped[float] = mapped_column(Float, default=0.60, nullable=False)

    # Target Sources & Quotas
    source_ids: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    daily_discovery_limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # Status: draft | active | paused | completed | cancelled
    status: Mapped[str] = mapped_column(String(30), default=DiscoveryCampaignStatus.DRAFT, nullable=False, index=True)

    campaign_metadata: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_discovery_campaigns_org_status", "organization_id", "status"),
        Index("ix_discovery_campaigns_org_country", "organization_id", "country_code"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DISCOVERY RUN
# ─────────────────────────────────────────────────────────────────────────────

class DiscoveryRun(Base):
    """
    Execution instance of a discovery campaign.
    Tracks pagination cursors, counters, errors, and provider resource usage.
    """
    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String(30), default=DiscoveryRunStatus.QUEUED, nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Counters
    records_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_prospects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Error & Usage details
    errors: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    provider_usage: Mapped[Optional[dict]] = mapped_column(JSONBType, default=dict, nullable=True)
    cursor_position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    run_metadata: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_discovery_runs_org_campaign", "organization_id", "campaign_id"),
        Index("ix_discovery_runs_org_status", "organization_id", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DISCOVERY CANDIDATE
# ─────────────────────────────────────────────────────────────────────────────

class DiscoveryCandidate(Base):
    """
    Pre-lead discovery entity discovered from an authorized source.
    Requires evidence validation and relevance evaluation before becoming a Lead.
    """
    __tablename__ = "discovery_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    discovery_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("discovery_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("discovery_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # External Provider Reference & Provenance
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_information: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    raw_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_data: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # 4 Distinct Confidence & Relevance Scores (0.0 – 1.0)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relevance_model_version: Mapped[str] = mapped_column(String(50), default="v1.0-real-estate-discovery", nullable=False)
    identity_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    intent_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    freshness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps for Freshness Decay
    observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Compliance & Duplicate Handling
    compliance_status: Mapped[str] = mapped_column(String(30), default=ComplianceStatus.UNKNOWN, nullable=False)
    duplicate_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN", nullable=False)
    matched_lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # State Machine Status
    status: Mapped[str] = mapped_column(String(30), default=CandidateStatus.DISCOVERED, nullable=False, index=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    review_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Canonical CRM Link
    canonical_lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_discovery_candidates_org_status", "organization_id", "status"),
        Index("ix_discovery_candidates_org_external", "organization_id", "external_id"),
        Index("ix_discovery_candidates_org_run", "organization_id", "discovery_run_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DISCOVERY EVIDENCE
# ─────────────────────────────────────────────────────────────────────────────

class DiscoveryEvidence(Base):
    """
    Concrete factual evidence supporting a candidate's discovery.
    LLM output alone is NEVER evidence. Only raw provider/source records qualify.
    """
    __tablename__ = "discovery_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("discovery_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value_reference: Mapped[str] = mapped_column(Text, nullable=False)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    provenance: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_discovery_evidence_candidate", "candidate_id"),
        Index("ix_discovery_evidence_org_field", "organization_id", "field_name"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DISCOVERY SIGNAL
# ─────────────────────────────────────────────────────────────────────────────

class DiscoverySignal(Base):
    """
    Structured buying/selling signal extracted from real events or verified data.
    """
    __tablename__ = "discovery_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("discovery_evidence.id", ondelete="SET NULL"), nullable=True, index=True
    )

    signal_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    signal_payload: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_discovery_signals_candidate", "candidate_id"),
        Index("ix_discovery_signals_org_type", "organization_id", "signal_type"),
    )
