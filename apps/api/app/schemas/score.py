from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
from pydantic import BaseModel, ConfigDict, Field

class QualifyRequest(BaseModel):
    lead_id: uuid.UUID
    force: bool = False

class QualifyResponse(BaseModel):
    lead_id: uuid.UUID
    score: str = Field(..., max_length=20)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    extracted_data: Dict[str, Any] = Field(default_factory=dict)

class ScoreBase(BaseModel):
    score: str = Field(..., max_length=20)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)

class ScoreCreate(ScoreBase):
    lead_id: uuid.UUID

class ScoreUpdate(BaseModel):
    score: Optional[str] = Field(None, max_length=20)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None

class ScoreResponse(ScoreBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ScoreListResponse(BaseModel):
    items: List[ScoreResponse]
    total: int
    page: int
    page_size: int
    pages: int
