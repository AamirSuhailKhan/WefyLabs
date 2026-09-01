"""
Part 21.1 — Lead Acquisition Domain DTOs
=========================================
Request/Response data transfer objects for the lead acquisition API.

Vocabulary: Lead, Prospect, Buyer, Seller, Tenant, Landlord, Investor,
            Broker, Campaign, Source, Property, Listing, Viewing.
NEVER: candidate, job, resume, CV, vacancy, employment.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator
import re


# ─── Lead Source DTOs ────────────────────────────────────────────────────────

class LeadSourceCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    channel: str = Field(..., description="WEBSITE|WHATSAPP|META|GOOGLE|EMAIL|TELEGRAM|API|WEBHOOK|MANUAL|OTHER")
    provider: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    market_id: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=100_000)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        valid = {"WEBSITE","WHATSAPP","META","GOOGLE","EMAIL","TELEGRAM","CRM","API","WEBHOOK","PARTNER","MANUAL","OTHER"}
        if v.upper() not in valid:
            raise ValueError(f"channel must be one of: {', '.join(sorted(valid))}")
        return v.upper()


class LeadSourceUpdateDTO(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    rate_limit_per_hour: Optional[int] = None


class LeadSourceResponseDTO(BaseModel):
    id: str
    organization_id: str
    name: str
    channel: str
    provider: Optional[str]
    status: str
    country_code: Optional[str]
    market_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Lead Campaign DTOs ───────────────────────────────────────────────────────

class LeadCampaignCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_id: Optional[str] = None
    market_id: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    budget: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 4217: AED, INR, USD")
    timezone: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    channel: Optional[str] = None
    target_lead_intent: Optional[str] = None
    target_transaction_type: Optional[str] = None
    property_ids: Optional[List[str]] = Field(None, description="Property IDs to associate with this campaign")
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v


class LeadCampaignUpdateDTO(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[Decimal] = None
    currency: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    property_ids: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class LeadCampaignResponseDTO(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    status: str
    source_id: Optional[str]
    market_id: Optional[str]
    country_code: Optional[str]
    budget: Optional[Decimal]
    currency: Optional[str]
    channel: Optional[str]
    start_at: Optional[datetime]
    end_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Website Lead Acquisition DTOs ───────────────────────────────────────────

class WebsiteLeadAcquisitionDTO(BaseModel):
    """
    Payload for POST /api/v1/leads/acquisition/website

    All fields optional except: at least one of (phone, email) must be present.
    DO NOT invent missing fields. Missing = None/null.
    """
    # Contact
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)

    # Message
    message: Optional[str] = None

    # Property context (must belong to same org — verified server-side)
    property_id: Optional[str] = None

    # Campaign context
    campaign_id: Optional[str] = None
    source_id: Optional[str] = None

    # Landing page & UTM (NULL if absent — never fabricated)
    landing_page: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None

    # Explicit consent (UNKNOWN by default — never auto-granted)
    marketing_consent: bool = False
    whatsapp_consent: bool = False
    email_consent: bool = False

    # Lead interest
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    lead_intent: Optional[str] = None
    budget_min: Optional[Decimal] = Field(None, ge=0)
    budget_max: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    timeline: Optional[str] = None

    # Country/Language (client-supplied, verified server-side)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    language: Optional[str] = None

    # Idempotency
    idempotency_key: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().lower()
            if "@" not in v:
                raise ValueError("Invalid email format")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    def validate_contact_present(self) -> bool:
        """At least phone or email must be present."""
        return bool(self.phone or self.email)


class AcquisitionResponseDTO(BaseModel):
    """Standard response for acquisition endpoints."""
    acquisition_event_id: str
    prospect_id: Optional[str]
    status: str  # accepted | duplicate | rejected
    message: str
    canonical_lead_id: Optional[str] = None
    is_new_prospect: bool = True


# ─── Webhook Acquisition DTOs ─────────────────────────────────────────────────

class WebhookAcquisitionDTO(BaseModel):
    """Generic webhook acquisition payload."""
    provider: str
    event_type: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    external_id: Optional[str] = None
    signature: Optional[str] = None
    timestamp: Optional[int] = None  # Unix timestamp for replay protection


# ─── CRM Import DTOs ──────────────────────────────────────────────────────────

class CrmImportRowDTO(BaseModel):
    """Single row from a CRM import (CSV, HubSpot, Salesforce, etc.)."""
    # Required: at least one contact field
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    # Optional enrichment
    company: Optional[str] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    lead_intent: Optional[str] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    currency: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    language: Optional[str] = None
    notes: Optional[str] = None

    # Consent (from source system if available)
    marketing_consent: Optional[bool] = None
    email_consent: Optional[bool] = None

    # Attribution
    source_name: Optional[str] = None
    external_id: Optional[str] = None
    campaign_name: Optional[str] = None

    # Raw data preserved
    raw_data: Optional[Dict[str, Any]] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().lower() or None
        return v


# ─── Prospect DTOs ────────────────────────────────────────────────────────────

class ProspectResponseDTO(BaseModel):
    id: str
    organization_id: str
    status: str
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    phone_e164: Optional[str]
    country: Optional[str]
    city: Optional[str]
    language: Optional[str]
    lead_intent: Optional[str]
    property_type: Optional[str]
    transaction_type: Optional[str]
    budget_min: Optional[Decimal]
    budget_max: Optional[Decimal]
    currency: Optional[str]
    timeline: Optional[str]
    consent_status: str
    duplicate_status: str
    canonical_lead_id: Optional[str]
    acquisition_quality_score: Optional[float]
    source_id: Optional[str]
    campaign_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProspectImportDTO(BaseModel):
    """Request to import a prospect as a canonical CRM lead."""
    override_name: Optional[str] = None
    override_email: Optional[str] = None
    broker_id: Optional[str] = Field(None, description="Assign to specific broker (org must own broker)")


class ProspectRejectDTO(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)
