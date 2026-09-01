import re
from datetime import datetime, timezone
from typing import Optional, List
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, computed_field

INDIAN_PHONE_REGEX = re.compile(r"^(\+91)?([6-9]\d{9})$")

def validate_and_normalize_indian_phone(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("Phone number must be a valid text string.")
    
    # Strip spaces, hyphens, parentheses, dots
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", v.strip())
    if not cleaned:
        return None
    
    # Handle leading 0 (e.g. 09876543210 -> 9876543210)
    if cleaned.startswith("0") and len(cleaned) == 11 and cleaned[1] in "6789":
        cleaned = cleaned[1:]
        
    match = INDIAN_PHONE_REGEX.match(cleaned)
    if not match:
        raise ValueError("Invalid phone number format. Please enter a valid 10-digit Indian phone number (e.g. +91 98765 43210 or 9876543210).")
    ten_digit = match.group(2)
    return f"+91{ten_digit}"

class BrokerBase(BaseModel):
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    name: str = Field(..., max_length=255)
    agency_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field("Bengaluru", max_length=100)
    whatsapp_number: Optional[str] = Field(None, max_length=20)

    @field_validator("phone", "whatsapp_number", mode="before")
    def validate_phone_numbers(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        res = validate_and_normalize_indian_phone(v)
        return res

class BrokerCreate(BrokerBase):
    subscription_status: str = Field("trial", max_length=20)
    subscription_plan: Optional[str] = Field(None, max_length=50)

class BrokerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    agency_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    whatsapp_number: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator("phone", "whatsapp_number", mode="before")
    def validate_phone_numbers(cls, v: Optional[str]) -> Optional[str]:
        return validate_and_normalize_indian_phone(v)

class BrokerResponse(BrokerBase):
    id: uuid.UUID
    subscription_status: str
    onboarding_status: str
    trial_ends_at: datetime
    subscription_plan: Optional[str] = None
    razorpay_customer_id: Optional[str] = None
    razorpay_subscription_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    def trial_days_remaining(self) -> int:
        if self.subscription_status == "active":
            return 30
        if self.subscription_status != "trial" or not self.trial_ends_at:
            return 0
        now = datetime.now(timezone.utc)
        trial_end = self.trial_ends_at
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        diff = trial_end - now
        return max(0, diff.days + (1 if diff.seconds > 0 else 0))

    model_config = ConfigDict(from_attributes=True)

class BrokerListResponse(BaseModel):
    items: List[BrokerResponse]
    total: int
    page: int
    page_size: int
    pages: int
