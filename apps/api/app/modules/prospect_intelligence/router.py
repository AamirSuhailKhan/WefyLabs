"""
Part 21.2A — AI Prospect Intelligence REST Router
===================================================
Endpoints:
    GET    /api/v1/leads/{lead_id}/intelligence             # Fetch full intelligence profile
    POST   /api/v1/leads/{lead_id}/intelligence/analyze     # Run intelligence extraction
    POST   /api/v1/leads/{lead_id}/intelligence/refresh     # Force re-analysis ignoring cache
    GET    /api/v1/leads/{lead_id}/intelligence/properties  # Fetch tenant matched properties
    GET    /api/v1/leads/{lead_id}/intelligence/brief       # Fetch grounded Sales Brief & Next Best Action
    POST   /api/v1/leads/{lead_id}/intelligence/override    # Apply human-verified field corrections
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.modules.prospect_intelligence.dto.prospect_intelligence_dto import (
    ProspectIntelligenceResponseDTO, AnalyzeProspectRequestDTO,
    HumanOverrideRequestDTO, SalesBriefDTO, MatchedPropertyDTO
)
from app.modules.prospect_intelligence.services.prospect_intelligence_service import ProspectIntelligenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/leads", tags=["AI Prospect Intelligence"])


@router.get(
    "/{lead_id}/intelligence",
    response_model=ProspectIntelligenceResponseDTO,
    summary="Fetch Full AI Prospect Intelligence Profile",
)
async def get_lead_intelligence_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Retrieves the structured intelligence profile for a CRM lead.
    Enforces strict multi-tenant isolation.
    """
    org_id = current_broker.organization_id
    service = ProspectIntelligenceService(db)
    profile = await service.get_profile(org_id, lead_id)
    if not profile:
        # If not analyzed yet, run initial analysis on demand
        try:
            profile = await service.analyze_lead(org_id, lead_id, force_refresh=False)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
        except Exception as e:
            logger.error(f"[PROSPECT_ROUTER] Analysis on retrieval failed for {lead_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI analysis is temporarily unavailable.")

    return profile


@router.post(
    "/{lead_id}/intelligence/analyze",
    response_model=ProspectIntelligenceResponseDTO,
    summary="Trigger AI Prospect Intelligence Analysis",
)
async def analyze_lead_intelligence_endpoint(
    lead_id: str,
    request: Optional[AnalyzeProspectRequestDTO] = None,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Executes end-to-end prospect intelligence pipeline across conversation and lead evidence.
    """
    org_id = current_broker.organization_id
    service = ProspectIntelligenceService(db)
    force = request.force_refresh if request else False
    try:
        profile = await service.analyze_lead(org_id, lead_id, force_refresh=force)
        return profile
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"[PROSPECT_ROUTER] analyze_lead failed for {lead_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Intelligence analysis failed: {str(e)}")


@router.post(
    "/{lead_id}/intelligence/refresh",
    response_model=ProspectIntelligenceResponseDTO,
    summary="Force Refresh AI Prospect Intelligence",
)
async def refresh_lead_intelligence_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Forces fresh AI re-analysis bypassing content hash caches.
    """
    org_id = current_broker.organization_id
    service = ProspectIntelligenceService(db)
    try:
        profile = await service.analyze_lead(org_id, lead_id, force_refresh=True)
        return profile
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"[PROSPECT_ROUTER] refresh_lead failed for {lead_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{lead_id}/intelligence/properties",
    response_model=List[MatchedPropertyDTO],
    summary="Fetch Verified Tenant Property Matches",
)
async def get_matched_properties_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Returns verified property inventory matching prospect requirements from current tenant inventory.
    """
    org_id = current_broker.organization_id
    service = ProspectIntelligenceService(db)
    profile = await service.get_profile(org_id, lead_id)
    if not profile:
        profile = await service.analyze_lead(org_id, lead_id, force_refresh=False)
    return profile.matched_properties or []


@router.get(
    "/{lead_id}/intelligence/brief",
    response_model=SalesBriefDTO,
    summary="Fetch Sales Intelligence Brief & Next Best Action",
)
async def get_sales_brief_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Returns concise sales briefing, missing data points, and recommended Next Best Action.
    """
    org_id = current_broker.organization_id
    service = ProspectIntelligenceService(db)
    profile = await service.get_profile(org_id, lead_id)
    if not profile:
        profile = await service.analyze_lead(org_id, lead_id, force_refresh=False)
    return profile.sales_brief


@router.post(
    "/{lead_id}/intelligence/override",
    response_model=ProspectIntelligenceResponseDTO,
    summary="Apply Human-Verified Correction to Intelligence Profile",
)
async def override_intelligence_endpoint(
    lead_id: str,
    request: HumanOverrideRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Allows a sales broker to apply authoritative corrections without being overwritten by AI.
    """
    org_id = current_broker.organization_id
    service = ProspectIntelligenceService(db)
    try:
        updated = await service.apply_human_override(
            organization_id=org_id,
            lead_id=lead_id,
            overrides=request.overrides,
            reason=request.reason or "Human broker override",
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"[PROSPECT_ROUTER] override_intelligence failed for {lead_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
