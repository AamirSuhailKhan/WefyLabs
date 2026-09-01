from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.notifications.service.notification_service import NotificationEngine
from app.modules.notifications.dto.notification_dto import NotificationSendDTO, NotificationSearchDTO

router = APIRouter(prefix="/v1/notifications", tags=["Notifications"])


@router.get("", response_model=APIResponse)
async def list_notifications(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    is_read: Optional[bool] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    engine = NotificationEngine(db)
    result = await engine.list_notifications(
        str(current_broker.id),
        NotificationSearchDTO(page=page, limit=limit, is_read=is_read, category=category),
    )
    return create_success_response(
        data=result["items"],
        meta={k: v for k, v in result.items() if k != "items"},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.post("/{notification_id}/read", response_model=APIResponse)
async def mark_notification_read(
    notification_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    engine = NotificationEngine(db)
    await engine.mark_read(notification_id, str(current_broker.id))
    return create_success_response(data={"marked_read": True}, request_id=getattr(request.state, "correlation_id", ""))


@router.post("/read-all", response_model=APIResponse)
async def mark_all_read(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    engine = NotificationEngine(db)
    count = await engine.mark_all_read(str(current_broker.id))
    return create_success_response(data={"marked_count": count}, request_id=getattr(request.state, "correlation_id", ""))
