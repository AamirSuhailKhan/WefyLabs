"""
Pydantic V2 DTO Schemas for AI Memory & Customer Intelligence Engine
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# ─── Record DTOs ───────────────────────────────────────────────────────────────

class RecordMemoryRequest(BaseModel):
    memory_type: str = Field(..., description="PREFERENCE | CONSTRAINT | NEGATIVE_PREFERENCE | INTENT | LOCATION | BUDGET | OBJECTION")
    key: str = Field(..., description="Canonical key, e.g. budget_max, bedrooms, locality")
    value_json: Dict[str, Any] = Field(default_factory=dict)
    value_text: Optional[str] = None
    source_type: str = Field("CUSTOMER_STATED", description="CUSTOMER_STATED | AGENT_CONFIRMED | CRM_VERIFIED | BEHAVIORAL_SIGNAL | AI_INFERRED")
    source_id: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    importance: float = Field(0.80, ge=0.0, le=1.0)
    is_customer_safe: bool = Field(True)


class MemoryEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_type: str
    evidence_id: str
    raw_snippet: Optional[str] = None
    timestamp_utc: datetime


class MemoryVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    value_json: Dict[str, Any]
    value_text: Optional[str] = None
    source_type: str
    confidence: float
    status: str
    reason_for_change: Optional[str] = None
    superseded_at: datetime


class MemoryRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    memory_type: str
    key: str
    value_json: Dict[str, Any]
    value_text: Optional[str] = None
    source_type: str
    source_id: Optional[str] = None
    confidence: float
    importance: float
    status: str
    version_number: int
    is_customer_safe: bool
    last_confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ─── Extraction & Search DTOs ──────────────────────────────────────────────────

class ExtractMemoryRequest(BaseModel):
    text: str = Field(..., description="Natural language text or customer message")
    is_customer_message: bool = Field(True)


class ExtractMemoryResponse(BaseModel):
    candidates_count: int
    candidates: List[Dict[str, Any]]


class MemoryContextResponse(BaseModel):
    lead_id: str
    context_text: str
    memories_count: int


class ConfirmMemoryRequest(BaseModel):
    key: str
    confirmed_by_customer: bool = True


class CorrectMemoryRequest(BaseModel):
    key: str
    corrected_value_json: Dict[str, Any]
    corrected_value_text: Optional[str] = None
    reason: Optional[str] = None


class ObjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    description: str
    status: str
    recurrence_count: int
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None


class PropertyFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: str
    feedback_type: str
    rejection_reason_code: Optional[str] = None
    feedback_notes: Optional[str] = None
    interest_score: float
