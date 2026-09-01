"""
Volume 2 PART 11 — Predictive Analytics, Conversion Forecasting & MLOps Engine Models
=====================================================================================
SQLAlchemy 2.0 models for:
1. PredictionModelEntity           — Registered ML/Statistical model entities
2. PredictionModelVersionEntity    — Versioned model artifacts, hyperparameters, metrics & approval status
3. PredictionFeatureDefinition     — Versioned feature schema and source transformations
4. PredictionTrainingDataset       — Versioned time-split training & validation datasets
5. PredictionInferenceRecord       — Persisted immutable predictions (probability, confidence, valid_until)
6. PredictionOutcomeRecord         — Ground truth historical outcomes for continuous learning & evaluation
7. PredictionCalibrationRecord     — Calibration metrics (Brier score, ECE, Platt scaling params)
8. PredictionDriftRecord           — Population Stability Index (PSI) and feature drift alerts
9. ForecastSnapshotRecord          — Multi-horizon pipeline forecasts (7d, 30d, 60d, 90d, Q)
10. ForecastScenarioRecord         — Non-destructive What-If revenue simulation scenarios
11. DemandPredictionSnapshot       — Project and locality property demand metrics
12. SalesCyclePredictionSnapshot   — Expected close dates, range intervals & sales cycle duration
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

def _gen_uuid() -> str:
    return str(uuid.uuid4())


class PredictionModelEntity(Base, TimestampMixin):
    """
    Registry of high-level predictive models (e.g. Lead Conversion, Close Date, Revenue Forecast).
    """
    __tablename__ = "prediction_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    model_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)  # lead_conversion | close_date | revenue_forecast | property_demand | no_show
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CLASSIFICATION | REGRESSION | TIME_SERIES | RANKING
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    versions: Mapped[List["PredictionModelVersionEntity"]] = relationship(
        "PredictionModelVersionEntity", back_populates="model", cascade="all, delete-orphan"
    )


class PredictionModelVersionEntity(Base, TimestampMixin):
    """
    Versioned model artifacts, evaluation metrics, approval state, and canary deployment status.
    """
    __tablename__ = "prediction_model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("prediction_models.id", ondelete="CASCADE"), nullable=False, index=True)
    version_tag: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # e.g. "v1.0.0", "v2.1.0-canary"
    algorithm_type: Mapped[str] = mapped_column(String(50), nullable=False)  # LOGISTIC_REGRESSION | GRADIENT_BOOSTING | RANDOM_FOREST | SURVIVAL_ANALYSIS | HYBRID_RULES

    # Lifecycle State
    lifecycle_state: Mapped[str] = mapped_column(String(30), default="DEVELOPMENT", nullable=False, index=True)  # DEVELOPMENT | TRAINED | EVALUATED | APPROVED | STAGED | CANARY | PRODUCTION | DEPRECATED | RETIRED
    traffic_allocation_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0.0 to 100.0 (e.g. 10.0 for canary)

    # Evaluation Metrics
    roc_auc_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pr_auc_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    brier_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mae_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rmse_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Calibration & Artifact Metadata
    calibration_method: Mapped[str] = mapped_column(String(30), default="PLATT_SCALING", nullable=False)  # PLATT_SCALING | ISOTONIC | NONE
    model_weights_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)

    # Governance & Approval
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    model: Mapped["PredictionModelEntity"] = relationship("PredictionModelEntity", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("model_id", "version_tag", name="uq_model_version_tag"),
        Index("ix_model_ver_state", "lifecycle_state"),
    )


class PredictionFeatureDefinition(Base, TimestampMixin):
    """
    Schema of versioned feature transformations and data sources.
    """
    __tablename__ = "prediction_feature_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    feature_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(30), default="v1.0.0", nullable=False)
    data_type: Mapped[str] = mapped_column(String(30), default="FLOAT", nullable=False)  # FLOAT | INTEGER | CATEGORICAL | BOOLEAN
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_entity: Mapped[str] = mapped_column(String(50), nullable=False)  # LEAD | CONVERSATION | MEETING | TASK | PIPELINE
    transformation_logic: Mapped[str] = mapped_column(Text, nullable=False)
    is_protected_attribute: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Privacy protection flag


class PredictionTrainingDataset(Base, TimestampMixin):
    """
    Versioned time-split training and validation datasets.
    """
    __tablename__ = "prediction_training_datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    split_type: Mapped[str] = mapped_column(String(30), default="TEMPORAL_SPLIT", nullable=False)  # TEMPORAL_SPLIT | STRATIFIED
    start_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_label_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dataset_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class PredictionInferenceRecord(Base, TimestampMixin):
    """
    Immutable inference execution record representing a point-in-time prediction.
    """
    __tablename__ = "prediction_inference_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # lead_id or deal_id
    entity_type: Mapped[str] = mapped_column(String(30), default="LEAD", nullable=False)  # LEAD | OPPORTUNITY | MEETING | PROJECT

    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # CONVERSION | CLOSE_DATE | NO_SHOW | REVENUE | DEMAND
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_probability: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    confidence_score: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)  # 0.0 to 1.0
    confidence_level: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)  # LOW | MEDIUM | HIGH

    model_version_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)
    features_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # SHAP / Feature Attributions
    positive_drivers: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    negative_drivers: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    outcome: Mapped[Optional["PredictionOutcomeRecord"]] = relationship(
        "PredictionOutcomeRecord", back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_pred_org_entity_type", "organization_id", "entity_id", "prediction_type"),
    )


class PredictionOutcomeRecord(Base, TimestampMixin):
    """
    Ground truth historical outcome for an inference record.
    Used for continuous model evaluation, Brier scoring, and calibration tracking.
    """
    __tablename__ = "prediction_outcome_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    prediction_id: Mapped[str] = mapped_column(String(36), ForeignKey("prediction_inference_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    actual_outcome: Mapped[str] = mapped_column(String(50), nullable=False)  # CONVERTED | WON | LOST | NO_SHOW | ATTENDED | CHURNED
    outcome_value: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)  # 1.0 for positive, 0.0 for negative
    outcome_revenue_aed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    outcome_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    brier_error: Mapped[float] = mapped_column(Float, nullable=False)  # (calibrated_prob - outcome_value)^2
    log_loss_error: Mapped[float] = mapped_column(Float, nullable=False)

    prediction: Mapped["PredictionInferenceRecord"] = relationship("PredictionInferenceRecord", back_populates="outcome")


class PredictionCalibrationRecord(Base, TimestampMixin):
    """
    Periodic calibration curve assessment and Expected Calibration Error (ECE).
    """
    __tablename__ = "prediction_calibration_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    model_version_tag: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    evaluation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    brier_score: Mapped[float] = mapped_column(Float, nullable=False)
    expected_calibration_error: Mapped[float] = mapped_column(Float, nullable=False)
    calibration_bins: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)  # Bin centers, predicted vs observed
    status: Mapped[str] = mapped_column(String(20), default="CALIBRATED", nullable=False)  # CALIBRATED | DEGRADED | RECALIBRATION_REQUIRED


class PredictionDriftRecord(Base, TimestampMixin):
    """
    Population Stability Index (PSI) drift monitoring audit record.
    """
    __tablename__ = "prediction_drift_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    model_version_tag: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    drift_type: Mapped[str] = mapped_column(String(50), default="PREDICTION_DRIFT", nullable=False)  # FEATURE_DRIFT | PREDICTION_DRIFT | OUTCOME_DRIFT
    psi_score: Mapped[float] = mapped_column(Float, nullable=False)  # < 0.10: No drift, 0.10 - 0.25: Moderate, > 0.25: Significant drift
    drift_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ForecastSnapshotRecord(Base, TimestampMixin):
    """
    Multi-horizon pipeline and revenue forecasts with conservative, expected, and optimistic bounds.
    """
    __tablename__ = "forecast_snapshot_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    horizon: Mapped[str] = mapped_column(String(30), default="30_DAYS", nullable=False)  # 7_DAYS | 30_DAYS | 60_DAYS | 90_DAYS | QUARTER
    reporting_currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)

    total_pipeline_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weighted_pipeline_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    conservative_revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # P10
    optimistic_revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)    # P90
    expected_commission: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    forecast_confidence: Mapped[float] = mapped_column(Float, default=0.88, nullable=False)

    segment_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ForecastScenarioRecord(Base, TimestampMixin):
    """
    Non-destructive What-If revenue and pipeline simulation scenario.
    """
    __tablename__ = "forecast_scenario_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(150), nullable=False)

    # Simulation Parameter Adjustments
    conversion_rate_delta_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # e.g. +10.0%
    response_time_reduction_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lead_volume_delta_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_deal_size_delta_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Computed Simulated Results
    baseline_revenue_aed: Mapped[float] = mapped_column(Float, nullable=False)
    simulated_revenue_aed: Mapped[float] = mapped_column(Float, nullable=False)
    revenue_delta_aed: Mapped[float] = mapped_column(Float, nullable=False)
    projected_commission_delta_aed: Mapped[float] = mapped_column(Float, nullable=False)


class DemandPredictionSnapshot(Base, TimestampMixin):
    """
    Property demand forecast by project, location, and bedroom configuration.
    """
    __tablename__ = "demand_prediction_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    locality_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    property_type: Mapped[str] = mapped_column(String(50), default="apartment", nullable=False)

    demand_score: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)  # 0.0 to 100.0
    active_searchers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_units_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    demand_supply_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    shortage_risk_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    predicted_demand_trend: Mapped[str] = mapped_column(String(30), default="STABLE", nullable=False)  # SURGING | INCREASING | STABLE | DECLINING


class SalesCyclePredictionSnapshot(Base, TimestampMixin):
    """
    Expected close date, duration, and range window for deals and leads.
    """
    __tablename__ = "sales_cycle_prediction_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    expected_sales_cycle_days: Mapped[int] = mapped_column(Integer, default=21, nullable=False)
    expected_close_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    range_earliest_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    range_latest_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    market_segment: Mapped[str] = mapped_column(String(50), default="luxury", nullable=False)
