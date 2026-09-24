from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid
from datetime import datetime

class LeadCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=5, max_length=50)
    email: Optional[EmailStr] = None
    source: Optional[str] = "manual"
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    preferred_locations: Optional[List[str]] = Field(default_factory=list)
    timeline: Optional[str] = None
    loan_status: Optional[str] = None
    notes: Optional[Any] = None
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)

class LeadUpdateDTO(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None
    pipeline_stage: Optional[str] = None
    score: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    preferred_locations: Optional[List[str]] = None
    timeline: Optional[str] = None
    loan_status: Optional[str] = None
    assigned_to: Optional[str] = None

class LeadQualifyDTO(BaseModel):
    score: str = Field(..., json_schema_extra={"example": "hot"})
    score_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    qualification_notes: Optional[str] = None
    recommended_properties: Optional[List[str]] = Field(default_factory=list)

class LeadSearchDTO(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    query: Optional[str] = None
    score: Optional[str] = None
    stage: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    cursor: Optional[str] = None

class LeadBulkDTO(BaseModel):
    lead_ids: List[uuid.UUID] = Field(..., min_length=1)
    action: str = Field(..., json_schema_extra={"example": "update_stage"})
    target_value: str = Field(...)

class LeadExportDTO(BaseModel):
    format: str = Field(default="csv", json_schema_extra={"example": "csv"})
    lead_ids: Optional[List[uuid.UUID]] = None
    filters: Optional[LeadSearchDTO] = None

class LeadResponseDTO(BaseModel):
    id: uuid.UUID
    broker_id: uuid.UUID
    phone: str
    name: str
    source: str
    score: str
    score_confidence: float
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    preferred_locations: List[str] = Field(default_factory=list)
    timeline: Optional[str] = None
    loan_status: Optional[str] = None
    status: str
    pipeline_stage: str
    notes: Optional[Any] = None
    qualified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LeadPaginatedResponseDTO(BaseModel):
    items: List[LeadResponseDTO]
    total: int
    page: int
    pages: int
    limit: int
    has_next: bool
    has_prev: bool
