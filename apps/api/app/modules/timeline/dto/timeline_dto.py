from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime


class TimelineCreateDTO(BaseModel):
    organization_id: str
    resource_type: str = Field(..., example="lead")  # lead | contact | property | deal
    resource_id: str
    event_type: str = Field(..., example="note_added")
    title: str
    body: Optional[str] = None
    channel: Optional[str] = None        # whatsapp | email | phone | system | ai
    actor_id: Optional[str] = None
    actor_type: str = "user"             # user | system | ai | webhook
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class TimelineSearchDTO(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=200)
    event_type: Optional[str] = None
    channel: Optional[str] = None
    actor_type: Optional[str] = None


class TimelineResponseDTO(BaseModel):
    id: str
    organization_id: str
    resource_type: str
    resource_id: str
    event_type: str
    channel: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: str
    title: str
    body: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class TimelinePaginatedDTO(BaseModel):
    items: List[TimelineResponseDTO]
    total: int
    page: int
    pages: int
    limit: int
    has_next: bool
    has_prev: bool
