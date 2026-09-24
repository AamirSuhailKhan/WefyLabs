"""
Part 21.1 — Lead Acquisition Domain DTOs
=========================================
Request/Response data transfer objects for the lead acquisition API.

Vocabulary: Lead, Prospect, Buyer, Seller, Tenant, Landlord, Investor,
            Broker, Campaign, Source, Property, Listing, Viewing.
NEVER: candidate, job, resume, CV, vacancy, employment.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any, Union
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

    city: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=255)

    # Idempotency
    idempotency_key: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().lower()
            if not v:
                return None
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


class PublicLeadCaptureDTO(BaseModel):
    """
    Public website / embeddable form / API capture payload.
    Supports flexible budget types (number or string like '50L', '1.5 Cr', '₹50,000,000').
    Enforces anti-spam honeypot.
    """
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)
    city: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=255)
    property_type: Optional[str] = Field(None, max_length=100)
    transaction_type: Optional[str] = Field(None, max_length=30)
    requirement: Optional[str] = None
    message: Optional[str] = None
    budget: Optional[Union[str, Decimal, int, float]] = None
    budget_min: Optional[Union[str, Decimal, int, float]] = None
    budget_max: Optional[Union[str, Decimal, int, float]] = None
    currency: Optional[str] = Field(None, max_length=3)
    timeline: Optional[str] = None
    campaign_id: Optional[str] = None
    landing_page: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    marketing_consent: bool = False
    whatsapp_consent: bool = False
    email_consent: bool = False
    idempotency_key: Optional[str] = None
    # Spam trap / Honeypot: bots fill this hidden field; humans don't
    hp_trap: Optional[str] = Field(None, alias="_hp_trap")
    website_url_hp: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None

    model_config = {"populate_by_name": True}

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().lower()
            if not v:
                return None
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
        return bool(self.phone or self.email)

    @property
    def is_honeypot_triggered(self) -> bool:
        """Returns True if bot honeypot fields were filled."""
        return bool(self.hp_trap or self.website_url_hp)


def _parse_flexible_budget(val: Optional[Union[str, Decimal, int, float]]) -> Optional[Decimal]:
    """
    Normalizes Indian and International budget representations:
      '50L', '50 lakhs', '1.5 Cr', '1.5 crore', '₹5,000,000', 5000000 -> Decimal(5000000)
    """
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(int(val)))

    text = str(val).strip().replace(",", "").replace("₹", "").replace("$", "").replace("AED", "").strip()
    if not text:
        return None

    # Check for Lakhs
    lakh_match = re.search(r"^([\d\.]+)\s*(?:l|lakh|lakhs|lac|lacs)$", text, re.IGNORECASE)
    if lakh_match:
        try:
            return Decimal(str(int(float(lakh_match.group(1)) * 100000)))
        except ValueError:
            pass

    # Check for Crores
    cr_match = re.search(r"^([\d\.]+)\s*(?:cr|crore|crores)$", text, re.IGNORECASE)
    if cr_match:
        try:
            return Decimal(str(int(float(cr_match.group(1)) * 10000000)))
        except ValueError:
            pass

    # Check for k / M
    k_match = re.search(r"^([\d\.]+)\s*k$", text, re.IGNORECASE)
    if k_match:
        try:
            return Decimal(str(int(float(k_match.group(1)) * 1000)))
        except ValueError:
            pass

    m_match = re.search(r"^([\d\.]+)\s*m$", text, re.IGNORECASE)
    if m_match:
        try:
            return Decimal(str(int(float(m_match.group(1)) * 1000000)))
        except ValueError:
            pass

    # Plain digits
    digits_only = re.sub(r"[^\d.]", "", text)
    if digits_only:
        try:
            return Decimal(str(int(float(digits_only))))
        except ValueError:
            pass

    return None


def _sanitize_text(text: Optional[str], max_chars: int = 1000) -> Optional[str]:
    """Sanitizes text fields to protect against prompt injection and control character abuse."""
    if not text:
        return None
    cleaned = text.strip()[:max_chars]
    # Neutralize prompt injection markers if passed directly to Gemini downstream
    injection_patterns = [
        r"(?i)\bignore\s+all\s+(?:previous|prior)\s+instructions\b",
        r"(?i)\bsystem\s*:\s*",
        r"(?i)\bdeveloper\s+mode\b",
        r"(?i)\byou\s+are\s+now\s+(?:in|a\s+malicious)\b",
    ]
    for pattern in injection_patterns:
        cleaned = re.sub(pattern, "[FILTERED_INSTRUCTION]", cleaned)
    # Remove script tags
    cleaned = re.sub(r"(?i)<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", cleaned)
    return cleaned


_sanitize_untrusted_text = _sanitize_text


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


# ─── Canonical Universal Lead Intake DTOs (Part 9) ───────────────────────────

class UniversalSourceType:
    WEBSITE = "WEBSITE"
    PUBLIC_AI = "PUBLIC_AI"
    MANUAL = "MANUAL"
    CSV = "CSV"
    API = "API"
    WEBHOOK = "WEBHOOK"
    EMAIL = "EMAIL"
    META = "META"
    GOOGLE = "GOOGLE"
    PORTAL = "PORTAL"
    REFERRAL = "REFERRAL"
    PAID_AD = "PAID_AD"
    ORGANIC = "ORGANIC"
    AI_AGENT = "AI_AGENT"
    OTHER = "OTHER"

    @classmethod
    def all_values(cls) -> set[str]:
        return {
            cls.WEBSITE, cls.PUBLIC_AI, cls.MANUAL, cls.CSV,
            cls.API, cls.WEBHOOK, cls.EMAIL, cls.META,
            cls.GOOGLE, cls.PORTAL, cls.REFERRAL, cls.PAID_AD,
            cls.ORGANIC, cls.AI_AGENT, cls.OTHER
        }


class CanonicalLeadIntakeDTO(BaseModel):
    """
    Universal Lead Intake Contract for WefyLabs Revenue Growth Layer (Part 9).
    Single authoritative contract ingested from:
      - Web forms & widgets
      - Public AI conversation experience
      - Internal manual lead creation
      - CSV bulk imports
      - Authenticated REST API
      - External webhooks (Meta, Google, Portals)
    """
    source_type: str = Field(
        default=UniversalSourceType.WEBSITE,
        description="Controlled source taxonomy: WEBSITE|PUBLIC_AI|MANUAL|CSV|API|WEBHOOK|EMAIL|META|GOOGLE|PORTAL|REFERRAL|OTHER"
    )
    external_source: Optional[str] = Field(
        default=None,
        description="Underlying origin identifier, e.g. 'website_form', 'meta_lead_ads', 'csv_importer'"
    )
    external_lead_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="External lead ID / submission ID from provider for idempotency tracking"
    )
    name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    message: Optional[str] = Field(default=None, max_length=4000)

    # Real-estate requirements
    property_type: Optional[str] = Field(default=None, max_length=100)
    transaction_type: Optional[str] = Field(default=None, max_length=50)
    property_interest: Optional[str] = Field(default=None, max_length=255)
    property_id: Optional[str] = Field(default=None, max_length=36)
    budget: Optional[Union[str, int, float, Decimal]] = None
    budget_min: Optional[Union[str, int, float, Decimal]] = None
    budget_max: Optional[Union[str, int, float, Decimal]] = None
    currency: Optional[str] = Field(default="INR", max_length=3)
    city: Optional[str] = Field(default=None, max_length=100)
    preferred_locations: Optional[List[str]] = Field(default_factory=list)
    timeline: Optional[str] = Field(default=None, max_length=50)
    raw_requirements: Optional[Union[str, Dict[str, Any]]] = None
    requirements: Optional[Dict[str, Any]] = None

    # Source Attribution & UTM parameters
    landing_page: Optional[str] = Field(default=None, max_length=2000)
    referrer: Optional[str] = Field(default=None, max_length=2000)
    utm_source: Optional[str] = Field(default=None, max_length=255)
    utm_medium: Optional[str] = Field(default=None, max_length=255)
    utm_campaign: Optional[str] = Field(default=None, max_length=255)
    utm_term: Optional[str] = Field(default=None, max_length=255)
    utm_content: Optional[str] = Field(default=None, max_length=255)

    # Association & Context
    campaign_id: Optional[str] = None
    source_id: Optional[str] = None
    conversation_id: Optional[str] = Field(
        default=None,
        description="Active conversation ID if lead was captured from a conversational AI experience"
    )
    assigned_broker_id: Optional[str] = Field(
        default=None,
        description="Optional pre-assigned broker UUID (subject to tenant verification)"
    )

    # Consent
    consent: Optional[Union[bool, Dict[str, Any]]] = None
    marketing_consent: bool = False
    email_consent: bool = False
    whatsapp_consent: bool = False
    sms_consent: bool = False

    # Security & Idempotency
    idempotency_key: Optional[str] = Field(default=None, max_length=255)
    source_metadata: Optional[Dict[str, Any]] = None

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        upper = (v or "OTHER").strip().upper()
        if upper not in UniversalSourceType.all_values():
            return UniversalSourceType.OTHER
        return upper

    @field_validator("email")
    @classmethod
    def validate_email_norm(cls, v: Optional[str]) -> Optional[str]:
        if v:
            clean = v.strip().lower()
            return clean if clean else None
        return None

    def validate_contact_present(self) -> bool:
        """Enforces that at least one of phone or email is provided."""
        has_phone = bool(self.phone and self.phone.strip())
        has_email = bool(self.email and self.email.strip())
        return has_phone or has_email


class CanonicalLeadIntakeResultDTO(BaseModel):
    """Universal result contract for all lead ingestion operations."""
    status: str = Field(description="ACCEPTED | DUPLICATE | REJECTED | FAILED")
    lead_id: str
    customer_id: str
    event_id: str
    is_duplicate: bool = False
    is_new_lead: bool = True
    identity_outcome: str = Field(
        description="NEW_LEAD | UPDATE_EXISTING_LEAD | LINKED_TO_EXISTING_CUSTOMER | DUPLICATE_SOURCE_EVENT | POSSIBLE_DUPLICATE"
    )
    attribution_id: Optional[str] = None
    assigned_broker_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message: str = "Lead processed successfully"
    activations: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


# ─── Reconciliation & Backfill DTOs (Part 13) ────────────────────────────────

class ReconciliationRequestDTO(BaseModel):
    provider: str = Field(..., description="meta|google")
    source_id: Optional[str] = None
    form_id: Optional[str] = None
    since_hours: int = Field(default=24, ge=1, le=168)


class ReconciliationResponseDTO(BaseModel):
    status: str
    provider: str
    reconciled_count: int
    missing_count: int
    recovered_count: int
    details: Optional[Dict[str, Any]] = None


class BackfillRequestDTO(BaseModel):
    provider: str = Field(..., description="meta|google")
    source_id: str
    form_id: Optional[str] = None
    start_time: datetime
    end_time: datetime
    limit: int = Field(default=100, ge=1, le=500)
    dry_run: bool = False


class BackfillResponseDTO(BaseModel):
    status: str
    provider: str
    processed_count: int
    dry_run: bool
    window: Dict[str, Any]


class ProviderConnectDTO(BaseModel):
    provider: str = Field(..., description="meta|google")
    name: Optional[str] = None
    page_id: Optional[str] = None
    form_id: Optional[str] = None
    customer_id: Optional[str] = None
    ad_account_id: Optional[str] = None
    access_token: Optional[str] = None
    app_secret: Optional[str] = None
    developer_token: Optional[str] = None
    google_key: Optional[str] = None
    verify_token: Optional[str] = None
    webhook_url_token: Optional[str] = None


class ProviderStatusDTO(BaseModel):
    provider: str
    status: str
    is_configured: bool
    note: Optional[str] = None
    last_verified_at: Optional[datetime] = None


