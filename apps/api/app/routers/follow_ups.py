import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.schemas.follow_up import FollowUpResponse
from app.services.followup_service import cancel_pending_followups

router = APIRouter(prefix="/leads", tags=["Follow-Ups"])

@router.get("/{lead_id}/follow-ups", response_model=List[FollowUpResponse])
async def list_lead_followups(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves all follow-up records (scheduled, sent, cancelled, failed) for a lead.
    Enforces multi-tenant isolation.
    """
    lead_stmt = select(Lead).where(
        Lead.id == lead_id,
        Lead.broker_id == current_broker.id,
        Lead.deleted_at.is_(None)
    )
    lead = (await db.execute(lead_stmt)).scalars().first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    stmt = select(FollowUp).where(FollowUp.lead_id == lead_id).order_by(FollowUp.sequence_number.asc())
    results = await db.execute(stmt)
    items = results.scalars().all()
    return [FollowUpResponse.model_validate(item) for item in items]

@router.post("/{lead_id}/follow-ups/cancel")
async def cancel_lead_followups(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancels all scheduled follow-up messages for a lead.
    """
    lead_stmt = select(Lead).where(
        Lead.id == lead_id,
        Lead.broker_id == current_broker.id,
        Lead.deleted_at.is_(None)
    )
    lead = (await db.execute(lead_stmt)).scalars().first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    cancelled_count = await cancel_pending_followups(db, lead_id)
    return {
        "status": "success",
        "lead_id": str(lead_id),
        "cancelled_count": cancelled_count,
        "message": f"Successfully cancelled {cancelled_count} pending follow-ups."
    }
