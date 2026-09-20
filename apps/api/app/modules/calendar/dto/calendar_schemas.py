"""
Pydantic v2 Data Transfer Objects for Calendar, Meeting, Viewing & Scheduling Intelligence Engine
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


class TimeSlotDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start_utc: datetime
    end_utc: datetime
    broker_local_start: str
    customer_local_start: str
    broker_id: str
    broker_name: Optional[str] = None
    is_held: bool = False
    suitability_score: float = 1.0


class SlotSearchRequestDTO(BaseModel):
    lead_id: str = Field(..., description="Target Lead UUID")
    broker_id: Optional[str] = Field(None, description="Optional target broker ID")
    meeting_type: str = Field("PROPERTY_VIEWING", description="PROPERTY_VIEWING | SITE_VISIT | CALL | VIDEO_CALL")
    property_id: Optional[str] = Field(None, description="Target property ID for viewings")
    duration_minutes: int = Field(45, ge=15, le=180)
    search_days_ahead: int = Field(7, ge=1, le=30)
    customer_timezone: Optional[str] = Field(None, description="Override customer timezone")


class SlotSearchResponseDTO(BaseModel):
    lead_id: str
    meeting_type: str
    customer_timezone: str
    broker_timezone: str
    available_slots: List[TimeSlotDTO]


class SlotHoldRequestDTO(BaseModel):
    lead_id: str
    broker_id: str
    slot_start_utc: datetime
    duration_minutes: int = 45


class SlotHoldResponseDTO(BaseModel):
    hold_id: str
    broker_id: str
    lead_id: str
    slot_start_utc: datetime
    slot_end_utc: datetime
    expires_at_utc: datetime


class BookingRequestDTO(BaseModel):
    lead_id: str
    broker_id: Optional[str] = None
    meeting_type: str = "PROPERTY_VIEWING"
    property_id: Optional[str] = None
    slot_start_utc: datetime
    duration_minutes: int = 45
    location_type: str = "PROPERTY"
    location_address: Optional[str] = None
    virtual_provider: str = "NONE" # GOOGLE_MEET | MICROSOFT_TEAMS | ZOOM | NONE
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class BookingResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    broker_id: str
    lead_id: Optional[str] = None
    meeting_type: str
    title: str
    status: str
    start_utc: datetime
    end_utc: datetime
    customer_timezone: str
    broker_timezone: str
    duration_minutes: int
    location_address: Optional[str] = None
    virtual_provider: str
    meeting_url: Optional[str] = None
    property_id: Optional[str] = None

    @field_validator("id", "organization_id", "broker_id", "lead_id", mode="before")
    @classmethod
    def serialize_identifier(cls, value: object) -> Optional[str]:
        """Keep the existing string API contract when ORM fields are UUIDs."""
        return None if value is None else str(value)


class RescheduleRequestDTO(BaseModel):
    new_slot_start_utc: datetime
    reason: Optional[str] = None


class CancellationRequestDTO(BaseModel):
    reason: str
    cancelled_by: str = "CUSTOMER" # CUSTOMER | BROKER | PROPERTY


class ItineraryStopDTO(BaseModel):
    property_id: str
    property_title: str
    estimated_arrival_utc: datetime
    estimated_duration_minutes: int = 45
    locality: str


class ItineraryRequestDTO(BaseModel):
    lead_id: str
    broker_id: Optional[str] = None
    property_ids: List[str] = Field(..., min_length=2, max_length=5)
    start_date_utc: datetime


class ItineraryResponseDTO(BaseModel):
    lead_id: str
    broker_id: str
    total_stops: int
    total_duration_minutes: int
    stops: List[ItineraryStopDTO]


class MeetingPreparationBriefDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    lead_id: str
    buyer_summary: str
    verified_budget: str
    key_objections: List[str] = []
    recommended_properties: List[Dict[str, Any]] = []
    suggested_questions: List[str] = []
    next_best_action: str


class RecordOutcomeRequestDTO(BaseModel):
    outcome_category: str # INTERESTED | VERY_INTERESTED | NEEDS_FOLLOW_UP | NOT_INTERESTED | NEGOTIATION | CONVERTED | NO_SHOW
    buyer_interest_level: int = Field(3, ge=1, le=5)
    detailed_feedback: Optional[str] = None
    agreed_next_step: Optional[str] = None
    next_follow_up_date: Optional[datetime] = None
    agent_notes: Optional[str] = None

    @field_validator("buyer_interest_level", mode="before")
    @classmethod
    def parse_interest_level(cls, value: Any) -> int:
        if isinstance(value, str):
            mapping = {
                "VERY_HIGH": 5,
                "HIGH": 4,
                "MEDIUM": 3,
                "LOW": 2,
                "VERY_LOW": 1,
            }
            clean_val = value.strip().upper()
            if clean_val in mapping:
                return mapping[clean_val]
            try:
                parsed = int(value)
                return max(1, min(5, parsed))
            except ValueError:
                return 3
        return int(value) if value is not None else 3


class MeetingOutcomeDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    outcome_category: str
    buyer_interest_level: int
    detailed_feedback: Optional[str] = None
    agreed_next_step: Optional[str] = None
    next_follow_up_date: Optional[datetime] = None


class NoShowPredictionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    no_show_probability: float
    risk_level: str
    confidence: float
    influencing_factors: List[str] = []
    preventative_action: Optional[str] = None


class CalendarConflictDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    external_event_id: str
    conflict_description: str
    resolution_status: str
    detected_at: datetime
