from typing import Optional
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.event_history.service.event_history_service import EventHistoryService

router = APIRouter(prefix="/v1/event-history", tags=["Event History"])


@router.get("", response_model=APIResponse)
async def list_event_history(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = EventHistoryService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    result = await service.search(
        organization_id=org_id or None,
        event_type=event_type,
        status=status,
        page=page,
        limit=limit,
    )
    return create_success_response(
        data=[
            {
                "id": str(r.id),
                "event_id": r.event_id,
                "event_type": r.event_type,
                "processing_status": r.processing_status,
                "actor_id": r.actor_id,
                "published_at": r.published_at,
                "created_at": r.created_at,
            }
            for r in result["items"]
        ],
        meta={"total": result["total"], "page": result["page"], "limit": result["limit"]},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.post("/{record_id}/replay", response_model=APIResponse)
async def replay_event(
    record_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = EventHistoryService(db)
    try:
        await service.replay(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return create_success_response(data={"replayed": True, "record_id": record_id}, request_id=getattr(request.state, "correlation_id", ""))
