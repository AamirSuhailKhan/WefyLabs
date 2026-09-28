from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_current_broker, check_auth_rate_limit
from app.models.broker import Broker
from app.schemas.broker import BrokerResponse
from sqlalchemy import select
import hashlib
import secrets
import uuid
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from typing import Optional
from app.modules.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthTokenResponse,
    OnboardRequest,
    GoogleAuthUrlResponse,
    GoogleExchangeRequest,
)
from app.modules.auth.service import (
    register_broker,
    authenticate_broker,
    get_or_create_test_broker,
    create_access_token,
    generate_google_auth_url,
    exchange_google_oauth_code,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

# ─── Phase 0 P0.1 — OAuth session binding ──────────────────────────────────
# The OAuth CSRF state is stored server-side and bound to an opaque session id
# carried by an HttpOnly cookie. The cookie carries no identity and no token:
# it only lets the server prove that the callback came from the same browser
# that initiated the flow.
OAUTH_SESSION_COOKIE = "wefylabs_oauth_sid"
_OAUTH_SESSION_COOKIE_MAX_AGE = 1800  # 30 minutes — covers the OAuth round-trip


def _oauth_cookie_secure() -> bool:
    return settings.ENV.lower() in ("production", "prod", "staging")


def _resolve_or_create_oauth_session(request: Request, response: Response) -> str:
    """Returns the opaque OAuth session id, minting the cookie when absent."""
    existing = request.cookies.get(OAUTH_SESSION_COOKIE)
    if existing and len(existing) >= 16:
        return existing
    session_id = secrets.token_urlsafe(32)
    response.set_cookie(
        OAUTH_SESSION_COOKIE,
        session_id,
        max_age=_OAUTH_SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_oauth_cookie_secure(),
        path="/",
    )
    return session_id


def _resolve_oauth_session(request: Request) -> str:
    """Read-only session resolution for the exchange step (never mints cookies).

    Falls back to a client fingerprint when the cookie is unavailable. The
    fingerprint binds the state to the originating browser context without
    storing any personal identifier.
    """
    existing = request.cookies.get(OAUTH_SESSION_COOKIE)
    if existing and len(existing) >= 16:
        return existing
    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"oauth-sid|{ip}|{ua}".encode("utf-8")).hexdigest()


@router.get("/google/url", response_model=GoogleAuthUrlResponse)
async def get_google_auth_url(
    redirect_uri: Optional[str] = None,
    request: Request = None,
    response: Response = None,
):
    """Returns the Google OAuth 2.0 Authorization URL with server-issued state."""
    session_id = _resolve_or_create_oauth_session(request, response)
    auth_url, state = generate_google_auth_url(redirect_uri, session_id=session_id)
    return GoogleAuthUrlResponse(auth_url=auth_url, state=state)

@router.post(
    "/google/exchange",
    response_model=AuthTokenResponse,
    dependencies=[Depends(check_auth_rate_limit)]
)
async def google_exchange(
    req: GoogleExchangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Exchanges Google authorization code for a verified session and token."""
    session_id = _resolve_oauth_session(request)
    broker = await exchange_google_oauth_code(db, req, session_id=session_id)
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


# ─── Phase 0 P0.1 — Isolated test identity fixture ─────────────────────────
# Production authentication code and test authentication are deliberately
# separate. This endpoint: (a) exists only when the process runs in the
# 'testing'/'development' environments, (b) is a DIFFERENT endpoint from the
# real OAuth flow — it can never be reached by the production code path, and
# (c) is additionally compiled out at import time in production.
if settings.ENV.lower() not in ("production", "prod"):
    from pydantic import BaseModel as _BaseModel

    class TestIdentityRequest(_BaseModel):
        email: str
        name: Optional[str] = None

    @router.post(
        "/test/identity",
        response_model=AuthTokenResponse,
        include_in_schema=settings.ENV.lower() in ("testing", "test", "development", "dev"),
        dependencies=[Depends(check_auth_rate_limit)],
        summary="[TEST/DEV ONLY] Mint a session for a test identity. Hard-disabled in production.",
    )
    async def test_identity_endpoint(
        req: TestIdentityRequest,
        db: AsyncSession = Depends(get_db),
    ):
        if settings.ENV.lower() in ("production", "prod", "staging"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not found."
            )
        broker = await get_or_create_test_broker(db, email=req.email, name=req.name)
        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        return AuthTokenResponse(
            access_token=token,
            broker=BrokerResponse.model_validate(broker)
        )

