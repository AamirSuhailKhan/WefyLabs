from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.timeline.service.timeline_service import TimelineService
from app.modules.timeline.dto.timeline_dto import TimelineSearchDTO

router = APIRouter(prefix="/v1/timeline", tags=["Activity Timeline"])


@router.get("/{resource_type}/{resource_id}", response_model=APIResponse)
async def get_resource_timeline(
    resource_type: str,
    resource_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = None,
    channel: Optional[str] = None,
    actor_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Unified timeline for any CRM object (lead, contact, property, deal)."""
    search_dto = TimelineSearchDTO(
        page=page, limit=limit,
        event_type=event_type, channel=channel, actor_type=actor_type
    )
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    service = TimelineService(db)
    result = await service.get_timeline(resource_type, resource_id, org_id, search_dto)
    return create_success_response(
        data=result.items,
        meta={
            "total": result.total, "page": result.page,
            "pages": result.pages, "limit": result.limit,
            "has_next": result.has_next, "has_prev": result.has_prev,
        },
        request_id=getattr(request.state, "correlation_id", ""),
    )
