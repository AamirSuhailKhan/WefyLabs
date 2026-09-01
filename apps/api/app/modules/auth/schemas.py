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

class OnboardRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Broker full name")
    phone: str = Field(..., max_length=20, description="Contact phone number")
    whatsapp_number: str = Field(..., max_length=20, description="WhatsApp contact number")
    agency_name: str = Field(..., min_length=1, max_length=255, description="Agency or company name")
    city: str = Field("Bengaluru", min_length=1, max_length=100, description="Operating city")

    @field_validator("name", "agency_name", "city", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if isinstance(v, str):
            val = v.strip()
            if not val:
                raise ValueError("This field cannot be blank.")
            return val
        return v

    @field_validator("phone", "whatsapp_number", mode="before")
    @classmethod
    def validate_phone_numbers(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Phone number is required.")
        res = validate_and_normalize_indian_phone(v)
        if not res:
            raise ValueError("Invalid phone number format. Please enter a valid 10-digit Indian phone number.")
        return res

class GoogleAuthUrlResponse(BaseModel):
    auth_url: str
    state: str

class GoogleExchangeRequest(BaseModel):
    code: str
    state: Optional[str] = None
    redirect_uri: Optional[str] = None
    # For automated tests / mock exchange:
    email: Optional[EmailStr] = None
    name: Optional[str] = None
