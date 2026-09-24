from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class ApiKeyCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None


class ApiKeyResponseDTO(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreatedDTO(ApiKeyResponseDTO):
    key: str = Field(..., description="Raw API key — shown ONCE only")
