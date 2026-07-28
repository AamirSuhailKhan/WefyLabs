import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.broker import Broker

security = HTTPBearer()

# In-memory IP rate limiter: ip -> list of request timestamps
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60.0  # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 5  # 5 requests per minute

def clear_rate_limits():
    """Resets the in-memory rate limiting store for testing."""
    _rate_limit_store.clear()

async def check_auth_rate_limit(request: Request) -> None:
    """Enforces rate limiting of 5 requests per minute per IP for auth endpoints."""
    if settings.ENV in ("testing", "test"):
        return

    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    
    # Remove timestamps older than window
    timestamps = [ts for ts in _rate_limit_store[client_ip] if now - ts < RATE_LIMIT_WINDOW]
    
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 5 authentication requests per minute allowed."
        )
    
    timestamps.append(now)
    _rate_limit_store[client_ip] = timestamps

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async dependency yielding a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_current_broker(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Broker:
    """
    Validates Supabase JWT from Authorization: Bearer <token> header,
    verifies exp/iat claims, and retrieves the corresponding Broker model from DB.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256", "RS256"],
            options={"verify_aud": False, "verify_exp": True, "verify_iat": True}
        )
        sub_identifier: str = payload.get("email") or payload.get("sub")
        if not sub_identifier:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    # Query broker by email or UUID
    try:
        broker_uuid = uuid.UUID(sub_identifier)
        stmt = select(Broker).where((Broker.email == sub_identifier) | (Broker.id == broker_uuid))
    except (ValueError, AttributeError):
        stmt = select(Broker).where(Broker.email == sub_identifier)

    result = await db.execute(stmt)
    broker = result.scalars().first()

    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker account not found"
        )
        
    return broker

async def require_active_subscription(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
) -> Broker:
    """
    Enforces active subscription or non-expired trial.
    Returns HTTP 403 with code TRIAL_EXPIRED or SUBSCRIPTION_INACTIVE if restricted.
    """
    if broker.subscription_status == "active":
        return broker

    now = datetime.now(timezone.utc)
    trial_end = broker.trial_ends_at
    if trial_end and trial_end.tzinfo is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)

    if broker.subscription_status == "trial":
        if trial_end and now > trial_end:
            broker.subscription_status = "expired"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "TRIAL_EXPIRED",
                    "message": "Your 7-day trial has expired. Please upgrade your subscription to continue."
                }
            )
        return broker

    if broker.subscription_status == "expired":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TRIAL_EXPIRED",
                "message": "Your trial has expired. Please upgrade your subscription to continue."
            }
        )

    if broker.subscription_status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUBSCRIPTION_INACTIVE",
                "message": "Your subscription is cancelled. Please renew to continue."
            }
        )

    return broker
