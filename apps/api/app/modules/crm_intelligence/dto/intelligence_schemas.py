"""
Pydantic V2 DTO Schemas for CRM Intelligence & Autonomous Sales Operations Engine
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# ─── Lead Health DTOs ─────────────────────────────────────────────────────────

class LeadHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    broker_id: Optional[str] = None
    health_state: str
    health_score: float
    engagement_health: float
    intent_health: float
    response_health: float
    follow_up_health: float
    meeting_health: float
    qualification_health: float
    property_match_health: float
    agent_attention_health: float
    conversion_health: float
    explanation: str
    decay_detected: bool
    neglect_detected: bool
    evaluated_at: datetime


class LeadRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    risk_type: str
    severity: str
    confidence: float
    evidence: str
    recommended_recovery_action: str
    status: str
    created_at: datetime


# ─── Pipeline Health DTOs ──────────────────────────────────────────────────────

class PipelineHealthStageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stage_id: str
    stage_name: str
    lead_count: int
    total_pipeline_value_aed: float
    weighted_pipeline_value_aed: float
    avg_stage_duration_days: float
    stagnant_leads_count: int
    conversion_rate_pct: float
    drop_off_rate_pct: float
    revenue_at_risk_aed: float
    snapshot_date: datetime


class OpportunityHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    deal_health: str
    momentum_score: float
    closing_probability: float
    stagnation_days: int
    revenue_at_risk_aed: float
    recommended_recovery_action: str


# ─── SLA DTOs ─────────────────────────────────────────────────────────────────

class SlaBreachResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    broker_id: Optional[str] = None
    sla_type: str
    target_deadline_utc: datetime
    breached_at_utc: datetime
    overdue_minutes: int
    escalation_sent: bool


# ─── Agent Workload DTOs ──────────────────────────────────────────────────────

class AgentWorkloadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    broker_id: str
    active_leads_count: int
    high_priority_leads_count: int
    open_tasks_count: int
    overdue_tasks_count: int
    scheduled_meetings_today: int
    workload_status: str
    capacity_utilization_pct: float
    rebalancing_recommended: bool


# ─── Insights & NBA DTOs ──────────────────────────────────────────────────────

class SalesInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    insight_type: str
    title: str
    summary_markdown: str
    priority: str
    impact_level: str
    confidence: float
    evidence: List[str]
    recommended_action: str
    is_active: bool
    expires_at: Optional[datetime] = None


class NextBestActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    broker_id: Optional[str] = None
    action_type: str
    title: str
    description: str
    priority: str
    urgency_hours: int
    potential_revenue_impact_aed: float
    governance_policy: str
    status: str


class ActionExecutionRequest(BaseModel):
    executed_by: str = Field("BROKER_1CLICK", description="Actor executing the action")
    payload: Optional[Dict[str, Any]] = None


class ActionExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action_id: str
    executed_by: str
    execution_status: str
    result_payload: Dict[str, Any]
    executed_at: datetime


class ManagerBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    brief_date: datetime
    today_new_leads: int
    high_intent_leads_count: int
    at_risk_leads_count: int
    sla_breaches_count: int
    upcoming_viewings_count: int
    stagnant_deals_count: int
    revenue_at_risk_aed: float
    overloaded_agents: List[Dict[str, Any]]
    top_manager_actions: List[str]
    executive_summary: str


class AgentBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    broker_id: str
    brief_date: datetime
    top_leads_to_call: List[Dict[str, Any]]
    upcoming_meetings_today: List[Dict[str, Any]]
    overdue_follow_ups_count: int
    urgent_tasks: List[Dict[str, Any]]
    daily_focus_summary: str
