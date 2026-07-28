from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.schemas.broker import BrokerResponse, validate_and_normalize_indian_phone

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    phone: str = Field(..., max_length=20)
    name: str = Field(..., max_length=255)
    agency_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field("Bengaluru", max_length=100)
    whatsapp_number: str = Field(..., max_length=20)

    @field_validator("phone", "whatsapp_number", mode="before")
    def validate_phone_numbers(cls, v: str) -> str:
        res = validate_and_normalize_indian_phone(v)
        assert res is not None
        return res

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class OAuthCallbackRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    whatsapp_number: Optional[str] = Field(None, max_length=20)
    agency_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field("Bengaluru", max_length=100)

    @field_validator("phone", "whatsapp_number", mode="before")
    def validate_phone_numbers(cls, v: Optional[str]) -> Optional[str]:
        return validate_and_normalize_indian_phone(v)

class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    broker: BrokerResponse
