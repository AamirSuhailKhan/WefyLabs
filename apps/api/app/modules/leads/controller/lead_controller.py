import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.infrastructure.events.event_bus import ActorContext
from app.modules.leads.service.lead_service import LeadService
from app.modules.leads.dto.lead_dto import (
    LeadCreateDTO, LeadUpdateDTO, LeadSearchDTO, LeadQualifyDTO, LeadBulkDTO
)

router = APIRouter(prefix="/v1/leads", tags=["Leads Hexagonal V1"])

@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    req: LeadCreateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker = Depends(get_current_broker)
):
    actor = ActorContext(
        user_id=str(current_broker.id),
        role=getattr(current_broker, "role", "broker"),
        actor_type="user"
    )
    service = LeadService(db)
    result = await service.create_lead(req, current_broker.id, actor)
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))

@router.get("", response_model=APIResponse)
async def list_leads(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    query: Optional[str] = None,
    score: Optional[str] = None,
    stage: Optional[str] = None,
    source: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_broker = Depends(get_current_broker)
):
    search_dto = LeadSearchDTO(
        page=page,
        limit=limit,
        query=query,
        score=score,
        stage=stage,
        source=source,
        status=status_filter
    )
    service = LeadService(db)
    result = await service.search_leads(search_dto, current_broker.id)
    return create_success_response(
        data=result.items,
        meta={
            "total": result.total,
            "page": result.page,
            "pages": result.pages,
            "limit": result.limit,
            "has_next": result.has_next,
            "has_prev": result.has_prev
        },
        request_id=getattr(request.state, "correlation_id", "")
    )

@router.get("/{lead_id}", response_model=APIResponse)
async def get_lead(
    lead_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker = Depends(get_current_broker)
):
    service = LeadService(db)
    result = await service.get_lead(lead_id, current_broker.id)
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))

@router.put("/{lead_id}", response_model=APIResponse)
async def update_lead(
    lead_id: uuid.UUID,
    dto: LeadUpdateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker = Depends(get_current_broker)
):
    actor = ActorContext(
        user_id=str(current_broker.id),
        role=getattr(current_broker, "role", "broker"),
        actor_type="user"
    )
    service = LeadService(db)
    result = await service.update_lead(lead_id, dto, current_broker.id, actor)
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))

@router.post("/{lead_id}/qualify", response_model=APIResponse)
async def qualify_lead(
    lead_id: uuid.UUID,
    dto: LeadQualifyDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker = Depends(get_current_broker)
):
    actor = ActorContext(
        user_id=str(current_broker.id),
        role=getattr(current_broker, "role", "broker"),
        actor_type="user"
    )
    service = LeadService(db)
    result = await service.qualify_lead(lead_id, dto, current_broker.id, actor)
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))

@router.post("/bulk", response_model=APIResponse)
async def bulk_lead_operations(
    dto: LeadBulkDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker = Depends(get_current_broker)
):
    actor = ActorContext(
        user_id=str(current_broker.id),
        role=getattr(current_broker, "role", "broker"),
        actor_type="user"
    )
    service = LeadService(db)
    updated_count = await service.bulk_operation(dto, current_broker.id, actor)
    return create_success_response(data={"updated_count": updated_count}, request_id=getattr(request.state, "correlation_id", ""))

@router.delete("/{lead_id}", response_model=APIResponse)
async def archive_lead(
    lead_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker = Depends(get_current_broker)
):
    actor = ActorContext(
        user_id=str(current_broker.id),
        role=getattr(current_broker, "role", "broker"),
        actor_type="user"
    )
    service = LeadService(db)
    await service.archive_lead(lead_id, current_broker.id, actor)
    return create_success_response(data={"archived": True}, request_id=getattr(request.state, "correlation_id", ""))
