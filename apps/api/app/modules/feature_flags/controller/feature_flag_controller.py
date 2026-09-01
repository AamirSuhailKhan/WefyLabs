from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.feature_flags.service.feature_flag_service import FeatureFlagService
from app.modules.feature_flags.dto.feature_flag_dto import FeatureFlagUpdateDTO, FeatureFlagResponseDTO

router = APIRouter(prefix="/v1/feature-flags", tags=["Feature Flags"])


@router.get("", response_model=APIResponse)
async def list_feature_flags(
    request: Request,
    environment: str = Query(default="production"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = FeatureFlagService(db)
    flags = await service.list_flags(environment=environment)
    return create_success_response(
        data=[FeatureFlagResponseDTO.model_validate(f) for f in flags],
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/{key}", response_model=APIResponse)
async def evaluate_feature_flag(
    key: str,
    request: Request,
    environment: str = Query(default="production"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = FeatureFlagService(db)
    org_id = str(getattr(current_broker, "organization_id", "") or "")
    enabled = await service.is_enabled(
        key=key,
        organization_id=org_id or None,
        user_id=str(current_broker.id),
        environment=environment,
    )
    return create_success_response(
        data={"key": key, "enabled": enabled},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.put("/{key}", response_model=APIResponse)
async def set_feature_flag(
    key: str,
    dto: FeatureFlagUpdateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = FeatureFlagService(db)
    flag = await service.set_flag(
        key=key,
        is_enabled=dto.is_enabled,
        scope=dto.scope,
        scope_id=dto.scope_id,
        rollout_percentage=dto.rollout_percentage,
        description=dto.description,
        environment=dto.environment,
    )
    return create_success_response(
        data=FeatureFlagResponseDTO.model_validate(flag),
        request_id=getattr(request.state, "correlation_id", ""),
    )
