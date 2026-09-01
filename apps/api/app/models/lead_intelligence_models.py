"""
Volume 2 PART 4 — AI Lead Intelligence & Revenue Engine Models
==============================================================
SQLAlchemy 2.0 models for:
1. LeadIntelligenceProfile  — Aggregated lead intelligence profile snapshot
2. LeadPrediction           — Granular event probabilities (closing, meeting, viewing, etc.)
3. LeadRecommendation       — Ranked Next Best Actions with % conversion lift & reasoning
4. PredictionHistory        — Immutable execution audit log for replay and tracking
5. ScoringRule              — Configurable business rules editable at runtime
6. MLModelVersion           — Registry of active/historical ML models & weights
7. FeatureVector            — Persisted feature vector snapshots for model inputs & debug
8. PredictionExplanation    — Explainable AI drivers (positive & negative factors)
9. RevenueForecast          — Aggregated pipeline revenue forecasts
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, BigInteger, Float,
    JSON, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class LeadIntelligenceProfile(Base):
    """
    Unified intelligence profile for a Lead.
    Stores dynamic scores, intent phase, urgency, temperature, momentum, and expected revenue.
    """
    __tablename__ = "lead_intelligence_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Core Composite Scores (0.0 - 100.0)
    lead_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    intent_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    budget_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    property_match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Dynamic Lead Momentum & Categorization
    score_yesterday: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    momentum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)  # today - yesterday score
    temperature: Mapped[str] = mapped_column(String(20), default="cold", nullable=False, index=True)  # cold | warm | hot | very_hot | purchase_ready
    intent_phase: Mapped[str] = mapped_column(String(30), default="research", nullable=False, index=True)  # research | comparison | decision | negotiation | purchase_ready | post_purchase

    # Priorities (1 - 100)
    follow_up_priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False, index=True)
    agent_priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    # Primary Probabilities (0.0 - 1.0)
    conversion_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    closing_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Financial & Revenue Intelligence
    estimated_revenue_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    probability_weighted_revenue_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_commission_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ltv_estimate_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Model & Confidence Metadata
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0.0 - 1.0
    active_model_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_intel_org_score", "organization_id", "lead_score"),
        Index("ix_intel_org_temp", "organization_id", "temperature"),
        Index("ix_intel_org_phase", "organization_id", "intent_phase"),
    )


class LeadPrediction(Base):
    """
    Detailed predictive probabilities for specific conversion milestones.
    """
    __tablename__ = "lead_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Probabilities (0.0 - 1.0)
    response_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meeting_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    viewing_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    closing_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    churn_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    referral_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Categorical Inferences
    buying_timeline_predicted: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)  # immediate | 1_month | 3_months | 6_months
    investment_potential_tier: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)  # low | medium | high | ultra_high
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0.0 - 100.0

    # Model & Confidence
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_prediction_lead_created", "lead_id", "created_at"),
    )


class LeadRecommendation(Base):
    """
    Ranked Next Best Actions generated by AI for sales agents.
    Includes estimated conversion lift (% increase) and rationale.
    """
    __tablename__ = "lead_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 = top recommendation
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # call_30m | schedule_visit | offer_financing | share_brochure | assign_senior | offer_discount | nurture
    action_title: Mapped[str] = mapped_column(String(255), nullable=False)
    estimated_conversion_lift: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # e.g. +18.0 for +18%
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active | accepted | rejected | expired
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_recommendation_lead_status", "lead_id", "status"),
    )


class PredictionHistory(Base):
    """
    Immutable audit log recording every scoring execution pass.
    Enables historical replay, model drift tracking, and debug verification.
    """
    __tablename__ = "prediction_histories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    trigger_event: Mapped[str] = mapped_column(String(50), nullable=False)  # LeadCreated | LeadEnriched | IdentityResolved | ManualRe-score
    lead_score: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_probability: Mapped[float] = mapped_column(Float, nullable=False)
    temperature: Mapped[str] = mapped_column(String(20), nullable=False)
    intent_phase: Mapped[str] = mapped_column(String(30), nullable=False)

    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    rules_fired_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    features_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_pred_history_lead_created", "lead_id", "created_at"),
    )


class ScoringRule(Base):
    """
    Configurable business rule entity editable by business users via API/Admin.
    Allows changing scoring logic without code deployment.
    """
    __tablename__ = "scoring_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    condition_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)  # {"field": "budget_max", "operator": ">=", "value": 2000000}
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)  # add_score | subtract_score | set_temperature | set_priority
    action_value: Mapped[float] = mapped_column(Float, nullable=False)  # +20.0

    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)  # Execution order
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_scoring_rules_org_active", "organization_id", "is_active"),
    )


class MLModelVersion(Base):
    """
    Registry of ML models (Hybrid, XGBoost, Random Forest, Neural Net, LLM).
    Tracks model version, algorithm type, accuracy metrics, and active deployment status.
    """
    __tablename__ = "ml_model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)  # e.g. "v1.2.0"
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    algorithm_type: Mapped[str] = mapped_column(String(50), nullable=False)  # hybrid_rule_ml | xgboost | random_forest | neural_net | llm_adapter

    accuracy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # AUC / ROC score
    precision_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    weights_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_ml_model_active", "is_active"),
    )


class FeatureVector(Base):
    """
    Extracted feature vector snapshot for a lead at a specific point in time.
    Stored for ML model input, continuous learning hooks, and debugging.
    """
    __tablename__ = "feature_vectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    feature_data: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class PredictionExplanation(Base):
    """
    Explainable AI model outputs for a lead.
    Stores top positive conversion drivers and top negative friction points.
    """
    __tablename__ = "prediction_explanations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    positive_drivers: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)  # [{"feature": "viewing_booked", "impact": "+24%"}]
    negative_drivers: Mapped[List[Any]] = mapped_column(JSONBType, default=list, nullable=False)  # [{"feature": "inactive_14_days", "impact": "-12%"}]
    feature_contributions: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    business_rationale: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_explanation_lead", "lead_id"),
    )


class RevenueForecast(Base):
    """
    Aggregated pipeline revenue forecast per organization or workspace.
    """
    __tablename__ = "revenue_forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    total_leads_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pipeline_total_revenue_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    probability_weighted_revenue_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_commission_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lost_revenue_risk_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    timeframe: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)  # monthly | quarterly | annual

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_rev_forecast_org_time", "organization_id", "timeframe"),
    )
