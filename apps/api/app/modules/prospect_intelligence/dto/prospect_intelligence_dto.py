"""
Part 21.2A — AI Prospect Intelligence Engine DTOs
===================================================
Pydantic schemas for:
- Strict Structured LLM Extraction
- API Requests & Responses
- Sales Intelligence Briefs & Ranked Property Recommendations
- Human Corrections / Field Overrides
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ─── 1. Sub-Entity DTOs ───────────────────────────────────────────────────────

class BudgetDTO(BaseModel):
    budget_min: Optional[float] = Field(None, description="Minimum budget numeric amount")
    budget_max: Optional[float] = Field(None, description="Maximum budget numeric amount")
    currency: Optional[str] = Field("UNKNOWN", description="ISO 4217 Currency code or UNKNOWN")
    budget_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in budget extraction")
    budget_source: Optional[str] = Field(None, description="Origin snippet or message ID")


class PropertyRequirementsDTO(BaseModel):
    property_type: Optional[str] = Field(None, description="apartment | villa | townhouse | penthouse | plot | commercial | etc.")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms (e.g. 1, 2, 3, 4, 5+)")
    bathrooms: Optional[int] = Field(None, description="Number of bathrooms")
    location: Optional[str] = Field(None, description="Primary city or metropolitan area")
    preferred_areas: List[str] = Field(default_factory=list, description="Specific neighborhoods, towers, or communities")
    size_min: Optional[float] = Field(None, description="Minimum area size")
    size_max: Optional[float] = Field(None, description="Maximum area size")
    size_unit: Optional[str] = Field("sqft", description="sqft | sqm")
    furnished_preference: Optional[str] = Field(None, description="furnished | semi-furnished | unfurnished")
    parking_required: Optional[bool] = Field(None, description="Parking space requirement")
    amenities: List[str] = Field(default_factory=list, description="Desired amenities e.g. pool, gym, balcony, sea view")
    view_preference: Optional[str] = Field(None, description="sea view | golf course | park | city skyline")
    floor_preference: Optional[str] = Field(None, description="low | mid | high | penthouse")
    new_or_resale: Optional[str] = Field(None, description="new | resale")
    ready_or_off_plan: Optional[str] = Field(None, description="ready | off_plan")


class FieldConfidenceDTO(BaseModel):
    intent_confidence: float = Field(0.0, ge=0.0, le=1.0)
    property_type_confidence: float = Field(0.0, ge=0.0, le=1.0)
    location_confidence: float = Field(0.0, ge=0.0, le=1.0)
    budget_confidence: float = Field(0.0, ge=0.0, le=1.0)
    timeline_confidence: float = Field(0.0, ge=0.0, le=1.0)
    financing_confidence: float = Field(0.0, ge=0.0, le=1.0)
    purpose_confidence: float = Field(0.0, ge=0.0, le=1.0)
    urgency_confidence: float = Field(0.0, ge=0.0, le=1.0)
    property_match_confidence: float = Field(0.0, ge=0.0, le=1.0)
    identity_confidence: float = Field(0.0, ge=0.0, le=1.0)
    source_confidence: float = Field(0.0, ge=0.0, le=1.0)


class NextBestQuestionDTO(BaseModel):
    field: str = Field(..., description="The missing information field (e.g. financing_method, move_in_date)")
    question: str = Field(..., description="High-value question for sales broker to ask")
    priority: int = Field(1, description="Priority ranking (1 = highest value)")
    business_rationale: str = Field(..., description="Why this information is critical for closing")


class MatchedPropertyDTO(BaseModel):
    property_id: str = Field(..., description="Tenant property UUID")
    title: str = Field(..., description="Property listing title")
    property_type: Optional[str] = None
    city: Optional[str] = None
    price: Optional[float] = None
    currency_code: str = "AED"
    match_score: float = Field(..., ge=0.0, le=1.0, description="Overall compatibility score")
    matched_requirements: List[str] = Field(default_factory=list)
    unmatched_requirements: List[str] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    reason: str = Field(...)


class SalesBriefDTO(BaseModel):
    headline: str = Field(..., description="Summary headline e.g. 🔥 HIGH-INTENT 3BHK BUYER")
    intent_summary: str = Field(...)
    buyer_profile_summary: str = Field(...)
    financial_summary: str = Field(...)
    timeline_summary: str = Field(...)
    verified_matches_count: int = Field(0)
    missing_critical_info: List[str] = Field(default_factory=list)
    recommended_action: str = Field(...)
    recommended_action_type: str = Field(...)
    action_rationale: str = Field(...)


# ─── 2. Strict AI Output DTO ─────────────────────────────────────────────────

class StrictLLMProspectExtractionDTO(BaseModel):
    """
    Schema enforced on LLM output.
    Any unverified or missing value MUST be None / UNKNOWN.
    """
    language: Optional[str] = "en"
    prospect_types: List[str] = Field(default_factory=lambda: ["BUYER"])
    transaction_intent: str = Field("UNKNOWN")

    # Property
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    location: Optional[str] = None
    preferred_areas: List[str] = Field(default_factory=list)
    size_min: Optional[float] = None
    size_max: Optional[float] = None
    size_unit: Optional[str] = "sqft"
    furnished_preference: Optional[str] = None
    parking_required: Optional[bool] = None
    amenities: List[str] = Field(default_factory=list)
    view_preference: Optional[str] = None
    floor_preference: Optional[str] = None
    new_or_resale: Optional[str] = None
    ready_or_off_plan: Optional[str] = None

    # Budget
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: Optional[str] = "UNKNOWN"

    # Timeline, Financing, Purpose, Urgency
    timeline: Optional[str] = "UNKNOWN"
    financing: Optional[str] = "UNKNOWN"
    purpose: Optional[str] = "UNKNOWN"
    urgency: Optional[str] = "UNKNOWN"

    # Raw Evidence Quotes
    evidence_snippets: Dict[str, str] = Field(default_factory=dict)
    field_confidences: Dict[str, float] = Field(default_factory=dict)


# ─── 3. API Request / Response DTOs ──────────────────────────────────────────

class AnalyzeProspectRequestDTO(BaseModel):
    force_refresh: bool = Field(False, description="Ignore cached content hash and force re-analysis")
    custom_instruction: Optional[str] = Field(None, description="Optional agent guidance for analysis")


class HumanOverrideRequestDTO(BaseModel):
    overrides: Dict[str, Any] = Field(..., description="Field-value pairs verified by human broker")
    reason: Optional[str] = Field("Human broker verification", description="Reason for override")


class ProspectIntelligenceResponseDTO(BaseModel):
    id: str
    lead_id: str
    organization_id: str
    status: str
    intelligence_version: str

    # Identity
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    language: str = "en"

    # Extracted Intelligence
    prospect_types: List[str] = Field(default_factory=list)
    transaction_intent: str = "UNKNOWN"
    property_requirements: Dict[str, Any] = Field(default_factory=dict)
    budget: Dict[str, Any] = Field(default_factory=dict)
    timeline: str = "UNKNOWN"
    financing: str = "UNKNOWN"
    purpose: str = "UNKNOWN"
    urgency: str = "UNKNOWN"

    # Confidences & Scores
    confidences: Dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = 0.0
    discovery_relevance_score: float = 0.0
    sales_readiness: str = "NOT_READY"

    # Decision Engine Outputs
    missing_information: List[str] = Field(default_factory=list)
    next_best_questions: List[Dict[str, Any]] = Field(default_factory=list)
    matched_properties: List[Dict[str, Any]] = Field(default_factory=list)
    sales_brief: Dict[str, Any] = Field(default_factory=dict)
    next_best_action: str = "NO_ACTION"
    next_best_action_reason: Optional[str] = None

    # Provenance & Audit
    provenance: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    human_overrides: Dict[str, Any] = Field(default_factory=dict)
    model_provider: str = "gemini"
    model_name: str = "gemini-3.5-flash"
    analyzed_at: datetime
    created_at: datetime
    updated_at: datetime
