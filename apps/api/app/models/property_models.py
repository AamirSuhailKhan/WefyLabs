import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Boolean, Float, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

class PropertyListing(Base, TimestampMixin, SoftDeleteMixin):
    """
    Global Property Listing model.
    Country-specific fields live in extended_fields JSON, driven by PropertySchemaRegistry.
    Area is stored canonically in area_value (sqft internally) + area_unit (as-supplied).
    Price uses Float for storage but must always accompany currency_code — never unitless.
    NEVER store: price = 2000000 without currency.
    """
    __tablename__ = "property_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    property_category: Mapped[str] = mapped_column(String(50), default="residential", nullable=False)
    # Validated by PropertySchemaRegistry — NOT hardcoded ('1bhk', '2bhk', 'villa', ...)
    property_type: Mapped[str] = mapped_column(String(100), default="apartment", nullable=False, index=True)
    transaction_category: Mapped[str] = mapped_column(String(50), default="resale", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="available", nullable=False, index=True)

    # Price: ALWAYS store with explicit currency_code
    price: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)  # "AED", "INR", "USD" — no default
    # Area: canonical sqft value for internal computation + original supplied unit
    area_value: Mapped[float] = mapped_column(Float, nullable=False)            # canonical area number
    area_unit: Mapped[str] = mapped_column(String(20), default="sqft", nullable=False)  # sqft|sqm|sqyd|marla|kanal
    bedrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parking_spaces: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Building & Unit Hierarchy
    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    building_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unit_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Geo Location — no hardcoded city/locality defaults
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    locality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Global / Multi-Country Fields ────────────────────────────────────────
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)  # "AE", "IN"
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # Country-specific fields (RERA, DLD, MLS, tenure) stored as extensible JSON
    # Validated at application layer by PropertySchemaRegistry, not at DB level
    extended_fields: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    amenities: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    # AI Valuation Cache
    estimated_market_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_overpriced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_annual_roi_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    media: Mapped[List["PropertyMedia"]] = relationship("PropertyMedia", back_populates="property_listing", cascade="all, delete-orphan")
    price_history: Mapped[List["PropertyPriceHistory"]] = relationship("PropertyPriceHistory", back_populates="property_listing", cascade="all, delete-orphan")

    def __init__(self, *args, **kwargs):
        if "currency" in kwargs and "currency_code" not in kwargs:
            kwargs["currency_code"] = kwargs.pop("currency")
        if "built_up_area_sqft" in kwargs and "area_value" not in kwargs:
            kwargs["area_value"] = kwargs.pop("built_up_area_sqft")
        super().__init__(*args, **kwargs)

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

class PropertyMedia(Base, TimestampMixin):
    """Media assets: Floor plans, Photos, Virtual 360 Tours, Documents."""
    __tablename__ = "property_media"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(30), nullable=False) # photo | floorplan | video | tour_360 | document
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    property_listing: Mapped["PropertyListing"] = relationship("PropertyListing", back_populates="media")

class PropertyPriceHistory(Base):
    """Price audit history log."""
    __tablename__ = "property_price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    old_price: Mapped[float] = mapped_column(Float, nullable=False)
    new_price: Mapped[float] = mapped_column(Float, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    property_listing: Mapped["PropertyListing"] = relationship("PropertyListing", back_populates="price_history")
