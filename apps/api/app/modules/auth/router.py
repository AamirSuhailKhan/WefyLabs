from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker, check_auth_rate_limit
from app.models.broker import Broker
from app.schemas.broker import BrokerResponse
from sqlalchemy import select
import uuid
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from typing import Optional
from app.modules.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    OAuthCallbackRequest,
    AuthTokenResponse,
    OnboardRequest,
    GoogleAuthUrlResponse,
    GoogleExchangeRequest
)
from app.modules.auth.service import (
    register_broker,
    authenticate_broker,
    sync_oauth_broker,
    create_access_token,
    generate_google_auth_url,
    exchange_google_oauth_code
)

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/google/url", response_model=GoogleAuthUrlResponse)
async def get_google_auth_url(redirect_uri: Optional[str] = None):
    """Returns the Google OAuth 2.0 Authorization URL with CSRF state."""
    auth_url, state = generate_google_auth_url(redirect_uri)
    return GoogleAuthUrlResponse(auth_url=auth_url, state=state)

@router.post(
    "/google/exchange",
    response_model=AuthTokenResponse,
    dependencies=[Depends(check_auth_rate_limit)]
)
async def google_exchange(req: GoogleExchangeRequest, db: AsyncSession = Depends(get_db)):
    """Exchanges Google authorization code for verified session and token."""
    broker = await exchange_google_oauth_code(db, req)
    token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
    return AuthTokenResponse(
        access_token=token,
        broker=BrokerResponse.model_validate(broker)
    )

@router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_auth_rate_limit)]
)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    broker = await register_broker(db, req)
    token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
    return AuthTokenResponse(
        access_token=token,
        broker=BrokerResponse.model_validate(broker)
    )

@router.post(
    "/login",
    response_model=AuthTokenResponse,
    dependencies=[Depends(check_auth_rate_limit)]
)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    broker = await authenticate_broker(db, req.email, req.password)
    token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
    return AuthTokenResponse(
        access_token=token,
        broker=BrokerResponse.model_validate(broker)
    )

@router.post(
    "/callback",
    response_model=AuthTokenResponse,
    dependencies=[Depends(check_auth_rate_limit)]
)
async def oauth_callback(req: OAuthCallbackRequest, db: AsyncSession = Depends(get_db)):
    broker = await sync_oauth_broker(db, req)
    token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
    return AuthTokenResponse(
        access_token=token,
        broker=BrokerResponse.model_validate(broker)
    )

@router.post(
    "/onboard",
    response_model=BrokerResponse,
    dependencies=[Depends(check_auth_rate_limit)]
)
async def onboard(
    req: OnboardRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    if current_broker.onboarding_status == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This broker account has been suspended."
        )

    # Validate phone and whatsapp uniqueness
    stmt = select(Broker).where(
        (Broker.id != current_broker.id) & 
        ((Broker.phone == req.phone) | (Broker.whatsapp_number == req.whatsapp_number))
    )
    conflict = (await db.execute(stmt)).scalars().first()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A broker with this phone number or WhatsApp number already exists."
        )

    # Update Broker
    current_broker.name = req.name
    current_broker.phone = req.phone
    current_broker.whatsapp_number = req.whatsapp_number
    current_broker.agency_name = req.agency_name
    current_broker.city = req.city
    current_broker.onboarding_status = "ONBOARDED"
    db.add(current_broker)
    await db.flush()

    # Query existing org
    stmt_member = select(OrganizationMember).where(OrganizationMember.broker_id == current_broker.id)
    existing_member = (await db.execute(stmt_member)).scalars().first()

    if not existing_member:
        org = Organization(
            id=uuid.uuid4(),
            name=req.agency_name or f"{req.name}'s Agency",
            slug=f"org-{uuid.uuid4().hex[:6]}",
            plan="pro",
            country_code="IN"
        )
        db.add(org)
        await db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            broker_id=current_broker.id,
            role="owner"
        )
        db.add(member)
        org_id_str = str(org.id)
    else:
        org_id_str = str(existing_member.organization_id)

    # Sync User
    stmt_user = select(User).where(User.id == current_broker.id)
    existing_user = (await db.execute(stmt_user)).scalars().first()
    if not existing_user:
        user = User(
            id=current_broker.id,
            email=current_broker.email,
            name=req.name,
            phone=req.phone,
            whatsapp_number=req.whatsapp_number,
            organization_id=org_id_str,
            auth_provider="google",
            subscription_status="active"
        )
        db.add(user)
    else:
        existing_user.name = req.name
        existing_user.phone = req.phone
        existing_user.whatsapp_number = req.whatsapp_number
        existing_user.organization_id = org_id_str

    await db.commit()
    await db.refresh(current_broker)
    return current_broker

@router.get("/me", response_model=BrokerResponse)
async def get_me(current_broker: Broker = Depends(get_current_broker)):
    if current_broker.onboarding_status == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This broker account has been suspended."
        )
    return BrokerResponse.model_validate(current_broker)


# ─── PART 24.1 — Self-Service Password Reset Endpoints ─────────────────────────
from pydantic import BaseModel, EmailStr, Field
from app.modules.auth.password_reset_service import PasswordResetService, GENERIC_RESET_RESPONSE
from app.modules.auth.account_deletion_service import AccountDeletionService
from fastapi import Request


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8)


@router.post(
    "/forgot-password",
    dependencies=[Depends(check_auth_rate_limit)],
    summary="Request password reset instructions (Self-Service)"
)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Public self-service forgot password initiation.
    Returns identical generic response regardless of account existence to prevent enumeration.
    """
    base_url = str(request.base_url).rstrip("/")
    return await PasswordResetService.request_password_reset(
        email=req.email,
        db=db,
        frontend_base_url=base_url
    )


@router.get(
    "/verify-reset-token",
    summary="Verify reset token validity prior to password submission"
)
async def verify_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verifies that a reset token is valid, unexpired, and not yet used."""
    is_valid, err_msg, _ = await PasswordResetService.verify_reset_token(token, db)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    return {"valid": True, "message": "Token is valid."}


@router.post(
    "/reset-password",
    dependencies=[Depends(check_auth_rate_limit)],
    summary="Execute password reset with secure token"
)
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validates token and updates user password.
    Enforces password security standards and single-use token consumption.
    """
    return await PasswordResetService.execute_password_reset(
        token=req.token,
        new_password=req.new_password,
        db=db
    )


# ─── PART 24.1 — Google OAuth Revocation & Account Deletion ───────────────────
@router.delete(
    "/me",
    summary="Delete broker account and revoke external OAuth connections"
)
async def delete_account_me(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes the authenticated broker account, clears associated entities,
    and safely revokes external Google OAuth connections without blocking local cleanup.
    """
    return await AccountDeletionService.delete_broker_account(
        db=db,
        broker_id=current_broker.id
    )

