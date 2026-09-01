"""
Canonical Lead DTO & Ingestion Validation
=========================================
Standardized canonical schema that EVERY incoming lead must be normalized into,
regardless of original source (Website, WhatsApp, Email, CSV, REST Webhook).
"""
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class CanonicalLeadDTO(BaseModel):
    """
    Canonical Lead Schema.
    All source connectors must map their raw payload into this exact format.
    """
    name: str = Field(..., min_length=1, max_length=255, json_schema_extra={"example": "John Doe"})
    email: Optional[str] = Field(None, json_schema_extra={"example": "john.doe@example.com"})
    phone: str = Field(..., json_schema_extra={"example": "+971501234567"})
    country_code: str = Field(default="AE", json_schema_extra={"example": "AE"})
    whatsapp_number: Optional[str] = Field(None, json_schema_extra={"example": "+971501234567"})
    budget_min: Optional[float] = Field(None, ge=0)
    budget_max: Optional[float] = Field(None, ge=0)
    currency: str = Field(default="USD", max_length=10)
    property_type: Optional[str] = Field(None, json_schema_extra={"example": "apartment"})
    city: Optional[str] = Field(None, json_schema_extra={"example": "Dubai"})
    state: Optional[str] = Field(None)
    country: Optional[str] = Field(default="United Arab Emirates")
    source: str = Field(..., json_schema_extra={"example": "website_contact_form"})
    campaign: Optional[str] = Field(None, json_schema_extra={"example": "google_ads_q3"})
    language: str = Field(default="en", max_length=10)
    notes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 7:
            raise ValueError("Phone number must contain at least 7 digits.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        cleaned = v.strip().lower()
        if "@" not in cleaned or "." not in cleaned:
            raise ValueError("Invalid email format.")
        return cleaned


class IngestionRequestDTO(BaseModel):
    """Envelope for incoming Lead Ingestion API requests."""
    source: str = Field(..., json_schema_extra={"example": "website"})
    connector_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    payload: Dict[str, Any] = Field(..., json_schema_extra={"example": {"name": "John Doe", "phone": "+971501234567"}})


class IngestionResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ingestion_id: str
    status: str # ingested | duplicate | rejected | queued
    lead_id: Optional[str] = None
    source: str
    latency_ms: float
    message: str
