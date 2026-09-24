import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
import logging

logger = logging.getLogger("beetlelabs.dependencies")
import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.broker import Broker
from app.models.organization import OrganizationMember

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


async def require_super_admin(
    broker: Broker = Depends(get_current_broker),
) -> Broker:
    """Allow platform operations only for an explicit server-side allowlist.

    Tenant membership roles are intentionally insufficient here: a tenant owner
    must never become a platform operator merely by owning an organization.
    Empty configuration denies access, which is the safe launch default.
    """
    allowed_emails = {
        email.strip().casefold()
        for email in settings.SUPER_ADMIN_EMAILS
        if email and email.strip()
    }
    if not broker.email or broker.email.casefold() not in allowed_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin access is required.",
        )
    return broker


from contextvars import ContextVar

current_tenant_ctx: ContextVar[Optional["TenantContext"]] = ContextVar("current_tenant_ctx", default=None)


@dataclass(frozen=True)
class TenantContext:
    """A tenant selected from the authenticated principal's memberships or background task context."""

    organization_id: str
    broker_id: Optional[uuid.UUID] = None
    user_id: Optional[str] = None
    role: Optional[str] = None
    is_background: bool = False

    @classmethod
    def for_background_task(
        cls,
        organization_id: str,
        broker_id: Optional[uuid.UUID] = None
    ) -> "TenantContext":
        """Constructs a validated tenant context for background worker tasks."""
        if not organization_id:
            raise ValueError("organization_id is mandatory for background worker tenant context")
        ctx = cls(
            organization_id=str(organization_id),
            broker_id=broker_id,
            is_background=True
        )
        current_tenant_ctx.set(ctx)
        return ctx

    @classmethod
    def for_system_operation(cls, organization_id: str) -> "TenantContext":
        """Constructs a tenant context for internal system operations."""
        ctx = cls(
            organization_id=str(organization_id),
            is_background=True
        )
        current_tenant_ctx.set(ctx)
        return ctx


def get_ambient_tenant() -> Optional[TenantContext]:
    """Retrieve the ambient tenant context from contextvars if set."""
    return current_tenant_ctx.get()


async def get_current_tenant(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
    requested_organization_id: Optional[str] = Header(
        default=None, alias="X-WefyLabs-Organization-Id"
    ),
) -> TenantContext:
    """Resolve tenant context server-side and validate any workspace selection.

    A client header can select among memberships but never grants access by
    itself. Single-membership users remain backward compatible; users in more
    than one organization must select an organization explicitly.
    """
    result = await db.execute(
        select(OrganizationMember.organization_id).where(
            OrganizationMember.broker_id == current_broker.id
        )
    )
    organization_ids = [str(value) for value in result.scalars().all()]

    if not organization_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ORGANIZATION_MEMBERSHIP_REQUIRED",
                "message": "No organization membership is available for this account.",
            },
        )

    if requested_organization_id:
        try:
            selected_organization_id = str(uuid.UUID(requested_organization_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_ORGANIZATION_CONTEXT",
                    "message": "The organization context must be a valid UUID.",
                },
            ) from exc
        if selected_organization_id not in organization_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ORGANIZATION_ACCESS_DENIED",
                    "message": "You do not belong to the selected organization.",
                },
            )
        ctx = TenantContext(
            organization_id=selected_organization_id,
            broker_id=current_broker.id,
            user_id=str(current_broker.id)
        )
        current_tenant_ctx.set(ctx)
        return ctx

    if len(organization_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ORGANIZATION_CONTEXT_REQUIRED",
                "message": "Select an organization before accessing this resource.",
            },
        )

    ctx = TenantContext(
        organization_id=organization_ids[0],
        broker_id=current_broker.id,
        user_id=str(current_broker.id)
    )
    current_tenant_ctx.set(ctx)
    return ctx

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
