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
