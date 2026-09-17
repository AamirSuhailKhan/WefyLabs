"""
Part 21.3 — AI Property Recommendation Engine DTOs
===================================================
Pydantic Data Transfer Objects for property matching, explainable scoring,
candidate filtering, comparison, simulation, and feedback capture.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NormalizedRequirementsDTO(BaseModel):
    """Normalized prospect requirements derived from Lead and ProspectIntelligence."""
    property_type: Optional[str] = None
    category: Optional[str] = None
    min_bedrooms: int = 1
    max_bedrooms: int = 4
    min_bathrooms: int = 1
    min_budget: float = 0.0
    max_budget: float = 0.0
    currency: str = "AED"
    location: Optional[str] = None
    preferred_areas: List[str] = Field(default_factory=list)
    excluded_areas: List[str] = Field(default_factory=list)
    preferred_developers: List[str] = Field(default_factory=list)
    excluded_developers: List[str] = Field(default_factory=list)
    amenities: List[str] = Field(default_factory=list)
    transaction_intent: str = "BUY"  # BUY | SELL | RENT | LEASE | INVEST | INQUIRE | UNKNOWN
    purchase_purpose: str = "end_user"  # end_user | investment | holiday_home
    possession_timeline: str = "immediate"  # immediate | 3_months | 6_months | offplan
    financing_required: bool = False
    urgency: str = "MEDIUM"


class ScoreBreakdownDTO(BaseModel):
    """8-dimensional score component breakdown (0.0 – 100.0)."""
    budget_fit: float = 0.0
    location_fit: float = 0.0
    property_fit: float = 0.0
    preference_fit: float = 0.0
    investment_fit: float = 0.0
    timeline_fit: float = 0.0
    financing_fit: float = 0.0
    behavioral_fit: float = 0.0


class RequirementCoverageDTO(BaseModel):
    """Explicit requirement fulfillment analysis."""
    matched: List[str] = Field(default_factory=list)
    unmet: List[str] = Field(default_factory=list)
    unknown: List[str] = Field(default_factory=list)


class PropertyRecommendationItemDTO(BaseModel):
    """Ranked, grounded property recommendation item."""
    property_id: str
    rank_position: int
    recommendation_type: str  # BEST_OVERALL | BEST_VALUE | BEST_LOCATION | BEST_INVESTMENT | BEST_PREMIUM | ALTERNATIVE
    match_score: float  # 0.0 – 100.0
    confidence: float = 1.0
    title: str
    price: float
    currency: str
    normalized_price_aed: float
    built_up_area_sqft: float
    bedrooms: int
    bathrooms: int
    city: Optional[str] = None
    locality: Optional[str] = None
    project_name: Optional[str] = None
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    amenities: List[str] = Field(default_factory=list)
    status: str = "available"
    score_breakdown: ScoreBreakdownDTO
    requirement_coverage: RequirementCoverageDTO
    why_matches: List[str] = Field(default_factory=list)
    trade_offs: List[str] = Field(default_factory=list)
    agent_talking_points: List[str] = Field(default_factory=list)
    suggested_next_action: str = "Schedule Viewing"
    evidence_references: Dict[str, Any] = Field(default_factory=dict)


class PropertyRecommendationRequestDTO(BaseModel):
    """Input payload for generating recommendations."""
    lead_id: str = Field(..., description="CRM Lead UUID")
    top_k: int = Field(5, ge=1, le=50, description="Top N recommendations (default 5)")
    include_tradeoffs: bool = Field(True, description="Include detailed trade-offs & sales talking points")
    filter_overpriced: bool = Field(False, description="Exclude overpriced listings")
    override_budget: Optional[float] = Field(None, description="Simulation budget override")
    override_currency: Optional[str] = Field(None, description="Simulation currency override")


class PropertyRecommendationResponseDTO(BaseModel):
    """Structured response containing ranked, grounded recommendations."""
    recommendation_id: str
    lead_id: str
    organization_id: str
    scoring_version: str = "v1.0-property-match"
    total_candidates_retrieved: int
    filtered_candidates_count: int
    recommendation_mode: str = "hybrid_matching"
    execution_duration_ms: int = 0
    items: List[PropertyRecommendationItemDTO] = Field(default_factory=list)


class PropertyComparisonRequestDTO(BaseModel):
    """Request payload for side-by-side property comparison."""
    lead_id: Optional[str] = None
    property_ids: List[str] = Field(..., min_length=2, max_length=4)


class PropertyComparisonResponseDTO(BaseModel):
    """Side-by-side comparative matrix of target properties."""
    lead_id: Optional[str] = None
    compared_count: int
    properties: List[Dict[str, Any]]
    key_differences: List[str] = Field(default_factory=list)


class SimulationRequestDTO(BaseModel):
    """What-If scenario simulation."""
    lead_id: str
    budget_delta_pct: float = Field(0.0, description="Shift budget by percentage e.g. 10.0 for +10%")
    expand_location_radius_km: float = Field(0.0, description="Search radius expansion in km")
    relax_bedroom_min: bool = Field(False, description="Allow min_bedrooms - 1")


class ReverseMatchingResponseDTO(BaseModel):
    """Reverse property-to-lead matching response."""
    property_id: str
    total_qualified_leads_evaluated: int
    matching_leads: List[Dict[str, Any]] = Field(default_factory=list)


class RecommendationFeedbackDTO(BaseModel):
    """Explicit agent or user feedback on a recommended property."""
    property_id: str
    action: str  # viewed | saved | shortlisted | rejected | shared | viewing_booked | deal_won | deal_lost
    feedback_reason: Optional[str] = None
    override_comment: Optional[str] = None


class LeadMatchItemDTO(BaseModel):
    """Structured result for reverse property-to-lead candidate matching."""
    lead_id: str
    name: Optional[str] = None
    phone: str
    lead_tier: str = "warm"  # hot | warm | cold | unqualified
    match_score: float = 0.0
    confidence: float = 1.0
    budget_fit: float = 0.0
    location_fit: float = 0.0
    bhk_fit: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    mismatches: List[str] = Field(default_factory=list)
    status: str = "active"
    notes: Optional[str] = None
    last_activity: Optional[str] = None


class MatchingDashboardDTO(BaseModel):
    """Analytics and overview metrics for AI Matching dashboard."""
    leads_needing_matches_count: int = 0
    unmatched_hot_leads: List[Dict[str, Any]] = Field(default_factory=list)
    high_demand_properties: List[Dict[str, Any]] = Field(default_factory=list)
    supply_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    strongest_recent_matches: List[Dict[str, Any]] = Field(default_factory=list)
    total_inventory_count: int = 0
    total_leads_count: int = 0


class ShortlistRequestDTO(BaseModel):
    """Payload to shortlist a property for a lead."""
    lead_id: str
    property_id: str
    notes: Optional[str] = None
    interest_level: str = "high"


class RecommendRequestDTO(BaseModel):
    """Payload to formally recommend a property to a lead."""
    lead_id: str
    property_id: str
    notes: Optional[str] = None
    create_followup_task: bool = True


class RequirementExtractionRequestDTO(BaseModel):
    """Payload to extract requirements from free text."""
    text: str


class RequirementExtractionResponseDTO(BaseModel):
    """Structured requirements extracted from natural text."""
    extracted_requirements: Dict[str, Any]
    confidence: float
    provenance: str = "AI_EXTRACTED"
    summary: str


class MatchFeedbackRequestDTO(BaseModel):
    """Payload to record match feedback."""
    lead_id: str
    property_id: str
    feedback: str  # good_match | bad_match | wrong_budget | wrong_location | wrong_property_type | already_contacted | customer_rejected | customer_interested | customer_shortlisted
    notes: Optional[str] = None


class MatchCompareRequestDTO(BaseModel):
    """Payload to compare multiple matched properties."""
    property_ids: List[str] = Field(..., min_length=2, max_length=5)
    lead_id: Optional[str] = None


