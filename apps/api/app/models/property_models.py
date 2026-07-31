import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

class PropertyListing(Base, TimestampMixin, SoftDeleteMixin):
    """
    Enterprise Property Listing model supporting Zillow and Property Finder requirements:
    Building/Tower/Unit hierarchy, Geo-spatial coordinates, price history, and AI Valuation.
    """
    __tablename__ = "property_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    property_category: Mapped[str] = mapped_column(String(50), default="residential", nullable=False)
    property_type: Mapped[str] = mapped_column(String(50), default="apartment", nullable=False, index=True)
    transaction_category: Mapped[str] = mapped_column(String(50), default="resale", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="available", nullable=False, index=True)

    price: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)
    built_up_area_sqft: Mapped[float] = mapped_column(Float, nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parking_spaces: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Building & Unit Hierarchy
    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    building_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unit_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Geo Location
    city: Mapped[str] = mapped_column(String(100), default="Dubai", nullable=False, index=True)
    locality: Mapped[str] = mapped_column(String(100), default="Dubai Marina", nullable=False, index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    amenities: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    # AI Valuation Cache
    estimated_market_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_overpriced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_annual_roi_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    media: Mapped[List["PropertyMedia"]] = relationship("PropertyMedia", back_populates="property_listing", cascade="all, delete-orphan")
    price_history: Mapped[List["PropertyPriceHistory"]] = relationship("PropertyPriceHistory", back_populates="property_listing", cascade="all, delete-orphan")

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
