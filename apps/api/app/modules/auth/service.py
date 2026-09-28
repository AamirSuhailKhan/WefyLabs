import hashlib
import os
from datetime import datetime, timezone, timedelta
import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.broker import Broker, default_trial_ends_at
from app.modules.auth.schemas import RegisterRequest

def hash_password(password: str) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}${key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verifies password against stored PBKDF2 hash."""
    if not hashed or '$' not in hashed:
        return False
    salt_hex, key_hex = hashed.split('$', 1)
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return new_key.hex() == key_hex

def create_access_token(data: dict | str | uuid.UUID, expires_delta: timedelta | None = None) -> str:
    if isinstance(data, (str, uuid.UUID)):
        to_encode = {"sub": str(data)}
    else:
        to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

import uuid
from app.models.user import User
from app.models.organization import Organization, OrganizationMember

async def register_broker(db: AsyncSession, req: RegisterRequest) -> Broker:
    # Check for duplicate email, phone, or whatsapp_number
    stmt = select(Broker).where(
        (Broker.email == req.email) | 
        (Broker.phone == req.phone) | 
        (Broker.whatsapp_number == req.whatsapp_number)
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        if existing.email == req.email:
            msg = "A broker with this email already exists."
        elif existing.phone == req.phone:
            msg = "A broker with this phone number already exists."
        else:
            msg = "A broker with this WhatsApp number already exists."
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=msg
        )

    broker = Broker(
        email=req.email,
        phone=req.phone,
        name=req.name,
        agency_name=req.agency_name,
        city=req.city or "Bengaluru",
        whatsapp_number=req.whatsapp_number,
        password_hash=hash_password(req.password),
        subscription_status="trial",
        trial_ends_at=default_trial_ends_at(),
        onboarding_status="ONBOARDED"
    )
    db.add(broker)
    await db.flush()

    # Create Organization & Member
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
        broker_id=broker.id,
        role="owner"
    )
    db.add(member)

    # Sync App User
    user = User(
        id=broker.id,
        email=broker.email,
        name=broker.name,
        phone=broker.phone,
        whatsapp_number=broker.whatsapp_number,
        organization_id=str(org.id),
        auth_provider="email",
        subscription_status="active"
    )
    db.add(user)

    await db.commit()
    await db.refresh(broker)
    return broker

async def authenticate_broker(db: AsyncSession, email: str, password: str) -> Broker:
    stmt = select(Broker).where(Broker.email == email)
    result = await db.execute(stmt)
    broker = result.scalars().first()

    if not broker or not broker.password_hash or not verify_password(password, broker.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    return broker

async def get_or_create_test_broker(db: AsyncSession, email: str, name: Optional[str] = None) -> Broker:
    """Test/development-only identity fixture.

    Phase 0 P0.1: this REPLACES the former caller-controlled OAuth identity
    path. It is invoked exclusively by the isolated ``/auth/test/identity``
    endpoint, which is compiled out of production builds. It must never be
    called from any production authentication flow.
    """
    if settings.ENV.lower() in ("production", "prod"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found."
        )
    stmt = select(Broker).where(Broker.email == email)
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        return existing
    new_broker = Broker(
        email=email,
        name=name or "Test Broker",
        subscription_status="trial",
        trial_ends_at=default_trial_ends_at(),
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db.add(new_broker)
    await db.commit()
    await db.refresh(new_broker)
    return new_broker

import secrets
import urllib.parse
import httpx

# Phase 0 P0.1: distributed OAuth state + replay protection (Redis, TTL-bound,
# one-time, session-bound). Replaces the former process-local _used_oauth_codes
# set which did not protect against replay across multiple workers.
from app.common.auth.oauth_state import (
    consume_authorization_code,
    issue_oauth_state,
    consume_oauth_state,
    OAuthStateError,
    OAuthStateMissing,
    OAuthStateReplayed,
    OAuthStateSessionMismatch,
    OAuthStateExpired,
)

# Kept as a deprecated alias so any stale import fails loudly at import time
# with a clear message instead of silently working.
def __getattr__(name: str):
    if name == "_used_oauth_codes":
        raise AttributeError(
            "_used_oauth_codes was removed in Phase 0 (P0.1). "
            "Authorization-code replay is now distributed via "
            "app.common.auth.oauth_state.consume_authorization_code()."
        )
    raise AttributeError(name)

def validate_google_client_id(client_id: Optional[str]) -> bool:
    """Validates that Google OAuth Client ID is well-formed and not a placeholder."""
    if not client_id or not isinstance(client_id, str):
        return False
    val = client_id.strip().strip("'\"").strip()
    if not val:
        return False
    lower_val = val.lower()
    placeholders = (
        "placeholder",
        "your_client_id",
        "your_google_client_id",
        "your_",
        "changeme",
        "<your",
        "todo",
        "dummy",
        "xxx"
    )
    if any(p in lower_val for p in placeholders):
        return False
    return lower_val.endswith(".apps.googleusercontent.com")

def generate_google_auth_url(
    redirect_uri: Optional[str] = None,
    session_id: str = "",
) -> tuple[str, str]:
    """Generates the real Google OAuth 2.0 authorization URL with CSRF state.

    Phase 0 P0.1: ``session_id`` is mandatory — the state is stored server-side
    and bound to the initiating browser session. Without a session the flow is
    refused instead of issuing an unbound state.
    """
    client_id = (settings.GOOGLE_CLIENT_ID or "").strip()

    # Phase 0 P0.1: server-generated, server-stored, session-bound one-time
    # state. The session id is supplied by the transport layer (router) so the
    # state is cryptographically bound to the initiating browser session.
    state = issue_oauth_state(session_id)
    target_redirect = redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI

    # In non-testing environments, reject unconfigured placeholder Client IDs gracefully
    if settings.ENV not in ("testing", "test") and not validate_google_client_id(client_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth 2.0 is not configured. Please set a valid GOOGLE_CLIENT_ID ending with '.apps.googleusercontent.com' and GOOGLE_CLIENT_SECRET in backend environment variables."
        )
    
    # Clean and validate redirect URI
    params = {
        "client_id": client_id,
        "redirect_uri": target_redirect,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account"
    }
    query_string = urllib.parse.urlencode(params)
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"
    return auth_url, state

async def exchange_google_oauth_code(
    db: AsyncSession,
    req: GoogleExchangeRequest,
    session_id: str = "",
) -> Broker:
    """
    Exchanges Google OAuth code for verified identity and securely resolves or links broker profile.
    Guarantees no duplicate account or organization creation on identity linking.

    Phase 0 P0.1: ``session_id`` is mandatory. The CSRF state returned by the
    caller is validated against the server-side store and consumed atomically.
    """
    session_id = (session_id or "").strip()
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth session context is required."
        )
    if not req.code or not req.code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code is required."
        )

    # ── Phase 0 P0.1: mock identity paths removed from production code ──
    # The previous implementation accepted caller-supplied email/name (or a
    # 'test_code_' prefix) as a verified Google identity: any caller could mint
    # a session for ANY email address. Test authentication is served exclusively
    # by the isolated test-only fixture endpoint (router, testing env only).
    if getattr(req, "email", None) or getattr(req, "name", None) or req.code.startswith("test_code_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Caller-supplied OAuth identity is not accepted. Use the verified Google OAuth flow."
        )

    # ── Phase 0 P0.1: distributed one-time replay protection ─────────────
    # Atomic Redis SET-NX with TTL, shared across all workers.
    try:
        consume_authorization_code(req.code)
    except OAuthStateReplayed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code has already been consumed or is invalid."
        )
    except OAuthStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OAuth replay protection unavailable: {exc}"
        )

    verified_email: Optional[str] = None
    verified_name: Optional[str] = None

    # Production Google Token & UserInfo Exchange
    try:
        target_redirect = req.redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": req.code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": target_redirect,
                    "grant_type": "authorization_code"
                }
            )
            if token_res.status_code != 200:
                err_json = {}
                try:
                    err_json = token_res.json()
                except Exception:
                    pass
                err_code = err_json.get("error", "")
                err_desc = err_json.get("error_description", "")
                
                if err_code == "invalid_client":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Google OAuth client authentication failed (invalid_client). Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
                    )
                elif err_code == "redirect_uri_mismatch":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Google OAuth redirect URI mismatch: '{target_redirect}' does not match authorized URIs in Google Cloud Console."
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Failed to authenticate with Google OAuth token service: {err_desc or err_code or token_res.status_code}"
                    )
            token_data = token_res.json()
            access_token = token_data.get("access_token")

            # Fetch verified userinfo
            userinfo_res = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_res.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to retrieve verified Google profile identity."
                )
            userinfo = userinfo_res.json()
            verified_email = userinfo.get("email")
            verified_name = userinfo.get("name") or "Google User"
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google OAuth provider communication error: {str(e)}"
        )

    if not verified_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account did not return a verified email address."
        )

    # ── Phase 0 P0.1: OAuth CSRF state validation (session-bound, one-time) ──
    # MUST be provided when the flow was initiated with server-side state.
    try:
        consume_oauth_state(req.state, session_id)
    except OAuthStateSessionMismatch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state does not belong to this session."
        )
    except OAuthStateReplayed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state has already been used."
        )
    except OAuthStateExpired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state has expired. Please restart sign-in."
        )
    except OAuthStateMissing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing, unknown, or invalid OAuth state."
        )
    except OAuthStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OAuth state validation unavailable: {exc}"
        )

    # Resolve existing broker for safe identity linking
    stmt = select(Broker).where(Broker.email == verified_email)
    existing = (await db.execute(stmt)).scalars().first()

    if existing:
        # Check suspension
        if existing.onboarding_status == "SUSPENDED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This broker account has been suspended."
            )
        # Update name if previously blank or generic
        if verified_name and (not existing.name or existing.name == "Google User"):
            existing.name = verified_name
        
        # Link user auth provider if synced User row exists
        stmt_user = select(User).where(User.id == existing.id)
        existing_user = (await db.execute(stmt_user)).scalars().first()
        if existing_user and existing_user.auth_provider != "google":
            existing_user.auth_provider = "google"

        await db.commit()
        await db.refresh(existing)
        return existing

    # Create new broker in AUTHENTICATED_NOT_ONBOARDED status (No fake data!)
    new_broker = Broker(
        email=verified_email,
        name=verified_name or "Google Broker",
        phone=None,
        whatsapp_number=None,
        agency_name=None,
        city=None,
        subscription_status="trial",
        trial_ends_at=default_trial_ends_at(),
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db.add(new_broker)
    await db.commit()
    await db.refresh(new_broker)
    return new_broker


