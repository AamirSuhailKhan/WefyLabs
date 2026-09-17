"""
Part 30 — AI Real-Estate Agent Daily Command Center DTOs
=========================================================
Strict Pydantic schemas representing the operational command center,
priority queue, inventory intelligence, SLA monitoring, and morning briefings.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PriorityItemDTO(BaseModel):
    id: str = Field(..., description="Unique deterministic priority item identifier")
    item_key: str = Field(..., description="Key used for dismissal and state tracking")
    priority: str = Field(..., description="CRITICAL | HIGH | MEDIUM | LOW")
    priority_score: float = Field(..., description="Internal normalized rank score 0-100")
    category: str = Field(..., description="first_contact | site_visit | meeting | overdue_followup | followup_due | hot_lead | strong_match | stale_lead | inventory_opportunity")
    title: str = Field(..., description="Concise human-readable action directive")
    description: str = Field(..., description="Grounded, fact-based rationale")
    due_at: Optional[str] = None
    overdue_minutes: Optional[int] = None
    entity_type: str = Field(..., description="lead | task | meeting | property | match")
    entity_id: str = Field(..., description="Underlying database primary key")
    lead_id: Optional[str] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    property_id: Optional[str] = None
    property_title: Optional[str] = None
    match_score: Optional[float] = None
    recommended_action: str = Field(..., description="CALL | OPEN_LEAD | OPEN_PROPERTY | SCHEDULE_VISIT | RECORD_OUTCOME | RESCHEDULE | COMPLETE_TASK | REVIEW_MATCHES")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FirstContactSlaItemDTO(BaseModel):
    lead_id: str
    lead_name: str
    lead_phone: Optional[str] = None
    source: str = "manual"
    created_at: str
    sla_deadline: str
    is_overdue: bool
    overdue_minutes: Optional[int] = None
    time_remaining_minutes: Optional[int] = None
    pipeline_stage: str = "new"


class OverdueFollowupItemDTO(BaseModel):
    task_id: str
    lead_id: Optional[str] = None
    lead_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    due_at: str
    overdue_days: int
    overdue_hours: int
    priority: str = "normal"


class TodayScheduleItemDTO(BaseModel):
    id: str
    meeting_type: str  # site_visit | call | office_meeting | video_call
    title: str
    scheduled_at: str
    duration_minutes: int
    lead_id: Optional[str] = None
    lead_name: Optional[str] = None
    property_id: Optional[str] = None
    property_title: Optional[str] = None
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    status: str
    is_starting_soon: bool = False  # Within 2 hours


class HotLeadItemDTO(BaseModel):
    lead_id: str
    name: str
    phone: Optional[str] = None
    pipeline_stage: str
    temperature: str = "hot"
    last_activity_at: Optional[str] = None
    budget_max: Optional[float] = None
    preferred_locations: List[str] = Field(default_factory=list)
    property_type: Optional[str] = None
    strongest_property_match: Optional[str] = None
    match_score: Optional[float] = None
    uncontacted_days: int = 0


class StaleLeadSummaryDTO(BaseModel):
    stale_7_days_count: int = 0
    stale_14_days_count: int = 0
    stale_30_plus_days_count: int = 0
    total_stale_leads: int = 0
    sample_stale_leads: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def total_stale_count(self) -> int:
        return self.total_stale_leads

    @property
    def stale_14_to_30_days_count(self) -> int:
        return self.stale_14_days_count



class InventoryOpportunityDTO(BaseModel):
    property_id: str
    property_code: Optional[str] = None
    title: str
    price: float
    locality: Optional[str] = None
    city: Optional[str] = None
    bedrooms: Optional[int] = None
    property_type: str
    status: str
    created_at: str
    potential_leads_count: int = 0
    strong_matches_count: int = 0


class DemandHeatmapDTO(BaseModel):
    top_locations: List[Dict[str, Any]] = Field(default_factory=list)
    top_bhk: List[Dict[str, Any]] = Field(default_factory=list)
    top_budget_ranges: List[Dict[str, Any]] = Field(default_factory=list)
    top_property_types: List[Dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = "Demand aggregated exclusively from your verified CRM leads"


class InventoryGapItemDTO(BaseModel):
    segment_label: str
    property_type: str
    locality: Optional[str] = None
    bhk: Optional[int] = None
    demand_lead_count: int
    supply_property_count: int
    gap_deficit: int
    gap_severity: str  # HIGH | MEDIUM | BALANCED
    actionable_recommendation: str


class DailyBriefingDTO(BaseModel):
    greeting: str
    briefing_text: str
    generated_at: str
    is_ai_generated: bool = False
    highlights: List[str] = Field(default_factory=list)


class CommandCenterSummaryDTO(BaseModel):
    critical_actions_count: int = 0
    high_actions_count: int = 0
    medium_actions_count: int = 0
    total_priority_actions: int = 0
    overdue_followups_count: int = 0
    sla_breaches_count: int = 0
    meetings_today_count: int = 0
    site_visits_today_count: int = 0
    hot_leads_count: int = 0
    strong_matches_count: int = 0
    stale_leads_count: int = 0
    inventory_gaps_count: int = 0

    @property
    def today_meetings_count(self) -> int:
        return self.meetings_today_count

    @property
    def today_site_visits_count(self) -> int:
        return self.site_visits_today_count



class CommandCenterResponseDTO(BaseModel):
    organization_id: str
    broker_id: str
    broker_name: str
    timezone: str = "Asia/Kolkata"
    summary: CommandCenterSummaryDTO
    daily_briefing: DailyBriefingDTO
    priorities: List[PriorityItemDTO]
    first_contact_queue: List[FirstContactSlaItemDTO]
    overdue_followups: List[OverdueFollowupItemDTO]
    today_schedule: List[TodayScheduleItemDTO]
    hot_leads: List[HotLeadItemDTO]
    stale_leads_summary: StaleLeadSummaryDTO
    inventory_opportunities: List[InventoryOpportunityDTO]
    inventory_gaps: List[InventoryGapItemDTO]
    demand_heatmap: DemandHeatmapDTO
    recent_activities: List[Dict[str, Any]] = Field(default_factory=list)


class DismissItemRequestDTO(BaseModel):
    item_key: str = Field(..., min_length=1, description="Key identifying the item to dismiss or snooze")
    entity_type: str = Field(..., min_length=1, description="lead | task | meeting | match | property")
    entity_id: str = Field(..., min_length=1, description="Entity identifier")
    action_type: str = Field("dismissed", pattern="^(dismissed|snoozed)$", description="dismissed | snoozed")
    snooze_hours: Optional[int] = Field(None, description="Number of hours to snooze (if action_type == 'snoozed')")



class StartMyDayStepDTO(BaseModel):
    step_number: int
    total_steps: int
    item: PriorityItemDTO


class StartMyDayResponseDTO(BaseModel):
    total_items: int
    steps: List[StartMyDayStepDTO]
