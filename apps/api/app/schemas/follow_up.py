from datetime import datetime
from typing import Optional, List
import uuid
from pydantic import BaseModel, ConfigDict, Field

class FollowUpBase(BaseModel):
    sequence_number: int = Field(..., ge=1, le=3)
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    status: str = Field("scheduled", max_length=20)
    message: str

class FollowUpCreate(FollowUpBase):
    lead_id: uuid.UUID

class FollowUpUpdate(BaseModel):
    sequence_number: Optional[int] = Field(None, ge=1, le=3)
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    status: Optional[str] = Field(None, max_length=20)
    message: Optional[str] = None

class FollowUpResponse(FollowUpBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FollowUpListResponse(BaseModel):
    items: List[FollowUpResponse]
    total: int
    page: int
    page_size: int
    pages: int
