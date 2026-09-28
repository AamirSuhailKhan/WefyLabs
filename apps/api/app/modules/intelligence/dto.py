"""
Master Build 14 — Competitive Moat & Intelligence Graph DTOs
============================================================
Pydantic V2 schemas for outcomes, learning signals, graph traversal,
AI action lifecycle, objections, funnel, experimentation, benchmarking,
snapshots, insights, data quality, drift, replay, and backfill.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models.intelligence_models import (
    OutcomeEventType,
    OutcomeEntityType,
    OutcomeSource,
    LearningSignalType,
    ObjectionType,
    ExperimentStatus,
    BenchmarkType,
    DataQualityIssueType,
    RegistryEntityType,
    RegistryEntryStatus,
    DriftType,
    InsightType,
)


# ─── Canonical Outcome Events ───────────────────────────────────────────────

class OutcomeEventCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_type: OutcomeEventType
    entity_type: OutcomeEntityType
    entity_id: str
    occurred_at: Optional[datetime] = None
    outcome_source: OutcomeSource = OutcomeSource.HUMAN
    financial_value: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = "INR"
    lead_id: Optional[str] = None
    property_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    agent_id: Optional[str] = None
    channel: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    policy_version: Optional[str] = None
    event_metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance_hash: Optional[str] = None


class OutcomeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    event_type: str
    entity_type: str
    entity_id: str
    occurred_at: datetime
    recorded_at: datetime
    outcome_source: str
    financial_value: Optional[Decimal]
    currency: str
    lead_id: Optional[str]
    property_id: Optional[str]
    opportunity_id: Optional[str]
    agent_id: Optional[str]
    channel: Optional[str]
    model_version: Optional[str]
    prompt_version: Optional[str]
    policy_version: Optional[str]
    event_metadata: Dict[str, Any]
    provenance_hash: Optional[str]


# ─── Learning Signals & Verification Gate ───────────────────────────────────

class LearningEventCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signal_type: LearningSignalType
    signal_name: str
    source_table: str
    source_event_id: str
    entity_type: str
    entity_id: str
    lead_id: Optional[str] = None
    property_id: Optional[str] = None
    agent_id: Optional[str] = None
    signal_weight: Decimal = Field(default=Decimal("1.0"), ge=0, le=10)
    confidence: Decimal = Field(default=Decimal("0.8"), ge=0, le=1)
    evidence_type: str = "DIRECT_OBSERVATION"
    signal_payload: Dict[str, Any] = Field(default_factory=dict)


class LearningEventVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verified_by: str = Field(..., description="ID or name of human verifying the learning signal")
    notes: Optional[str] = None


class LearningEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    signal_type: str
    signal_name: str
    source_table: str
    source_event_id: str
    entity_type: str
    entity_id: str
    lead_id: Optional[str]
    property_id: Optional[str]
    agent_id: Optional[str]
    signal_weight: Decimal
    confidence: Decimal
    evidence_type: str
    signal_payload: Dict[str, Any]
    is_verified: bool
    verified_by: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime


# ─── Sales Outcome Graph ───────────────────────────────────────────────────

class SalesOutcomeEdgeCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    from_entity_type: str
    from_entity_id: str
    to_entity_type: str
    to_entity_id: str
    edge_type: str
    weight: Decimal = Field(default=Decimal("1.0"), ge=0)
    time_delta_seconds: Optional[int] = None
    lead_id: Optional[str] = None
    property_id: Optional[str] = None
    agent_id: Optional[str] = None
    edge_metadata: Dict[str, Any] = Field(default_factory=dict)


class SalesOutcomeEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    from_entity_type: str
    from_entity_id: str
    to_entity_type: str
    to_entity_id: str
    edge_type: str
    weight: Decimal
    time_delta_seconds: Optional[int]
    lead_id: Optional[str]
    property_id: Optional[str]
    agent_id: Optional[str]
    edge_metadata: Dict[str, Any]
    created_at: datetime


class GraphPathResponse(BaseModel):
    lead_id: Optional[str]
    nodes: List[Dict[str, Any]]
    edges: List[SalesOutcomeEdgeResponse]
    path_length: int
    conversion_confirmed: bool


# ─── AI Action Lifecycle & Human Override ───────────────────────────────────

class AIActionOutcomeCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action_id: str
    action_type: str
    model_version: str
    prompt_version: str
    lead_id: Optional[str] = None
    agent_id: Optional[str] = None
    was_accepted: bool = False
    was_rejected: bool = False
    human_overridden: bool = False
    override_reason: Optional[str] = None
    actual_outcome_type: Optional[str] = None
    financial_outcome: Optional[Decimal] = None
    action_metadata: Dict[str, Any] = Field(default_factory=dict)


class AIActionOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    override_reason: str = Field(..., min_length=3)
    rejection_feedback: Optional[str] = None
    corrected_action: Optional[str] = None


class AIActionOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    action_id: str
    action_type: str
    model_version: str
    prompt_version: str
    lead_id: Optional[str]
    agent_id: Optional[str]
    was_accepted: bool
    was_rejected: bool
    human_overridden: bool
    override_reason: Optional[str]
    actual_outcome_type: Optional[str]
    financial_outcome: Optional[Decimal]
    action_metadata: Dict[str, Any]
    created_at: datetime


# ─── Objection Intelligence ─────────────────────────────────────────────────

class ObjectionRecordCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    objection_type: ObjectionType
    lead_id: Optional[str] = None
    property_id: Optional[str] = None
    agent_id: Optional[str] = None
    raw_statement: str
    normalized_objection: str
    was_resolved: bool = False
    rebuttal_used: Optional[str] = None
    winning_rebuttal: Optional[str] = None
    conversation_channel: Optional[str] = None
    objection_metadata: Dict[str, Any] = Field(default_factory=dict)


class ObjectionRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    objection_type: str
    lead_id: Optional[str]
    property_id: Optional[str]
    agent_id: Optional[str]
    raw_statement: str
    normalized_objection: str
    was_resolved: bool
    rebuttal_used: Optional[str]
    winning_rebuttal: Optional[str]
    conversation_channel: Optional[str]
    objection_metadata: Dict[str, Any]
    created_at: datetime


class ObjectionAnalyticsResponse(BaseModel):
    total_objections: int
    resolution_rate: float
    by_type: Dict[str, int]
    top_effective_rebuttals: List[Dict[str, Any]]


# ─── Funnel Transitions & Velocity ──────────────────────────────────────────

class FunnelTransitionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lead_id: str
    from_stage: str
    to_stage: str
    opportunity_id: Optional[str] = None
    agent_id: Optional[str] = None
    duration_in_stage_seconds: Optional[int] = None
    is_backward: bool = False
    dropoff_reason: Optional[str] = None
    transition_metadata: Dict[str, Any] = Field(default_factory=dict)


class FunnelTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    opportunity_id: Optional[str]
    agent_id: Optional[str]
    from_stage: str
    to_stage: str
    duration_in_stage_seconds: Optional[int]
    is_backward: bool
    dropoff_reason: Optional[str]
    transition_metadata: Dict[str, Any]
    created_at: datetime


class FunnelMetricsResponse(BaseModel):
    stages: List[str]
    transition_counts: Dict[str, int]
    dropoff_rates: Dict[str, float]
    average_duration_seconds: Dict[str, float]
    bottleneck_stages: List[str]


# ─── Experimentation Engine ─────────────────────────────────────────────────

class ExperimentVariantCreate(BaseModel):
    name: str
    description: Optional[str] = None
    traffic_pct: Decimal = Field(default=Decimal("50.0"), ge=0, le=100)
    config_payload: Dict[str, Any] = Field(default_factory=dict)
    is_control: bool = False


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=3)
    description: Optional[str] = None
    target_metric: str
    layer: str = "GLOBAL"
    max_sample_size: Optional[int] = None
    variants: List[ExperimentVariantCreate] = Field(..., min_length=2)


class ExperimentAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity_id: str
    entity_type: str = "LEAD"


class ExperimentConversionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity_id: str
    metric_name: str
    metric_value: Decimal = Field(default=Decimal("1.0"))
    conversion_metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experiment_id: str
    name: str
    description: Optional[str]
    traffic_pct: Decimal
    config_payload: Dict[str, Any]
    is_control: bool
    assignment_count: int
    conversion_count: int
    conversion_rate: Optional[Decimal]


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: Optional[str]
    status: str
    layer: str
    target_metric: str
    created_at: datetime
    started_at: Optional[datetime]
    concluded_at: Optional[datetime]
    winning_variant_id: Optional[str]
    variants: List[ExperimentVariantResponse] = []


class ExperimentEvaluationResponse(BaseModel):
    experiment_id: str
    status: str
    target_metric: str
    total_assignments: int
    total_conversions: int
    variants: List[Dict[str, Any]]
    is_statistically_significant: bool
    confidence_interval: Optional[Dict[str, float]]
    recommended_variant: Optional[str]


# ─── Benchmarking Engine & Privacy ──────────────────────────────────────────

class BenchmarkDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    metric_name: str
    benchmark_type: BenchmarkType = BenchmarkType.ANONYMIZED_COHORT
    industry_segment: Optional[str] = "REAL_ESTATE_COMMERCIAL"
    geographic_region: Optional[str] = "GLOBAL"
    minimum_cohort_size: int = Field(default=5, ge=5)
    description: Optional[str] = None


class BenchmarkSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    benchmark_id: str
    organization_id: Optional[str]  # NULL for anonymized cross-tenant benchmarks
    period_start: datetime
    period_end: datetime
    sample_size: int
    mean_value: Optional[Decimal]
    p50_value: Optional[Decimal]
    p75_value: Optional[Decimal]
    p90_value: Optional[Decimal]
    created_at: datetime


class BenchmarkComparisonResponse(BaseModel):
    metric_name: str
    organization_value: Optional[float]
    benchmark_p50: Optional[float]
    benchmark_p75: Optional[float]
    benchmark_p90: Optional[float]
    cohort_sample_size: int
    percentile_rank: Optional[float]
    privacy_preserved: bool = True


# ─── Intelligence Snapshots & Insights ──────────────────────────────────────

class IntelligenceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    snapshot_date: datetime
    period_type: str
    total_leads: int
    qualified_leads: int
    site_visits_completed: int
    bookings_completed: int
    conversion_rate: Optional[Decimal]
    total_revenue_realized: Optional[Decimal]
    ai_actions_count: int
    ai_acceptance_rate: Optional[Decimal]
    data_quality_score: Optional[Decimal]
    metrics_payload: Dict[str, Any]
    created_at: datetime


class InsightRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    insight_type: str
    title: str
    description: str
    evidence_type: str
    impact_score: Decimal
    urgency_score: Decimal
    recommended_action: Optional[str]
    source_table: Optional[str]
    source_id: Optional[str]
    is_actioned: bool
    actioned_at: Optional[datetime]
    created_at: datetime


# ─── Data Quality & Drift ───────────────────────────────────────────────────

class DataQualityIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    issue_type: str
    affected_table: str
    affected_record_id: Optional[str]
    severity: str
    description: str
    is_resolved: bool
    created_at: datetime


class DataQualityReportResponse(BaseModel):
    overall_quality_score: float
    total_issues: int
    unresolved_issues: int
    issues_by_severity: Dict[str, int]
    recent_issues: List[DataQualityIssueResponse]


class DriftAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    drift_type: str
    feature_name: Optional[str]
    model_version: Optional[str]
    baseline_value: Optional[Decimal]
    current_value: Optional[Decimal]
    drift_magnitude: Decimal
    p_value: Optional[Decimal]
    status: str
    created_at: datetime


# ─── Policy Registry & Promotion Gates ──────────────────────────────────────

class PolicyRegistryEntryCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity_type: RegistryEntityType
    name: str
    version: str
    status: RegistryEntryStatus = RegistryEntryStatus.CANDIDATE
    definition_payload: Dict[str, Any] = Field(default_factory=dict)
    eval_score: Optional[Decimal] = Field(default=None, ge=0, le=1)
    notes: Optional[str] = None


class PolicyPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_status: RegistryEntryStatus
    eval_score: Decimal = Field(..., ge=0, le=1)
    validation_notes: str = Field(..., min_length=5)


class PolicyRegistryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    entity_type: str
    name: str
    version: str
    status: str
    definition_payload: Dict[str, Any]
    eval_score: Optional[Decimal]
    promoted_at: Optional[datetime]
    created_at: datetime


# ─── Replay & Backfill ──────────────────────────────────────────────────────

class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_date: datetime
    end_date: datetime
    simulate_only: bool = True


class ReplayResponse(BaseModel):
    total_events_replayed: int
    start_date: datetime
    end_date: datetime
    simulated: bool
    recalculated_snapshots: int
    duration_ms: float
    status: str


class BackfillRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_sources: List[str] = Field(
        default=["leads", "appointments", "deals", "ai_actions"],
        description="Operational tables to backfill outcomes from"
    )
    batch_size: int = Field(default=100, ge=1, le=1000)


class BackfillResponse(BaseModel):
    sources_scanned: List[str]
    total_records_inspected: int
    new_outcome_events_created: int
    skipped_duplicates: int
    duration_ms: float
    status: str


# ─── Organization Learning Profile ──────────────────────────────────────────

class OrganizationLearningProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    total_learning_events: int
    verified_learning_events: int
    high_intent_signals: Dict[str, Any]
    property_affinity_rules: Dict[str, Any]
    objection_playbook: Dict[str, Any]
    optimal_contact_times: Dict[str, Any]
    velocity_benchmarks: Dict[str, Any]
    last_profile_refresh: Optional[datetime]
    profile_version: int
    created_at: datetime
    updated_at: datetime


# ─── Master Build 14 Extended Dashboards & Intelligence DTOs ────────────────

class ExecutiveIntelligenceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    period_type: str
    period_start: datetime
    period_end: datetime
    total_pipeline_value: Decimal
    realized_revenue: Decimal
    previous_revenue: Decimal
    revenue_growth_pct: Decimal
    variable_cost: Decimal
    gross_margin_pct: Decimal
    overall_conversion_rate: Decimal
    sales_velocity_days: Decimal
    ai_recommendation_acceptance_rate: Decimal
    ai_cost_per_booking: Decimal
    channel_summary: List[Dict[str, Any]]
    operational_bottlenecks: List[str]
    learning_signals_count: int
    sample_size: int


class ManagerIntelligenceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    team_workload: Dict[str, Any]
    follow_up_risks: List[Dict[str, Any]]
    lead_quality_distribution: Dict[str, int]
    conversion_stages: List[Dict[str, Any]]
    site_visits_metrics: Dict[str, Any]
    booking_pipeline: Dict[str, Any]
    agent_bottlenecks: List[Dict[str, Any]]
    coaching_insights: List[Dict[str, Any]]


class SalesUserIntelligenceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    agent_id: str
    organization_id: str
    my_leads_count: int
    priority_actions: List[Dict[str, Any]]
    follow_up_risks: List[Dict[str, Any]]
    property_opportunities: List[Dict[str, Any]]
    pending_appointments: List[Dict[str, Any]]
    conversion_progress: Dict[str, Any]
    ai_recommendations: List[Dict[str, Any]]
    personal_performance_history: List[Dict[str, Any]]


class MoatMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    data_coverage_score: Decimal
    outcome_density: Decimal
    recommendation_acceptance_rate: Decimal
    workflow_automation_coverage: Decimal
    ai_outcome_linkage_rate: Decimal
    cross_feature_connectivity_score: Decimal
    customer_retention_index: Decimal
    time_to_value_days: Decimal
    operational_adoption_rate: Decimal
    learning_loop_maturity_stage: str
    evidence_grade: str


class CompetitiveCapabilityMatrixResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_name: str
    architecture_version: str
    dimensions: List[Dict[str, Any]]
    wefylabs_capabilities: Dict[str, Any]
    evidence_records: List[Dict[str, Any]]


class ChannelPerformanceRecord(BaseModel):
    channel: str
    volume: int
    response_rate: Decimal
    qualification_rate: Decimal
    appointment_rate: Decimal
    site_visit_rate: Decimal
    booking_rate: Decimal
    revenue: Decimal
    cost: Decimal
    gross_margin_pct: Decimal


class ChannelIntelligenceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    channels: List[ChannelPerformanceRecord]
    top_performing_channel: str
    lowest_cost_channel: str
    highest_margin_channel: str


class AgentCoachingSignal(BaseModel):
    agent_id: str
    agent_name: Optional[str] = None
    signal_type: str
    severity: str
    description: str
    underlying_event_ids: List[str]
    recommended_action: str


class AgentCoachingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    signals: List[AgentCoachingSignal]
    total_signals: int


class OrganizationPlaybookResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    best_followup_cadence_hours: int
    lead_prioritization_rules: List[Dict[str, Any]]
    property_matching_heuristics: List[Dict[str, Any]]
    top_objections_and_counters: List[Dict[str, Any]]
    channel_preferences: Dict[str, Any]
    updated_at: datetime

