from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.saved_searches.service.saved_search_service import SavedSearchService
from app.modules.search.dto.search_dto import SavedSearchCreateDTO

router = APIRouter(prefix="/v1/saved-searches", tags=["Saved Searches"])


@router.get("", response_model=APIResponse)
async def list_saved_searches(
    request: Request,
    entity_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    service = SavedSearchService(db)
    items = await service.list_for_user(str(current_broker.id), org_id, entity_type)
    return create_success_response(data=items, request_id=getattr(request.state, "correlation_id", ""))


@router.post("", response_model=APIResponse)
async def create_saved_search(
    dto: SavedSearchCreateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    service = SavedSearchService(db)
    result = await service.create(dto, str(current_broker.id), org_id)
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))


@router.put("/{search_id}", response_model=APIResponse)
async def update_saved_search(
    search_id: str,
    dto: SavedSearchCreateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    from fastapi import HTTPException
    service = SavedSearchService(db)
    result = await service.update(search_id, str(current_broker.id), dto)
    if not result:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))


@router.delete("/{search_id}", response_model=APIResponse)
async def delete_saved_search(
    search_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    from fastapi import HTTPException
    service = SavedSearchService(db)
    deleted = await service.delete(search_id, str(current_broker.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    return create_success_response(data={"deleted": True}, request_id=getattr(request.state, "correlation_id", ""))
