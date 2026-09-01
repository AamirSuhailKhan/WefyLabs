"""
Part 21.2 — Real-Estate AI Lead Discovery DTOs
===============================================
Data Transfer Objects for the AI Lead Discovery Engine.

Strictly real-estate domain terminology:
  Prospect, Buyer, Seller, Tenant, Landlord, Investor, Broker,
  Campaign, Discovery Run, Candidate, Evidence, Signal, Property.
Zero recruitment keywords.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ─── Discovery Source DTOs ───────────────────────────────────────────────────

class DiscoverySourceCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    provider: str = Field(..., description="meta_lead_ads, google_lead_form, partner_api, customer_api, customer_database, website_signal, licensed_provider, crm")
    source_type: str = Field(..., description="META, GOOGLE, PARTNER_API, CUSTOMER_API, CUSTOMER_DATABASE, WEBSITE_SIGNAL, LICENSED_PROVIDER, CRM, OTHER_AUTHORIZED_PROVIDER")
    configuration: Optional[Dict[str, Any]] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    market_id: Optional[str] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=10_000)
    daily_limit: Optional[int] = Field(None, ge=1, le=1_000_000)
    monthly_limit: Optional[int] = Field(None, ge=1, le=10_000_000)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        valid = {
            "META", "GOOGLE", "PARTNER_API", "CUSTOMER_API",
            "CUSTOMER_DATABASE", "WEBSITE_SIGNAL", "LICENSED_PROVIDER",
            "CRM", "OTHER_AUTHORIZED_PROVIDER"
        }
        if v.upper() not in valid:
            raise ValueError(f"source_type must be one of: {', '.join(sorted(valid))}")
        return v.upper()


class DiscoverySourceUpdateDTO(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    rate_limit_per_minute: Optional[int] = None
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    is_active: Optional[bool] = None


class DiscoverySourceResponseDTO(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    provider: str
    source_type: str
    status: str
    country_code: Optional[str]
    market_id: Optional[str]
    rate_limit_per_minute: Optional[int]
    daily_limit: Optional[int]
    monthly_limit: Optional[int]
    usage_today: int
    usage_month: int
    last_success_at: Optional[datetime]
    last_error_at: Optional[datetime]
    last_error_message: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Discovery Campaign DTOs ─────────────────────────────────────────────────

class DiscoveryCampaignCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    market_id: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    cities: Optional[List[str]] = Field(default_factory=list)
    property_types: Optional[List[str]] = Field(default_factory=list)
    transaction_types: Optional[List[str]] = Field(default_factory=list)
    lead_types: Optional[List[str]] = Field(default_factory=list)
    budget_min: Optional[Decimal] = Field(None, ge=0)
    budget_max: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    timeline: Optional[str] = None
    languages: Optional[List[str]] = Field(default_factory=list)
    intent_threshold: float = Field(0.70, ge=0.0, le=1.0)
    minimum_confidence: float = Field(0.60, ge=0.0, le=1.0)
    source_ids: Optional[List[str]] = Field(default_factory=list)
    daily_discovery_limit: int = Field(100, ge=1, le=100_000)
    campaign_metadata: Optional[Dict[str, Any]] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v


class DiscoveryCampaignUpdateDTO(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    market_id: Optional[str] = None
    country_code: Optional[str] = None
    cities: Optional[List[str]] = None
    property_types: Optional[List[str]] = None
    transaction_types: Optional[List[str]] = None
    lead_types: Optional[List[str]] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    currency: Optional[str] = None
    timeline: Optional[str] = None
    languages: Optional[List[str]] = None
    intent_threshold: Optional[float] = None
    minimum_confidence: Optional[float] = None
    source_ids: Optional[List[str]] = None
    daily_discovery_limit: Optional[int] = None
    status: Optional[str] = None
    campaign_metadata: Optional[Dict[str, Any]] = None


class DiscoveryCampaignResponseDTO(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    market_id: Optional[str]
    country_code: Optional[str]
    cities: Optional[List[str]]
    property_types: Optional[List[str]]
    transaction_types: Optional[List[str]]
    lead_types: Optional[List[str]]
    budget_min: Optional[Decimal]
    budget_max: Optional[Decimal]
    currency: Optional[str]
    timeline: Optional[str]
    languages: Optional[List[str]]
    intent_threshold: float
    minimum_confidence: float
    source_ids: Optional[List[str]]
    daily_discovery_limit: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Discovery Run DTOs ──────────────────────────────────────────────────────

class DiscoveryRunCreateDTO(BaseModel):
    campaign_id: str
    limit: Optional[int] = Field(50, ge=1, le=1000)
    cursor: Optional[str] = None
    run_metadata: Optional[Dict[str, Any]] = None


class DiscoveryRunResponseDTO(BaseModel):
    id: str
    organization_id: str
    campaign_id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    records_scanned: int
    candidates_found: int
    candidates_rejected: int
    duplicates_found: int
    new_prospects: int
    errors: Optional[List[Any]]
    provider_usage: Optional[Dict[str, Any]]
    cursor_position: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Discovery Candidate DTOs ────────────────────────────────────────────────

class DiscoveryCandidateResponseDTO(BaseModel):
    id: str
    organization_id: str
    discovery_run_id: Optional[str]
    source_id: Optional[str]
    external_id: Optional[str]
    source_url: Optional[str]
    display_name: Optional[str]
    contact_information: Optional[Dict[str, Any]]
    normalized_data: Optional[Dict[str, Any]]
    relevance_score: Optional[float]
    relevance_model_version: str
    identity_confidence: Optional[float]
    evidence_confidence: Optional[float]
    intent_confidence: Optional[float]
    freshness_score: Optional[float]
    observed_at: Optional[datetime]
    source_created_at: Optional[datetime]
    retrieved_at: datetime
    compliance_status: str
    duplicate_status: str
    matched_lead_id: Optional[str]
    status: str
    rejection_reason: Optional[str]
    review_reason: Optional[str]
    canonical_lead_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateApproveDTO(BaseModel):
    override_name: Optional[str] = None
    override_email: Optional[str] = None
    broker_id: Optional[str] = None
    notes: Optional[str] = None


class CandidateRejectDTO(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)


# ─── Evidence & Signal DTOs ──────────────────────────────────────────────────

class DiscoveryEvidenceDTO(BaseModel):
    id: str
    candidate_id: str
    source_id: Optional[str]
    field_name: str
    value_reference: str
    source_timestamp: Optional[datetime]
    retrieved_at: datetime
    confidence: float
    provenance: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class DiscoverySignalDTO(BaseModel):
    id: str
    candidate_id: str
    evidence_id: Optional[str]
    signal_type: str
    source: str
    observed_at: datetime
    strength: float
    confidence: float
    signal_payload: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Provider Status DTO ─────────────────────────────────────────────────────

class ProviderStatusDTO(BaseModel):
    provider: str
    status: str
    is_live: bool
    configured_sources: int
    note: Optional[str] = None


# ─── Dashboard Metrics DTO ───────────────────────────────────────────────────

class DiscoveryDashboardMetricsDTO(BaseModel):
    total_discovered_candidates: int
    high_intent_prospects: int
    duplicates_detected: int
    rejected_candidates: int
    imported_leads: int
    active_campaigns: int
    completed_runs: int
    average_relevance_score: float
    source_distribution: Dict[str, int]
