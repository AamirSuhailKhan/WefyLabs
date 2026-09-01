from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class SettingUpsertDTO(BaseModel):
    key: str
    value: Any
    scope: str = "organization"
    scope_id: Optional[str] = None
    value_type: str = "string"
    description: Optional[str] = None
    is_sensitive: bool = False


class SettingResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    scope: str
    scope_id: Optional[str] = None
    value: Optional[Any] = None
    value_type: str
    description: Optional[str] = None
    is_sensitive: bool
    updated_at: datetime

