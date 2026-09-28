"""
WefyLabs Master Build 13 — Canonical Billing, Pricing, Usage & Entitlement Domain Models
=======================================================================================
Enterprise financial architecture for WefyLabs Revenue OS:
- Tenant-isolated by organization_id across all tenant-owned entities.
- Zero floating-point monetary columns: Numeric(20, 4) or integer minor units only.
- Immutable append-only ledgers for UsageEvent, CreditLedgerEntry, CostEvent, and BillingEvent.
- Plan versioning: Historical plan versions are immutable once active subscriptions reference them.
- Idempotency guarantees on external provider events, usage events, and financial adjustments.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKey, func, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)
PctType = Numeric(precision=7, scale=4)


# ─── Canonical Enums ─────────────────────────────────────────────────────────

class BillingAccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class PlanInterval(str, Enum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"
    CUSTOM = "CUSTOM"
    ONE_TIME = "ONE_TIME"


class EntitlementType(str, Enum):
    BOOLEAN = "BOOLEAN"
    INTEGER_LIMIT = "INTEGER_LIMIT"
    UNLIMITED = "UNLIMITED"
    USAGE_LIMIT = "USAGE_LIMIT"
    FEATURE_ACCESS = "FEATURE_ACCESS"
    SEAT_LIMIT = "SEAT_LIMIT"
    RATE_LIMIT = "RATE_LIMIT"
    AI_TOKEN_LIMIT = "AI_TOKEN_LIMIT"
    MESSAGE_LIMIT = "MESSAGE_LIMIT"
    PROPERTY_LIMIT = "PROPERTY_LIMIT"
    LEAD_LIMIT = "LEAD_LIMIT"
    EXPORT_LIMIT = "EXPORT_LIMIT"
    AUTOMATION_LIMIT = "AUTOMATION_LIMIT"
    STORAGE_LIMIT = "STORAGE_LIMIT"


class SubscriptionLifecycleStatus(str, Enum):
    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    PAUSED = "PAUSED"
    CANCEL_AT_PERIOD_END = "CANCEL_AT_PERIOD_END"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class MeterAggregationType(str, Enum):
    COUNT = "COUNT"
    SUM = "SUM"
    MAX = "MAX"
    UNIQUE = "UNIQUE"
    DURATION = "DURATION"
    TOKEN_COUNT = "TOKEN_COUNT"
    GB_DAY = "GB_DAY"


class BillingPeriodStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    INVOICED = "INVOICED"


class CanonicalInvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAST_DUE = "PAST_DUE"
    VOID = "VOID"
    UNCOLLECTIBLE = "UNCOLLECTIBLE"
    REFUNDED = "REFUNDED"


class CreditEntryType(str, Enum):
    CREDIT_ISSUED = "CREDIT_ISSUED"
    CREDIT_APPLIED = "CREDIT_APPLIED"
    CREDIT_EXPIRED = "CREDIT_EXPIRED"
    CREDIT_REVERSED = "CREDIT_REVERSED"


class AdjustmentType(str, Enum):
    DISCOUNT = "DISCOUNT"
    COURTESY = "COURTESY"
    CORRECTION = "CORRECTION"
    PROMOTION = "PROMOTION"
    WRITE_OFF = "WRITE_OFF"


class LimitEnforcementPolicy(str, Enum):
    HARD_LIMIT = "HARD_LIMIT"
    SOFT_LIMIT = "SOFT_LIMIT"
    OVERAGE = "OVERAGE"
    GRACE = "GRACE"
    UNLIMITED = "UNLIMITED"


# ─── 1. BILLING ACCOUNT & CUSTOMER ──────────────────────────────────────────

class BillingCustomer(Base, TimestampMixin):
    """
    Billing identity for customer contact and legal entity representation.
    """
    __tablename__ = "billing_customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tax_identifier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # GSTIN, VAT, EIN
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    billing_accounts: Mapped[List["BillingAccount"]] = relationship("BillingAccount", back_populates="customer")


class BillingAccount(Base, TimestampMixin):
    """
    Canonical Tenant Billing Account.
    Authoritative state of the organization's commercial standing with WefyLabs.
    """
    __tablename__ = "billing_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    billing_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_customers.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="razorpay", nullable=False)  # razorpay, stripe, etc.
    provider_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=BillingAccountStatus.ACTIVE.value, nullable=False, index=True
    )
    default_payment_method_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tax_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    customer: Mapped[Optional["BillingCustomer"]] = relationship("BillingCustomer", back_populates="billing_accounts")
    subscriptions: Mapped[List["CanonicalSubscription"]] = relationship("CanonicalSubscription", back_populates="billing_account")
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="billing_account")


# ─── 2. PRODUCT CATALOG & PLANS ──────────────────────────────────────────────

class Plan(Base, TimestampMixin):
    """
    Canonical Product Plan (e.g. FREE, STARTER, PRO, ENTERPRISE).
    """
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    versions: Mapped[List["PlanVersion"]] = relationship("PlanVersion", back_populates="plan", lazy="selectin")


class PlanVersion(Base, TimestampMixin):
    """
    Versioned commercial parameters of a plan.
    Immutable once assigned to an active customer subscription.
    """
    __tablename__ = "plan_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    interval: Mapped[str] = mapped_column(String(20), default=PlanInterval.MONTHLY.value, nullable=False)
    price: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)  # in major units (e.g. 2999.00)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["Plan"] = relationship("Plan", back_populates="versions")
    entitlements: Mapped[List["PlanEntitlement"]] = relationship("PlanEntitlement", back_populates="plan_version", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("plan_id", "version", "interval", name="uq_plan_version_interval"),
    )


class PlanEntitlement(Base, TimestampMixin):
    """
    Entitlements and quota rules attached to a PlanVersion.
    """
    __tablename__ = "plan_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entitlement_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entitlement_type: Mapped[str] = mapped_column(String(50), nullable=False)  # EntitlementType
    limit_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL for unlimited/boolean
    boolean_value: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    enforcement_policy: Mapped[str] = mapped_column(
        String(50), default=LimitEnforcementPolicy.HARD_LIMIT.value, nullable=False
    )
    overage_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overage_unit_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    reset_period: Mapped[str] = mapped_column(String(20), default="MONTHLY", nullable=False)

    plan_version: Mapped["PlanVersion"] = relationship("PlanVersion", back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint("plan_version_id", "entitlement_key", name="uq_plan_version_entitlement"),
    )


# ─── 3. SUBSCRIPTIONS & ITEMS ────────────────────────────────────────────────

class CanonicalSubscription(Base, TimestampMixin):
    """
    Authoritative Organization Subscription.
    Governs plan version, billing cycle, period dates, and lifecycle states.
    """
    __tablename__ = "canonical_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    billing_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default=SubscriptionLifecycleStatus.TRIALING.value, nullable=False, index=True
    )
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    billing_account: Mapped["BillingAccount"] = relationship("BillingAccount", back_populates="subscriptions")
    plan_version: Mapped["PlanVersion"] = relationship("PlanVersion", lazy="selectin")
    items: Mapped[List["SubscriptionItem"]] = relationship("SubscriptionItem", back_populates="subscription", lazy="selectin")
    billing_periods: Mapped[List["BillingPeriod"]] = relationship("BillingPeriod", back_populates="subscription", lazy="selectin")


class SubscriptionItem(Base, TimestampMixin):
    """
    Add-ons, extra seats, or custom line items bound to a subscription.
    """
    __tablename__ = "subscription_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(String(50), default="SEAT", nullable=False)  # SEAT, ADDON, METER
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    subscription: Mapped["CanonicalSubscription"] = relationship("CanonicalSubscription", back_populates="items")


# ─── 4. BILLING PERIOD ───────────────────────────────────────────────────────

class BillingPeriod(Base, TimestampMixin):
    """
    Non-overlapping discrete billing cycle for usage metering and invoicing.
    """
    __tablename__ = "billing_periods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), default=BillingPeriodStatus.OPEN.value, nullable=False, index=True
    )

    subscription: Mapped["CanonicalSubscription"] = relationship("CanonicalSubscription", back_populates="billing_periods")
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="billing_period")

    __table_args__ = (
        UniqueConstraint("organization_id", "subscription_id", "period_start", "period_end", name="uq_billing_period_org_sub"),
    )


# ─── 5. USAGE METERS, IMMUTABLE EVENTS & AGGREGATES ─────────────────────────

class UsageMeter(Base, TimestampMixin):
    """
    Definition of a billable/metered product metric (AI requests, WhatsApp messages, etc).
    """
    __tablename__ = "usage_meters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)  # tokens, messages, requests, gb_day
    aggregation_type: Mapped[str] = mapped_column(
        String(50), default=MeterAggregationType.COUNT.value, nullable=False
    )
    source_event: Mapped[str] = mapped_column(String(100), nullable=False)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reset_policy: Mapped[str] = mapped_column(String(50), default="BILLING_PERIOD", nullable=False)


class UsageEvent(Base):
    """
    Immutable append-only usage ingestion event.
    Deduplicated via unique idempotency_key per organization.
    """
    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    meter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usage_meters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AI_GATEWAY, WHATSAPP, WORKFLOW
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    billing_period_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_usage_event_org_idemp"),
        Index("ix_usage_events_org_meter_time", "organization_id", "meter_id", "occurred_at"),
    )


class UsageAggregate(Base, TimestampMixin):
    """
    Durable rollup aggregation of raw usage events for billing and quota checks.
    """
    __tablename__ = "usage_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    meter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usage_meters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    billing_period_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=4), default=Decimal("0.0"), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    last_aggregated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "meter_id", "billing_period_id", name="uq_usage_agg_org_meter_period"),
        Index("ix_usage_agg_org_period", "organization_id", "period_start", "period_end"),
    )


# ─── 6. INVOICES & INVOICE LINES ─────────────────────────────────────────────

class Invoice(Base, TimestampMixin):
    """
    Authoritative Invoice Record.
    All monetary calculations are recomputable from lines, discounts, taxes, and credits.
    """
    __tablename__ = "canonical_invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    billing_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    billing_period_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), default=CanonicalInvoiceStatus.DRAFT.value, nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    subtotal: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    amount_due: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)

    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    billing_account: Mapped["BillingAccount"] = relationship("BillingAccount", back_populates="invoices")
    billing_period: Mapped[Optional["BillingPeriod"]] = relationship("BillingPeriod", back_populates="invoices")
    lines: Mapped[List["InvoiceLine"]] = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")
    credit_notes: Mapped[List["CreditNote"]] = relationship("CreditNote", back_populates="invoice")


class InvoiceLine(Base, TimestampMixin):
    """
    Discrete line item of an invoice with full provenance.
    """
    __tablename__ = "canonical_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=4), default=Decimal("1.0"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    discount: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    plan_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_versions.id", ondelete="SET NULL"), nullable=True
    )
    meter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usage_meters.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # PLAN, USAGE, AD_HOC
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")


# ─── 7. CREDITS & ADJUSTMENTS LEDGER ─────────────────────────────────────────

class CreditBalance(Base, TimestampMixin):
    """
    Cached organization credit balance.
    The CreditLedgerEntry append-only ledger remains the authoritative source of truth.
    """
    __tablename__ = "credit_balances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    balance: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "currency", name="uq_credit_balance_org_curr"),
    )


class CreditLedgerEntry(Base):
    """
    Append-only financial credit ledger.
    Every credit modification has immutable provenance, reason, and actor.
    """
    __tablename__ = "credit_ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # CreditEntryType
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # INVOICE, REFUND, PROMOTION
    reference_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )


class CreditNote(Base, TimestampMixin):
    """
    Commercial credit note issued against an invoice.
    """
    __tablename__ = "credit_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    credit_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ISSUED", nullable=False)
    reason: Mapped[Text] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="credit_notes")


class BillingAdjustment(Base, TimestampMixin):
    """
    Explicit manual or automated adjustment applied to an invoice or account balance.
    """
    __tablename__ = "billing_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    adjustment_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AdjustmentType
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


# ─── 8. ENTITLEMENT GRANTS & CONSUMPTION ─────────────────────────────────────

class EntitlementGrant(Base, TimestampMixin):
    """
    Custom or override entitlement granted to a specific organization.
    """
    __tablename__ = "entitlement_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entitlement_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    limit_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    boolean_value: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="MANUAL_OVERRIDE", nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EntitlementConsumption(Base):
    """
    Deterministic ledger of pre-action entitlement reservations and consumptions.
    """
    __tablename__ = "entitlement_consumptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entitlement_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    billing_period_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    action_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


# ─── 9. COST LEDGER & UNIT ECONOMICS ─────────────────────────────────────────

class CostEvent(Base):
    """
    Immutable ledger of internal direct variable costs incurred by WefyLabs for an organization.
    (AI tokens, WhatsApp messages, compute, SMS, email, storage, payment processing fees).
    """
    __tablename__ = "cost_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # AI, WHATSAPP, PAYMENT_FEES, STORAGE
    vendor: Mapped[str] = mapped_column(String(50), nullable=False)  # OPENAI, ANTHROPIC, META, RAZORPAY, AWS
    unit: Mapped[str] = mapped_column(String(50), nullable=False)  # TOKENS, MESSAGES, TRANSACTIONS, GB_DAY
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # request_id, message_id
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_cost_events_org_service_time", "organization_id", "service", "occurred_at"),
    )


class UnitEconomicsSnapshot(Base, TimestampMixin):
    """
    Computed unit economics snapshot per organization for a given time window.
    Strictly derived from actual Invoices, Payments, Refunds, and CostEvents.
    """
    __tablename__ = "unit_economics_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    mrr: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    arr: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    gross_revenue: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    net_revenue: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    refunds: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    credits: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)

    payment_fees: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    ai_cost: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    messaging_cost: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    storage_cost: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    other_cost: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    total_variable_cost: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)

    gross_profit: Mapped[Decimal] = mapped_column(MoneyType, default=Decimal("0.0"), nullable=False)
    gross_margin_pct: Mapped[Decimal] = mapped_column(PctType, default=Decimal("0.0"), nullable=False)

    cac: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    ltv: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    data_quality_notes: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_unit_econ_snapshot_org_period", "organization_id", "period_start", "period_end"),
    )


# Convenience aliases for internal module code
Subscription = CanonicalSubscription
CanonicalInvoice = Invoice
