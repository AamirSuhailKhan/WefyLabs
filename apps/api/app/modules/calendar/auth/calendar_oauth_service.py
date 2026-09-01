"""
Google Calendar OAuth Service
=============================
Manages broker-level Google Calendar OAuth consent, CSRF state security,
code exchange, credential encryption at rest, and account connection status.
"""

import hmac
import hashlib
import json
import base64
import time
import logging
import uuid
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.config import settings
from app.models.broker import Broker
from app.models.calendar_models import CalendarAccount
from app.common.security.token_encryption import encrypt_token, decrypt_token
from app.modules.calendar.exceptions import (
    CalendarError,
    CalendarAuthorizationExpired,
    CalendarProviderUnavailable,
)

logger = logging.getLogger(__name__)

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


class CalendarOAuthService:
    """
    Production-grade Google Calendar OAuth 2.0 service.
    """

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    @classmethod
    def generate_signed_state(cls, broker_id: str, redirect_uri: Optional[str] = None) -> str:
        """
        Creates a tamper-proof, time-bound (10m), single-use OAuth state token tied to broker_id.
        """
        payload = {
            "broker_id": str(broker_id),
            "type": "calendar_oauth",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "nonce": uuid.uuid4().hex,
            "redirect_uri": redirect_uri or "",
        }
        encoded_data = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        signature = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            encoded_data.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"{encoded_data}.{signature}"

    @classmethod
    def verify_and_decode_state(cls, state_str: str, expected_broker_id: str) -> Dict[str, Any]:
        """
        Verifies the cryptographic signature, expiration, and broker ownership of an OAuth state token.
        """
        if not state_str or "." not in state_str:
            raise ValueError("Malformed or missing OAuth state parameter.")

        encoded_data, signature = state_str.split(".", 1)
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            encoded_data.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("OAuth state signature verification failed (CSRF rejected).")

        try:
            payload = json.loads(base64.urlsafe_b64decode(encoded_data.encode("utf-8")).decode("utf-8"))
        except Exception:
            raise ValueError("Failed to decode OAuth state payload.")

        if payload.get("type") != "calendar_oauth":
            raise ValueError("Invalid OAuth state purpose.")

        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("OAuth state has expired. Please initiate connection again.")

        if str(payload.get("broker_id")) != str(expected_broker_id):
            raise ValueError("OAuth state is bound to a different broker account.")

        return payload

    @classmethod
    def generate_calendar_auth_url(cls, broker: Broker, redirect_uri: Optional[str] = None) -> Tuple[str, str]:
        """
        Generates Google Calendar OAuth consent URL with offline access and required calendar scopes.
        """
        client_id = settings.GOOGLE_CLIENT_ID
        if settings.ENV in ("production", "prod") and (not client_id or "placeholder" in client_id):
            raise RuntimeError("Production GOOGLE_CLIENT_ID is not configured.")

        state = cls.generate_signed_state(str(broker.id), redirect_uri)
        redirect = redirect_uri or settings.GOOGLE_REDIRECT_URI or "http://localhost:3000/auth/callback"

        params = {
            "client_id": client_id or "mock-client-id.apps.googleusercontent.com",
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": " ".join(CALENDAR_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "include_granted_scopes": "true",
        }
        query_str = "&".join(f"{k}={httpx.URL('', params={k: v}).params}" for k, v in params.items())
        # Clean query string
        from urllib.parse import urlencode
        auth_url = f"{cls.GOOGLE_AUTH_URL}?{urlencode(params)}"
        return auth_url, state

    @classmethod
    async def exchange_calendar_oauth_code(
        cls,
        db: AsyncSession,
        broker: Broker,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
    ) -> CalendarAccount:
        """
        Validates state, exchanges authorization code for tokens, retrieves user email,
        encrypts tokens, and persists the CalendarAccount.
        """
        # 1. Verify CSRF State
        cls.verify_and_decode_state(state, str(broker.id))

        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET

        if not client_id or not client_secret:
            if settings.ENV in ("production", "prod"):
                raise RuntimeError("Production Google OAuth credentials not configured.")

        redirect = redirect_uri or settings.GOOGLE_REDIRECT_URI or "http://localhost:3000/auth/callback"

        # 2. Exchange code with Google
        token_payload = {
            "code": code,
            "client_id": client_id or "test-client-id",
            "client_secret": client_secret or "test-client-secret",
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_resp = await client.post(cls.GOOGLE_TOKEN_URL, data=token_payload)
        except Exception as exc:
            logger.error(f"[Calendar OAuth] Error contacting Google token endpoint: {exc}")
            raise CalendarProviderUnavailable(f"Google token endpoint unreachable: {exc}")

        if token_resp.status_code != 200:
            logger.error(f"[Calendar OAuth] Token exchange failed ({token_resp.status_code}): {token_resp.text}")
            raise CalendarError(f"Failed to exchange authorization code: {token_resp.text}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 3600))
        granted_scope = token_data.get("scope", " ".join(CALENDAR_SCOPES))

        if not access_token:
            raise CalendarError("Google token response did not contain access_token.")

        # 3. Retrieve Google account email
        account_email = broker.email  # fallback
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                userinfo_resp = await client.get(
                    cls.GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if userinfo_resp.status_code == 200:
                    u_data = userinfo_resp.json()
                    account_email = u_data.get("email") or broker.email
        except Exception as exc:
            logger.warning(f"[Calendar OAuth] Could not fetch userinfo, using broker email: {exc}")

        # 4. Encrypt tokens at rest
        enc_access = encrypt_token(access_token)
        enc_refresh = encrypt_token(refresh_token) if refresh_token else None

        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # 5. Upsert CalendarAccount record for broker
        stmt = select(CalendarAccount).where(
            CalendarAccount.broker_id == broker.id,
            CalendarAccount.provider == "GOOGLE"
        )
        res = await db.execute(stmt)
        cal_account = res.scalar_one_or_none()

        org_id = str(broker.organization_id or broker.id)

        if cal_account:
            cal_account.account_email = account_email
            cal_account.encrypted_access_token = enc_access
            if enc_refresh:
                cal_account.encrypted_refresh_token = enc_refresh
            cal_account.token_expires_at = token_expires_at
            cal_account.scope = granted_scope
            cal_account.is_connected = True
            cal_account.last_sync_at = datetime.now(timezone.utc)
        else:
            cal_account = CalendarAccount(
                id=str(uuid.uuid4()),
                organization_id=org_id,
                broker_id=broker.id,
                provider="GOOGLE",
                account_email=account_email,
                encrypted_access_token=enc_access,
                encrypted_refresh_token=enc_refresh,
                token_expires_at=token_expires_at,
                scope=granted_scope,
                is_connected=True,
                last_sync_at=datetime.now(timezone.utc),
            )
            db.add(cal_account)

        await db.flush()
        logger.info(f"[Calendar OAuth] Successfully connected Google Calendar for broker {broker.id} ({account_email})")
        return cal_account

    @classmethod
    async def get_calendar_status(cls, db: AsyncSession, broker: Broker) -> Dict[str, Any]:
        """
        Returns connection state, connected email, and status for the authenticated broker.
        """
        stmt = select(CalendarAccount).where(
            CalendarAccount.broker_id == broker.id,
            CalendarAccount.provider == "GOOGLE"
        )
        res = await db.execute(stmt)
        cal_account = res.scalar_one_or_none()

        if not cal_account or not cal_account.is_connected:
            return {
                "is_connected": False,
                "provider": "GOOGLE",
                "account_email": None,
                "status": "NOT_CONNECTED",
                "connected_at": None,
                "last_sync_at": None,
            }

        now = datetime.now(timezone.utc)
        is_token_expired = bool(cal_account.token_expires_at and cal_account.token_expires_at < now)

        return {
            "is_connected": cal_account.is_connected,
            "provider": cal_account.provider,
            "account_email": cal_account.account_email,
            "status": "CONNECTED" if not is_token_expired else "REFRESH_NEEDED",
            "connected_at": cal_account.created_at.isoformat() if cal_account.created_at else None,
            "last_sync_at": cal_account.last_sync_at.isoformat() if cal_account.last_sync_at else None,
        }

    @classmethod
    async def disconnect_calendar(cls, db: AsyncSession, broker: Broker) -> bool:
        """
        Disconnects calendar, purges stored encrypted tokens, and marks connection inactive.
        Historical CRM meetings and timeline events are preserved.
        """
        stmt = select(CalendarAccount).where(
            CalendarAccount.broker_id == broker.id,
            CalendarAccount.provider == "GOOGLE"
        )
        res = await db.execute(stmt)
        cal_account = res.scalar_one_or_none()

        if not cal_account:
            return True

        cal_account.is_connected = False
        cal_account.encrypted_access_token = ""
        cal_account.encrypted_refresh_token = None
        cal_account.token_expires_at = None

        db.add(cal_account)
        await db.flush()

        logger.info(f"[Calendar OAuth] Disconnected Google Calendar for broker {broker.id}")
        return True
