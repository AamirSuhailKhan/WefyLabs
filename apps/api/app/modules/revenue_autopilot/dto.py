"""
Part 35 — AI Real Estate Revenue Autopilot DTOs
================================================
Typed Pydantic schemas for Action Queue, Opportunities, Outreaches,
Feedback, Briefing, and Demand Gap Intelligence.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ActionQueueItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_type: str
    priority: str  # CRITICAL | HIGH | MEDIUM | LOW
    urgency: str   # CRITICAL | HIGH | MEDIUM | LOW
    opportunity_score: float
    match_score: float
    confidence: float

    # Lead Information
    lead_id: str
    lead_name: str
    lead_phone: str
    lead_score: str
    lead_stage: Optional[str] = None

    # Property Information (Optional if non-property-tied)
    property_id: Optional[str] = None
    property_title: Optional[str] = None
    property_price: Optional[float] = None
    property_currency: str = "INR"
    property_locality: Optional[str] = None
    property_bedrooms: Optional[int] = None
    property_status: Optional[str] = None

    # Grounded Explainability
    reason: str
    why_now: str
    why_property: Optional[str] = None
    risk_of_inactivity: Optional[str] = None

    # Action Directives
    recommended_action: str
    recommended_channel: str
    positive_signals: List[str] = Field(default_factory=list)
    negative_signals: List[str] = Field(default_factory=list)
    data_freshness: Dict[str, Any] = Field(default_factory=dict)

    # Lifecycle State
    status: str
    created_at: str
    expires_at: Optional[str] = None


class ActionQueueResponseDTO(BaseModel):
    items: List[ActionQueueItemDTO]
    total_count: int
    critical_count: int
    high_count: int
    briefing_headline: str
    # Empty-state intelligence metadata (Part 35.1)
    active_leads_count: int = 0
    active_properties_count: int = 0
    completed_today_count: int = 0
    last_scan_at: Optional[str] = None


class RevenueOpportunityDTO(ActionQueueItemDTO):
    recommended_property_snapshot: Dict[str, Any] = Field(default_factory=dict)
    alternative_properties: List[Dict[str, Any]] = Field(default_factory=list)
    call_brief: Dict[str, Any] = Field(default_factory=dict)
    email_draft: Dict[str, Any] = Field(default_factory=dict)
    provenance: List[str] = Field(default_factory=list)
    scoring_version: str = "v1"
    dedup_key: str = ""

    actioned_at: Optional[str] = None
    completed_at: Optional[str] = None
    dismissed_at: Optional[str] = None
    dismissal_reason: Optional[str] = None
    feedback_rating: Optional[str] = None
    feedback_notes: Optional[str] = None
    actual_outcome: Optional[str] = None


class OpportunityListResponseDTO(BaseModel):
    items: List[RevenueOpportunityDTO]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class DismissOpportunityRequestDTO(BaseModel):
    reason: str = Field(default="Not relevant", description="Dismissal reason")
    notes: Optional[str] = None


class ActionOpportunityRequestDTO(BaseModel):
    action_type: str = Field(..., description="CALL_LEAD | SEND_EMAIL | SEND_PROPERTY_RECOMMENDATION | FOLLOW_UP | SCHEDULE_SITE_VISIT | REACTIVATE_LEAD | REVIEW_DEAL")
    notes: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    send_email_now: bool = False
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    create_follow_up_task: bool = True


class FeedbackOpportunityRequestDTO(BaseModel):
    rating: str = Field(..., description="YES | NO | NOT_SURE")
    reason: Optional[str] = None
    notes: Optional[str] = None
    actual_outcome: Optional[str] = Field(None, description="Contacted | Interested | Site Visit Booked | Deal Won | Deal Lost")


class OutreachDraftDTO(BaseModel):
    opportunity_id: str
    lead_name: str
    channel: str
    call_brief: Dict[str, Any]
    email_draft: Dict[str, Any]
    is_ai_generated: bool
    model_used: str


class DemandGapItemDTO(BaseModel):
    segment_id: str
    locality: str
    bedrooms: int
    property_type: str
    budget_band: str
    active_buyer_demand_count: int
    matching_inventory_count: int
    deficit_count: int
    urgency: str
    recommended_action: str


class DemandIntelligenceResponseDTO(BaseModel):
    total_active_buyers: int
    total_available_listings: int
    top_demand_gaps: List[DemandGapItemDTO]
    high_demand_localities: List[str]


class RevenueBriefingDTO(BaseModel):
    greeting: str
    headline: str
    immediate_actions_count: int
    critical_actions_count: int
    hot_leads_count: int
    top_recommendation_text: str
    evidence_points: List[str]
    generated_at: str
