"""
Pydantic Data Transfer Objects for AI Property Recommendation Engine
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RecommendationRequestDTO(BaseModel):
    lead_id: str = Field(..., description="Target Lead UUID")
    top_k: int = Field(10, ge=1, le=50, description="Number of recommendations requested")
    include_tradeoffs: bool = Field(True, description="Include trade-offs and agent talking points")
    filter_overpriced: bool = Field(False, description="Exclude listings marked as overpriced by AI AVM")
    override_budget: Optional[float] = Field(None, description="Optional simulation budget override")
    override_currency: Optional[str] = Field(None, description="Optional simulation currency override")


class ScoreBreakdownDTO(BaseModel):
    budget_fit: float
    location_fit: float
    property_fit: float
    preference_fit: float
    investment_fit: float
    timeline_fit: float
    payment_plan_fit: float
    behavioral_fit: float


class RecommendationItemDTO(BaseModel):
    property_id: str
    rank_position: int
    recommendation_type: str  # BEST_OVERALL | BEST_VALUE | BEST_LOCATION | BEST_INVESTMENT | BEST_PREMIUM | ALTERNATIVE
    match_score: float
    conversion_relevance_score: float
    commercial_priority_score: float
    recommendation_confidence: float
    title: str
    price: float
    currency: str
    normalized_price_aed: float
    built_up_area_sqft: float
    bedrooms: int
    bathrooms: int
    city: str
    locality: str
    project_name: Optional[str] = None
    building_name: Optional[str] = None
    amenities: List[str] = []
    status: str
    score_breakdown: ScoreBreakdownDTO
    strong_matches: List[str] = []
    weak_matches: List[str] = []
    tradeoffs: List[str] = []
    agent_talking_points: List[str] = []
    suggested_next_action: str


class RecommendationResponseDTO(BaseModel):
    recommendation_id: str
    lead_id: str
    total_candidates_retrieved: int
    filtered_candidates_count: int
    recommendation_mode: str
    active_model_version: str
    items: List[RecommendationItemDTO]


class FeedbackRequestDTO(BaseModel):
    property_id: str
    action: str  # viewed | saved | rejected | shared | viewing_booked | offer_made | purchased
    feedback_reason: Optional[str] = None


class PropertyComparisonRequestDTO(BaseModel):
    lead_id: Optional[str] = None
    property_ids: List[str] = Field(..., min_length=2, max_length=4)


class SimulationRequestDTO(BaseModel):
    lead_id: str
    budget_delta_pct: float = Field(0.0, description="Percentage shift in budget, e.g. 10.0 for +10%")
    expand_location_radius_km: float = Field(0.0, description="Radius expansion in km")
    relax_bedroom_min: bool = Field(False, description="Whether to allow N-1 bedrooms")


class ReverseMatchingResponseDTO(BaseModel):
    property_id: str
    total_qualified_leads_evaluated: int
    matching_leads: List[Dict[str, Any]]


class DemandIntelligenceResponseDTO(BaseModel):
    organization_id: str
    total_active_buyer_profiles: int
    top_demanded_locations: List[Dict[str, Any]]
    top_demanded_property_types: List[Dict[str, Any]]
    unmet_demand_gaps: List[Dict[str, Any]]
