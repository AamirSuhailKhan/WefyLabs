from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator, computed_field

from app.schemas.broker import validate_and_normalize_indian_phone
from app.schemas.conversation import ConversationResponse
from app.schemas.score import ScoreResponse
from app.schemas.follow_up import FollowUpResponse

class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)
    color_tag: Optional[str] = Field("blue", max_length=20)

class NoteResponse(BaseModel):
    id: str
    content: str
    color_tag: str = "blue"
    created_at: str

class StatusUpdate(BaseModel):
    status: str = Field(..., max_length=20)

    @field_validator("status")
    def validate_status(cls, v: str) -> str:
        allowed = {"pending", "active", "qualified", "converted", "lost"}
        if v not in allowed:
            raise ValueError(f"Invalid status: {v}. Must be one of {allowed}")
        return v

class StageUpdate(BaseModel):
    stage: str = Field(..., max_length=30)

    @field_validator("stage")
    def validate_stage(cls, v: str) -> str:
        allowed = {"new", "contacted", "viewing", "negotiating", "closed_won", "closed_lost"}
        if v not in allowed:
            raise ValueError(f"Invalid stage: {v}. Must be one of {allowed}")
        return v

class LeadBase(BaseModel):
    phone: str = Field(..., max_length=20)
    name: Optional[str] = Field(None, max_length=255)
    source: str = Field("manual", max_length=50)
    score: str = Field("pending", max_length=20)
    score_confidence: float = Field(0.0, ge=0.0, le=1.0)
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = Field(None, max_length=50)
    transaction_type: Optional[str] = Field(None, max_length=20)
    preferred_locations: List[str] = Field(default_factory=list)
    timeline: Optional[str] = Field(None, max_length=50)
    loan_status: Optional[str] = Field(None, max_length=50)
    status: str = Field("pending", max_length=20)
    pipeline_stage: str = Field("new", max_length=30)

    @field_validator("phone", mode="before")
    def validate_phone_number(cls, v: str) -> str:
        res = validate_and_normalize_indian_phone(v)
        assert res is not None
        return res

class LeadCreate(BaseModel):
    phone: str = Field(..., max_length=20)
    name: Optional[str] = Field(None, max_length=255)
    source: Optional[str] = Field("manual", max_length=50)
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = Field(None, max_length=50)
    transaction_type: Optional[str] = Field(None, max_length=20)
    preferred_locations: Optional[List[str]] = None
    timeline: Optional[str] = Field(None, max_length=50)
    loan_status: Optional[str] = Field(None, max_length=50)
    notes: Optional[Union[str, NoteCreate]] = None

    @field_validator("phone", mode="before")
    def validate_phone_number(cls, v: str) -> str:
        res = validate_and_normalize_indian_phone(v)
        assert res is not None
        return res

class LeadUpdate(BaseModel):
    phone: Optional[str] = Field(None, max_length=20)
    name: Optional[str] = Field(None, max_length=255)
    source: Optional[str] = Field(None, max_length=50)
    score: Optional[str] = Field(None, max_length=20)
    score_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = Field(None, max_length=50)
    transaction_type: Optional[str] = Field(None, max_length=20)
    preferred_locations: Optional[List[str]] = None
    timeline: Optional[str] = Field(None, max_length=50)
    loan_status: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=20)
    pipeline_stage: Optional[str] = Field(None, max_length=30)
    last_message_at: Optional[datetime] = None
    qualified_at: Optional[datetime] = None

    @field_validator("phone", mode="before")
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        return validate_and_normalize_indian_phone(v)

class LeadResponse(LeadBase):
    id: uuid.UUID
    broker_id: uuid.UUID
    notes: List[Dict[str, Any]] = Field(default_factory=list)
    last_message_at: Optional[datetime] = None
    qualified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    conversations: List[ConversationResponse] = Field(default_factory=list)
    scores: List[ScoreResponse] = Field(default_factory=list)
    follow_ups: List[FollowUpResponse] = Field(default_factory=list)

    @computed_field
    def conversation_count(self) -> int:
        return len(self.conversations)

    @computed_field
    def latest_score(self) -> Optional[ScoreResponse]:
        if self.scores:
            return self.scores[0]
        return None

    model_config = ConfigDict(from_attributes=True)

class LeadListResponse(BaseModel):
    data: List[LeadResponse]
    total: int
    page: int
    pages: int
