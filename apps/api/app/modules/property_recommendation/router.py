"""
Part 21.3 — AI Property Recommendation FastAPI REST Router
============================================================
Endpoints:
    GET    /api/v1/leads/{lead_id}/recommendations                       # Fetch recommendations
    POST   /api/v1/leads/{lead_id}/recommendations/generate              # Generate recommendations
    POST   /api/v1/leads/{lead_id}/recommendations/refresh               # Force refresh recommendations
    GET    /api/v1/leads/{lead_id}/recommendations/{recommendation_id}   # Fetch specific session
    POST   /api/v1/leads/{lead_id}/recommendations/{recommendation_id}/feedback # Record feedback
    POST   /api/v1/recommendations/compare                              # Compare properties
    POST   /api/v1/recommendations/simulate                             # What-If simulation
    GET    /api/v1/recommendations/properties/{property_id}/matching-leads # Reverse matching
    GET    /api/v1/recommendations/configuration                        # Org configuration
"""
import uuid
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.modules.property_recommendation.service import PropertyRecommendationService
from app.modules.property_recommendation.dto import (
    PropertyRecommendationRequestDTO, PropertyRecommendationResponseDTO,
    PropertyComparisonRequestDTO, PropertyComparisonResponseDTO,
    SimulationRequestDTO, ReverseMatchingResponseDTO, RecommendationFeedbackDTO
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Property Recommendation Engine"])


# ─── Lead-Scoped Endpoints ───────────────────────────────────────────────────

@router.get(
    "/api/v1/leads/{lead_id}/recommendations",
    response_model=PropertyRecommendationResponseDTO,
    summary="Fetch Property Recommendations for Lead",
)
async def get_lead_recommendations_endpoint(
    lead_id: str,
    top_k: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Retrieves grounded AI property recommendations for a specific CRM lead.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    broker_id = str(current_broker.id)
    service = PropertyRecommendationService(db)
    dto = PropertyRecommendationRequestDTO(lead_id=lead_id, top_k=top_k)
    try:
        return await service.generate_recommendations(
            dto=dto, organization_id=org_id, broker_id=broker_id, force_refresh=False
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as exc:
        logger.error(f"[REC_ROUTER] get_lead_recommendations failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/api/v1/leads/{lead_id}/recommendations/generate",
    response_model=PropertyRecommendationResponseDTO,
    summary="Generate AI Property Recommendations on Demand",
)
async def generate_lead_recommendations_endpoint(
    lead_id: str,
    request: Optional[PropertyRecommendationRequestDTO] = None,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Executes real-time recommendation pipeline matching lead requirements against verified tenant inventory.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    broker_id = str(current_broker.id)
    service = PropertyRecommendationService(db)
    dto = request or PropertyRecommendationRequestDTO(lead_id=lead_id)
    dto.lead_id = lead_id
    try:
        return await service.generate_recommendations(
            dto=dto, organization_id=org_id, broker_id=broker_id, force_refresh=False
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as exc:
        logger.error(f"[REC_ROUTER] generate_lead_recommendations failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/api/v1/leads/{lead_id}/recommendations/refresh",
    response_model=PropertyRecommendationResponseDTO,
    summary="Force Refresh Property Recommendations",
)
async def refresh_lead_recommendations_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Forces complete re-evaluation bypassing recommendation caches and re-checking live inventory.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    broker_id = str(current_broker.id)
    service = PropertyRecommendationService(db)
    dto = PropertyRecommendationRequestDTO(lead_id=lead_id, top_k=5)
    try:
        return await service.generate_recommendations(
            dto=dto, organization_id=org_id, broker_id=broker_id, force_refresh=True
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as exc:
        logger.error(f"[REC_ROUTER] refresh_lead_recommendations failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/api/v1/leads/{lead_id}/recommendations/{recommendation_id}/feedback",
    summary="Record Recommendation Feedback or Broker Override",
)
async def record_recommendation_feedback_endpoint(
    lead_id: str,
    recommendation_id: str,
    dto: RecommendationFeedbackDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Captures broker or customer interaction signals (viewed, shortlisted, rejected, viewing_booked).
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = PropertyRecommendationService(db)
    try:
        return await service.record_feedback(
            organization_id=org_id,
            recommendation_id=recommendation_id,
            lead_id=lead_id,
            dto=dto,
        )
    except Exception as exc:
        logger.error(f"[REC_ROUTER] record_feedback failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ─── Global Matching & Comparison Endpoints ─────────────────────────────────

@router.post(
    "/api/v1/recommendations/compare",
    response_model=PropertyComparisonResponseDTO,
    summary="Compare Properties Side-by-Side",
)
async def compare_properties_endpoint(
    dto: PropertyComparisonRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Generates structured side-by-side comparison matrix for 2 to 4 properties within tenant scope.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = PropertyRecommendationService(db)
    try:
        return await service.compare_properties(organization_id=org_id, dto=dto)
    except Exception as exc:
        logger.error(f"[REC_ROUTER] compare_properties failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/api/v1/recommendations/simulate",
    response_model=PropertyRecommendationResponseDTO,
    summary="What-If Search Simulation",
)
async def simulate_recommendation_endpoint(
    dto: SimulationRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Simulates recommendations under shifted parameter conditions (e.g. +10% budget shift).
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = PropertyRecommendationService(db)
    try:
        return await service.simulate_recommendations(organization_id=org_id, dto=dto)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as exc:
        logger.error(f"[REC_ROUTER] simulate_recommendations failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/api/v1/recommendations/properties/{property_id}/matching-leads",
    response_model=ReverseMatchingResponseDTO,
    summary="Reverse Matching: Find Qualified Leads for Property",
)
async def reverse_matching_endpoint(
    property_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Reverse Matching: identifies qualified buyer leads in the tenant CRM most likely to purchase this property.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = PropertyRecommendationService(db)
    try:
        return await service.reverse_match_leads(organization_id=org_id, property_id=property_id, limit=limit)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as exc:
        logger.error(f"[REC_ROUTER] reverse_matching failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/api/v1/recommendations/configuration",
    summary="Fetch Organization Recommendation Configuration",
)
async def get_configuration_endpoint(
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Returns organization scoring weights and currency parameters.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    return {
        "organization_id": org_id,
        "scoring_version": "v1.0-property-match",
        "base_currency": "AED",
        "default_budget_flexibility_pct": 10.0,
        "weights": {
            "end_user": {
                "budget_fit": 0.25,
                "location_fit": 0.20,
                "property_fit": 0.20,
                "preference_fit": 0.10,
                "timeline_fit": 0.10,
                "investment_fit": 0.05,
                "financing_fit": 0.05,
                "behavioral_fit": 0.05,
            },
            "investor": {
                "budget_fit": 0.20,
                "investment_fit": 0.30,
                "location_fit": 0.15,
                "property_fit": 0.10,
                "financing_fit": 0.10,
                "timeline_fit": 0.05,
                "preference_fit": 0.05,
                "behavioral_fit": 0.05,
            },
        },
    }
