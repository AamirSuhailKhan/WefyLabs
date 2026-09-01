"""
Part 21.1 — Real-Estate Lead Acquisition Domain Models
=======================================================
Distinct from the existing Lead/ConnectorConfig/IngestionLog models.
These models form the acquisition layer BEFORE a Lead is created in CRM.

Domain Objects:
  LeadSource         — Organization-scoped named origin (website, meta, google, whatsapp)
  LeadCampaign       — Real-estate acquisition campaign entity
  CampaignPropertyLink — Many-to-many: campaign ↔ property
  LeadAcquisitionEvent — Immutable provenance record for each incoming event
  LeadProspect       — Pre-canonical person before becoming a CRM Lead
  SourceAttribution  — UTM + full provenance per lead

Domain Vocabulary: Lead, Prospect, Buyer, Seller, Tenant, Landlord, Investor,
                   Broker, Property, Listing, Campaign, Source, Viewing, Market.
Domain Restriction: This is a Real Estate CRM domain — not a recruitment platform.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric,
    JSON, Index, UniqueConstraint, ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")
NumericType = Numeric(precision=20, scale=4)  # Decimal-safe — NEVER use Float for budget
UUIDType = UUID(as_uuid=True).with_variant(String(36), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS (stored as VARCHAR — no DB-level enum to avoid migration pain)
# ─────────────────────────────────────────────────────────────────────────────

class AcquisitionChannel:
    """Normalized channel taxonomy — channel is HOW, provider is WHO."""
    WEBSITE = "WEBSITE"
    WHATSAPP = "WHATSAPP"
    META = "META"
    GOOGLE = "GOOGLE"
    EMAIL = "EMAIL"
    TELEGRAM = "TELEGRAM"
    CRM = "CRM"
    API = "API"
    WEBHOOK = "WEBHOOK"
    PARTNER = "PARTNER"
    MANUAL = "MANUAL"
    OTHER = "OTHER"


class LeadIntent:
    BUYER = "BUYER"
    SELLER = "SELLER"
    TENANT = "TENANT"
    LANDLORD = "LANDLORD"
    INVESTOR = "INVESTOR"
    OTHER = "OTHER"


class TransactionType:
    BUY = "BUY"
    SELL = "SELL"
    RENT = "RENT"
    LEASE = "LEASE"
    INVEST = "INVEST"
    UNKNOWN = "UNKNOWN"


class ConsentStatus:
    UNKNOWN = "UNKNOWN"
    GRANTED = "GRANTED"
    DENIED = "DENIED"


class ProspectStatus:
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    NORMALIZED = "NORMALIZED"
    MATCHING = "MATCHING"
    DUPLICATE = "DUPLICATE"
    READY = "READY"
    IMPORTED = "IMPORTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class DuplicateMatchStatus:
    NO_MATCH = "NO_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    HIGH_CONFIDENCE_MATCH = "HIGH_CONFIDENCE_MATCH"
    EXACT_MATCH = "EXACT_MATCH"
    UNKNOWN = "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────────
# LEAD SOURCE
# ─────────────────────────────────────────────────────────────────────────────

class LeadSource(Base):
    """
    Organization-scoped named lead origin.

    A LeadSource describes WHERE leads come from within a specific organization.
    One org may have many sources: their own website, their WhatsApp number,
    their Meta page, their Google ad account, a partner API, etc.

    Distinct from ConnectorConfig (system-level connector configuration).
    """
    __tablename__ = "lead_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Channel & Provider taxonomy
    # channel: WEBSITE | WHATSAPP | META | GOOGLE | EMAIL | TELEGRAM | API | WEBHOOK | MANUAL | OTHER
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # provider: meta_lead_ads | google_lead_form | twilio_whatsapp | sendgrid | custom
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status: active | paused | inactive | configuration_required
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False, index=True)

    # Country/Market scope (NULL = org default)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    market_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Provider-specific configuration (encrypted secrets stored separately in ConnectorConfig)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # Webhook security (for inbound webhook sources)
    webhook_secret_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    webhook_url_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)

    # Rate limiting config per source
    rate_limit_per_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, insert_default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_lead_sources_org_channel", "organization_id", "channel"),
        Index("ix_lead_sources_org_status", "organization_id", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LEAD CAMPAIGN
# ─────────────────────────────────────────────────────────────────────────────

class LeadCampaign(Base):
    """
    Real-estate acquisition campaign.

    A campaign is a targeted marketing effort to attract leads for specific
    properties, locations, or buyer segments.

    Examples:
      - Dubai Marina 2BHK Campaign
      - Mumbai Luxury Buyers Q3 2026
      - Abu Dhabi Investor Campaign

    DO NOT confuse campaign with property or lead.
    A campaign may promote multiple properties (see CampaignPropertyLink).
    """
    __tablename__ = "lead_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status: draft | active | paused | completed | cancelled
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)

    # Source association
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Market & Geography (no hardcoded country logic — resolved from Country registry)
    market_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)

    # Budget & Money — ALWAYS with currency (never raw float budget without currency)
    budget: Mapped[Optional[Decimal]] = mapped_column(NumericType, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # ISO 4217: AED, INR, USD

    # Timing
    timezone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # IANA timezone
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Channel: WEBSITE | META | GOOGLE | WHATSAPP | EMAIL | TELEGRAM | OTHER
    channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Lead intent this campaign targets
    target_lead_intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # BUYER | INVESTOR | etc.
    target_transaction_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Extensible metadata
    campaign_metadata: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_lead_campaigns_org_status", "organization_id", "status"),
        Index("ix_lead_campaigns_org_market", "organization_id", "market_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN ↔ PROPERTY LINK (many-to-many)
# ─────────────────────────────────────────────────────────────────────────────

class CampaignPropertyLink(Base):
    """
    Many-to-many junction between LeadCampaign and PropertyListing.
    A campaign may promote zero, one, or many properties.
    NEVER store only a hardcoded property_id inside campaign metadata.
    """
    __tablename__ = "campaign_property_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lead_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    property_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )  # FK to property_listings.id — no hard FK to avoid circular dep
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "property_id", name="uq_campaign_property"),
        Index("ix_campaign_property_org", "organization_id", "campaign_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LEAD ACQUISITION EVENT
# ─────────────────────────────────────────────────────────────────────────────

class LeadAcquisitionEvent(Base):
    """
    Immutable provenance record for the exact moment a prospect enters BeetleLabs.

    Each event maps to exactly one external incoming signal:
      - website form submission
      - WhatsApp message
      - Meta Lead Ad submission
      - Google Lead Form submission
      - CRM import row
      - API webhook call
      - Email inquiry

    This object provides full provenance. Never mutable after creation.
    Idempotency is enforced via (source_id, external_id) or idempotency_key.
    """
    __tablename__ = "lead_acquisition_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Source & Campaign
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # External provider reference
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timing
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    # Raw event reference (pointer to OriginalPayload, not the payload itself)
    raw_event_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Processing status: pending | processing | processed | rejected | failed
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)

    # IP, user_agent for abuse detection (hashed/truncated for privacy)
    ip_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Channel resolved from source
    channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_acq_event_org_status", "organization_id", "status"),
        Index("ix_acq_event_org_received", "organization_id", "received_at"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_acq_event_org_idem_key"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LEAD PROSPECT
# ─────────────────────────────────────────────────────────────────────────────

class LeadProspect(Base):
    """
    Pre-canonical person/business inquiry BEFORE becoming a fully resolved CRM Lead.

    A prospect enters via any acquisition source and progresses through:
      RECEIVED → VALIDATING → NORMALIZED → MATCHING → READY → IMPORTED
      or:
      RECEIVED → VALIDATING → DUPLICATE (→ existing lead updated)
      or:
      RECEIVED → REJECTED / FAILED

    DO NOT automatically create duplicate CRM Leads.
    DO NOT auto-grant consent.
    DO NOT invent contact details.

    Vocabulary: prospect, buyer, seller, tenant, landlord, investor.
    Prohibited: recruitment terminology.
    """
    __tablename__ = "lead_prospects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Provenance
    acquisition_event_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_acquisition_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Contact (as-received, before normalization — normalization updates in place)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)  # E.164 after normalization

    # Normalized contact fingerprints for dedup
    email_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # SHA-256 of lowercase email
    phone_e164: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)  # Normalized E.164

    # Geography & Locale
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)  # ISO alpha-2
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # BCP 47: en-AE, ar-AE, hi-IN

    # Property interest (as expressed by prospect)
    property_interest: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # free-text description
    # Lead intent: BUYER | SELLER | TENANT | LANDLORD | INVESTOR | OTHER
    lead_intent: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Property type from existing property taxonomy
    property_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Transaction type: BUY | SELL | RENT | LEASE | INVEST | UNKNOWN
    transaction_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Budget — ALWAYS with currency (never unitless)
    budget_min: Mapped[Optional[Decimal]] = mapped_column(NumericType, nullable=True)
    budget_max: Mapped[Optional[Decimal]] = mapped_column(NumericType, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # ISO 4217

    # Timeline (as expressed): immediate | 1_month | 3_months | 6_months | 12_months | unknown
    timeline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Message / Inquiry text (as-received)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Consent ──────────────────────────────────────────────────────────────
    # UNKNOWN must never automatically become GRANTED
    # consent_status: UNKNOWN | GRANTED | DENIED
    consent_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    email_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    whatsapp_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    consent_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_policy_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ── Confidence Scores ────────────────────────────────────────────────────
    identity_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)  # 0.0 – 1.0
    data_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)

    # ── AI Extraction metadata ───────────────────────────────────────────────
    ai_extracted_fields: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    ai_extraction_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)

    # ── Duplicate Detection ──────────────────────────────────────────────────
    # duplicate_status: NO_MATCH | POSSIBLE_MATCH | HIGH_CONFIDENCE_MATCH | EXACT_MATCH | UNKNOWN
    duplicate_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN", nullable=False)
    matched_lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # ── Lifecycle ────────────────────────────────────────────────────────────
    # status: RECEIVED | VALIDATING | NORMALIZED | MATCHING | DUPLICATE | READY | IMPORTED | REJECTED | FAILED
    status: Mapped[str] = mapped_column(String(20), default="RECEIVED", nullable=False, index=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Once imported, the canonical CRM Lead ID
    canonical_lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Acquisition quality score (0.0 – 1.0, separate from lead score)
    acquisition_quality_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_prospect_org_status", "organization_id", "status"),
        Index("ix_prospect_org_phone", "organization_id", "phone_e164"),
        Index("ix_prospect_org_email_fp", "organization_id", "email_fingerprint"),
        Index("ix_prospect_org_created", "organization_id", "created_at"),
        Index("ix_prospect_campaign", "campaign_id"),
        Index("ix_prospect_source", "source_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE ATTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────

class SourceAttribution(Base):
    """
    UTM + full provenance attribution record for a CRM Lead.

    Every lead must answer:
      - Where did this person come from?
      - Which campaign? Which channel? Which provider?
      - When? Which external ID? Which property?

    Created when a Prospect is imported as a canonical Lead.
    Preserved on merge — never destroyed.
    """
    __tablename__ = "source_attributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # The canonical CRM Lead this attribution belongs to
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Acquisition provenance
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True
    )
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_campaigns.id", ondelete="SET NULL"), nullable=True
    )
    acquisition_event_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_acquisition_events.id", ondelete="SET NULL"), nullable=True
    )
    prospect_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_prospects.id", ondelete="SET NULL"), nullable=True
    )

    # Channel & Provider
    channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Landing page & URL context
    landing_page: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referrer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # UTM parameters (NULL if not present — never fabricated)
    utm_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_term: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Touch points
    first_touch_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_touch_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_source_attribution_lead", "lead_id"),
        Index("ix_source_attribution_org_campaign", "organization_id", "campaign_id"),
        Index("ix_source_attribution_org_source", "organization_id", "source_id"),
    )
