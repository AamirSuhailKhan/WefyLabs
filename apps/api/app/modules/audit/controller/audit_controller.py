import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.audit.service.audit_service import AuditService
from app.modules.audit.dto.audit_dto import AuditSearchDTO

router = APIRouter(prefix="/v1/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=APIResponse)
async def search_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Search immutable audit logs. Admins only."""
    dto = AuditSearchDTO(
        page=page,
        limit=limit,
        organization_id=str(getattr(current_broker, "organization_id", "")) or None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    service = AuditService(db)
    result = await service.search(dto)
    return create_success_response(
        data=result["items"],
        meta={k: v for k, v in result.items() if k != "items"},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/{audit_id}", response_model=APIResponse)
async def get_audit_log(
    audit_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    from fastapi import HTTPException
    service = AuditService(db)
    result = await service.get_by_id(audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit log entry not found.")
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))
