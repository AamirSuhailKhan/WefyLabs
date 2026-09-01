from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.api_keys.service.api_key_service import ApiKeyService
from app.modules.api_keys.dto.api_key_dto import ApiKeyCreateDTO, ApiKeyResponseDTO, ApiKeyCreatedDTO

router = APIRouter(prefix="/v1/api-keys", tags=["API Key Management"])


@router.get("", response_model=APIResponse)
async def list_api_keys(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = ApiKeyService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    keys = await service.list_keys(org_id)
    return create_success_response(
        data=[ApiKeyResponseDTO.model_validate(k) for k in keys],
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    dto: ApiKeyCreateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = ApiKeyService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    result = await service.create(
        organization_id=org_id,
        broker_id=str(current_broker.id),
        name=dto.name,
        scopes=dto.scopes,
        expires_at=dto.expires_at,
    )
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))


@router.post("/{key_id}/rotate", response_model=APIResponse)
async def rotate_api_key(
    key_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = ApiKeyService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    try:
        result = await service.rotate(key_id, org_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))


@router.delete("/{key_id}", response_model=APIResponse)
async def revoke_api_key(
    key_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = ApiKeyService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    await service.revoke(key_id, org_id)
    return create_success_response(data={"revoked": True}, request_id=getattr(request.state, "correlation_id", ""))
