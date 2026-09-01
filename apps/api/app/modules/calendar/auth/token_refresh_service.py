"""
Token Refresh Service
=====================
Handles automated access-token refresh for external calendar connections.
Implements concurrency race protection to prevent duplicate refresh token exchanges.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.calendar_models import CalendarAccount
from app.common.security.token_encryption import encrypt_token, decrypt_token
from app.modules.calendar.exceptions import (
    CalendarAuthorizationExpired,
    CalendarProviderUnavailable,
    CalendarNotConnected
)

logger = logging.getLogger(__name__)

# In-memory lock registry per account ID to prevent concurrent refresh races within the process
_REFRESH_LOCKS: Dict[str, asyncio.Lock] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def _get_account_lock(account_id: str) -> asyncio.Lock:
    """Returns or creates an asyncio.Lock for the given account_id."""
    async with _REGISTRY_LOCK:
        if account_id not in _REFRESH_LOCKS:
            _REFRESH_LOCKS[account_id] = asyncio.Lock()
        return _REFRESH_LOCKS[account_id]


class TokenRefreshService:
    """
    Automated token refresh engine with race protection and encrypted storage.
    """

    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

    @classmethod
    async def get_valid_access_token(
        cls,
        db: AsyncSession,
        calendar_account: CalendarAccount,
        safety_buffer_seconds: int = 300
    ) -> str:
        """
        Retrieves a valid, unexpired access token for the given calendar account.
        Automatically performs refresh if token is within safety buffer of expiring.
        """
        if not calendar_account or not calendar_account.is_connected:
            raise CalendarNotConnected("Calendar account is not connected.")

        now = datetime.now(timezone.utc)

        # 1. Check if existing access token is still valid
        if calendar_account.token_expires_at and calendar_account.token_expires_at > (now + timedelta(seconds=safety_buffer_seconds)):
            token = decrypt_token(calendar_account.encrypted_access_token)
            if token:
                return token

        # 2. Acquire lock to prevent concurrent refresh token exchanges
        lock = await _get_account_lock(calendar_account.id)
        async with lock:
            # Re-check expiration in case another coroutine refreshed it while we were waiting
            if calendar_account.token_expires_at and calendar_account.token_expires_at > (now + timedelta(seconds=safety_buffer_seconds)):
                token = decrypt_token(calendar_account.encrypted_access_token)
                if token:
                    return token

            # 3. Decrypt refresh token
            refresh_token = decrypt_token(calendar_account.encrypted_refresh_token)
            if not refresh_token:
                logger.warning(f"[Calendar] No refresh token available for account {calendar_account.id}")
                calendar_account.is_connected = False
                db.add(calendar_account)
                await db.flush()
                raise CalendarAuthorizationExpired("No refresh token available. Reauthorization required.")

            # 4. Exchange refresh token with Google OAuth
            client_id = settings.GOOGLE_CLIENT_ID
            client_secret = settings.GOOGLE_CLIENT_SECRET

            if not client_id or not client_secret:
                if settings.ENV in ("production", "prod"):
                    raise RuntimeError("Production Google OAuth credentials missing.")
                # In test / dev with placeholder, return decrypted existing or mock token if not expired
                token = decrypt_token(calendar_account.encrypted_access_token)
                if token:
                    return token

            payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(cls.GOOGLE_TOKEN_URL, data=payload)
            except Exception as exc:
                logger.error(f"[Calendar] Token refresh network error for account {calendar_account.id}: {exc}")
                raise CalendarProviderUnavailable(f"Failed to connect to Google OAuth service: {exc}")

            if resp.status_code == 200:
                data = resp.json()
                new_access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))

                if not new_access_token:
                    raise CalendarAuthorizationExpired("Google token response omitted access_token.")

                # If Google rotated the refresh token, store the new one
                if "refresh_token" in data:
                    calendar_account.encrypted_refresh_token = encrypt_token(data["refresh_token"])

                calendar_account.encrypted_access_token = encrypt_token(new_access_token)
                calendar_account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                calendar_account.last_sync_at = datetime.now(timezone.utc)
                calendar_account.is_connected = True

                db.add(calendar_account)
                await db.flush()

                logger.info(f"[Calendar] Successfully refreshed access token for account {calendar_account.id}")
                return new_access_token

            elif resp.status_code in (400, 401):
                err_data = {}
                try:
                    err_data = resp.json()
                except Exception:
                    pass
                err_code = err_data.get("error", "invalid_grant")
                logger.warning(f"[Calendar] Refresh token rejected by Google ({err_code}) for account {calendar_account.id}")

                calendar_account.is_connected = False
                db.add(calendar_account)
                await db.flush()

                raise CalendarAuthorizationExpired(f"Google Calendar authorization expired: {err_code}. Reauthorization required.")
            else:
                logger.error(f"[Calendar] Google token endpoint returned HTTP {resp.status_code}")
                raise CalendarProviderUnavailable(f"Google token endpoint returned HTTP {resp.status_code}")
