from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker, check_auth_rate_limit
from app.models.broker import Broker
from app.schemas.broker import BrokerResponse
from app.modules.auth.schemas import RegisterRequest, LoginRequest, OAuthCallbackRequest, AuthTokenResponse
from app.modules.auth.service import register_broker, authenticate_broker, sync_oauth_broker, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])

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

@router.get("/me", response_model=BrokerResponse)
async def get_me(current_broker: Broker = Depends(get_current_broker)):
    return BrokerResponse.model_validate(current_broker)
