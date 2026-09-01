from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid


class AuditCreateDTO(BaseModel):
    action: str = Field(..., json_schema_extra={"example": "lead.create"})
    resource_type: str = Field(..., json_schema_extra={"example": "lead"})
    resource_id: Optional[str] = None
    actor_id: Optional[uuid.UUID] = None
    actor_type: str = "user"
    organization_id: Optional[uuid.UUID] = None
    previous_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changes: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    api_key_id: Optional[str] = None


class AuditSearchDTO(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=200)
    organization_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    actor_id: Optional[str] = None


class AuditResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    actor_id: Optional[uuid.UUID] = None
    actor_type: str
    organization_id: Optional[uuid.UUID] = None
    changes: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: datetime
