import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("/{lead_id}", response_model=List[ConversationResponse])
async def get_lead_conversations(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns full chat history for a specific lead ordered by created_at ASC.
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

    stmt = select(Conversation).where(Conversation.lead_id == lead_id).order_by(Conversation.created_at.asc())
    results = await db.execute(stmt)
    items = results.scalars().all()
    return [ConversationResponse.model_validate(item) for item in items]
