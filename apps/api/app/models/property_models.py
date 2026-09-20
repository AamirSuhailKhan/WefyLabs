import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Boolean, Float, Numeric, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.broker import Broker

JSONBType = JSONB().with_variant(JSON(), "sqlite")


class PropertyListing(Base, TimestampMixin, SoftDeleteMixin):
    """
    Global Canonical Property Listing model for Enterprise Real Estate CRM.
    Supports residential, commercial, land, and industrial properties with full inventory lifecycle.
    """
    __tablename__ = "property_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    property_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    share_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    property_category: Mapped[str] = mapped_column(String(50), default="residential", nullable=False)
    property_type: Mapped[str] = mapped_column(String(100), default="apartment", nullable=False, index=True)
    transaction_category: Mapped[str] = mapped_column(String(50), default="resale", nullable=False, index=True)
    listing_type: Mapped[str] = mapped_column(String(50), default="exclusive", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="available", nullable=False, index=True)

    # ── Price Model ──────────────────────────────────────────────────────────
    price: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    price_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_rent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    security_deposit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_per_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    # ── Area / Size ──────────────────────────────────────────────────────────
    area_value: Mapped[float] = mapped_column(Float, nullable=False)
    area_unit: Mapped[str] = mapped_column(String(20), default="sqft", nullable=False)
    carpet_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    super_built_up_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plot_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Specifications & Attributes ──────────────────────────────────────────
    bedrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    balconies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parking_spaces: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    facing: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    furnishing: Mapped[str] = mapped_column(String(30), default="unfurnished", nullable=False)
    age_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    possession_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    construction_status: Mapped[str] = mapped_column(String(50), default="ready_to_move", nullable=False)

    # ── Project & Unit Hierarchy ─────────────────────────────────────────────
    developer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    building_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unit_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ── Location ─────────────────────────────────────────────────────────────
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    locality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Market / Extended Attributes ─────────────────────────────────────────
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    extended_fields: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    amenities: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    marketing_highlights: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    # ── Ownership & Assigned Agent (Strictly Internal) ───────────────────────
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assigned_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True, index=True)

    # ── Commercial Data (Strictly Internal) ──────────────────────────────────
    commission_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Listing Expiry ───────────────────────────────────────────────────────
    listing_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    listing_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── AI Valuation Cache ───────────────────────────────────────────────────
    estimated_market_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_overpriced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_annual_roi_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    media: Mapped[List["PropertyMedia"]] = relationship("PropertyMedia", back_populates="property_listing", cascade="all, delete-orphan")
    price_history: Mapped[List["PropertyPriceHistory"]] = relationship("PropertyPriceHistory", back_populates="property_listing", cascade="all, delete-orphan")
    interested_leads: Mapped[List["LeadPropertyInterest"]] = relationship("LeadPropertyInterest", back_populates="property_listing", cascade="all, delete-orphan")

    def __init__(self, *args, **kwargs):
        if "location" in kwargs and "locality" not in kwargs:
            kwargs["locality"] = kwargs.pop("location")
        if "currency" in kwargs and "currency_code" not in kwargs:
            kwargs["currency_code"] = kwargs.pop("currency")
        if "built_up_area_sqft" in kwargs and "area_value" not in kwargs:
            kwargs["area_value"] = kwargs.pop("built_up_area_sqft")
        if "price" in kwargs and "price_per_sqft" not in kwargs and kwargs.get("area_value"):
            try:
                kwargs["price_per_sqft"] = round(float(kwargs["price"]) / float(kwargs["area_value"]), 2)
            except (ZeroDivisionError, ValueError):
                pass
        super().__init__(*args, **kwargs)

    @property
    def location(self) -> Optional[str]:
        return self.address or self.locality

    @location.setter
    def location(self, val: str):
        self.locality = val

    @property
    def currency(self) -> str:
        return self.currency_code

    @currency.setter
    def currency(self, val: str):
        self.currency_code = val

    @property
    def built_up_area_sqft(self) -> float:
        return self.area_value

    @built_up_area_sqft.setter
    def built_up_area_sqft(self, val: float):
        self.area_value = val

    @property
    def organization_id(self) -> str:
        return str(self.broker_id)


class PropertyMedia(Base, TimestampMixin):
    """Media assets: Floor plans, Photos, Virtual 360 Tours, Documents."""
    __tablename__ = "property_media"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(30), nullable=False)  # photo | floorplan | video | tour_360 | document
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), default="uploaded", nullable=False)  # uploaded | pending_review | verified | rejected

    property_listing: Mapped["PropertyListing"] = relationship("PropertyListing", back_populates="media")


class PropertyPriceHistory(Base):
    """Price audit history log."""
    __tablename__ = "property_price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    old_price: Mapped[float] = mapped_column(Float, nullable=False)
    new_price: Mapped[float] = mapped_column(Float, nullable=False)
    changed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    property_listing: Mapped["PropertyListing"] = relationship("PropertyListing", back_populates="price_history")


class LeadPropertyInterest(Base, TimestampMixin):
    """
    Canonical Lead ↔ Property Relationship Entity.
    Tracks a lead's interest, viewing journey, visits, offers, and conversions for each property.
    Many-to-Many junction with rich CRM metadata.
    """
    __tablename__ = "lead_property_interests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False, index=True)

    # Status: MATCHED | SHORTLISTED | INTERESTED | VISIT_REQUESTED | VISIT_SCHEDULED | VISITED | REJECTED | RESERVED | PURCHASED
    status: Mapped[str] = mapped_column(String(30), default="INTERESTED", nullable=False, index=True)
    interest_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)  # low | medium | high

    first_matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    interested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    visit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    deterministic_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    reasons: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    mismatches: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSONBType, default=dict, nullable=True)
    source_of_match: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)  # manual | copilot | recommendation | website
    assigned_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    @property
    def final_score(self) -> float:
        return self.match_score

    @property
    def interaction_type(self) -> str:
        return self.status

    @interaction_type.setter
    def interaction_type(self, val: str):
        self.status = val

    __table_args__ = (
        UniqueConstraint("organization_id", "lead_id", "property_id", name="uq_org_lead_property"),
        Index("ix_lpi_org_status", "organization_id", "status"),
        Index("ix_lpi_lead_status", "lead_id", "status"),
        Index("ix_lpi_property_status", "property_id", "status"),
        Index("ix_lpi_org_match_score", "organization_id", "match_score"),
    )

    property_listing: Mapped["PropertyListing"] = relationship("PropertyListing", back_populates="interested_leads")
    lead: Mapped["Lead"] = relationship("Lead", back_populates="interested_properties", foreign_keys=[lead_id])
