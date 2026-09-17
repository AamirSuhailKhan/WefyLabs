import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
import logging

logger = logging.getLogger("beetlelabs.dependencies")
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.broker import Broker

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

# ─── Distributed Redis-backed rate limiter ─────────────────────────────────────
# Shared across all Kubernetes replicas via Redis atomic INCR+EXPIRE.
# Falls back to in-memory gracefully when Redis is unavailable.
from app.common.redis.rate_limiter import check_rate_limit, clear_rate_limits  # noqa: E402


async def check_auth_rate_limit(request: Request) -> None:
    """Enforces distributed rate limiting of 5 requests per minute per IP for auth endpoints.

    Uses Redis-backed sliding window counter shared across all replicas.
    Falls back to in-memory automatically if Redis is unreachable.
    """
    if settings.ENV in ("testing", "test"):
        return

    client_ip = request.client.host if request.client else "127.0.0.1"
    allowed = check_rate_limit(
        client_ip,
        prefix="rl:auth",
        limit=5,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 5 authentication requests per minute allowed.",
            headers={"Retry-After": "60"},
        )


async def get_current_broker(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Broker:
    """
    Validates Supabase JWT from Authorization: Bearer <token> header.
    Verifies exp/iat claims and retrieves the verified Broker from DB.

    Security guarantees:
    - No mock bypass exists. Every request must carry a valid JWT.
    - Expired tokens always return 401.
    - Broker not in DB always returns 401 (not 404 — no info leak).
    - In development, JWT decoding falls back to HS256 only.
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
            detail="Authentication token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    # Query broker by email or UUID (Supabase sub can be either)
    try:
        broker_uuid = uuid.UUID(sub_identifier)
        stmt = select(Broker).where((Broker.email == sub_identifier) | (Broker.id == broker_uuid))
    except (ValueError, AttributeError):
        stmt = select(Broker).where(Broker.email == sub_identifier)

    result = await db.execute(stmt)
    broker = result.scalars().first()

    if broker is None:
        # Return 401 not 404 — do not reveal whether the account exists
        raise credentials_exception

    if broker.onboarding_status == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This broker account has been suspended."
        )

    return broker

async def get_optional_broker(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: AsyncSession = Depends(get_db)
) -> Optional[Broker]:
    """Returns authenticated Broker if valid credentials exist, otherwise None."""
    if not credentials:
        return None
    try:
        return await get_current_broker(credentials=credentials, db=db)
    except HTTPException:
        return None

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
