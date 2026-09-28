"""
Build 09 — WefyLabs Revenue Intelligence OS
============================================
Canonical models for the Revenue Intelligence, Attribution, Forecasting,
Leakage Detection, and Unit Economics system.

Design principles (absolute):
- NEVER use Float for monetary values — all money is Numeric(20, 4)
- Every model is tenant-isolated via organization_id
- Attribution touchpoints are immutable once recorded
- Forecast snapshots are immutable (never update historical rows)
- Leakage events are append-only
- Anomaly records are append-only; resolved via resolution_at field
- Metric definitions are versioned; formula changes create new versions
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)
PctType   = Numeric(precision=7, scale=4)


# ---------------------------------------------------------------------------
# CONTROLLED VOCABULARIES
# ---------------------------------------------------------------------------

class AttributionModel:
    FIRST_TOUCH     = "FIRST_TOUCH"
    LAST_TOUCH      = "LAST_TOUCH"
    LINEAR          = "LINEAR"
    TIME_DECAY      = "TIME_DECAY"
    POSITION_BASED  = "POSITION_BASED"
    ALL = [FIRST_TOUCH, LAST_TOUCH, LINEAR, TIME_DECAY, POSITION_BASED]


class TouchChannel:
    META_ADS    = "META_ADS"
    GOOGLE_ADS  = "GOOGLE_ADS"
    INDIA_MART  = "INDIA_MART"
    ACRES99     = "99ACRES"
    WEBSITE     = "WEBSITE"
    WHATSAPP    = "WHATSAPP"
    EMAIL       = "EMAIL"
    ORGANIC     = "ORGANIC"
    REFERRAL    = "REFERRAL"
    AGENT       = "AGENT"
    DIRECT      = "DIRECT"
    UNKNOWN     = "UNKNOWN"


class ForecastMethod:
    STAGE_WEIGHTED        = "stage_weighted"
    HISTORICAL_CONVERSION = "historical_conversion"
    MOVING_AVERAGE        = "moving_average"
    PIPELINE_VELOCITY     = "pipeline_velocity"


class ForecastPeriod:
    DAY     = "DAY"
    WEEK    = "WEEK"
    MONTH   = "MONTH"
    QUARTER = "QUARTER"


class ForecastQuality:
    GOOD     = "GOOD"
    LIMITED  = "LIMITED"      # important inputs missing
    UNKNOWN  = "UNKNOWN"


class LeakageCondition:
    LEAD_NO_RESPONSE            = "LEAD_NO_RESPONSE"
    QUALIFIED_NO_PROPERTY       = "QUALIFIED_NO_PROPERTY"
    PROPERTY_NO_FOLLOWUP        = "PROPERTY_NO_FOLLOWUP"
    APPOINTMENT_NO_CONFIRMATION = "APPOINTMENT_NO_CONFIRMATION"
    SITE_VISIT_NO_OUTCOME       = "SITE_VISIT_NO_OUTCOME"
    OPPORTUNITY_NO_NEXT_ACTION  = "OPPORTUNITY_NO_NEXT_ACTION"
    NEGOTIATION_STALLED         = "NEGOTIATION_STALLED"
    BOOKING_INTENT_NO_HOLD      = "BOOKING_INTENT_NO_HOLD"
    HOLD_EXPIRING               = "HOLD_EXPIRING"
    BOOKING_NO_PAYMENT          = "BOOKING_NO_PAYMENT"
    PAYMENT_NO_BOOKING          = "PAYMENT_NO_BOOKING"
    BOOKING_NO_REVENUE_EVENT    = "BOOKING_NO_REVENUE_EVENT"


class LeakageSeverity:
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"


class AnomalyMetric:
    BOOKING_COUNT     = "booking_count"
    BOOKING_VALUE     = "booking_value"
    PAYMENT_AMOUNT    = "payment_amount"
    REFUND_AMOUNT     = "refund_amount"
    LEAD_VOLUME       = "lead_volume"
    CONVERSION_RATE   = "conversion_rate"
    PAYMENT_FAILURE   = "payment_failure"


class AIContributionCategory:
    AI_TOUCHED   = "AI_TOUCHED"    # AI participated at any point
    AI_ASSISTED  = "AI_ASSISTED"   # AI contributed a meaningful action
    AI_INFLUENCED = "AI_INFLUENCED" # AI influenced a decision (evidence required)
    AI_EXECUTED  = "AI_EXECUTED"   # AI was the primary executor
    HUMAN_ONLY   = "HUMAN_ONLY"    # No AI participation
    UNKNOWN      = "UNKNOWN"


class DataQualityDimension:
    EVENT_COMPLETENESS       = "event_completeness"
    FINANCIAL_COMPLETENESS   = "financial_completeness"
    ATTRIBUTION_COMPLETENESS = "attribution_completeness"
    FORECAST_COMPLETENESS    = "forecast_completeness"
    DATA_FRESHNESS           = "data_freshness"
    RECONCILIATION_HEALTH    = "reconciliation_health"


class ReconciliationDifference:
    MISSING_PAYMENT       = "MISSING_PAYMENT"
    MISSING_BOOKING       = "MISSING_BOOKING"
    MISSING_REVENUE_EVENT = "MISSING_REVENUE_EVENT"
    INVENTORY_MISMATCH    = "INVENTORY_MISMATCH"
    AMOUNT_MISMATCH       = "AMOUNT_MISMATCH"
    CURRENCY_MISMATCH     = "CURRENCY_MISMATCH"
    DUPLICATE_EVENT       = "DUPLICATE_EVENT"


# ---------------------------------------------------------------------------
# 1. ATTRIBUTION TOUCHPOINT
# ---------------------------------------------------------------------------

class AttributionTouchpoint(Base, TimestampMixin):
    """
    Immutable record of every marketing or sales touchpoint for a customer identity.

    Once written, this record MUST NOT be mutated.
    Attribution models (first-touch, last-touch, etc.) are computed FROM these records.

    Design:
    - Links to canonical Identity (Build 02) and Lead
    - Records the channel, source, campaign, and event that triggered the touch
    - Weight is populated by attribution calculation jobs (not on creation)
    - Supports configurable attribution windows via occurred_at comparisons
    """
    __tablename__ = "attribution_touchpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Canonical identity linkage (Build 02)
    identity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Touchpoint classification
    channel: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TouchChannel.UNKNOWN
    )
    source_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    campaign_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # What event triggered this touchpoint
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "meta_lead", "website_form", "whatsapp_inbound", "agent_call"

    # UTM parameters (from acquisition)
    utm_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Actor who triggered the touch (agent, system, etc)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="SYSTEM", nullable=False)

    # When the actual touchpoint occurred (immutable)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Attribution weight — populated by attribution calculation job
    # NULL until calculated; set per model_type
    weight_first_touch: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    weight_last_touch: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    weight_linear: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    weight_time_decay: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)
    weight_position_based: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)

    # Metadata payload
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    __table_args__ = (
        Index("ix_attr_touch_org_lead", "organization_id", "lead_id"),
        Index("ix_attr_touch_org_identity", "organization_id", "identity_id"),
        Index("ix_attr_touch_org_time", "organization_id", "occurred_at"),
        Index("ix_attr_touch_channel", "organization_id", "channel"),
    )


# ---------------------------------------------------------------------------
# 2. ATTRIBUTION RESULT
# ---------------------------------------------------------------------------

class AttributionResult(Base):
    """
    Computed attribution result for a booking / revenue event.

    One row per (revenue_event_id, attribution_model, model_version).
    Historical results are NEVER deleted. Model version changes create new rows.

    The calculation_inputs JSONB preserves the exact state of touchpoints
    used in this calculation for full reproducibility.
    """
    __tablename__ = "attribution_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Link to the revenue event being attributed
    revenue_event_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Attributed monetary value
    attributed_amount: Mapped[Optional[Decimal]] = mapped_column(
        MoneyType, nullable=True
    )
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # Attribution model used
    attribution_model: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1"
    )

    # Attribution window used (in days)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Number of touchpoints included
    touchpoint_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # First-touch and last-touch source (denormalized for query performance)
    first_touch_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    first_touch_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_touch_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_touch_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_touch_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_touch_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_touch_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_touch_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Touchpoint breakdown per source/channel (serialized list)
    touchpoint_breakdown: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    # Inputs used (snapshot of touchpoints at calculation time — for reproducibility)
    calculation_inputs: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "revenue_event_id", "attribution_model", "model_version",
            name="uq_attribution_result_event_model"
        ),
        Index("ix_attr_result_org_model", "organization_id", "attribution_model"),
        Index("ix_attr_result_event", "revenue_event_id"),
    )


# ---------------------------------------------------------------------------
# 3. FORECAST SNAPSHOT V2
# ---------------------------------------------------------------------------

class ForecastSnapshotV2(Base):
    """
    Immutable versioned forecast snapshot.

    Historical snapshots MUST NOT be mutated.
    Each snapshot captures: pipeline inputs, method, period, confidence, outputs.

    CRITICAL: All monetary values use Numeric(20, 4). Never Float.
    If inputs are incomplete, quality = LIMITED and a quality_notes field explains why.
    """
    __tablename__ = "forecast_snapshots_v2"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Period
    period_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # DAY / WEEK / MONTH / QUARTER
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    timezone_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC"
    )

    # Method
    method: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ForecastMethod.STAGE_WEIGHTED
    )
    method_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1"
    )

    # Scenario
    scenario: Mapped[str] = mapped_column(
        String(20), nullable=False, default="BASE"
    )  # BASE / UPSIDE / DOWNSIDE

    # Forecast values (all Numeric — NEVER Float)
    pipeline_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    weighted_pipeline: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    forecast_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    upside_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    downside_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)

    # Reporting currency
    reporting_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="AED"
    )

    # Confidence
    quality: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ForecastQuality.UNKNOWN
    )
    quality_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Opportunity inputs used
    opportunity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage_distribution: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )
    # Serialized list of probability assumptions used
    probability_assumptions: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )
    # Serialized snapshot of top opportunities included
    opportunity_ids_included: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=list, nullable=False
    )

    # Actuals (backfilled when the period closes)
    actual_revenue: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    actual_bookings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    forecast_error_pct: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Immutable flag: once actuals backfilled, is_reconciled = True
    is_reconciled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    __table_args__ = (
        Index("ix_forecast_v2_org_period", "organization_id", "period_start"),
        Index("ix_forecast_v2_org_method", "organization_id", "method"),
    )


# ---------------------------------------------------------------------------
# 4. REVENUE LEAKAGE EVENT V2
# ---------------------------------------------------------------------------

class RevenueLeakageEventV2(Base, TimestampMixin):
    """
    Append-only leakage event covering all Build 08 + Build 09 leakage conditions.

    Extends the Part 11 RevenueLeakageEvent with:
    - Full Build 08 opportunity / site visit / negotiation / booking states
    - estimated_value uses Numeric(20,4) — NOT Float
    - severity, age, owner, recommended_action
    - resolution tracking
    - cooldown suppression via last_suppressed_at

    This table is append-only. No updates to business data fields.
    Resolution writes resolution_at and resolution_action only.
    """
    __tablename__ = "revenue_leakage_events_v2"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Identity linkage
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    site_visit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    booking_intent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Leakage classification
    condition: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # LeakageCondition constants
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LeakageSeverity.MEDIUM, index=True
    )

    # Age of the stall in days
    age_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Revenue at risk — Numeric(20,4). NULL if value unknown.
    # Label as ESTIMATE in all API responses.
    estimated_value_at_risk: Mapped[Optional[Decimal]] = mapped_column(
        MoneyType, nullable=True
    )
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # Evidence (what triggered this detection)
    evidence: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    # Owner
    owner_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="AGENT"
    )

    # NBA linkage (Build 07)
    work_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Cooldown suppression
    last_suppressed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suppression_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Resolution
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    resolution_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_leakage_v2_org_condition", "organization_id", "condition"),
        Index("ix_leakage_v2_org_severity", "organization_id", "severity"),
        Index("ix_leakage_v2_org_detected", "organization_id", "detected_at"),
        Index("ix_leakage_v2_org_resolved", "organization_id", "is_resolved"),
    )


# ---------------------------------------------------------------------------
# 5. REVENUE ANOMALY
# ---------------------------------------------------------------------------

class RevenueAnomaly(Base, TimestampMixin):
    """
    Append-only record for detected revenue anomalies.

    Anomalies are detected by deterministic statistical rules, not ML.
    Resolution writes resolution_at; the anomaly row itself is never mutated.
    Duplicate anomalies for the same unresolved condition are suppressed.
    """
    __tablename__ = "revenue_anomalies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    metric: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # AnomalyMetric constants

    # Statistical detection evidence
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    observed_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    threshold_pct: Mapped[Optional[Decimal]] = mapped_column(PctType, nullable=True)

    period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LeakageSeverity.MEDIUM
    )

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    is_resolved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    resolution_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_anomaly_org_metric", "organization_id", "metric"),
        Index("ix_anomaly_org_detected", "organization_id", "detected_at"),
    )


# ---------------------------------------------------------------------------
# 6. METRIC DEFINITION (Revenue Semantics Registry)
# ---------------------------------------------------------------------------

class MetricDefinition(Base, TimestampMixin):
    """
    Canonical registry of all revenue metric definitions.

    Every metric shown in any dashboard MUST have an entry here.
    Formula changes create a new row (new metric_version).
    Historical reports reference metric_version for reproducibility.

    This is the Revenue Semantics Registry mandated by Build 09.
    """
    __tablename__ = "metric_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )  # NULL = global/platform-wide definition

    metric_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g. "gross_booking_value", "net_revenue", "cac"
    metric_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1"
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    # e.g. "SUM(revenue_events.amount WHERE event_type IN ('booking.created', 'booking.confirmed'))"

    numerator_definition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    denominator_definition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Data source
    source_tables: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=list, nullable=False
    )
    filters: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    # Reporting requirements
    requires_currency: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_date_range: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timezone_sensitive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deprecated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "metric_id", "metric_version",
            name="uq_metric_def_id_version"
        ),
        Index("ix_metric_def_org", "organization_id", "metric_id"),
    )


# ---------------------------------------------------------------------------
# 7. UNIT ECONOMICS RECORD
# ---------------------------------------------------------------------------

class UnitEconomicsRecord(Base):
    """
    Computed unit economics snapshot for an organization.

    Rules:
    - Only populate fields where data is reliably available.
    - NULL means the metric cannot be computed (not zero).
    - data_quality_notes explains which inputs are missing.
    - All monetary values: Numeric(20, 4).
    - Snapshots are immutable once created.
    """
    __tablename__ = "unit_economics_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reporting_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="AED"
    )

    # Lead counts
    total_leads: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qualified_leads: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_appointments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_site_visits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_bookings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Revenue
    gross_booking_value: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    collected_revenue: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    net_revenue: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    refunded_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)

    # Acquisition costs (NULL if cost data not available)
    total_acquisition_cost: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    ai_cost: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    communication_cost: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)

    # Computed economics (NULL = INSUFFICIENT_DATA)
    cac: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    cost_per_qualified_lead: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    cost_per_appointment: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    cost_per_site_visit: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    cost_per_booking: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    revenue_per_lead: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    revenue_per_booking: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    contribution_margin: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)

    # Data quality notes (which inputs were absent)
    data_quality_notes: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_unit_econ_org_period", "organization_id", "period_start"),
    )


# ---------------------------------------------------------------------------
# 8. REVENUE RECONCILIATION RECORD
# ---------------------------------------------------------------------------

class RevenueReconciliationRecord(Base, TimestampMixin):
    """
    Records discrepancies found during periodic revenue reconciliation.

    Reconciliation compares:
    - booking_system vs payment_system vs revenue_ledger vs inventory

    Discrepancies are recorded here and connected to Build 07 WorkItems
    for resolution. Historical records are never deleted.
    """
    __tablename__ = "revenue_reconciliation_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    reconciliation_run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    difference_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # ReconciliationDifference constants

    # References to the entities in conflict
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revenue_event_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    # Expected vs actual values
    expected_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    actual_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    expected_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    actual_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    # Resolution via WorkItem
    work_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    resolution_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_recon_org_type", "organization_id", "difference_type"),
        Index("ix_recon_run", "reconciliation_run_id"),
    )


# ---------------------------------------------------------------------------
# 9. AI CONTRIBUTION RECORD
# ---------------------------------------------------------------------------

class AIContributionRecord(Base, TimestampMixin):
    """
    Records AI contribution to a revenue journey for observability and attribution.

    CRITICAL: This record is observational, not causal.
    It records that AI participated, not that AI CAUSED the outcome.
    Category uses explicit operational definitions from AIContributionCategory.
    """
    __tablename__ = "ai_contribution_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revenue_event_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    # AI contribution category (operationally defined)
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, default=AIContributionCategory.UNKNOWN, index=True
    )

    # AI agent run linkage (Build 06)
    agent_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # e.g. "qualification", "property_recommendation", "follow_up", "appointment_assist"

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Outcome that followed (not causally attributed, just correlated)
    subsequent_event_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    subsequent_event_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    __table_args__ = (
        Index("ix_ai_contrib_org_lead", "organization_id", "lead_id"),
        Index("ix_ai_contrib_org_category", "organization_id", "category"),
    )
