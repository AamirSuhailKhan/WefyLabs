from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class NotificationSendDTO(BaseModel):
    recipient_id: str
    title: str
    body: Optional[str] = None
    category: str = Field(default="system")    # lead | task | meeting | billing | system | ai
    channels: List[str] = Field(default=["in_app"])  # in_app | email | whatsapp | telegram | sms
    action_url: Optional[str] = None
    organization_id: Optional[str] = None
    priority: str = "normal"                   # low | normal | high | urgent
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class NotificationPreferenceUpdateDTO(BaseModel):
    channel: str
    event_type: str
    is_enabled: bool = True
    is_muted: bool = False
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class NotificationResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    broker_id: str
    organization_id: Optional[str] = None
    category: str
    title: str
    body: Optional[str] = None
    action_url: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime



class NotificationSearchDTO(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=30, ge=1, le=100)
    is_read: Optional[bool] = None
    category: Optional[str] = None
