"""
Part 19 - Real Estate Supply, Project, Unit Inventory & Channel Partner Network OS
Canonical supply-side domain models for WefyLabs.
Developer -> Project -> Phase -> Building -> Floor -> Unit
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List, Dict, TYPE_CHECKING
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKey, Date
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.broker import Broker
    from app.models.deal_models import Deal

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)
PctType   = Numeric(precision=7, scale=4)


class DeveloperStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class ProjectStatus:
    ANNOUNCED          = "announced"
    PRE_LAUNCH         = "pre_launch"
    LAUNCHED           = "launched"
    UNDER_CONSTRUCTION = "under_construction"
    NEAR_COMPLETION    = "near_completion"
    READY_TO_MOVE      = "ready_to_move"
    COMPLETED          = "completed"
    CANCELLED          = "cancelled"
    SUSPENDED          = "suspended"


class UnitInventoryStatus:
    AVAILABLE   = "available"
    RESERVED    = "reserved"
    BOOKED      = "booked"
    SOLD        = "sold"
    BLOCKED     = "blocked"
    UNDER_OFFER = "under_offer"
    RETURNED    = "returned"

    VALID_TRANSITIONS = {
        "available":   {"reserved", "blocked", "under_offer"},
        "reserved":    {"available", "booked", "blocked"},
        "under_offer": {"reserved", "available", "booked"},
        "booked":      {"sold", "returned"},
        "returned":    {"available"},
        "blocked":     {"available"},
        "sold":        set(),
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        return to_status in cls.VALID_TRANSITIONS.get(from_status, set())


class ChannelPartnerStatus:
    ACTIVE       = "active"
    INACTIVE     = "inactive"
    PENDING_KYC  = "pending_kyc"
    KYC_VERIFIED = "kyc_verified"
    SUSPENDED    = "suspended"
    BLACKLISTED  = "blacklisted"


class ChannelPartnerTier:
    PLATINUM = "platinum"
    GOLD     = "gold"
    SILVER   = "silver"
    STANDARD = "standard"


class PriceBookStatus:
    DRAFT      = "draft"
    ACTIVE     = "active"
    EXPIRED    = "expired"
    SUPERSEDED = "superseded"


# ---------------------------------------------------------------------------
# 1. RealEstateDeveloper
# ---------------------------------------------------------------------------

class RealEstateDeveloper(Base, TimestampMixin, SoftDeleteMixin):
    """Canonical Real Estate Developer / Builder entity."""
    __tablename__ = "real_estate_developers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    developer_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    rera_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    gst_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pan_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    cin_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    primary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    rating: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    total_projects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_projects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ongoing_projects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    years_in_business: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=DeveloperStatus.ACTIVE, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extended_fields: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    projects: Mapped[List["RealEstateProject"]] = relationship("RealEstateProject", back_populates="developer", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("organization_id", "developer_code", name="uq_org_developer_code"),
        Index("ix_developer_org_status", "organization_id", "status"),
    )


# ---------------------------------------------------------------------------
# 2. RealEstateProject
# ---------------------------------------------------------------------------

class RealEstateProject(Base, TimestampMixin, SoftDeleteMixin):
    """Canonical Real Estate Project entity."""
    __tablename__ = "real_estate_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    developer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_developers.id", ondelete="SET NULL"), nullable=True, index=True)
    project_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    tagline: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hero_image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    brochure_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    project_type: Mapped[str] = mapped_column(String(50), default="residential", nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(30), default="primary_sale", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default=ProjectStatus.ANNOUNCED, nullable=False, index=True)
    rera_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    rera_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    micro_market: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    locality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    launch_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    possession_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    price_min: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True, index=True)
    price_max: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sold_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cp_commission_pct: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    cp_commission_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amenities: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    highlights: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    unit_configs: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    area_range: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extended_fields: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    developer: Mapped[Optional["RealEstateDeveloper"]] = relationship("RealEstateDeveloper", back_populates="projects")
    phases: Mapped[List["ProjectPhase"]] = relationship("ProjectPhase", back_populates="project", cascade="all, delete-orphan")
    price_books: Mapped[List["ProjectPriceBook"]] = relationship("ProjectPriceBook", back_populates="project", cascade="all, delete-orphan")
    media: Mapped[List["ProjectMedia"]] = relationship("ProjectMedia", back_populates="project", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("organization_id", "project_code", name="uq_org_project_code"),
        Index("ix_project_org_status", "organization_id", "status"),
        Index("ix_project_city_type", "city", "project_type"),
        Index("ix_project_locality", "locality"),
        Index("ix_project_price_min", "price_min"),
    )


# ---------------------------------------------------------------------------
# 3. ProjectPhase
# ---------------------------------------------------------------------------

class ProjectPhase(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "project_phases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_code: Mapped[str] = mapped_column(String(50), nullable=False)
    phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phase_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    phase_type: Mapped[str] = mapped_column(String(30), default="tower", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default=ProjectStatus.ANNOUNCED, nullable=False, index=True)
    rera_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    launch_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    possession_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extended_fields: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    project: Mapped["RealEstateProject"] = relationship("RealEstateProject", back_populates="phases")
    buildings: Mapped[List["ProjectBuilding"]] = relationship("ProjectBuilding", back_populates="phase", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("project_id", "phase_code", name="uq_phase_code_per_project"),
        Index("ix_phase_project_status", "project_id", "status"),
        Index("ix_phase_org", "organization_id"),
    )


# ---------------------------------------------------------------------------
# 4. ProjectBuilding
# ---------------------------------------------------------------------------

class ProjectBuilding(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "project_buildings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    phase_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_phases.id", ondelete="CASCADE"), nullable=False, index=True)
    building_code: Mapped[str] = mapped_column(String(50), nullable=False)
    building_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    construction_status: Mapped[str] = mapped_column(String(50), default="under_construction", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phase: Mapped["ProjectPhase"] = relationship("ProjectPhase", back_populates="buildings")
    floors: Mapped[List["ProjectFloor"]] = relationship("ProjectFloor", back_populates="building", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("phase_id", "building_code", name="uq_building_code_per_phase"),
        Index("ix_building_phase", "phase_id"),
        Index("ix_building_org", "organization_id"),
    )


# ---------------------------------------------------------------------------
# 5. ProjectFloor
# ---------------------------------------------------------------------------

class ProjectFloor(Base, TimestampMixin):
    __tablename__ = "project_floors"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    building_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_buildings.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    floor_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    total_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    building: Mapped["ProjectBuilding"] = relationship("ProjectBuilding", back_populates="floors")
    units: Mapped[List["ProjectUnit"]] = relationship("ProjectUnit", back_populates="floor", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("building_id", "floor_number", name="uq_floor_per_building"),
        Index("ix_floor_building", "building_id"),
    )


# ---------------------------------------------------------------------------
# 6. ProjectUnit (atomic inventory item)
# ---------------------------------------------------------------------------

class ProjectUnit(Base, TimestampMixin, SoftDeleteMixin):
    """Atomic sellable/leasable inventory unit with state machine for inventory_status."""
    __tablename__ = "project_units"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("project_phases.id", ondelete="SET NULL"), nullable=True, index=True)
    building_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("project_buildings.id", ondelete="SET NULL"), nullable=True, index=True)
    floor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("project_floors.id", ondelete="SET NULL"), nullable=True, index=True)
    property_listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    unit_number: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    facing: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    carpet_area: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    built_up_area: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    super_built_up_area: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    area_unit: Mapped[str] = mapped_column(String(20), default="sqft", nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    balconies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parking_slots: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    study_rooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    servant_quarters: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    base_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True, index=True)
    price_per_sqft: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    floor_rise_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    amenity_charges: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    parking_charges: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    total_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    inventory_status: Mapped[str] = mapped_column(String(30), default=UnitInventoryStatus.AVAILABLE, nullable=False, index=True)
    reserved_by_deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    reserved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    booked_by_deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    booked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    possession_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_reservation_idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    channel_partner_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_partners.id", ondelete="SET NULL"), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extended_fields: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    floor: Mapped[Optional["ProjectFloor"]] = relationship("ProjectFloor", back_populates="units")
    status_logs: Mapped[List["ProjectUnitStatusLog"]] = relationship("ProjectUnitStatusLog", back_populates="unit", cascade="all, delete-orphan", order_by="ProjectUnitStatusLog.created_at", lazy="selectin")
    __table_args__ = (
        UniqueConstraint("project_id", "unit_code", name="uq_unit_code_per_project"),
        Index("ix_unit_org_status", "organization_id", "inventory_status"),
        Index("ix_unit_project_status", "project_id", "inventory_status"),
        Index("ix_unit_type_status", "unit_type", "inventory_status"),
        Index("ix_unit_floor_facing", "floor_number", "facing"),
        Index("ix_unit_price", "base_price"),
        Index("ix_unit_total_price", "total_price"),
    )


# ---------------------------------------------------------------------------
# 7. ProjectUnitStatusLog (append-only audit)
# ---------------------------------------------------------------------------

class ProjectUnitStatusLog(Base, TimestampMixin):
    __tablename__ = "project_unit_status_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_units.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    changed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    changed_by_type: Mapped[str] = mapped_column(String(30), default="user", nullable=False)
    deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    outbox_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    unit: Mapped["ProjectUnit"] = relationship("ProjectUnit", back_populates="status_logs")
    __table_args__ = (
        Index("ix_unit_status_log_unit", "unit_id"),
        Index("ix_unit_status_log_org_new", "organization_id", "new_status"),
    )


# ---------------------------------------------------------------------------
# 8. ProjectPriceBook + PriceBookEntry
# ---------------------------------------------------------------------------

class ProjectPriceBook(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "project_price_books"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=PriceBookStatus.DRAFT, nullable=False, index=True)
    base_price_floor: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    floor_rise_per_floor: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    project: Mapped["RealEstateProject"] = relationship("RealEstateProject", back_populates="price_books")
    entries: Mapped[List["PriceBookEntry"]] = relationship("PriceBookEntry", back_populates="price_book", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_pricebook_version"),
        Index("ix_pricebook_project_status", "project_id", "status"),
        Index("ix_pricebook_org", "organization_id"),
    )


class PriceBookEntry(Base, TimestampMixin):
    __tablename__ = "price_book_entries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_price_books.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("project_units.id", ondelete="CASCADE"), nullable=True, index=True)
    unit_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    base_price: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    price_per_sqft: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    floor_rise_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    parking_charges: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    other_charges: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    total_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    price_book: Mapped["ProjectPriceBook"] = relationship("ProjectPriceBook", back_populates="entries")
    __table_args__ = (
        Index("ix_pbe_book_unit", "price_book_id", "unit_id"),
        Index("ix_pbe_book_type", "price_book_id", "unit_type"),
    )


# ---------------------------------------------------------------------------
# 9. ProjectMedia
# ---------------------------------------------------------------------------

class ProjectMedia(Base, TimestampMixin):
    __tablename__ = "project_media"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(30), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    project: Mapped["RealEstateProject"] = relationship("RealEstateProject", back_populates="media")
    __table_args__ = (Index("ix_project_media_project", "project_id", "media_type"),)


# ---------------------------------------------------------------------------
# 10. ChannelPartner
# ---------------------------------------------------------------------------

class ChannelPartner(Base, TimestampMixin, SoftDeleteMixin):
    """Channel Partner - broker/agent/firm that sources buyers."""
    __tablename__ = "channel_partners"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    cp_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    firm_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    whatsapp_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    rera_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    pan_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    gst_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    kyc_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kyc_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default=ChannelPartnerTier.STANDARD, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=ChannelPartnerStatus.PENDING_KYC, nullable=False, index=True)
    default_commission_pct: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    total_deals_sourced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_deals_closed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_commission_earned: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extended_fields: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    project_agreements: Mapped[List["ChannelPartnerProjectAgreement"]] = relationship("ChannelPartnerProjectAgreement", back_populates="channel_partner", cascade="all, delete-orphan")
    commission_records: Mapped[List["ChannelPartnerCommission"]] = relationship("ChannelPartnerCommission", back_populates="channel_partner", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("organization_id", "cp_code", name="uq_org_cp_code"),
        Index("ix_cp_org_status", "organization_id", "status"),
        Index("ix_cp_org_tier", "organization_id", "tier"),
        Index("ix_cp_city", "city"),
        Index("ix_cp_rera", "rera_number"),
    )


# ---------------------------------------------------------------------------
# 11. ChannelPartnerProjectAgreement
# ---------------------------------------------------------------------------

class ChannelPartnerProjectAgreement(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cp_project_agreements"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    channel_partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_partners.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    commission_pct: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    brokerage_fee: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    commission_slabs: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    is_exclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    document_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel_partner: Mapped["ChannelPartner"] = relationship("ChannelPartner", back_populates="project_agreements")
    __table_args__ = (
        UniqueConstraint("channel_partner_id", "project_id", name="uq_cp_project_agreement"),
        Index("ix_cp_agreement_project", "project_id", "is_active"),
        Index("ix_cp_agreement_org", "organization_id"),
    )


# ---------------------------------------------------------------------------
# 12. ChannelPartnerCommission (immutable ledger record)
# ---------------------------------------------------------------------------

class ChannelPartnerCommission(Base, TimestampMixin):
    __tablename__ = "cp_commissions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    channel_partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_partners.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("project_units.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_value: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    commission_pct: Mapped[Decimal] = mapped_column(PctType, nullable=False)
    commission_amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    gst_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    tds_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    net_payable: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel_partner: Mapped["ChannelPartner"] = relationship("ChannelPartner", back_populates="commission_records")
    __table_args__ = (
        Index("ix_cp_commission_cp_status", "channel_partner_id", "payment_status"),
        Index("ix_cp_commission_org", "organization_id"),
        Index("ix_cp_commission_deal", "deal_id"),
    )


# ---------------------------------------------------------------------------
# 13. InventoryAvailabilitySnapshot (read-optimized denormalized cache)
# ---------------------------------------------------------------------------

class InventoryAvailabilitySnapshot(Base, TimestampMixin):
    """Denormalized availability snapshot per project — read cache, not source of truth."""
    __tablename__ = "inventory_availability_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("real_estate_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    total_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    booked_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sold_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    under_offer_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    by_unit_type: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    by_phase: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    price_range_available: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    __table_args__ = (
        Index("ix_inv_snapshot_project_at", "project_id", "snapshot_at"),
        Index("ix_inv_snapshot_org", "organization_id"),
    )
