from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Request, status, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.integrations.service.integration_service import IntegrationService

router = APIRouter(prefix="/v1/integrations", tags=["Integrations Framework"])


class IntegrationConnectDTO(BaseModel):
    credentials: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None


@router.get("/providers", response_model=APIResponse)
async def list_providers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = IntegrationService(db)
    providers = service.list_available_providers()
    return create_success_response(data=providers, request_id=getattr(request.state, "correlation_id", ""))


@router.get("", response_model=APIResponse)
async def list_connected_integrations(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = IntegrationService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    integrations = await service.list_connected(org_id)
    return create_success_response(
        data=[
            {"id": str(i.id), "provider": i.provider, "display_name": i.display_name, "status": i.status}
            for i in integrations
        ],
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.post("/{provider}/connect", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def connect_integration(
    provider: str,
    dto: IntegrationConnectDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = IntegrationService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    try:
        integration = await service.connect(org_id, provider, dto.credentials, dto.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return create_success_response(
        data={"id": str(integration.id), "provider": integration.provider, "status": integration.status},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.delete("/{provider}", response_model=APIResponse)
async def disconnect_integration(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = IntegrationService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    try:
        await service.disconnect(org_id, provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return create_success_response(data={"disconnected": True}, request_id=getattr(request.state, "correlation_id", ""))
