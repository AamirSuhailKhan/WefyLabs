"""
Part 11 — Revenue Intelligence DTOs
=====================================
Pydantic v2 request/response shapes for all Revenue Intelligence endpoints.

DESIGN PRINCIPLES:
- All numeric fields that could be zero-divided are Optional[float] — never
  defaulting to 100% or 0% when data is absent.
- All "estimate" fields carry a suffix `_estimate` in their name so callers
  cannot mistake them for transactional facts.
- No fabricated values: if the DB has no rows, counts are 0 and rates are None.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ──────────────────────────────────────────────────────────────────────────────
# Shared sub-DTOs
# ──────────────────────────────────────────────────────────────────────────────

class FunnelStageDTO(BaseModel):
    """Count and conversion rate for a single funnel stage."""
    stage: str
    count: int
    conversion_rate_pct: Optional[float] = Field(
        None,
        description=(
            "Percentage of leads that advanced from this stage to the next. "
            "Null when denominator is 0 (prevents division-by-zero fabrication)."
        )
    )


class FunnelSummaryDTO(BaseModel):
    """Full funnel state — stage-by-stage counts and rates."""
    organization_id: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_leads: int
    stages: List[FunnelStageDTO]
    overall_conversion_rate_pct: Optional[float] = Field(
        None,
        description="Percentage of all leads that reached 'converted'. Null when total_leads=0."
    )
    active_opportunities: int
    estimated_pipeline_value_estimate: Optional[float] = Field(
        None,
        description="Sum of budget_max for active qualified+ leads. ESTIMATE — not a confirmed transaction value."
    )
    confirmed_revenue: Optional[float] = Field(
        None,
        description="Sum of estimated_commission_amount from completed deal_transactions."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Leakage
# ──────────────────────────────────────────────────────────────────────────────

class LeakageByStageDTO(BaseModel):
    stage: str
    lost_count: int
    total_estimated_value_lost_estimate: Optional[float] = Field(
        None,
        description="Sum of budget_max for lost leads at this stage. ESTIMATE."
    )
    avg_days_in_stage: Optional[float] = None
    top_reason: Optional[str] = None


class LeakageReportDTO(BaseModel):
    organization_id: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    staleness_threshold_days: int = 14
    total_leakage_events: int
    total_estimated_value_at_risk_estimate: Optional[float] = Field(
        None,
        description=(
            "Sum of budget_max across all detected leakage leads. "
            "ESTIMATE — not a confirmed loss figure."
        )
    )
    by_stage: List[LeakageByStageDTO]


# ──────────────────────────────────────────────────────────────────────────────
# Outcomes
# ──────────────────────────────────────────────────────────────────────────────

class OutcomeDistributionItemDTO(BaseModel):
    outcome: str
    count: int
    pct: Optional[float] = None


class OutcomeSummaryDTO(BaseModel):
    organization_id: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_feedback_records: int
    win_rate_pct: Optional[float] = Field(
        None,
        description="Percentage of feedback records with positive outcome. Null when no data."
    )
    positive_feedback_count: int
    negative_feedback_count: int
    completed_deals: int
    avg_opportunity_score_at_win: Optional[float] = None
    outcome_distribution: List[OutcomeDistributionItemDTO]


# ──────────────────────────────────────────────────────────────────────────────
# Source Attribution
# ──────────────────────────────────────────────────────────────────────────────

class SourceAttributionItemDTO(BaseModel):
    source: str
    lead_count: int
    converted_count: int
    conversion_rate_pct: Optional[float] = None
    estimated_revenue_estimate: Optional[float] = Field(
        None,
        description="Sum of budget_max for converted leads from this source. ESTIMATE."
    )


class AttributionReportDTO(BaseModel):
    organization_id: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_sources: int
    by_source: List[SourceAttributionItemDTO]
    top_source_by_leads: Optional[str] = None
    top_source_by_conversion: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Learning Loop
# ──────────────────────────────────────────────────────────────────────────────

class TopOpportunityTypeDTO(BaseModel):
    opportunity_type: str
    total_count: int
    actioned_count: int
    positive_feedback_count: int
    action_rate_pct: Optional[float] = None
    positive_feedback_rate_pct: Optional[float] = None


class LearningLoopSummaryDTO(BaseModel):
    """
    Heuristic summary of what is working in the revenue system.

    IMPORTANT: These are deterministic aggregations of historical data.
    There is NO machine-learning model behind these figures. All percentages
    are computed from actual rows in revenue_feedback_logs and
    revenue_opportunities. Do not represent these as ML predictions.
    """
    organization_id: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    computation_method: str = "heuristic_aggregation_v1"
    top_opportunity_types: List[TopOpportunityTypeDTO]
    top_source_by_conversion: Optional[str] = None
    total_opportunities_evaluated: int
    total_positive_signals: int


# ──────────────────────────────────────────────────────────────────────────────
# Snapshot
# ──────────────────────────────────────────────────────────────────────────────

class SnapshotCaptureRequestDTO(BaseModel):
    period_type: str = Field("DAILY", description="DAILY | WEEKLY | MONTHLY")


class FunnelSnapshotDTO(BaseModel):
    id: str
    organization_id: str
    period_type: str
    snapshot_date: str
    total_leads: int
    leads_new: int
    leads_contacted: int
    leads_qualified: int
    leads_site_visit: int
    leads_negotiation: int
    leads_converted: int
    leads_lost: int
    active_opportunities: int
    estimated_pipeline_value_estimate: Optional[float]
    confirmed_revenue: Optional[float]
    metrics: Dict[str, Any]
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class SnapshotListDTO(BaseModel):
    organization_id: str
    total: int
    snapshots: List[FunnelSnapshotDTO]


# ──────────────────────────────────────────────────────────────────────────────
# Overview & Forecast Foundation
# ──────────────────────────────────────────────────────────────────────────────

class RevenueOverviewDTO(BaseModel):
    organization_id: str
    realized_revenue: Optional[float] = Field(None, description="Confirmed revenue from closed transactions.")
    current_pipeline_estimate: Optional[float] = Field(None, description="Sum of budget_max for active qualified+ leads.")
    revenue_at_risk_estimate: Optional[float] = Field(None, description="Value of stalled or explicitly lost opportunities.")
    active_opportunities: int
    total_leads: int
    attributed_revenue: Optional[float] = Field(None, description="Revenue linked to known source.")
    unattributed_revenue: Optional[float] = Field(None, description="Revenue missing source attribution.")
    attribution_coverage_pct: Optional[float] = Field(None, description="Percentage of leads with known source.")
    forecast_status: str = Field("FORECAST_NOT_AVAILABLE", description="Forecast status or model label.")
    forecast_disclaimer: str = Field(
        "Forecast is not available because validated ML forecasting models are not enabled. Projections rely strictly on deterministic pipeline values.",
        description="Explains forecast basis."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Extended 15-Category Leakage DTOs
# ──────────────────────────────────────────────────────────────────────────────

class ExtendedLeakageItemDTO(BaseModel):
    leakage_type: str = Field(..., description="One of 15 canonical leakage categories.")
    severity: str = Field(..., description="CRITICAL | HIGH | MEDIUM | LOW")
    entity_type: str = Field(..., description="lead | opportunity | appointment | site_visit | match")
    entity_id: str
    organization_id: str
    detected_at: str
    age_days: Optional[int] = None
    evidence: Dict[str, Any]
    estimated_impact_estimate: Optional[float] = None
    recommended_next_action: str
    source_channel: Optional[str] = None
    status: str = "ACTIVE"


# ──────────────────────────────────────────────────────────────────────────────
# Data Quality Panel
# ──────────────────────────────────────────────────────────────────────────────

class DataQualityItemDTO(BaseModel):
    metric: str
    missing_count: int
    total_count: int
    coverage_pct: Optional[float]
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    description: str


class DataQualityReportDTO(BaseModel):
    organization_id: str
    data_health_score_pct: float
    total_records_audited: int
    issues: List[DataQualityItemDTO]
    audited_at: str


# ──────────────────────────────────────────────────────────────────────────────
# Journeys (Lead & Property)
# ──────────────────────────────────────────────────────────────────────────────

class JourneyEventDTO(BaseModel):
    event_id: str
    occurred_at: str
    stage: str
    title: str
    description: Optional[str] = None
    actor_type: str = "SYSTEM"  # SYSTEM | USER | AI_AGENT | AUTOMATION
    channel: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LeadRevenueJourneyDTO(BaseModel):
    lead_id: str
    organization_id: str
    lead_name: Optional[str] = None
    source: Optional[str] = None
    pipeline_stage: str
    score: Optional[str] = None
    budget_max: Optional[float] = None
    total_events: int
    journey: List[JourneyEventDTO]


class PropertyRevenueJourneyDTO(BaseModel):
    property_id: str
    organization_id: str
    property_title: Optional[str] = None
    price: Optional[float] = None
    total_matches: int
    qualified_leads_count: int
    appointments_count: int
    site_visits_count: int
    deals_closed: int
    confirmed_revenue: Optional[float] = None
    conversion_rate_pct: Optional[float] = None


# ──────────────────────────────────────────────────────────────────────────────
# Team / Agent Operational Intelligence
# ──────────────────────────────────────────────────────────────────────────────

class AgentOperationalMetricsDTO(BaseModel):
    broker_id: str
    name: str
    email: Optional[str] = None
    assigned_leads: int
    contacted_leads: int
    qualified_leads: int
    scheduled_appointments: int
    completed_site_visits: int
    active_opportunities: int
    closed_deals: int


class TeamIntelligenceDTO(BaseModel):
    organization_id: str
    total_agents: int
    agents: List[AgentOperationalMetricsDTO]


# ──────────────────────────────────────────────────────────────────────────────
# Heuristic Propensity
# ──────────────────────────────────────────────────────────────────────────────

class PropensityScoreDTO(BaseModel):
    lead_id: str
    organization_id: str
    score: float = Field(..., description="Deterministic heuristic propensity score 0.0 - 100.0")
    method: str = "DETERMINISTIC_HEURISTIC"
    version: str = "heuristic_v1"
    features_used: Dict[str, Any]
    calculation_breakdown: List[str]
    generated_at: str
    data_window_days: int = 30
