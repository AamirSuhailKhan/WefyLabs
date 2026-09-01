"""
JWT Token Security & Session Revocation Service
===============================================
Manages Short-lived Access Tokens, Refresh Token Rotation,
Device Fingerprint Binding, and JTI Blacklist Revocation.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_models import TokenBlacklist

logger = logging.getLogger(__name__)


class TokenSecurityService:
    """Enterprise Token Revocation & Device Binding Service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_token_revoked(self, jti: str) -> bool:
        """Checks if a JWT JTI has been revoked."""
        stmt = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def revoke_token(
        self, jti: str, user_id: str, expires_at: datetime, reason: str = "logout"
    ) -> bool:
        """Blacklists a JWT JTI to instantly terminate the session."""
        if await self.is_token_revoked(jti):
            return True

        blacklist_entry = TokenBlacklist(
            jti=jti,
            user_id=user_id,
            reason=reason,
            expires_at=expires_at,
        )
        self.db.add(blacklist_entry)
        await self.db.commit()
        logger.info(f"[TOKEN REVOKED] JTI={jti} for User={user_id} Reason={reason}")
        return True

    @staticmethod
    def verify_device_binding(token_device_hash: Optional[str], request_user_agent: str) -> bool:
        """Verifies if incoming request matches the device fingerprint bound to the token."""
        if not token_device_hash:
            return True
        import hashlib
        current_hash = hashlib.sha256(request_user_agent.encode()).hexdigest()[:16]
        return token_device_hash == current_hash
