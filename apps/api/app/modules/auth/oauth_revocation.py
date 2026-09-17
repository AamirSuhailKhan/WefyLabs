"""
PART 24.1 — External Google OAuth Token Revocation
===================================================
Handles secure external token revocation against Google's OAuth 2.0 endpoint:
- Endpoint: https://oauth2.googleapis.com/revoke
- Non-blocking, fault-tolerant execution
- Idempotent handling (200 OK and 400 invalid_token treated as safe)
- Zero credential logging (access and refresh tokens are strictly unlogged)
- Safe fallback when Google servers are unreachable
"""
import logging
from typing import Tuple, Optional
import httpx

logger = logging.getLogger("beetlelabs.auth.oauth_revocation")

GOOGLE_REVOCATION_URL = "https://oauth2.googleapis.com/revoke"


def perform_google_token_revocation(token: Optional[str]) -> Tuple[bool, int, Optional[str]]:
    """
    Synchronously attempts to revoke a Google OAuth token.
    Safe against timeouts and network issues: never raises unhandled exceptions.
    Never logs raw tokens.
    
    Returns:
        (success: bool, status_code: int, error_message: Optional[str])
    """
    if not token or not token.strip():
        return True, 200, "No token provided"

    clean_token = token.strip()

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                GOOGLE_REVOCATION_URL,
                data={"token": clean_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

        if resp.status_code == 200:
            logger.info("[Google OAuth Revocation] Token revoked successfully at Google endpoint.")
            return True, 200, None

        # Google returns 400 with {"error": "invalid_token"} if already revoked
        if resp.status_code == 400:
            logger.info("[Google OAuth Revocation] Token was already revoked or expired at Google endpoint.")
            return True, 400, "Token was already revoked or expired"

        logger.warning(
            f"[Google OAuth Revocation] Google endpoint returned non-success status: {resp.status_code}"
        )
        return False, resp.status_code, f"Google returned HTTP {resp.status_code}"

    except httpx.TimeoutException:
        logger.warning("[Google OAuth Revocation] Google revocation endpoint timed out (5s limit).")
        return False, 504, "Google revocation endpoint timed out"
    except httpx.RequestError as req_err:
        logger.warning(f"[Google OAuth Revocation] Network error communicating with Google: {type(req_err).__name__}")
        return False, 503, f"Network error: {type(req_err).__name__}"
    except Exception as exc:
        logger.warning(f"[Google OAuth Revocation] Unexpected error during revocation: {type(exc).__name__}")
        return False, 500, f"Unexpected error: {type(exc).__name__}"
