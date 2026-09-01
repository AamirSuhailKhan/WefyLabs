"""
Volume 2 PART 7 — AI Property Recommendation & Buyer-Property Matching Engine Models
========================================================================================
SQLAlchemy 2.0 models for enterprise buyer matching, explainable scoring, vector caching,
reverse property-to-lead matching, feedback loops, and demand intelligence.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

def _gen_uuid() -> str:
    return str(uuid.uuid4())


class BuyerProfile(Base, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Buyer Profile representing synthesized requirements, budget,
    intent, lifestyle preferences, and behavioral signals for a Lead.
    """
    __tablename__ = "buyer_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    broker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Demographic & Identity Signals
    country: Mapped[str] = mapped_column(String(100), default="UAE", nullable=False)
    residence_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)

    # Budget & Currency
    currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)
    target_budget: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    max_budget: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    min_budget: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    budget_flexibility_pct: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)  # Acceptable % over budget
    financing_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Purpose & Strategy
    purchase_purpose: Mapped[str] = mapped_column(String(30), default="end_user", nullable=False, index=True) # end_user | investment | holiday_home | flipping
    investment_horizon_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_rental_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_roi_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Physical Property Specs
    property_types: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False) # ["apartment", "villa", "penthouse"]
    min_bedrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_bedrooms: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    min_bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    min_area_sqft: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_area_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Location Hierarchy & Preferences
    preferred_cities: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    preferred_locations: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    excluded_locations: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    preferred_developers: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    excluded_developers: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)

    # Lifestyle & Family Requirements
    amenities: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    floor_preference: Mapped[Optional[str]] = mapped_column(String(30), nullable=True) # low | mid | high | penthouse
    view_preference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # sea_view | park_view | skyline | golf_course
    furnishing_preference: Mapped[Optional[str]] = mapped_column(String(30), nullable=True) # unfurnished | semi_furnished | fully_furnished

    # Timeline & Urgency
    possession_timeline: Mapped[str] = mapped_column(String(30), default="immediate", nullable=False) # immediate | 3_months | 6_months | offplan_2025 | offplan_2026
    urgency_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)

    # Summary Scores & AI Memory
    profile_completeness_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_memory_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_extracted_features: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_buyer_profiles_org_purpose", "organization_id", "purchase_purpose"),
        Index("ix_buyer_profiles_org_budget", "organization_id", "max_budget"),
    )


class BuyerPreference(Base, TimestampMixin):
    """Granular attribute preferences for a buyer profile."""
    __tablename__ = "buyer_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    buyer_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("buyer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    preference_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # location | amenity | developer | view | floor
    preference_key: Mapped[str] = mapped_column(String(100), nullable=False)
    preference_value: Mapped[str] = mapped_column(String(255), nullable=False)
    preference_type: Mapped[str] = mapped_column(String(30), default="SOFT_PREFERENCE", nullable=False) # HARD_CONSTRAINT | SOFT_PREFERENCE | INFERRED_PREFERENCE | NEGATIVE_PREFERENCE
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    provenance_source: Mapped[str] = mapped_column(String(50), default="customer_statement", nullable=False) # customer_statement | crm_field | conversation_extraction | website_behavior
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class BuyerConstraint(Base, TimestampMixin):
    """Hard constraints that strictly filter out properties."""
    __tablename__ = "buyer_constraints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    buyer_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("buyer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False) # max_price | min_bedrooms | max_bedrooms | required_city | availability
    operator: Mapped[str] = mapped_column(String(10), default="eq", nullable=False) # eq | lte | gte | in | not_in
    constraint_value: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    is_flexible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flexibility_range: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, default=dict, nullable=True)


class BuyerPreferenceEvidence(Base, TimestampMixin):
    """Audit evidence log tracking why preferences were inferred or assigned."""
    __tablename__ = "buyer_preference_evidences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    buyer_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("buyer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    preference_key: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False) # conversation | note | search | view | rejection | explicit_form
    source_ref_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class PropertyFeatureVector(Base, TimestampMixin):
    """Pre-calculated normalized property vector for similarity matching."""
    __tablename__ = "property_feature_vectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    property_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    general_vector: Mapped[List[float]] = mapped_column(JSONBType, nullable=False)
    location_vector: Mapped[List[float]] = mapped_column(JSONBType, nullable=False)
    investment_vector: Mapped[List[float]] = mapped_column(JSONBType, nullable=False)
    lifestyle_vector: Mapped[List[float]] = mapped_column(JSONBType, nullable=False)
    features_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    investment_yield_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    vector_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class Recommendation(Base, TimestampMixin):
    """Recommendation Session entity representing a set of generated items for a lead."""
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    buyer_profile_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    total_candidates_retrieved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    filtered_candidates_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommendation_mode: Mapped[str] = mapped_column(String(50), default="hybrid_matching", nullable=False) # hybrid_matching | simulation | fallback
    active_model_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)

    items: Mapped[List["RecommendationItem"]] = relationship("RecommendationItem", back_populates="recommendation", cascade="all, delete-orphan")


