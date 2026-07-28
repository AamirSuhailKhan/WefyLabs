import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.schemas.lead import (
    LeadCreate, LeadResponse, LeadListResponse, NoteCreate, StageUpdate, StatusUpdate
)
from app.modules.leads.service import (
    list_leads, create_lead, get_lead_by_id, update_lead_status,
    update_lead_stage, add_lead_note, soft_delete_lead
)

router = APIRouter(prefix="/leads", tags=["Leads"])

@router.get("", response_model=LeadListResponse)
async def get_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    score: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    return await list_leads(
        db=db,
        broker_id=current_broker.id,
        page=page,
        limit=limit,
        score=score,
        stage=stage,
        source=source,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_new_lead(
    lead_req: LeadCreate,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    return await create_lead(db=db, broker_id=current_broker.id, req=lead_req)

@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead_detail(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    return await get_lead_by_id(db=db, lead_id=lead_id, broker_id=current_broker.id)

@router.patch("/{lead_id}/status", response_model=LeadResponse)
async def patch_lead_status(
    lead_id: uuid.UUID,
    status_req: StatusUpdate,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    return await update_lead_status(
        db=db,
        lead_id=lead_id,
        broker_id=current_broker.id,
        new_status=status_req.status
    )

@router.patch("/{lead_id}/stage", response_model=LeadResponse)
async def patch_lead_stage(
    lead_id: uuid.UUID,
    stage_req: StageUpdate,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    return await update_lead_stage(
        db=db,
        lead_id=lead_id,
        broker_id=current_broker.id,
        new_stage=stage_req.stage
    )

@router.post("/{lead_id}/notes", response_model=LeadResponse)
async def create_lead_note(
    lead_id: uuid.UUID,
    note_req: NoteCreate,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    return await add_lead_note(
        db=db,
        lead_id=lead_id,
        broker_id=current_broker.id,
        note_req=note_req
    )

@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    await soft_delete_lead(db=db, lead_id=lead_id, broker_id=current_broker.id)
    return None
