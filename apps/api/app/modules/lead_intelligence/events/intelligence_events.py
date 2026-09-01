"""
Lead Intelligence Events — Pydantic Event DTOs
================================================
Events emitted by the AI Lead Intelligence & Revenue Engine.
Published to Redis Pub/Sub for workflow automation, CRM alerts, and real-time dashboards.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class LeadScored(BaseModel):
    event_type: str = "LeadScored"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    organization_id: str
    lead_score: float
    intent_score: float
    urgency_score: float
    temperature: str
    intent_phase: str
    momentum: float
    conversion_probability: float
    occurred_at: datetime = Field(default_factory=_now_utc)


class LeadPriorityChanged(BaseModel):
    event_type: str = "LeadPriorityChanged"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    organization_id: str
    old_temperature: str
    new_temperature: str
    follow_up_priority: int
    agent_priority: int
    momentum: float
    occurred_at: datetime = Field(default_factory=_now_utc)


class IntentUpdated(BaseModel):
    event_type: str = "IntentUpdated"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    organization_id: str
    intent_score: float
    intent_phase: str
    occurred_at: datetime = Field(default_factory=_now_utc)


class PredictionUpdated(BaseModel):
    event_type: str = "PredictionUpdated"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    organization_id: str
    conversion_probability: float
    closing_probability: float
    churn_probability: float
    risk_score: float
    occurred_at: datetime = Field(default_factory=_now_utc)


class RecommendationGenerated(BaseModel):
    event_type: str = "RecommendationGenerated"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    organization_id: str
    top_action_type: str
    top_action_title: str
    estimated_conversion_lift: float
    occurred_at: datetime = Field(default_factory=_now_utc)


class RevenueForecastUpdated(BaseModel):
    event_type: str = "RevenueForecastUpdated"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    pipeline_total_revenue_aed: float
    probability_weighted_revenue_aed: float
    occurred_at: datetime = Field(default_factory=_now_utc)
