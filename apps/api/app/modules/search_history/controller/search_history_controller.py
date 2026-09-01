from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.search_history.service.search_history_service import SearchHistoryService

router = APIRouter(prefix="/v1/search/history", tags=["Search History"])


@router.get("", response_model=APIResponse)
async def get_recent_history(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    service = SearchHistoryService(db)
    items = await service.get_recent(str(current_broker.id), org_id, limit)
    return create_success_response(data=items, request_id=getattr(request.state, "correlation_id", ""))


@router.get("/popular", response_model=APIResponse)
async def get_popular_searches(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    service = SearchHistoryService(db)
    items = await service.get_popular(org_id, limit)
    return create_success_response(data=items, request_id=getattr(request.state, "correlation_id", ""))


@router.delete("/{history_id}", response_model=APIResponse)
async def delete_history_entry(
    history_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    from fastapi import HTTPException
    service = SearchHistoryService(db)
    deleted = await service.delete_entry(history_id, str(current_broker.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return create_success_response(data={"deleted": True}, request_id=getattr(request.state, "correlation_id", ""))


@router.delete("", response_model=APIResponse)
async def clear_all_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    service = SearchHistoryService(db)
    count = await service.clear_history(str(current_broker.id), org_id)
    return create_success_response(data={"cleared": count}, request_id=getattr(request.state, "correlation_id", ""))
