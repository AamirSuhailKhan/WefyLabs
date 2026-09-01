"""
FastAPI Router for AI Property Recommendation & Buyer-Property Matching Engine
================================================================================
Exposes production-grade REST APIs for forward matching, reverse property-to-lead matching,
What-If simulations, property comparisons, feedback tracking, and demand intelligence.
"""

import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.modules.recommendation.service import PropertyRecommendationService
from app.modules.recommendation.dto.recommendation_schemas import (
    RecommendationRequestDTO, RecommendationResponseDTO, FeedbackRequestDTO,
    PropertyComparisonRequestDTO, SimulationRequestDTO, ReverseMatchingResponseDTO
)

router = APIRouter(prefix="/v1/recommendations", tags=["AI Property Recommendation Engine"])


@router.post("", response_model=RecommendationResponseDTO, status_code=status.HTTP_200_OK)
async def generate_recommendations_endpoint(
    dto: RecommendationRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Generates ranked, explainable AI property recommendations for a buyer lead.
    Calculates 8-dimension match scores (0-100), trade-offs, and agent talking points.
    """
    try:
        service = PropertyRecommendationService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        broker_id = str(current_broker.id)
        return await service.generate_recommendations(dto, organization_id=org_id, broker_id=broker_id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Recommendation failed: {exc}")


@router.get("/{lead_id}", response_model=RecommendationResponseDTO)
async def get_latest_recommendations_endpoint(
    lead_id: str,
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves the latest active recommendation snapshot for a buyer lead.
    """
    try:
        service = PropertyRecommendationService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        broker_id = str(current_broker.id)
        dto = RecommendationRequestDTO(lead_id=lead_id, top_k=top_k)
        return await service.generate_recommendations(dto, organization_id=org_id, broker_id=broker_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/{recommendation_id}/feedback")
async def record_recommendation_feedback_endpoint(
    recommendation_id: str,
    lead_id: str = Query(...),
    dto: FeedbackRequestDTO = ...,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Records explicit user or agent feedback (viewed, saved, rejected, booked, purchased).
    """
    try:
        service = PropertyRecommendationService(db)
        return await service.feedback_processor.record_feedback(recommendation_id, lead_id, dto)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/compare")
async def compare_properties_endpoint(
    dto: PropertyComparisonRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Generates structured side-by-side comparison matrix for 2 to 4 properties.
    """
    try:
        service = PropertyRecommendationService(db)
        return await service.compare_properties(dto)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/simulate", response_model=RecommendationResponseDTO)
async def simulate_recommendation_endpoint(
    dto: SimulationRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Runs What-If search simulation (e.g. +10% budget shift or expanded location).
    """
    try:
        service = PropertyRecommendationService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        broker_id = str(current_broker.id)
        return await service.simulate_recommendations(dto, organization_id=org_id, broker_id=broker_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/refresh", response_model=RecommendationResponseDTO)
async def refresh_recommendation_endpoint(
    dto: RecommendationRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Revalidates live inventory and generates fresh recommendations.
    """
    try:
        service = PropertyRecommendationService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        broker_id = str(current_broker.id)
        return await service.generate_recommendations(dto, organization_id=org_id, broker_id=broker_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/properties/{property_id}/matching-leads")
async def reverse_property_lead_matching_endpoint(
    property_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Reverse Matching: Identifies qualified buyer leads in the CRM most likely to purchase this property.
    """
    try:
        service = PropertyRecommendationService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.reverse_matcher.match_leads_for_property(property_id, organization_id=org_id, limit=limit)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/demand-intelligence/analytics")
async def get_demand_intelligence_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Aggregates anonymized tenant buyer demand analytics and uncovers unmet inventory gaps.
    """
    try:
        service = PropertyRecommendationService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.demand_analyzer.analyze_demand(organization_id=org_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/configuration")
async def get_recommendation_config_endpoint(
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Returns organization-level scoring weights and currency parameters.
    """
    return {
        "organization_id": str(current_broker.organization_id or current_broker.id),
        "base_currency": "AED",
        "default_budget_flexibility_pct": 10.0,
        "scoring_weights": {
            "end_user": {
                "budget_fit": 0.25,
                "location_fit": 0.20,
                "property_fit": 0.20,
                "preference_fit": 0.10,
                "investment_fit": 0.05,
                "timeline_fit": 0.10,
                "payment_plan_fit": 0.05,
                "behavioral_fit": 0.05
            },
            "investor": {
                "budget_fit": 0.20,
                "location_fit": 0.15,
                "property_fit": 0.10,
                "preference_fit": 0.05,
                "investment_fit": 0.30,
                "timeline_fit": 0.05,
                "payment_plan_fit": 0.10,
                "behavioral_fit": 0.05
            }
        }
    }
