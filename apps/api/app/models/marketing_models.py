"""
Part 20 — Real Estate Marketing, Listing Distribution, Project Launch & Demand Generation OS
======================================================================================
Canonical marketing domain models for WefyLabs.

Architecture decisions:
- MarketingCampaign is the native Part 20 entity (extends LeadCampaign concept with
  approval workflow, budget controls, state machine, inventory scope).
- Does NOT duplicate LeadCampaign from Part 9. References it via optional FK.
- PropertyListingPublication is a MARKETING REPRESENTATION grounded in canonical
  ProjectUnit/PropertyListing data. It does NOT store duplicate pricing or availability.
- LandingPage routes to the existing public_capture_controller for lead ingestion.
- TrackingLink generates UTM-valid links that feed SourceAttribution (Part 9).
- All money: Numeric(20, 4). No floats.
- All state changes: append-only audit log + OutboxEvent.
- Tenant isolation: organization_id on every query.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List, Dict, TYPE_CHECKING
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKey, Date, Float
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)
PctType   = Numeric(precision=7, scale=4)


# ─────────────────────────────────────────────────────────────────────────────
# STATUS CONSTANTS & STATE MACHINES
# ─────────────────────────────────────────────────────────────────────────────

class CampaignObjective:
    LEAD_GENERATION    = "lead_generation"
    PROJECT_LAUNCH     = "project_launch"
    INVENTORY_SALES    = "inventory_sales"
    REMARKETING        = "remarketing"
    SITE_VISIT         = "site_visit"
    BOOKING            = "booking"
    CHANNEL_PARTNER    = "channel_partner"
    BRAND              = "brand"

    ALL = {
        LEAD_GENERATION, PROJECT_LAUNCH, INVENTORY_SALES, REMARKETING,
        SITE_VISIT, BOOKING, CHANNEL_PARTNER, BRAND
    }


class CampaignStatus:
    DRAFT      = "draft"
    IN_REVIEW  = "in_review"
    APPROVED   = "approved"
    SCHEDULED  = "scheduled"
    ACTIVE     = "active"
    PAUSED     = "paused"
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"

    VALID_TRANSITIONS = {
        "draft":     {"in_review", "cancelled"},
        "in_review": {"approved", "draft", "cancelled"},
        "approved":  {"scheduled", "active", "cancelled"},
        "scheduled": {"active", "paused", "cancelled"},
        "active":    {"paused", "completed", "cancelled"},
        "paused":    {"active", "cancelled", "completed"},
        "completed": set(),
        "cancelled": set(),
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        return to_status in cls.VALID_TRANSITIONS.get(from_status, set())


class ListingPublicationStatus:
    DRAFT       = "draft"
    READY       = "ready"
    APPROVED    = "approved"
    PUBLISHED   = "published"
    PAUSED      = "paused"
    UNPUBLISHED = "unpublished"
    ERROR       = "error"
    STALE       = "stale"


class AssetStatus:
    DRAFT    = "draft"
    REVIEW   = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class AssetType:
    IMAGE          = "image"
    VIDEO          = "video"
    BROCHURE       = "brochure"
    FLOOR_PLAN     = "floor_plan"
    PRICE_SHEET    = "price_sheet"
    PDF            = "pdf"
    LANDING_PAGE   = "landing_page"
    EMAIL_TEMPLATE = "email_template"
    SMS_TEMPLATE   = "sms_template"
    SOCIAL_COPY    = "social_copy"
    QR_CODE        = "qr_code"


class DistributionChannel:
    WEBSITE        = "website"
    PARTNER_PORTAL = "partner_portal"
    SOCIAL         = "social"
    EMAIL          = "email"
    SMS            = "sms"
    EMBEDDED_WIDGET = "embedded_widget"
    PROPERTY_PORTAL = "property_portal"


class ApprovalDecision:
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LaunchStatus:
    DRAFT     = "draft"
    PREPARING = "preparing"
    APPROVED  = "approved"
    LAUNCHED  = "launched"
    PAUSED    = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ─────────────────────────────────────────────────────────────────────────────
# 1. MarketingCampaign — The canonical Part 20 campaign entity
# ─────────────────────────────────────────────────────────────────────────────

class MarketingCampaign(Base, TimestampMixin, SoftDeleteMixin):
    """
    WefyLabs Marketing Campaign — Part 20 canonical entity.

    Distinct from LeadCampaign (Part 9) which is a lead-acquisition campaign.
    A MarketingCampaign is a full demand-generation initiative with:
    - Controlled state machine (DRAFT→IN_REVIEW→APPROVED→SCHEDULED→ACTIVE→PAUSED→COMPLETED)
    - Approval workflow (no paid/external campaigns without human approval)
    - Budget tracking (planned/approved/spent/remaining)
    - Inventory scope (project/phase/BHK subset)
    - Campaign objectives (LEAD_GENERATION / PROJECT_LAUNCH / INVENTORY_SALES etc.)
    - Audit trail via MarketingCampaignAudit

    Integration:
    - References real_estate_projects.id (Part 19 supply)
    - References lead_campaigns.id (Part 9 acquisition) when bridged
    - MarketingAssets attached via MarketingCampaignAsset
    - Listings via CampaignListingLink
    - Approval via CampaignApproval
    """
    __tablename__ = "marketing_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Objective: lead_generation | project_launch | inventory_sales | remarketing | site_visit | booking | channel_partner | brand
    objective: Mapped[str] = mapped_column(String(50), nullable=False, default=CampaignObjective.LEAD_GENERATION)

    # State machine: draft | in_review | approved | scheduled | active | paused | completed | cancelled
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=CampaignStatus.DRAFT, index=True)

    # Inventory scope — references Part 19 supply hierarchy
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    phase_scope: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)   # phase_id filter
    bhk_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)    # comma-separated BHK types
    unit_status_scope: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="available")
    price_range_min: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    price_range_max: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    inventory_scope_metadata: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # Budget — ALWAYS with currency, ALWAYS Decimal
    budget_planned: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    budget_approved: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    budget_spent: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True, default=Decimal("0"))
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True, default="INR")

    # Timing
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Attribution / Tracking
    utm_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Part 9 reference — optional bridge to acquisition campaign
    lead_campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lead_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Owner / Requestor
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)  # broker_id

    # AI-generated content flags
    is_ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Approval state (cached from latest CampaignApproval)
    approval_status: Mapped[str] = mapped_column(String(20), default=ApprovalDecision.PENDING, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Performance metrics — NULL until actual provider data received (never fabricated)
    impressions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clicks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    leads_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qualified_leads_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    appointments_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bookings_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    revenue_attributed: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)

    # Data provenance flags
    metrics_provenance: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # MANUAL | PROVIDER | CALCULATED

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONBType, nullable=True)

    __table_args__ = (
        Index("ix_mktg_campaign_org_status", "organization_id", "status"),
        Index("ix_mktg_campaign_org_project", "organization_id", "project_id"),
        Index("ix_mktg_campaign_org_objective", "organization_id", "objective"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. CampaignApproval — Human approval gate for paid/external campaigns
# ─────────────────────────────────────────────────────────────────────────────

class CampaignApproval(Base, TimestampMixin):
    """
    Human approval gate record.
    AI cannot skip this. Paid/external campaigns require explicit approval.
    Every approval request is immutable; new approval = new record.
    """
    __tablename__ = "campaign_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Request
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)  # broker_id
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    budget_requested: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    channels_requested: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    target_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creative_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Decision
    decision: Mapped[str] = mapped_column(String(20), default=ApprovalDecision.PENDING, nullable=False, index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget_approved: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)

    __table_args__ = (
        Index("ix_campaign_approval_org_campaign", "organization_id", "campaign_id"),
        Index("ix_campaign_approval_decision", "decision"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. CampaignAuditLog — Append-only trail for all campaign state changes
# ─────────────────────────────────────────────────────────────────────────────

class CampaignAuditLog(Base):
    """Immutable append-only audit log for all campaign mutations."""
    __tablename__ = "campaign_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)        # e.g., STATUS_CHANGED, APPROVED, BUDGET_UPDATED
    from_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    to_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONBType, nullable=True)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_campaign_audit_org_campaign", "organization_id", "campaign_id"),
        Index("ix_campaign_audit_performed_at", "performed_at"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. MarketingAsset — Images, brochures, floor plans, email templates etc.
# ─────────────────────────────────────────────────────────────────────────────

class MarketingAsset(Base, TimestampMixin, SoftDeleteMixin):
    """
    Tenant/project-scoped marketing asset with versioning and approval.
    Never silently overwrite approved assets.
    """
    __tablename__ = "marketing_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Asset identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # AssetType constants
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scope
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Storage — URL/path to media (uses existing Part 17 media infrastructure)
    storage_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Approval workflow
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AssetStatus.DRAFT, index=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    previous_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # AI-generated content flag
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Publication state
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Creator
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_mktg_asset_org_project", "organization_id", "project_id"),
        Index("ix_mktg_asset_org_campaign", "organization_id", "campaign_id"),
        Index("ix_mktg_asset_org_type_status", "organization_id", "asset_type", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. PropertyListingPublication — Marketing representation of canonical inventory
# ─────────────────────────────────────────────────────────────────────────────

class PropertyListingPublication(Base, TimestampMixin, SoftDeleteMixin):
    """
    A marketing-ready representation of supply-side inventory.

    Grounded in canonical sources:
    - project_id → real_estate_projects (Part 19)
    - unit_id    → project_units (Part 19)
    - price      → project_price_books (Part 19) — NEVER overridden here

    This entity holds MARKETING COPY and PUBLICATION STATE only.
    It does NOT store duplicate pricing, availability, or RERA data.
    Those fields are always fetched from the canonical source.

    AI-generated fields are marked is_ai_generated=True and remain editable.
    AI must never invent price, area, possession date, location, or legal data.
    """
    __tablename__ = "property_listing_publications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Canonical source references (required)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    unit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    # Also supports PropertyListing-scoped listings (for secondary market)
    property_listing_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Campaign scope
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Marketing copy — all AI-generated fields flagged
    listing_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    listing_title_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_description_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    full_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_description_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    highlights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of bullet points
    highlights_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    faq_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON FAQ pairs
    faq_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # SEO
    slug: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    seo_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    indexing_state: Mapped[str] = mapped_column(String(20), default="noindex", nullable=False)

    # Publication state machine
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ListingPublicationStatus.DRAFT, index=True
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Stale detection
    last_inventory_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    stale_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Version
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Creator
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_plp_org_project_status", "organization_id", "project_id", "status"),
        Index("ix_plp_org_unit", "organization_id", "unit_id"),
        Index("ix_plp_slug", "slug"),
        Index("ix_plp_stale", "is_stale"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. ListingDistribution — Channel-by-channel publication record
# ─────────────────────────────────────────────────────────────────────────────

class ListingDistribution(Base, TimestampMixin):
    """
    Records the distribution of a PropertyListingPublication to a specific channel.
    A listing may be distributed to: website, partner_portal, social, email, etc.
    Do NOT claim external portal sync succeeded unless provider acknowledged.
    """
    __tablename__ = "listing_distributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    listing_publication_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("property_listing_publications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # DistributionChannel constants
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "housing.com"
    external_listing_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status — never auto-confirm external sync
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_listing_dist_org_channel", "organization_id", "channel"),
        Index("ix_listing_dist_publication", "listing_publication_id"),
        UniqueConstraint("listing_publication_id", "channel", "provider_name", name="uq_listing_dist_channel_provider"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. LandingPage — Project/campaign-scoped landing page
# ─────────────────────────────────────────────────────────────────────────────

class LandingPage(Base, TimestampMixin, SoftDeleteMixin):
    """
    Project/campaign-scoped landing page for real-estate demand generation.
    Public pages expose ONLY explicitly publishable information.
    Lead capture connects to the existing Part 9 universal intake pipeline.
    """
    __tablename__ = "marketing_landing_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Scope
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # SEO
    page_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    indexing_state: Mapped[str] = mapped_column(String(20), default="noindex", nullable=False)

    # Content sections (JSON) — structured for rendering, no raw HTML stored
    hero_content: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    inventory_highlights: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    pricing_disclosure: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    amenities_content: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    location_content: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    trust_content: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Lead form configuration (routes to Part 9 universal intake)
    form_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    form_config: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # UTM defaults for this landing page
    utm_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Creator
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_landing_page_org_slug"),
        Index("ix_landing_page_org_status", "organization_id", "status"),
        Index("ix_landing_page_org_project", "organization_id", "project_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. TrackingLink — UTM-validated tracking links for campaigns
# ─────────────────────────────────────────────────────────────────────────────

class TrackingLink(Base, TimestampMixin):
    """
    WefyLabs tracking link builder output.
    Validates UTM parameters. Generates short tokens for QR / partner distribution.
    Does NOT expose internal IDs directly.
    Attribution feeds into SourceAttribution (Part 9) when a lead is captured.
    """
    __tablename__ = "tracking_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Scope
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    landing_page_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("marketing_landing_pages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel_partner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("channel_partners.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Destination
    destination_url: Mapped[str] = mapped_column(Text, nullable=False)

    # UTM parameters (validated at creation)
    utm_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_term: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Short token for QR / compact distribution (not an internal ID)
    short_token: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)

    # Optional QR code storage_url (from MarketingAsset)
    qr_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Analytics (incremented on redirect, no PII stored in counters)
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_tracking_link_org_campaign", "organization_id", "campaign_id"),
        Index("ix_tracking_link_short_token", "short_token"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 9. CampaignEvent — Standardized marketing events (where data actually exists)
# ─────────────────────────────────────────────────────────────────────────────

class CampaignEvent(Base):
    """
    Standardized marketing event record.
    Only records events where data actually exists — never fabricated.
    Idempotency enforced via (campaign_id, event_type, external_reference).
    """
    __tablename__ = "campaign_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Event type: campaign.created | listing.published | lead_form.submitted | campaign.lead_created | etc.
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # References
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    deal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    unit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    tracking_link_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Idempotency
    external_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)

    # Event payload
    payload: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_campaign_event_org_campaign", "organization_id", "campaign_id"),
        Index("ix_campaign_event_type", "event_type"),
        Index("ix_campaign_event_occurred", "occurred_at"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 10. ProjectLaunch — End-to-end project launch workflow checklist
# ─────────────────────────────────────────────────────────────────────────────

class ProjectLaunch(Base, TimestampMixin, SoftDeleteMixin):
    """
    Project Launch OS — governs the full launch readiness workflow.

    Checklist tracks readiness gates before a project is publicly promoted:
    - Project configured
    - Inventory loaded
    - Pricing ready
    - Media ready
    - Landing page ready
    - Lead form ready
    - Tracking ready
    - Partner distribution ready
    - Campaign ready
    - Approval complete
    - Published

    Human approval required before LAUNCHED state.
    AI may assist in drafting — cannot independently launch.
    """
    __tablename__ = "project_launches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    landing_page_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("marketing_landing_pages.id", ondelete="SET NULL"), nullable=True
    )

    # Status: draft | preparing | approved | launched | paused | completed | cancelled
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=LaunchStatus.DRAFT, index=True)

    # Checklist gates (True = ready)
    gate_project_configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_inventory_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_pricing_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_media_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_landing_page_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_lead_form_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_tracking_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_partner_distribution_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_campaign_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_approval_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Schedule & approval
    scheduled_launch_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    launched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Creator
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_project_launch_org_project", "organization_id", "project_id"),
        Index("ix_project_launch_status", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 11. CampaignListingLink — Many-to-many: campaign ↔ listing publication
# ─────────────────────────────────────────────────────────────────────────────

class CampaignListingLink(Base):
    """Links a marketing campaign to specific listing publications."""
    __tablename__ = "campaign_listing_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listing_publication_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("property_listing_publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "listing_publication_id", name="uq_campaign_listing_link"),
    )
