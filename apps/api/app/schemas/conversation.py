from datetime import datetime
from typing import Optional, List
import uuid
from pydantic import BaseModel, ConfigDict, Field

class ConversationBase(BaseModel):
    direction: str = Field(..., max_length=10)
    sender_type: str = Field(..., max_length=20)
    message: str
    message_type: str = Field("text", max_length=20)
    whatsapp_message_id: Optional[str] = Field(None, max_length=255)

class ConversationCreate(ConversationBase):
    lead_id: uuid.UUID

class ConversationUpdate(BaseModel):
    direction: Optional[str] = Field(None, max_length=10)
    sender_type: Optional[str] = Field(None, max_length=20)
    message: Optional[str] = None
    message_type: Optional[str] = Field(None, max_length=20)
    whatsapp_message_id: Optional[str] = Field(None, max_length=255)

class ConversationResponse(ConversationBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationListResponse(BaseModel):
    items: List[ConversationResponse]
    total: int
    page: int
    page_size: int
    pages: int
