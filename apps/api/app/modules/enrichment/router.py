"""
Volume 2 PART 2 — AI Lead Enrichment REST API Router

P0 Security Hardening (applied):
- All endpoints require authenticated principal via get_current_tenant.
- Lead ownership is validated against tenant organization_id before processing.
- Caller-supplied organization_id is removed; organization context derived from JWT.
"""
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_tenant, TenantContext
from app.models.lead import Lead
from app.models.enrichment_models import LeadEnrichment, ConfidenceScore
from app.modules.enrichment.service import LeadEnrichmentService
from app.modules.enrichment.monitoring import EnrichmentMetricsCollector

router = APIRouter(prefix="/api/v1/enrichment", tags=["AI Lead Enrichment Engine"])


async def _get_lead_for_tenant(lead_id: str, tenant: TenantContext, db: AsyncSession) -> Lead:
    """Resolve lead and enforce tenant ownership. Raises 403/404 appropriately."""
    try:
        lead_uuid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead_id UUID format.")

    stmt = select(Lead).where(Lead.id == lead_uuid)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()

    if not lead:
        # Return 403 not 404 to avoid information leakage about other tenants' leads
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lead not found or access denied.")

    # Enforce tenant ownership — lead must belong to the authenticated tenant
    lead_org_id = str(lead.organization_id) if hasattr(lead, "organization_id") and lead.organization_id else str(lead.broker_id)
    if lead_org_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lead not found or access denied.")

    return lead


@router.post("/enrich/{lead_id}", status_code=status.HTTP_200_OK)
async def enrich_lead_endpoint(
    lead_id: str,
    trigger_source: str = "ManualRequest",
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers full AI enrichment pipeline on a given lead.
    Requires authentication. Lead must belong to the authenticated tenant's organization.
    """
    lead = await _get_lead_for_tenant(lead_id, tenant, db)

    lead_dto = {
        "id": str(lead.id),
        "organization_id": tenant.organization_id,  # Always use server-side tenant, not client-supplied
        "phone": lead.phone,
        "name": lead.name,
        "source": lead.source,
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "property_type": lead.property_type,
        "timeline": lead.timeline,
        "notes": lead.notes or []
    }

    service = LeadEnrichmentService(db=db)
    result = await service.enrich_lead(lead_dto=lead_dto, trigger_source=trigger_source)
    return result


@router.get("/profile/{lead_id}", status_code=status.HTTP_200_OK)
async def get_enriched_profile(
    lead_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches the enriched profile and field-level confidence provenance for a lead.
    Lead must belong to the authenticated tenant's organization.
    """
    # Validate lead ownership first
    await _get_lead_for_tenant(lead_id, tenant, db)

    stmt = select(LeadEnrichment).where(LeadEnrichment.lead_id == lead_id)
    res = await db.execute(stmt)
    enrichment = res.scalar_one_or_none()

    if not enrichment:
        raise HTTPException(status_code=404, detail=f"No enriched profile found for lead {lead_id}")

    # Secondary tenant check on enrichment record itself
    if str(enrichment.organization_id) != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lead not found or access denied.")

    # Fetch confidence scores
    c_stmt = select(ConfidenceScore).where(ConfidenceScore.lead_id == lead_id)
    c_res = await db.execute(c_stmt)
    confidence_scores = [
        {
            "field_name": cs.field_name,
            "field_value": cs.field_value,
            "confidence": cs.confidence,
            "source_type": cs.source_type,
            "method": cs.method
        }
        for cs in c_res.scalars().all()
    ]

    return {
        "lead_id": lead_id,
        "organization_id": enrichment.organization_id,
        "overall_quality_score": enrichment.overall_quality_score,
        "quality_tier": enrichment.quality_tier,
        "overall_confidence": enrichment.overall_confidence,
        "field_completion_rate": enrichment.field_completion_rate,
        "identity_profile": enrichment.identity_profile,
        "location_profile": enrichment.location_profile,
        "financial_profile": enrichment.financial_profile,
        "intent_profile": enrichment.intent_profile,
        "property_interest": enrichment.property_interest,
        "communication_profile": enrichment.communication_profile,
        "ai_summary": enrichment.ai_summary,
        "ai_recommendations": enrichment.ai_recommendations,
        "confidence_scores": confidence_scores,
        "updated_at": enrichment.updated_at.isoformat()
    }


@router.post("/replay/{lead_id}", status_code=status.HTTP_200_OK)
async def replay_enrichment(
    lead_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Safely replays enrichment without overwriting observed data.
    Lead must belong to the authenticated tenant's organization.
    """
    lead = await _get_lead_for_tenant(lead_id, tenant, db)

    lead_dto = {
        "id": str(lead.id),
        "organization_id": tenant.organization_id,
        "phone": lead.phone,
        "name": lead.name,
        "source": lead.source,
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "property_type": lead.property_type,
        "timeline": lead.timeline,
        "notes": lead.notes or []
    }

    service = LeadEnrichmentService(db=db)
    result = await service.enrich_lead(lead_dto=lead_dto, trigger_source="ReplayRequested")
    return result


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_enrichment_metrics(
    tenant: TenantContext = Depends(get_current_tenant),
):
    """
    Retrieves real-time operational monitoring metrics (latency, token cost, provider health).
    Requires authenticated principal; metrics are platform-wide operational data.
    """
    return EnrichmentMetricsCollector.get_summary()
