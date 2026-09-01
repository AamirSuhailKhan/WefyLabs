from typing import Optional
from pydantic import BaseModel, Field


class FeatureFlagUpdateDTO(BaseModel):
    is_enabled: bool
    rollout_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    scope: str = "global"
    scope_id: Optional[str] = None
    description: Optional[str] = None
    environment: str = "production"


class FeatureFlagResponseDTO(BaseModel):
    id: str
    key: str
    scope: str
    scope_id: Optional[str] = None
    is_enabled: bool
    rollout_percentage: float
    environment: str
    description: Optional[str] = None

    class Config:
        from_attributes = True
