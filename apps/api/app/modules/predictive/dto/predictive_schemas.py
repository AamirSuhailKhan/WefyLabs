"""
Pydantic V2 DTO Schemas for Predictive Analytics & MLOps Engine
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# ─── Inference DTOs ───────────────────────────────────────────────────────────

class FeatureAttributionDTO(BaseModel):
    feature: str
    impact: float
    description: str

class LeadPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    entity_id: str
    entity_type: str
    prediction_type: str
    raw_score: float
    calibrated_probability: float
    confidence_score: float
    confidence_level: str
    model_version_tag: str
    feature_schema_version: str
    positive_drivers: List[Dict[str, Any]]
    negative_drivers: List[Dict[str, Any]]
    explanation_text: str
    generated_at: datetime
    valid_until: datetime


class SalesCyclePredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    expected_sales_cycle_days: int
    expected_close_date_utc: datetime
    range_earliest_date_utc: datetime
    range_latest_date_utc: datetime
    confidence: float
    market_segment: str


class RevenueForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    horizon: str
    reporting_currency: str
    total_pipeline_value: float
    weighted_pipeline_value: float
    expected_revenue: float
    conservative_revenue: float
    optimistic_revenue: float
    expected_commission: float
    forecast_confidence: float
    segment_breakdown: Dict[str, Any]
    generated_at: datetime


class DemandPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    locality_name: str
    property_type: str
    demand_score: float
    active_searchers_count: int
    available_units_count: int
    demand_supply_ratio: float
    shortage_risk_detected: bool
    predicted_demand_trend: str


# ─── Scenario Simulation DTOs ──────────────────────────────────────────────────

class ScenarioSimulationRequest(BaseModel):
    scenario_name: str = Field(..., description="Name for the What-If simulation")
    conversion_rate_delta_pct: float = Field(0.0, description="e.g. +10.0 for +10%")
    response_time_reduction_pct: float = Field(0.0, description="e.g. 50.0 for 50% faster")
    lead_volume_delta_pct: float = Field(0.0, description="e.g. +20.0 for +20% leads")
    average_deal_size_delta_pct: float = Field(0.0, description="e.g. +5.0 for +5% deal size")


class ScenarioSimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    scenario_name: str
    conversion_rate_delta_pct: float
    response_time_reduction_pct: float
    lead_volume_delta_pct: float
    average_deal_size_delta_pct: float
    baseline_revenue_aed: float
    simulated_revenue_aed: float
    revenue_delta_aed: float
    projected_commission_delta_aed: float


# ─── Outcome & Evaluation DTOs ─────────────────────────────────────────────────

class RecordOutcomeRequest(BaseModel):
    actual_outcome: str = Field(..., description="CONVERTED | WON | LOST | NO_SHOW | ATTENDED")
    outcome_revenue_aed: Optional[float] = None


class PredictionOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prediction_id: str
    organization_id: str
    entity_id: str
    actual_outcome: str
    outcome_value: float
    outcome_revenue_aed: Optional[float] = None
    outcome_timestamp: datetime
    brier_error: float
    log_loss_error: float


# ─── Model Registry DTOs ───────────────────────────────────────────────────────

class ApproveModelRequest(BaseModel):
    approved_by: str = Field(..., description="Name / email of model approver")
    approval_notes: Optional[str] = None


class DeployModelRequest(BaseModel):
    deployment_mode: str = Field("PRODUCTION", description="PRODUCTION | CANARY")
    traffic_pct: float = Field(100.0, ge=5.0, le=100.0)


class ModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_id: str
    version_tag: str
    algorithm_type: str
    lifecycle_state: str
    traffic_allocation_pct: float
    roc_auc_score: float
    pr_auc_score: float
    brier_score: float
    calibration_method: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class PredictionModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_key: str
    display_name: str
    domain_type: str
    is_active: bool
    versions: List[ModelVersionResponse]
