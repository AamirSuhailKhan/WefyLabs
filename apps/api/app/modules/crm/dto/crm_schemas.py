"""WefyLabs Native CRM Core — Data Transfer Objects & Schemas
=============================================================
Pydantic v2 schemas for Customer 360, Lead CRM, Pipeline, Deals,
Tasks, Activities, Notes, Universal Search, and Bulk Operations.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tasks, Activities & Notes
# ─────────────────────────────────────────────────────────────────────────────

class CRMTaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: str = Field("normal", pattern="^(low|normal|high|urgent)$")
    status: str = Field("pending", pattern="^(pending|in_progress|completed|cancelled)$")
    lead_id: Optional[str] = None
    assigned_broker_id: Optional[str] = None


class CRMTaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: Optional[str] = Field(None, pattern="^(low|normal|high|urgent)$")
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed|cancelled)$")
    assigned_broker_id: Optional[str] = None


class CRMTaskResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    broker_id: str
    lead_id: Optional[str] = None
    assigned_broker_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    status: str
    priority: str
    is_overdue: bool = False
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CRMActivityCreateRequest(BaseModel):
    lead_id: Optional[str] = None
    activity_type: str = Field(
        ...,
        description="call | email | sms | meeting | note | follow_up | site_visit | message | task | property_view | property_recommendation | custom"
    )
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    actor_type: str = Field("HUMAN", pattern="^(HUMAN|AI_AGENT|AUTOMATION|CUSTOMER|SYSTEM)$")
    activity_data: Dict[str, Any] = Field(default_factory=dict)


class CRMActivityResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    lead_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: str = "HUMAN"
    activity_type: str
    title: str
    description: Optional[str] = None
    activity_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CRMNoteCreateRequest(BaseModel):
    lead_id: str
    content: str = Field(..., min_length=1)
    visibility: str = Field("ORGANIZATION", pattern="^(PRIVATE|TEAM|ORGANIZATION)$")
    is_ai_generated: bool = False


class CRMNoteResponse(BaseModel):
    id: str
    lead_id: str
    broker_id: str
    content: str
    visibility: str = "ORGANIZATION"
    is_ai_generated: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lead CRM Models & Filter Query Parameters
# ─────────────────────────────────────────────────────────────────────────────

class LeadCRMListItem(BaseModel):
    id: str
    name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    source: str
    campaign: Optional[str] = None
    score: str  # hot | warm | cold | pending
    status: str  # pending | active | qualified | converted | lost
    pipeline_stage: str
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    budget_currency: str = "AED"
    preferred_locations: List[str] = Field(default_factory=list)
    property_type: Optional[str] = None
    owner_id: str
    owner_name: Optional[str] = None
    sla_status: str = "ON_TRACK"  # ON_TRACK | AT_RISK | BREACHED
    last_activity_at: Optional[datetime] = None
    next_action: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadCRMFilterParams(BaseModel):
    stage: Optional[str] = None
    status: Optional[str] = None
    score: Optional[str] = None
    source: Optional[str] = None
    owner_id: Optional[str] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    sla_status: Optional[str] = None
    search: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    sort_by: str = Field("created_at", pattern="^(created_at|updated_at|score|budget_max|name)$")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class LeadStageTransitionRequest(BaseModel):
    new_stage: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = None


class LeadAssignRequest(BaseModel):
    target_broker_id: str
    reason: Optional[str] = None


class SavedViewDTO(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    sorting: Dict[str, Any] = Field(default_factory=dict)
    columns: List[str] = Field(default_factory=list)
    is_shared: bool = False
    is_default: bool = False
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# 3. Deals / Opportunities
# ─────────────────────────────────────────────────────────────────────────────

class OpportunitySummaryDTO(BaseModel):
    id: str
    lead_id: str
    lead_name: Optional[str] = None
    lead_phone: str
    property_id: Optional[str] = None
    property_title: Optional[str] = None
    deal_name: str
    agreed_price: float
    currency: str = "AED"
    current_stage: str
    commission_percentage: float = 2.0
    estimated_commission_amount: float = 0.0
    risk_level: str = "low"
    closing_probability_pct: float = 85.0
    is_stalled: bool = False
    days_in_stage: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityCreateRequest(BaseModel):
    lead_id: str
    property_id: str
    deal_name: str
    agreed_price: float = Field(..., gt=0)
    currency: str = Field("AED", max_length=10)
    commission_percentage: float = Field(2.0, ge=0.0, le=100.0)
    current_stage: str = Field("lead", max_length=50)


class OpportunityStageUpdateRequest(BaseModel):
    current_stage: str = Field(..., min_length=1, max_length=50)
    reason: Optional[str] = None


class OpportunityDetailResponse(BaseModel):
    id: str
    broker_id: str
    lead_id: str
    lead_name: Optional[str] = None
    property_id: Optional[str] = None
    property_title: Optional[str] = None
    deal_name: str
    agreed_price: float
    currency: str
    current_stage: str
    commission_percentage: float
    estimated_commission_amount: float
    risk_level: str
    closing_probability_pct: float
    missing_documents: List[str] = Field(default_factory=list)
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    installments: List[Dict[str, Any]] = Field(default_factory=list)
    tasks: List[CRMTaskResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# 4. Sales Pipeline (Kanban)
# ─────────────────────────────────────────────────────────────────────────────

class PipelineCardDTO(BaseModel):
    id: str  # lead_id or deal_id
    lead_id: str
    deal_id: Optional[str] = None
    customer_name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    stage: str
    score: str
    property_interest: Optional[str] = None
    owner_id: str
    owner_name: Optional[str] = None
    deal_value: Optional[float] = None
    currency: str = "AED"
    age_days: int = 0
    last_activity_at: Optional[datetime] = None
    next_action: Optional[str] = None
    has_revenue_alert: bool = False


class PipelineColumnDTO(BaseModel):
    stage_key: str
    stage_name: str
    order_index: int
    color: str
    total_cards: int
    total_pipeline_value: float
    cards: List[PipelineCardDTO] = Field(default_factory=list)


class PipelineKanbanResponse(BaseModel):
    total_pipeline_value: float
    total_active_deals: int
    columns: List[PipelineColumnDTO] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Customer 360 Canonical Models
# ─────────────────────────────────────────────────────────────────────────────

class CustomerPreferencesDTO(BaseModel):
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    budget_currency: str = "AED"
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    preferred_locations: List[str] = Field(default_factory=list)
    timeline: Optional[str] = None
    loan_status: Optional[str] = None
    amenities: List[str] = Field(default_factory=list)


class CustomerRevenueJourneyDTO(BaseModel):
    stage: str
    source_channel: str
    first_seen_at: datetime
    qualified_at: Optional[datetime] = None
    appointment_booked_at: Optional[datetime] = None
    site_visit_completed_at: Optional[datetime] = None
    opportunity_created_at: Optional[datetime] = None
    deal_agreed_price: Optional[float] = None
    recorded_revenue: Optional[float] = None


class CustomerTimelineEventDTO(BaseModel):
    id: str
    event_type: str
    title: str
    description: Optional[str] = None
    timestamp: datetime
    actor: str
    actor_type: str  # HUMAN | AI_AGENT | AUTOMATION | CUSTOMER | SYSTEM
    source: str
    channel: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Customer360Response(BaseModel):
    customer_id: str
    organization_id: str
    # Header Info
    name: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: str
    owner_id: str
    owner_name: Optional[str] = None
    lead_status: str
    pipeline_stage: str
    temperature: str  # hot | warm | cold | pending
    source: str
    campaign: Optional[str] = None
    created_at: datetime
    last_activity_at: Optional[datetime] = None
    sla_state: str = "ON_TRACK"
    next_best_action: Optional[str] = None

    # Deep Details
    preferences: CustomerPreferencesDTO
    qualification: Dict[str, Any] = Field(default_factory=dict)
    property_interests: List[Dict[str, Any]] = Field(default_factory=list)
    property_matches: List[Dict[str, Any]] = Field(default_factory=list)
    conversations: List[Dict[str, Any]] = Field(default_factory=list)
    tasks: List[CRMTaskResponse] = Field(default_factory=list)
    activities: List[CRMActivityResponse] = Field(default_factory=list)
    notes: List[CRMNoteResponse] = Field(default_factory=list)
    appointments: List[Dict[str, Any]] = Field(default_factory=list)
    site_visits: List[Dict[str, Any]] = Field(default_factory=list)
    opportunities: List[OpportunitySummaryDTO] = Field(default_factory=list)
    revenue_journey: CustomerRevenueJourneyDTO
    timeline: List[CustomerTimelineEventDTO] = Field(default_factory=list)
    ai_insights: Dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Universal Search & Bulk Operations
# ─────────────────────────────────────────────────────────────────────────────

class CRMSearchResultItem(BaseModel):
    id: str
    entity_type: str  # customer | lead | opportunity | property | task | appointment
    title: str
    subtitle: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    deep_link: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CRMSearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[CRMSearchResultItem] = Field(default_factory=list)


class BulkLeadOperationRequest(BaseModel):
    operation: str = Field(
        ...,
        pattern="^(assign|change_stage|change_priority|add_tag|create_task|archive|export)$"
    )
    lead_ids: List[str] = Field(..., min_length=1, max_length=200)
    params: Dict[str, Any] = Field(default_factory=dict)


class BulkOperationResult(BaseModel):
    operation: str
    total_requested: int
    successful_count: int
    failed_count: int
    failed_items: List[Dict[str, Any]] = Field(default_factory=list)
    audit_id: Optional[str] = None


class CRMDashboardMetricsResponse(BaseModel):
    my_open_leads: int
    new_leads_today: int
    sla_risks_count: int
    todays_appointments_count: int
    upcoming_site_visits_count: int
    active_opportunities_count: int
    pipeline_total_value: float
    pipeline_currency: str = "AED"
    recorded_revenue_total: float
    overdue_tasks_count: int
    revenue_opportunities_count: int
