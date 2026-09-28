import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.infrastructure.tenancy.scope import resolve_organization_id_for_broker
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
    requested_org_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_org_id, allow_fallback=True)
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
        sort_order=sort_order,
        organization_id=org_id,
    )


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_new_lead(
    lead_req: LeadCreate,
    requested_org_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_org_id, allow_fallback=True)
    return await create_lead(db=db, broker_id=current_broker.id, req=lead_req, organization_id=org_id)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead_detail(
    lead_id: uuid.UUID,
    requested_org_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_org_id, allow_fallback=True)
    return await get_lead_by_id(db=db, lead_id=lead_id, broker_id=current_broker.id, organization_id=org_id)


@router.patch("/{lead_id}/status", response_model=LeadResponse)
async def patch_lead_status(
    lead_id: uuid.UUID,
    status_req: StatusUpdate,
    requested_org_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_org_id, allow_fallback=True)
    return await update_lead_status(
        db=db,
        lead_id=lead_id,
        broker_id=current_broker.id,
        new_status=status_req.status,
        organization_id=org_id,
    )


@router.patch("/{lead_id}/stage", response_model=LeadResponse)
async def patch_lead_stage(
    lead_id: uuid.UUID,
    stage_req: StageUpdate,
    requested_org_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_org_id, allow_fallback=True)
    return await update_lead_stage(
        db=db,
        lead_id=lead_id,
        broker_id=current_broker.id,
        new_stage=stage_req.stage,
        organization_id=org_id,
    )


@router.post("/{lead_id}/notes", response_model=LeadResponse)
async def create_lead_note(
    lead_id: uuid.UUID,
    note_req: NoteCreate,
    requested_org_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_org_id, allow_fallback=True)
    return await add_lead_note(
        db=db,
        lead_id=lead_id,
        broker_id=current_broker.id,
        note_req=note_req,
        organization_id=org_id,
    )


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    requested_org_id: Optional[str] = Header(None, alias="X-WefyLabs-Organization-Id"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    org_id = await resolve_organization_id_for_broker(db, current_broker.id, requested_org_id, allow_fallback=True)
    await soft_delete_lead(db=db, lead_id=lead_id, broker_id=current_broker.id, organization_id=org_id)
    return None
