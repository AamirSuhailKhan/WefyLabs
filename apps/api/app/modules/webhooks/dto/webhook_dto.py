from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class WebhookPayloadDTO(BaseModel):
    provider: str = Field(..., json_schema_extra={"example": "whatsapp"})  # whatsapp | facebook | telegram | zapier | n8n | custom
    event_type: str = Field(default="generic_webhook")
    payload: Dict[str, Any] = Field(...)
    signature: Optional[str] = None
    timestamp: Optional[str] = None
    nonce: Optional[str] = None

class WebhookVerificationDTO(BaseModel):
    provider: str
    verified: bool
    reason: Optional[str] = None

class WebhookResponseDTO(BaseModel):
    received: bool = True
    event_id: str
    status: str = "queued"
