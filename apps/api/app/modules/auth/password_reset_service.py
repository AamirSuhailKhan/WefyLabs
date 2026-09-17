"""
PART 24.1 — Self-Service Password Reset Service
===============================================
Secure token-based password reset workflow:
- Cryptographically secure single-use tokens (32 bytes urlsafe)
- SHA-256 token hashing in database (raw tokens never stored or logged)
- 15-minute expiration window
- Generic responses to eliminate user enumeration vectors
- Brevo SMTP integration via Celery queue worker
- Password complexity validation and synchronized broker/user update
"""
import secrets
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.broker import Broker
from app.models.user import User
from app.models.invitation_models import PasswordResetToken
from app.modules.auth.service import hash_password

logger = logging.getLogger("beetlelabs.auth.password_reset")

GENERIC_RESET_RESPONSE = {
    "message": "If this email address is registered, password reset instructions have been sent."
}


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class PasswordResetService:
    TOKEN_TTL_MINUTES = 15

    @classmethod
    def _hash_token(cls, raw_token: str) -> str:
        """Computes SHA-256 digest of raw token string."""
        return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

    @classmethod
    async def request_password_reset(
        cls,
        email: str,
        db: AsyncSession,
        frontend_base_url: Optional[str] = None
    ) -> dict:
        """
        Initiates password reset flow.
        Always returns generic response regardless of whether account exists.
        """
        normalized_email = email.strip().lower()
        if not normalized_email:
            return GENERIC_RESET_RESPONSE

        # Look up broker by email
        stmt = select(Broker).where(func.lower(Broker.email) == normalized_email)
        result = await db.execute(stmt)
        broker = result.scalars().first()

        if not broker:
            # Generic response to prevent account enumeration
            logger.info(f"[Password Reset] Request received for unregistered or unknown email.")
            return GENERIC_RESET_RESPONSE

        # Invalidate any prior unused reset tokens for this broker
        now = datetime.now(timezone.utc)
        await db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.broker_id == broker.id,
                PasswordResetToken.used_at.is_(None)
            )
            .values(used_at=now)
        )

        # Generate cryptographically secure token
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(raw_token)
        expires_at = now + timedelta(minutes=cls.TOKEN_TTL_MINUTES)

        # Persist token record
        reset_record = PasswordResetToken(
            broker_id=broker.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
        )
        db.add(reset_record)
        await db.commit()

        # Build reset link and asset URL
        base_url = (frontend_base_url or getattr(settings, "APP_URL", "http://localhost:3000")).rstrip("/")
        reset_link = f"{base_url}/reset-password?token={raw_token}"
        asset_url = getattr(settings, "ASSET_URL", None) or f"{base_url}/branding/wefylabs-mark.png"

        # Dispatch Brevo email via Celery async worker
        email_data = {
            "recipient": normalized_email,
            "subject": "Reset Your WefyLabs Account Password",
            "content": f"You requested a password reset for your WefyLabs account. Click here to reset your password: {reset_link}. This link expires in 15 minutes.",
            "html_content": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <img src="{asset_url}" alt="WefyLabs" width="120" style="width: 120px; max-width: 120px; height: auto; display: inline-block; border: 0;" />
                    </div>
                    <h2 style="color: #1a1a1a; margin-top: 0;">Password Reset Request</h2>
                    <p style="color: #4a4a4a; font-size: 15px; line-height: 1.5;">
                    We received a request to reset the password for your WefyLabs account (<strong>{normalized_email}</strong>).
                    Click the button below to choose a new password. This link is single-use and will expire in 15 minutes.
                    </p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" style="background-color: #0f172a; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Reset My Password</a>
                    </div>
                    <p style="color: #71717a; font-size: 13px;">
                    If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.
                    </p>
                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;" />
                    <p style="color: #a1a1aa; font-size: 12px; text-align: center;">
                    WefyLabs Autonomous Real Estate CRM &bull; Secure Authentication Service
                    </p>
                </div>
            """,
            "idempotency_key": f"reset:{broker.id}:{int(now.timestamp())}"
        }

        try:
            from app.tasks.queue_workers import process_email_dispatch
            process_email_dispatch.delay(email_data)
            logger.info(f"[Password Reset] Enqueued password reset email for broker_id={broker.id}")
        except Exception as e:
            logger.warning(f"[Password Reset] Celery dispatch unavailable or failed: {e}. Token created successfully.")

        return GENERIC_RESET_RESPONSE

    @classmethod
    async def verify_reset_token(
        cls,
        token: str,
        db: AsyncSession
    ) -> Tuple[bool, str, Optional[PasswordResetToken]]:
        """
        Validates token existence, expiration, and single-use status.
        """
        if not token or len(token.strip()) < 10:
            return False, "Invalid password reset token.", None

        token_hash = cls._hash_token(token)
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        result = await db.execute(stmt)
        token_record = result.scalars().first()

        if not token_record:
            return False, "Invalid or expired password reset token.", None

        if token_record.used_at is not None:
            return False, "Password reset token has already been used.", None

        now = datetime.now(timezone.utc)
        if _ensure_utc(token_record.expires_at) < now:
            return False, "Password reset token has expired.", None

        return True, "Token is valid.", token_record

    @classmethod
    async def execute_password_reset(
        cls,
        token: str,
        new_password: str,
        db: AsyncSession
    ) -> dict:
        """
        Validates password requirements, updates broker and synced user credentials,
        marks token as used, and invalidates any active sibling tokens.
        """
        # Validate password complexity
        clean_pwd = new_password.strip() if new_password else ""
        if len(clean_pwd) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long."
            )

        is_valid, error_msg, token_record = await cls.verify_reset_token(token, db)
        if not is_valid or not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        now = datetime.now(timezone.utc)
        # Mark token as used
        token_record.used_at = now

        # Update broker password hash
        new_hash = hash_password(clean_pwd)
        broker = await db.get(Broker, token_record.broker_id)
        if not broker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated broker account not found."
            )

        broker.password_hash = new_hash
        broker.updated_at = now

        # Synchronize User model if present
        user = await db.get(User, token_record.broker_id)
        if user:
            user.password_hash = new_hash
            user.updated_at = now

        # Invalidate any remaining tokens for this broker
        await db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.broker_id == broker.id,
                PasswordResetToken.used_at.is_(None)
            )
            .values(used_at=now)
        )

        await db.commit()
        logger.info(f"[Password Reset] Successfully reset password for broker_id={broker.id}")

        return {
            "success": True,
            "message": "Password has been successfully reset. You can now log in with your new password."
        }
