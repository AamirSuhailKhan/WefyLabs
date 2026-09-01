"""
Part 21.3 — AI Property Recommendation Engine Module
=====================================================
"""
from app.modules.property_recommendation.service import PropertyRecommendationService
from app.modules.property_recommendation.router import router as property_recommendation_router

__all__ = [
    "PropertyRecommendationService",
    "property_recommendation_router",
]
