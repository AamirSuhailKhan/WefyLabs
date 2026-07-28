import math
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.score import Score
from app.models.follow_up import FollowUp
from app.schemas.lead import LeadCreate, LeadResponse, LeadListResponse, NoteCreate
from app.services.followup_service import cancel_pending_followups

async def list_leads(
    db: AsyncSession,
    broker_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
    score: Optional[str] = None,
    stage: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> LeadListResponse:
    page = max(1, page)
    limit = min(100, max(1, limit))

    query = select(Lead).where(
        Lead.broker_id == broker_id,
        Lead.deleted_at.is_(None)
    )

    if score:
        query = query.where(Lead.score == score)
    if stage:
        query = query.where(Lead.pipeline_stage == stage)
    if source:
        query = query.where(Lead.source == source)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Lead.phone.ilike(search_pattern),
                Lead.name.ilike(search_pattern)
            )
        )

    # Calculate total matching count
    count_stmt = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one()

    # Determine sorting column
    sort_col = getattr(Lead, sort_by, Lead.created_at)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Pagination offset & limit
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Eager load relationships
    query = query.options(
        selectinload(Lead.conversations),
        selectinload(Lead.scores),
        selectinload(Lead.follow_ups)
    )

    results = await db.execute(query)
    items = results.scalars().all()

    pages = math.ceil(total / limit) if total > 0 else 0

    return LeadListResponse(
        data=[LeadResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        pages=pages
    )

async def create_lead(db: AsyncSession, broker_id: uuid.UUID, req: LeadCreate) -> LeadResponse:
    initial_notes: List[Dict[str, Any]] = []
    if req.notes:
        if isinstance(req.notes, str):
            initial_notes.append({
                "id": str(uuid.uuid4()),
                "content": req.notes,
                "color_tag": "blue",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        elif isinstance(req.notes, NoteCreate):
            initial_notes.append({
                "id": str(uuid.uuid4()),
                "content": req.notes.content,
                "color_tag": req.notes.color_tag or "blue",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        elif isinstance(req.notes, dict):
            initial_notes.append({
                "id": str(uuid.uuid4()),
                "content": req.notes.get("content", ""),
                "color_tag": req.notes.get("color_tag", "blue"),
                "created_at": datetime.now(timezone.utc).isoformat()
            })

    lead = Lead(
        broker_id=broker_id,
        phone=req.phone,
        name=req.name,
        source=req.source or "manual",
        score="pending",
        score_confidence=0.0,
        budget_min=req.budget_min,
        budget_max=req.budget_max,
        property_type=req.property_type,
        transaction_type=req.transaction_type,
        preferred_locations=req.preferred_locations or [],
        timeline=req.timeline,
        loan_status=req.loan_status,
        status="pending",
        pipeline_stage="new",
        notes=initial_notes
    )
    db.add(lead)
    await db.commit()

    # Re-query with eager loading
    return await get_lead_by_id(db, lead.id, broker_id)

async def get_lead_by_id(db: AsyncSession, lead_id: uuid.UUID, broker_id: uuid.UUID) -> LeadResponse:
    stmt = (
        select(Lead)
        .where(
            Lead.id == lead_id,
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        .options(
            selectinload(Lead.conversations),
            selectinload(Lead.scores),
            selectinload(Lead.follow_ups)
        )
    )
    result = await db.execute(stmt)
    lead = result.scalars().first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found or has been deleted."
        )

    # Ensure conversations capped to last 50 for detail view
    if len(lead.conversations) > 50:
        lead.conversations = lead.conversations[-50:]

    return LeadResponse.model_validate(lead)

async def update_lead_status(
    db: AsyncSession,
    lead_id: uuid.UUID,
    broker_id: uuid.UUID,
    new_status: str
) -> LeadResponse:
    stmt = select(Lead).where(
        Lead.id == lead_id,
        Lead.broker_id == broker_id,
        Lead.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    lead = result.scalars().first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    lead.status = new_status
    if new_status == "qualified":
        lead.qualified_at = datetime.now(timezone.utc)
    elif new_status in ("converted", "lost"):
        await cancel_pending_followups(db, lead_id)

    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return await get_lead_by_id(db, lead_id, broker_id)

async def update_lead_stage(
    db: AsyncSession,
    lead_id: uuid.UUID,
    broker_id: uuid.UUID,
    new_stage: str
) -> LeadResponse:
    stmt = select(Lead).where(
        Lead.id == lead_id,
        Lead.broker_id == broker_id,
        Lead.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    lead = result.scalars().first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    lead.pipeline_stage = new_stage
    if new_stage in ("closed_won", "closed_lost"):
        lead.status = "converted" if new_stage == "closed_won" else "lost"
        await cancel_pending_followups(db, lead_id)

    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return await get_lead_by_id(db, lead_id, broker_id)

async def add_lead_note(
    db: AsyncSession,
    lead_id: uuid.UUID,
    broker_id: uuid.UUID,
    note_req: NoteCreate
) -> LeadResponse:
    stmt = select(Lead).where(
        Lead.id == lead_id,
        Lead.broker_id == broker_id,
        Lead.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    lead = result.scalars().first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    note_obj = {
        "id": str(uuid.uuid4()),
        "content": note_req.content,
        "color_tag": note_req.color_tag or "blue",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    current_notes = list(lead.notes or [])
    current_notes.append(note_obj)
    lead.notes = current_notes
    lead.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return await get_lead_by_id(db, lead_id, broker_id)

async def soft_delete_lead(
    db: AsyncSession,
    lead_id: uuid.UUID,
    broker_id: uuid.UUID
) -> None:
    stmt = select(Lead).where(
        Lead.id == lead_id,
        Lead.broker_id == broker_id,
        Lead.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    lead = result.scalars().first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    lead.deleted_at = datetime.now(timezone.utc)
    await cancel_pending_followups(db, lead_id)
    await db.commit()
