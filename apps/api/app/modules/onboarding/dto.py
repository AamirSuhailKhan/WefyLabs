"""
PART 31 — Customer Onboarding, Tenant Activation & Demo Mode DTOs
=================================================================
Pydantic schemas for:
- Business profile configuration
- Onboarding step progression & state tracking
- Tenant activation score & milestone calculation
- Demo playground session management & exit
- Sanitized CSV batch preview & commit
- Team member invitations
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class BusinessProfileSetupDTO(BaseModel):
    agency_name: str = Field(..., min_length=2, max_length=255, description="Agency / Company legal trading name")
    business_type: str = Field("agency", description="agency | brokerage | developer | individual")
    city: str = Field(..., min_length=2, max_length=100, description="Primary operating city")
    country_code: str = Field("IN", min_length=2, max_length=2, description="ISO Alpha-2 country code")
    timezone: str = Field("Asia/Kolkata", max_length=100, description="Default IANA timezone")
    currency_code: str = Field("INR", min_length=3, max_length=3, description="ISO 4217 currency code")
    team_size: Optional[str] = Field("1-5", description="1-5 | 6-20 | 21-50 | 50+")
    primary_business_model: Optional[str] = Field("residential_sales", description="residential_sales | commercial | leasing | mixed")
    website: Optional[str] = Field(None, max_length=255)


class OnboardingStepUpdateDTO(BaseModel):
    step: str = Field(..., min_length=2, description="Step identifier to update")
    action: str = Field("complete", pattern="^(complete|skip)$", description="complete | skip")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary step form parameters")


class ChecklistItemDTO(BaseModel):
    id: str
    title: str
    description: str
    is_completed: bool
    is_skipped: bool = False
    action_route: str
    action_label: str
    order: int


class OnboardingStatusResponseDTO(BaseModel):
    organization_id: str
    broker_id: str
    current_step: str
    completed_steps: List[str]
    skipped_steps: List[str]
    is_completed: bool
    progress_percentage: int
    completed_at: Optional[str] = None
    checklist: List[ChecklistItemDTO]
    is_activated: bool = False
    activation_score: int = 0
    is_demo: bool = False


class MilestoneProgressDTO(BaseModel):
    code: str
    label: str
    achieved: bool
    achieved_at: Optional[str] = None
    weight: int
    description: str


class TenantActivationResponseDTO(BaseModel):
    organization_id: str
    is_activated: bool
    activation_score: int = Field(..., ge=0, le=100)
    completed_milestones: List[str]
    missing_requirements: List[str]
    milestone_breakdown: List[MilestoneProgressDTO]
    activated_at: Optional[str] = None
    time_to_activate_seconds: Optional[int] = None
    is_demo: bool = False


class DemoSessionCreateDTO(BaseModel):
    intended_agency_name: Optional[str] = Field(None, max_length=255)
    operating_city: Optional[str] = Field("Bengaluru", max_length=100)


class DemoSessionResponseDTO(BaseModel):
    session_token: str
    demo_organization_id: str
    demo_broker_id: str
    demo_email: str
    agency_name: str
    expires_at: str
    seeded_leads_count: int
    seeded_properties_count: int
    seeded_matches_count: int
    seeded_tasks_count: int
    banner_message: str = "Demo Mode — Synthetic Playground. Changes here are isolated and never impact production."


class CsvImportPreviewDTO(BaseModel):
    entity_type: str = Field("leads", pattern="^(leads|properties)$")
    filename: str
    total_rows: int
    valid_rows_count: int
    duplicate_rows_count: int
    invalid_rows_count: int
    preview_items: List[Dict[str, Any]]
    validation_errors: List[str] = Field(default_factory=list)


class CsvImportCommitDTO(BaseModel):
    entity_type: str = Field("leads", pattern="^(leads|properties)$")
    items: List[Dict[str, Any]] = Field(..., min_length=1, max_length=250)


class CsvImportResultDTO(BaseModel):
    status: str = "success"
    entity_type: str
    imported_count: int
    skipped_count: int
    imported_ids: List[str] = Field(default_factory=list)
    message: str


class OnboardingTeamInviteDTO(BaseModel):
    email: EmailStr
    role: str = Field("agent", pattern="^(admin|manager|agent)$")
