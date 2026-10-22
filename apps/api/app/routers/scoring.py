import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.infrastructure.tenancy.scope import resolve_organization_id_for_broker, tenant_lead_filter
from app.models.broker import Broker
from app.models.lead import Lead
from app.schemas.score import QualifyRequest, QualifyResponse
from app.services.lead_scorer import qualify_and_score_lead

router = APIRouter(prefix="/scoring", tags=["Scoring"])

@router.post("/qualify", response_model=QualifyResponse, status_code=status.HTTP_200_OK)
async def trigger_lead_qualification(
    req: QualifyRequest,
    x_organization_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers lead qualification and scoring pipeline.
    Evaluates ExtractedData against PRD Section 8 rules, saves Score audit record, and alerts broker.
    Idempotent: returns existing score if force=false and lead is already scored.
    Enforces multi-tenant organization and broker isolation.
    """
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_organization_id=x_organization_id, allow_fallback=True)
    stmt = select(Lead).where(
        Lead.id == req.lead_id,
        tenant_lead_filter(org_id, current_broker.id),
        Lead.deleted_at.is_(None)
    )
    lead = (await db.execute(stmt)).scalars().first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    res = await qualify_and_score_lead(db=db, lead_id=req.lead_id, force=req.force)
    return QualifyResponse(
        lead_id=uuid.UUID(res["lead_id"]),
        score=res["score"],
        confidence=res["confidence"],
        reasoning=res["reasoning"],
        extracted_data=res["extracted_data"]
    )
