import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.schemas.score import QualifyRequest, QualifyResponse
from app.services.lead_scorer import qualify_and_score_lead

router = APIRouter(prefix="/scoring", tags=["Scoring"])

@router.post("/qualify", response_model=QualifyResponse, status_code=status.HTTP_200_OK)
async def trigger_lead_qualification(
    req: QualifyRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers lead qualification and scoring pipeline.
    Evaluates ExtractedData against PRD Section 8 rules, saves Score audit record, and alerts broker.
    Idempotent: returns existing score if force=false and lead is already scored.
    """
    res = await qualify_and_score_lead(db=db, lead_id=req.lead_id, force=req.force)
    return QualifyResponse(
        lead_id=uuid.UUID(res["lead_id"]),
        score=res["score"],
        confidence=res["confidence"],
        reasoning=res["reasoning"],
        extracted_data=res["extracted_data"]
    )
