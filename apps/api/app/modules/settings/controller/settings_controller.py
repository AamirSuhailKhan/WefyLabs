from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.settings.service.settings_service import SettingsService
from app.modules.settings.dto.settings_dto import SettingUpsertDTO, SettingResponseDTO

router = APIRouter(prefix="/v1/settings", tags=["Settings"])


@router.get("", response_model=APIResponse)
async def list_settings(
    request: Request,
    scope: str = Query(default="organization"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = SettingsService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    items = await service.get_all(scope=scope, scope_id=org_id or None)
    return create_success_response(
        data=[SettingResponseDTO.model_validate(i) for i in items],
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.put("", response_model=APIResponse)
async def upsert_setting(
    dto: SettingUpsertDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = SettingsService(db)
    setting = await service.set(
        key=dto.key,
        value=dto.value,
        scope=dto.scope,
        scope_id=dto.scope_id,
        value_type=dto.value_type,
        description=dto.description,
        is_sensitive=dto.is_sensitive,
        updated_by=str(current_broker.id),
    )
    return create_success_response(
        data=SettingResponseDTO.model_validate(setting),
        request_id=getattr(request.state, "correlation_id", ""),
    )
