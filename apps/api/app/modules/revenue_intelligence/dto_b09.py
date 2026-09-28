"""
Build 09 — Revenue Intelligence DTOs
======================================
Pydantic v2 schemas for all Build 09 analytics API endpoints.

Rules:
- All monetary fields are str (from Decimal) — never float in API responses.
- Optional monetary fields return None (not 0) when data is absent.
- Every response includes a definition field referencing the metric registry.
- Period / currency / timezone always included where applicable.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ──────────────────────────────────────────────────────────────────────────────
# SHARED
# ──────────────────────────────────────────────────────────────────────────────

class PeriodFilter(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    timezone_name: str = "UTC"


class MetricValue(BaseModel):
    value: Optional[str] = None           # Decimal stringified, or None
    definition: Optional[str] = None      # Formula from metric registry
    verified: bool = False
    data_quality: Optional[str] = None    # GOOD / LIMITED / INSUFFICIENT_DATA


# ──────────────────────────────────────────────────────────────────────────────
# REVENUE OVERVIEW
# ──────────────────────────────────────────────────────────────────────────────

class RevenueSummaryResponse(BaseModel):
    period: Dict[str, Optional[str]]
    data_source: str
    metrics: Dict[str, MetricValue]
    event_breakdown: Dict[str, Dict[str, Any]]


class RevenueOverviewResponse(BaseModel):
    overview: RevenueSummaryResponse
    pipeline: Dict[str, Any]
    leakage: Dict[str, Any]
    data_freshness: Dict[str, Optional[str]]


# ──────────────────────────────────────────────────────────────────────────────
# ATTRIBUTION
# ──────────────────────────────────────────────────────────────────────────────

class TouchpointCreate(BaseModel):
    lead_id: Optional[uuid.UUID] = None
    identity_id: Optional[uuid.UUID] = None
    channel: str
    event_type: str
    occurred_at: Optional[datetime] = None
    source_name: Optional[str] = None
    campaign_id: Optional[uuid.UUID] = None
    campaign_name: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    actor_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class TouchpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    lead_id: Optional[uuid.UUID]
    channel: str
    event_type: str
    occurred_at: datetime
    source_name: Optional[str]
    campaign_name: Optional[str]


class AttributionComputeRequest(BaseModel):
    lead_id: uuid.UUID
    revenue_event_id: Optional[str] = None
    attributed_amount: Optional[str] = None  # Decimal as string
    currency: Optional[str] = None
    model: str = "FIRST_TOUCH"
    model_version: str = "v1"
    window_days: int = Field(default=30, ge=1, le=365)

    @field_validator("attributed_amount")
    @classmethod
    def validate_amount(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                Decimal(v)
            except Exception:
                raise ValueError(f"Invalid decimal value: {v!r}")
        return v


class AttributionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    revenue_event_id: Optional[str]
    lead_id: Optional[uuid.UUID]
    attributed_amount: Optional[str]
    currency: Optional[str]
    attribution_model: str
    model_version: str
    window_days: int
    touchpoint_count: int
    first_touch_channel: Optional[str]
    first_touch_source: Optional[str]
    first_touch_campaign: Optional[str]
    first_touch_at: Optional[datetime]
    last_touch_channel: Optional[str]
    last_touch_source: Optional[str]
    last_touch_campaign: Optional[str]
    last_touch_at: Optional[datetime]
    touchpoint_breakdown: Dict[str, Any]
    calculated_at: datetime


class SourceAttributionReportResponse(BaseModel):
    model: str
    window_days: int
    period: Dict[str, Optional[str]]
    sources: List[Dict[str, Any]]
    note: str


# ──────────────────────────────────────────────────────────────────────────────
# FUNNEL
# ──────────────────────────────────────────────────────────────────────────────

class FunnelStage(BaseModel):
    stage: str
    count: int


class FunnelConversion(BaseModel):
    from_stage: str
    to_stage: str
    conversion_pct: Optional[float]


class FunnelSummaryResponse(BaseModel):
    period: Dict[str, Optional[str]]
    data_source: str
    total_leads: int
    stages: List[FunnelStage]
    conversions: List[FunnelConversion]
    lead_to_won_pct: Optional[float]


class FunnelVelocityResponse(BaseModel):
    period: Dict[str, Optional[str]]
    data_source: str
    velocities: List[Dict[str, Any]]


# ──────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

class PipelineSummaryResponse(BaseModel):
    data_source: str
    probability_source: str
    opportunity_count: int
    pipeline_value: str
    weighted_pipeline: str
    stalled_opportunities: int
    stalled_value: str
    stage_breakdown: Dict[str, Dict[str, Any]]


# ──────────────────────────────────────────────────────────────────────────────
# FORECASTING
# ──────────────────────────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    period_type: str = "MONTH"
    period_start: datetime
    period_end: datetime
    timezone_name: str = "UTC"
    reporting_currency: str = "AED"
    scenario: str = "BASE"
    method: str = "stage_weighted"


class ForecastSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    timezone_name: str
    method: str
    method_version: str
    scenario: str
    pipeline_value: Optional[str]
    weighted_pipeline: Optional[str]
    forecast_value: Optional[str]
    upside_value: Optional[str]
    downside_value: Optional[str]
    reporting_currency: str
    quality: str
    quality_notes: Optional[str]
    opportunity_count: int
    stage_distribution: Dict[str, Any]
    probability_assumptions: Dict[str, Any]
    actual_revenue: Optional[str]
    forecast_error_pct: Optional[str]
    is_reconciled: bool
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────────────
# LEAKAGE
# ──────────────────────────────────────────────────────────────────────────────

class LeakageEventResponse(BaseModel):
    id: str
    condition: str
    severity: str
    age_days: int
    estimated_value_at_risk: Optional[str]
    currency: Optional[str]
    lead_id: Optional[str]
    opportunity_id: Optional[str]
    recommended_action: Optional[str]
    detected_at: Optional[str]


class LeakageReportResponse(BaseModel):
    open_count: int
    total_value_at_risk: str
    note: str
    events: List[LeakageEventResponse]


class LeakageResolveRequest(BaseModel):
    resolution_action: str
    resolution_outcome: str


class LeakageResolveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_resolved: bool
    resolution_at: Optional[datetime]
    resolution_action: Optional[str]
    resolution_outcome: Optional[str]


# ──────────────────────────────────────────────────────────────────────────────
# ANOMALIES
# ──────────────────────────────────────────────────────────────────────────────

class AnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    metric: str
    baseline_value: Optional[str]
    observed_value: Optional[str]
    threshold_pct: Optional[str]
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    severity: str
    description: Optional[str]
    evidence: Dict[str, Any]
    detected_at: datetime
    is_resolved: bool
    resolution_at: Optional[datetime]


class AnomalyScanResponse(BaseModel):
    scanned_at: datetime
    new_anomaly_count: int
    anomalies: List[AnomalyResponse]


# ──────────────────────────────────────────────────────────────────────────────
# UNIT ECONOMICS
# ──────────────────────────────────────────────────────────────────────────────

class UnitEconomicsRequest(BaseModel):
    period_type: str = "MONTH"
    period_start: datetime
    period_end: datetime
    reporting_currency: str = "AED"
    # Cost inputs — None = INSUFFICIENT_DATA
    acquisition_cost: Optional[str] = None   # Decimal as string
    ai_cost: Optional[str] = None
    communication_cost: Optional[str] = None

    @field_validator("acquisition_cost", "ai_cost", "communication_cost")
    @classmethod
    def validate_cost(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                Decimal(v)
            except Exception:
                raise ValueError(f"Invalid decimal value: {v!r}")
        return v


class UnitEconomicsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    reporting_currency: str
    total_leads: Optional[int]
    qualified_leads: Optional[int]
    total_bookings: Optional[int]
    gross_booking_value: Optional[str]
    collected_revenue: Optional[str]
    net_revenue: Optional[str]
    refunded_amount: Optional[str]
    total_acquisition_cost: Optional[str]
    ai_cost: Optional[str]
    communication_cost: Optional[str]
    cac: Optional[str]
    cost_per_qualified_lead: Optional[str]
    cost_per_booking: Optional[str]
    revenue_per_lead: Optional[str]
    revenue_per_booking: Optional[str]
    contribution_margin: Optional[str]
    data_quality_notes: Dict[str, Any]
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────────────
# RECONCILIATION
# ──────────────────────────────────────────────────────────────────────────────

class ReconciliationResponse(BaseModel):
    run_id: str
    organization_id: str
    discrepancy_count: int
    discrepancies: List[Dict[str, Any]]
    period: Dict[str, Optional[str]]


# ──────────────────────────────────────────────────────────────────────────────
# DATA QUALITY
# ──────────────────────────────────────────────────────────────────────────────

class DataQualityResponse(BaseModel):
    organization_id: str
    as_of: str
    dimensions: Dict[str, Any]
    open_anomaly_count: int
    open_leakage_count: int
    open_reconciliation_count: int