class RecommendationItem(Base, TimestampMixin):
    """Individual property item inside a recommendation result set."""
    __tablename__ = "recommendation_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    recommendation_id: Mapped[str] = mapped_column(String(36), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(40), default="BEST_OVERALL", nullable=False) # BEST_OVERALL | BEST_VALUE | BEST_LOCATION | BEST_INVESTMENT | BEST_PREMIUM | ALTERNATIVE
    match_score: Mapped[float] = mapped_column(Float, nullable=False, index=True) # 0.0 - 100.0
    conversion_relevance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    commercial_priority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recommendation_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    inventory_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    recommendation: Mapped["Recommendation"] = relationship("Recommendation", back_populates="items")
    score_breakdown: Mapped[Optional["RecommendationScore"]] = relationship("RecommendationScore", uselist=False, cascade="all, delete-orphan")
    explanation: Mapped[Optional["RecommendationExplanation"]] = relationship("RecommendationExplanation", uselist=False, cascade="all, delete-orphan")


class RecommendationScore(Base, TimestampMixin):
    """8-dimensional score component breakdown for an item."""
    __tablename__ = "recommendation_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    recommendation_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("recommendation_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    budget_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    location_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    property_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    preference_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    investment_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timeline_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payment_plan_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    behavioral_fit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class RecommendationExplanation(Base, TimestampMixin):
    """Grounded matching reasons, trade-offs, and sales agent guidance."""
    __tablename__ = "recommendation_explanations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    recommendation_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("recommendation_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    strong_matches: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    weak_matches: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    tradeoffs: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    missing_information: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    agent_talking_points: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    suggested_next_action: Mapped[str] = mapped_column(String(255), default="Schedule Viewing", nullable=False)


class RecommendationFeedback(Base, TimestampMixin):
    """User/Agent feedback capture for retraining and negative preference updates."""
    __tablename__ = "recommendation_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    recommendation_id: Mapped[str] = mapped_column(String(36), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True) # viewed | saved | rejected | shared | viewing_booked | offer_made | purchased
    feedback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_type: Mapped[str] = mapped_column(String(30), default="STRONG_BEHAVIORAL", nullable=False) # EXPLICIT | STRONG_BEHAVIORAL | WEAK_BEHAVIORAL


class RecommendationExperiment(Base, TimestampMixin):
    """A/B experiment testing configuration for recommendation models."""
    __tablename__ = "recommendation_experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    variant_weights: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class RecommendationModelVersion(Base, TimestampMixin):
    """Registry of scoring model versions and parameters."""
    __tablename__ = "recommendation_model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    version_tag: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    weights_config: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RecommendationFeature(Base, TimestampMixin):
    """Persisted feature vector snapshot for ML dataset logging."""
    __tablename__ = "recommendation_features"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    property_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    feature_data: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class RecommendationSimulation(Base, TimestampMixin):
    """Audit log of What-If search simulations."""
    __tablename__ = "recommendation_simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    results_summary: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class RecommendationComparison(Base, TimestampMixin):
    """Audit entity for structured property comparisons."""
    __tablename__ = "recommendation_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    property_ids: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    comparison_matrix: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class RecommendationHistory(Base, TimestampMixin):
    """Time-series execution history of recommendations generated."""
    __tablename__ = "recommendation_histories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    top_property_id: Mapped[str] = mapped_column(String(36), nullable=False)
    top_match_score: Mapped[float] = mapped_column(Float, nullable=False)


class RecommendationConfiguration(Base, TimestampMixin):
    """Organization-level configuration parameters for property matching."""
    __tablename__ = "recommendation_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    base_currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)
    default_budget_flexibility_pct: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    weights: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)


class RecommendationBusinessRule(Base, TimestampMixin):
    """Commercial priority & developer boosting business rules."""
    __tablename__ = "recommendation_business_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False) # boost_developer | block_developer | priority_project | minimum_margin
    target_value: Mapped[str] = mapped_column(String(255), nullable=False)
    score_boost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
