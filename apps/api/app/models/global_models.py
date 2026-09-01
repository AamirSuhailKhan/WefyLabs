"""
Volume 2 Part 14 — Global Multi-Country Infrastructure & Localization Engine
Database Models

Architecture Principle: Core application must remain country-agnostic.
All country/market-specific behavior is driven by configuration from these models.
NEVER add `if country == "IN": ...` in application code.
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Integer, Date, DateTime, ForeignKey,
    JSON, Text, UniqueConstraint, Index, Numeric, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")
NumericType = Numeric(precision=20, scale=8)  # Decimal-safe — NEVER use Float for money


# ─────────────────────────────────────────────────────────────────────────────
# COUNTRY & MARKET REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class Country(Base, TimestampMixin):
    """
    Canonical global country registry.
    A country must be in ACTIVE status before organizations can operate within it.
    NEVER hardcode country logic — always resolve from this registry.
    """
    __tablename__ = "countries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso_alpha2: Mapped[str] = mapped_column(String(2), unique=True, nullable=False, index=True)   # "IN", "AE"
    iso_alpha3: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)               # "IND", "ARE"
    numeric_code: Mapped[str] = mapped_column(String(3), nullable=False)                          # "356", "784"
    name: Mapped[str] = mapped_column(String(100), nullable=False)                                # "India"
    native_name: Mapped[str] = mapped_column(String(100), nullable=False)                         # "भारत"
    flag_emoji: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Currency
    default_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)                # "INR"
    supported_currency_codes: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)

    # Timezone
    default_timezone: Mapped[str] = mapped_column(String(100), nullable=False)                   # "Asia/Kolkata"
    supported_timezones: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)

    # Language & Locale
    default_language_code: Mapped[str] = mapped_column(String(10), nullable=False)               # "en"
    supported_language_codes: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    is_rtl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    date_format: Mapped[str] = mapped_column(String(20), default="DD/MM/YYYY", nullable=False)

    # Phone & Address
    phone_country_code: Mapped[str] = mapped_column(String(6), nullable=False)                   # "+91"
    address_format: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)              # structured format template

    # Launch Control
    # PLANNED → BETA → ACTIVE → SUSPENDED → DEPRECATED
    launch_status: Mapped[str] = mapped_column(String(20), default="PLANNED", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Extensible metadata (compliance framework names, payment gateways, portals)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    markets: Mapped[List["Market"]] = relationship("Market", back_populates="country", cascade="all, delete-orphan")
    configuration_versions: Mapped[List["CountryConfigurationVersion"]] = relationship(
        "CountryConfigurationVersion", back_populates="country", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_countries_launch_status", "launch_status"),
    )


class Market(Base, TimestampMixin):
    """
    Sub-country geographic/market unit.
    A country may contain multiple markets, each with distinct configuration.
    Example: UAE → Dubai, Abu Dhabi, Sharjah
             India → Delhi NCR, Mumbai, Bangalore
    """
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)             # "Dubai"
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)  # "dubai"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)    # "Dubai, UAE"

    # Locale (may differ from country default)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)        # "Asia/Dubai"
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)     # "AED"
    language_codes: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)  # ["en", "ar"]

    # Business rules
    # weekend_days: 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
    # UAE: [4, 5] = Fri/Sat; India/UK: [5, 6] = Sat/Sun
    weekend_days: Mapped[list] = mapped_column(JSONBType, default=lambda: [5, 6], nullable=False)
    business_hours: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)   # {mon: {start: "09:00", end: "18:00"}}

    # Market-specific configuration
    property_type_codes: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    lead_source_codes: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)

    # Launch Control
    launch_status: Mapped[str] = mapped_column(String(20), default="PLANNED", nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    country: Mapped["Country"] = relationship("Country", back_populates="markets")
    configurations: Mapped[List["MarketConfiguration"]] = relationship(
        "MarketConfiguration", back_populates="market", cascade="all, delete-orphan"
    )
    rollouts: Mapped[List["MarketRollout"]] = relationship(
        "MarketRollout", back_populates="market", cascade="all, delete-orphan"
    )


class MarketConfiguration(Base, TimestampMixin):
    """
    Versioned configuration binding an organization to a market.
    Overrides can specify provider preferences, SLA rules, business rules.
    Historical versions are preserved — never silently change behavior.
    """
    __tablename__ = "market_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)  # Provider overrides, SLA, etc.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    market: Mapped["Market"] = relationship("Market", back_populates="configurations")

    __table_args__ = (
        Index("ix_market_config_org_market", "organization_id", "market_id"),
    )


class CountryConfigurationVersion(Base):
    """
    Immutable audit trail of country-level configuration changes.
    Historical records must not be reinterpreted after config changes.
    """
    __tablename__ = "country_configuration_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    config_snapshot: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    changed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # actor user ID
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        server_default=func.now(), nullable=False
    )

    country: Mapped["Country"] = relationship("Country", back_populates="configuration_versions")


# ─────────────────────────────────────────────────────────────────────────────
# CURRENCY & EXCHANGE RATES
# All monetary values use Decimal (NUMERIC 20,8) — NEVER Python float for finance
# ─────────────────────────────────────────────────────────────────────────────

class Currency(Base, TimestampMixin):
    """
    Persistent currency registry — the authoritative source.
    Do NOT hardcode currency lists in application code.
    """
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)         # "AED", "INR"
    name: Mapped[str] = mapped_column(String(100), nullable=False)          # "UAE Dirham"
    native_name: Mapped[str] = mapped_column(String(100), nullable=False)   # "درهم"
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)         # "AED"
    symbol_native: Mapped[str] = mapped_column(String(10), nullable=False)  # "د.إ"
    decimal_digits: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    rounding: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_unit: Mapped[str] = mapped_column(
        String(30), default="standard", nullable=False
    )  # "standard" | "lakhs_crores" | "millions_billions"


class ExchangeRate(Base, TimestampMixin):
    """
    Current FX rate per currency pair per type.
    NEVER use Python float — uses NUMERIC(20,8) for Decimal precision.
    If FX is unavailable: return FX_UNAVAILABLE, never silently use 1:1.
    """
    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    # NUMERIC — Decimal-safe. Never store as Float.
    rate: Mapped[Decimal] = mapped_column(NumericType, nullable=False)
    # MARKET | ORGANIZATION | MANUAL | HISTORICAL
    rate_type: Mapped[str] = mapped_column(String(20), default="MARKET", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)       # "open_exchange" | "fixer" | "manual"
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_fx_base_quote_active", "base_currency", "quote_currency", "is_active"),
    )


class ExchangeRateSnapshot(Base):
    """
    Day-level historical FX snapshot for financial reporting.
    Historical reports MUST use the rate from the date the transaction occurred.
    """
    __tablename__ = "exchange_rate_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(NumericType, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("base_currency", "quote_currency", "snapshot_date", "provider",
                         name="uq_fx_snapshot_date"),
        Index("ix_fx_snapshot_lookup", "base_currency", "quote_currency", "snapshot_date"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# TIMEZONE, BUSINESS HOURS & HOLIDAYS
# ─────────────────────────────────────────────────────────────────────────────

class HolidayCalendar(Base, TimestampMixin):
    """
    Versioned holiday calendar for a country, market, or organization.
    null organization_id = system calendar (applies to all orgs unless overridden).
    Calendars are versioned — changing them does not affect historical scheduling.
    """
    __tablename__ = "holiday_calendars"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    country_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)           # "UAE Public Holidays 2026"
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    holidays: Mapped[List["Holiday"]] = relationship("Holiday", back_populates="calendar", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_holiday_calendar_lookup", "market_id", "year", "is_active"),
        Index("ix_holiday_calendar_org", "organization_id", "year"),
    )


class Holiday(Base):
    """
    Individual holiday entry. Supports full-day and recurring annual holidays.
    """
    __tablename__ = "holidays"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("holiday_calendars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)           # "Eid Al Fitr"
    name_native: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_full_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_recurring_annual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    calendar: Mapped["HolidayCalendar"] = relationship("HolidayCalendar", back_populates="holidays")


# ─────────────────────────────────────────────────────────────────────────────
# LOCALIZATION & TRANSLATION
# ─────────────────────────────────────────────────────────────────────────────

class Translation(Base, TimestampMixin):
    """
    Database-backed translation system.
    Fallback chain: ar-AE → ar → en. Never display raw translation keys or 'undefined'.

    Namespaces: common | crm | leads | properties | calendar | billing |
                workflow | analytics | ai | errors | notifications
    """
    __tablename__ = "translations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    namespace: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # "common", "crm"
    translation_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, index=True)     # "en-AE", "ar-AE"
    value: Mapped[str] = mapped_column(Text, nullable=False)
    fallback_locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # "en"
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # active | draft | deprecated
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("namespace", "translation_key", "locale", name="uq_translation_key_locale"),
        Index("ix_translation_lookup", "namespace", "locale", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROPERTY SCHEMA REGISTRY
# Replaces hardcoded ('1bhk', '2bhk', 'villa', 'plot') CheckConstraint
# ─────────────────────────────────────────────────────────────────────────────

class PropertySchema(Base, TimestampMixin):
    """
    Market-specific extensible property schema.
    Replaces the hardcoded property_type constraint in the Lead and Property models.
    Country-specific fields (RERA, DLD, tenure) live as PropertyField records.
    """
    __tablename__ = "property_schemas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    country_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="CASCADE"), nullable=True, index=True
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "UAE Residential Schema v2"
    # Canonical property type codes for this schema
    # e.g. ["apartment", "villa", "studio", "penthouse", "townhouse"]
    property_type_codes: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    # Canonical area units accepted: ["sqft", "sqm", "sqyd", "marla", "kanal"]
    area_units: Mapped[list] = mapped_column(JSONBType, default=lambda: ["sqft", "sqm"], nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    fields: Mapped[List["PropertyField"]] = relationship(
        "PropertyField", back_populates="schema", cascade="all, delete-orphan"
    )


class PropertyField(Base, TimestampMixin):
    """
    Country/market-specific property field definition.
    Examples:
      UAE: rera_permit_number (required), dld_reference, developer_name
      India: rera_project_id, carpet_area_sqft
      UK: tenure (freehold/leasehold), council_tax_band
      US: mls_number, hoa_fees_monthly
    """
    __tablename__ = "property_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("property_schemas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)      # "rera_permit_number"
    field_label: Mapped[str] = mapped_column(String(100), nullable=False)    # "RERA Permit No."
    # text | number | date | boolean | select | multi_select | json
    field_type: Mapped[str] = mapped_column(String(30), nullable=False)
    select_options: Mapped[Optional[list]] = mapped_column(JSONBType, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_rules: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    is_searchable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    schema: Mapped["PropertySchema"] = relationship("PropertySchema", back_populates="fields")


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER CONFIGURATION & HEALTH
# ─────────────────────────────────────────────────────────────────────────────

class ProviderConfiguration(Base, TimestampMixin):
    """
    Per-organization provider configuration.
    Secret credentials are stored in vault/secrets manager — only the reference is stored here.
    Core services must NEVER import provider SDKs directly — always go through the adapter.
    """
    __tablename__ = "provider_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # PAYMENT | WHATSAPP | SMS | EMAIL | CALENDAR | FX | KYC | LEAD_SOURCE | ENRICHMENT
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # razorpay | stripe | tap | 360dialog | twilio | meta_direct | sendgrid | ses
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    # 1 = primary, 2 = secondary, 3 = fallback
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Non-secret configuration (phone_number_id, WABA_ID, etc.)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    # Reference to vault secret (e.g. "vault://org_id/whatsapp/360dialog_key")
    secret_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    health: Mapped[Optional["ProviderHealth"]] = relationship(
        "ProviderHealth", back_populates="provider_config", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_provider_config_org_type", "organization_id", "provider_type", "is_active"),
    )


class ProviderHealth(Base, TimestampMixin):
    """
    Live health monitoring state for a provider.
    Never expose provider secrets — only health metrics.
    """
    __tablename__ = "provider_health"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_configurations.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    # HEALTHY | WARNING | DEGRADED | FAILED
    status: Mapped[str] = mapped_column(String(20), default="HEALTHY", nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_count_1h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count_1h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    provider_config: Mapped["ProviderConfiguration"] = relationship(
        "ProviderConfiguration", back_populates="health"
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE POLICIES & CONSENT
# ─────────────────────────────────────────────────────────────────────────────

class CompliancePolicy(Base, TimestampMixin):
    """
    Configurable and versioned compliance policy.
    Evaluated by PolicyService.evaluate() before any regulated action.
    scope: null org_id = global default; null market_id = country-level; all filled = org+market specific.
    """
    __tablename__ = "compliance_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    country_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # COMMUNICATION | CONSENT | DATA_RETENTION | KYC | AI_ACTION | MARKETING | DATA_RESIDENCY
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    policy_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rule_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # ACTIVE | DRAFT | EXPIRED
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_policy_lookup", "category", "policy_key", "status"),
        Index("ix_policy_org_market", "organization_id", "market_id", "category"),
    )


class ConsentRecord(Base, TimestampMixin):
    """
    Per-lead, per-channel consent tracking.
    Consent must NEVER be assumed from lead existence.
    Communication services check ConsentService before dispatch.
    """
    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # WHATSAPP | SMS | EMAIL | VOICE | PUSH
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # GRANTED | DENIED | WITHDRAWN | EXPIRED
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)         # "marketing" | "transactional"
    # FORM | IMPORT | EXPLICIT | API | INFERRED
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "lead_id", "channel", "purpose",
                         name="uq_consent_lead_channel_purpose"),
        Index("ix_consent_lead_channel", "lead_id", "channel", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DATA RESIDENCY
# ─────────────────────────────────────────────────────────────────────────────

class DataResidencyPolicy(Base, TimestampMixin):
    """
    Per-organization data residency configuration.
    Enforcement occurs server-side via RegionRouter + TenantRegionResolver.
    NEVER merely hide country in the UI — enforce at infrastructure level.
    """
    __tablename__ = "data_residency_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    # india | middle-east | europe | north-america | apac
    primary_region: Mapped[str] = mapped_column(String(50), nullable=False)
    backup_region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # List of region codes where processing is allowed
    allowed_processing_regions: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    # Restrictions on specific data categories
    sensitive_data_restrictions: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# REGIONAL PIPELINES
# Replaces hardcoded ('new', 'contacted', 'viewing', ...) CheckConstraint
# ─────────────────────────────────────────────────────────────────────────────

class RegionalPipeline(Base, TimestampMixin):
    """
    Market-configurable pipeline template.
    Different markets have different stage names and transitions.
    UAE: New → Qualified → Viewing → Offer → Reservation → Closed
    India: New → Qualified → Site Visit → Negotiation → Booked
    """
    __tablename__ = "regional_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    country_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)            # "UAE Standard Pipeline"
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stages: Mapped[List["RegionalPipelineStage"]] = relationship(
        "RegionalPipelineStage", back_populates="pipeline",
        cascade="all, delete-orphan", order_by="RegionalPipelineStage.order_index"
    )


class RegionalPipelineStage(Base, TimestampMixin):
    """Individual stage within a regional pipeline."""
    __tablename__ = "regional_pipeline_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regional_pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_key: Mapped[str] = mapped_column(String(50), nullable=False)        # "site_visit", "viewing"
    stage_label: Mapped[str] = mapped_column(String(100), nullable=False)     # "Site Visit", "Viewing"
    stage_label_native: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Arabic/Hindi label
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_next_stage_keys: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    required_field_keys: Mapped[list] = mapped_column(JSONBType, default=list, nullable=False)
    sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    forecast_weight: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    # closed_won | closed_lost | open
    stage_type: Mapped[str] = mapped_column(String(20), default="open", nullable=False)

    pipeline: Mapped["RegionalPipeline"] = relationship("RegionalPipeline", back_populates="stages")


# ─────────────────────────────────────────────────────────────────────────────
# MARKET FEATURE FLAGS & ROLLOUT
# ─────────────────────────────────────────────────────────────────────────────

class MarketFeatureFlag(Base, TimestampMixin):
    """
    Per-organization, per-market feature toggles.
    Examples: ai.voice, communication.whatsapp, property.advanced-filters
    NEVER hardcode country behavior — always check feature flags.
    """
    __tablename__ = "market_feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    flag_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rollout_percentage: Mapped[int] = mapped_column(Integer, default=100, nullable=False)  # 0-100

    __table_args__ = (
        UniqueConstraint("organization_id", "market_id", "flag_key", name="uq_market_flag"),
    )


class MarketRollout(Base, TimestampMixin):
    """
    Market rollout state machine per organization.
    Controls gradual market activation: INTERNAL → BETA → LIMITED → GENERAL → SUSPENDED
    A market must complete the activation checklist before going GENERAL.
    """
    __tablename__ = "market_rollouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # INTERNAL | BETA | LIMITED | GENERAL | SUSPENDED
    rollout_status: Mapped[str] = mapped_column(String(20), default="INTERNAL", nullable=False, index=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Tracks completion of each checklist item
    # {"currency": true, "timezone": true, "providers": false, ...}
    checklist_completed: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    market: Mapped["Market"] = relationship("Market", back_populates="rollouts")

    __table_args__ = (
        UniqueConstraint("organization_id", "market_id", name="uq_market_rollout_org_market"),
        Index("ix_rollout_org_status", "organization_id", "rollout_status"),
    )
