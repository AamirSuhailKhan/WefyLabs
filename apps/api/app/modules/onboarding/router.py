"""
PART 31 — Customer Onboarding, Tenant Activation & Demo Mode FastAPI REST Router
================================================================================
Endpoints:
    GET  /api/v1/onboarding/status            # Current step, progressive checklist, live activation
    POST /api/v1/onboarding/step              # Complete or skip onboarding step
    POST /api/v1/onboarding/business-profile  # Set organization business profile & defaults
    GET  /api/v1/onboarding/activation        # Tenant activation score and milestone breakdown
    POST /api/v1/onboarding/demo/start        # Initialize isolated ephemeral demo playground
    POST /api/v1/onboarding/demo/reset        # Safely teardown demo session
    POST /api/v1/onboarding/import/preview    # Sanitize and preview CSV leads/properties
    POST /api/v1/onboarding/import/commit     # Atomically commit imported records
    POST /api/v1/onboarding/invite-team       # Invite team member with RBAC role
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.common.redis.rate_limiter import check_rate_limit
from app.modules.onboarding.dto import (
    BusinessProfileSetupDTO,
    OnboardingStepUpdateDTO,
    OnboardingStatusResponseDTO,
    TenantActivationResponseDTO,
    DemoSessionCreateDTO,
    DemoSessionResponseDTO,
    CsvImportPreviewDTO,
    CsvImportCommitDTO,
    CsvImportResultDTO,
    OnboardingTeamInviteDTO,
)
from app.modules.onboarding.onboarding_service import OnboardingService
from app.modules.onboarding.activation_service import TenantActivationService
from app.modules.onboarding.demo_service import DemoModeService
from app.modules.onboarding.csv_import_service import OnboardingCsvImportService
from app.modules.auth.invitation_service import InvitationService

logger = logging.getLogger("beetlelabs.onboarding.router")

router = APIRouter(prefix="/api/v1/onboarding", tags=["Customer Onboarding & Tenant Activation"])


def _enforce_rate_limit(request: Request, prefix: str = "rl:onboarding", limit: int = 30) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip, prefix=prefix, limit=limit, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many onboarding requests. Please wait a minute."
        )


@router.get(
    "/status",
    response_model=OnboardingStatusResponseDTO,
    summary="Fetch Workspace Onboarding Status & Dynamic Checklist"
)
async def get_onboarding_status_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Returns the persistent onboarding state, real progress percentage,
    dynamic checklist synchronized with live CRM entities, and activation score.
    """
    service = OnboardingService(db)
    try:
        return await service.get_status(broker=current_broker)
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] get_status failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/step",
    response_model=OnboardingStatusResponseDTO,
    summary="Update / Skip Onboarding Step"
)
async def update_onboarding_step_endpoint(
    step_dto: OnboardingStepUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Advances or skips an onboarding step, saving payload parameters and advancing current step.
    """
    service = OnboardingService(db)
    try:
        return await service.update_step(broker=current_broker, step_dto=step_dto)
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] update_step failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/business-profile",
    response_model=OnboardingStatusResponseDTO,
    summary="Configure Organization Business Profile"
)
async def update_business_profile_endpoint(
    profile_dto: BusinessProfileSetupDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Configures agency legal name, business type, operating city, timezone, and currency.
    Marks ORGANIZATION_SETUP step as complete and records audit entry.
    """
    service = OnboardingService(db)
    try:
        return await service.update_business_profile(broker=current_broker, dto=profile_dto)
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] update_business_profile failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/activation",
    response_model=TenantActivationResponseDTO,
    summary="Get Deterministic Tenant Activation Status"
)
async def get_tenant_activation_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Returns real-time tenant activation score (0-100) and milestone checklist.
    Automatically evaluates live database entities for existing and new tenants.
    """
    service = TenantActivationService(db)
    try:
        return await service.get_or_calculate_activation(broker=current_broker)
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] get_activation failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/demo/start",
    response_model=DemoSessionResponseDTO,
    summary="Initialize Isolated Demo Playground"
)
async def start_demo_session_endpoint(
    request: Request,
    dto: DemoSessionCreateDTO = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Spawns an isolated demo tenant with synthetic Indian real estate properties, leads,
    AI matches, and tasks. External side-effects are blocked.
    """
    _enforce_rate_limit(request, prefix="rl:demo_start", limit=10)
    client_ip = request.client.host if request.client else "unknown"
    demo_svc = DemoModeService(db)
    try:
        session_dto = await demo_svc.create_demo_workspace(
            intended_agency_name=dto.intended_agency_name,
            operating_city=dto.operating_city or "Bengaluru",
            client_ip=client_ip
        )
        return session_dto
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] start_demo failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/demo/reset",
    summary="Safely Purge Demo Playground Session"
)
async def reset_demo_session_endpoint(
    session_token: str = Query(..., min_length=16),
    db: AsyncSession = Depends(get_db),
):
    """
    Safely tears down a demo workspace. Strictly verifies is_demo=True to guard against
    deleting production customer organizations.
    """
    demo_svc = DemoModeService(db)
    try:
        success = await demo_svc.reset_demo_session(session_token=session_token)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Demo session not found or already purged."
            )
        return {"status": "success", "message": "Demo workspace successfully purged."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] reset_demo failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/import/preview",
    response_model=CsvImportPreviewDTO,
    summary="Preview & Validate CSV Data with Formula Sanitization"
)
async def preview_csv_import_endpoint(
    entity_type: str = Query("leads", pattern="^(leads|properties)$"),
    raw_csv: str = Body("", media_type="text/plain"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Sanitizes against CSV formula injection (CWE-1236), parses columns, and detects duplicates.
    """
    svc = OnboardingCsvImportService(db)
    try:
        return await svc.preview_csv(
            broker=current_broker,
            raw_csv_text=raw_csv,
            entity_type=entity_type
        )
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] preview_csv failed: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/import/commit",
    response_model=CsvImportResultDTO,
    summary="Commit Sanitized CSV Records to Database"
)
async def commit_csv_import_endpoint(
    dto: CsvImportCommitDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Transactionally commits validated leads or properties, updating onboarding state automatically.
    """
    svc = OnboardingCsvImportService(db)
    onboarding_svc = OnboardingService(db)
    try:
        result = await svc.commit_import(broker=current_broker, dto=dto)
        
        # Trigger onboarding step progression
        step_name = "LEAD_SETUP" if dto.entity_type == "leads" else "PROPERTY_SETUP"
        await onboarding_svc.update_step(
            broker=current_broker,
            step_dto=OnboardingStepUpdateDTO(
                step=step_name,
                action="complete",
                payload={"imported_count": result.imported_count}
            )
        )
        return result
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] commit_csv failed: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/invite-team",
    summary="Invite Team Member during Onboarding"
)
async def invite_team_member_endpoint(
    invite_dto: OnboardingTeamInviteDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Creates an organization-scoped single-use invitation using the existing InvitationService.
    Marks TEAM_INVITE onboarding step as complete.
    """
    onboarding_svc = OnboardingService(db)
    try:
        invitation_data = await InvitationService.create_invitation(
            db=db,
            inviter=current_broker,
            email=invite_dto.email,
            role=invite_dto.role
        )
        # Mark TEAM_INVITE step complete
        await onboarding_svc.update_step(
            broker=current_broker,
            step_dto=OnboardingStepUpdateDTO(
                step="TEAM_INVITE",
                action="complete",
                payload={"invited_email": invite_dto.email, "role": invite_dto.role}
            )
        )
        return {
            "status": "success",
            "message": f"Invitation created and dispatched for {invite_dto.email}",
            "invitation": invitation_data
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[ONBOARDING_ROUTER] invite_team failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
