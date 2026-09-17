"""
PART 24.1 — Account Deletion Service with External Google OAuth Revocation
==========================================================================
Coordinates secure broker account deletion:
- Identifies active Google OAuth connections (calendar accounts)
- Securely retrieves and decrypts stored tokens
- Attempts external Google OAuth revocation (with safe async Celery fallback)
- Safe error handling: never blocks local database deletion if Google is unavailable
- Zero credential logging
- Comprehensive database cleanup (calendar accounts, reset tokens, invitations, memberships, user, broker)
- Tenant isolation preservation
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.user import User
from app.models.calendar_models import CalendarAccount
from app.models.invitation_models import PasswordResetToken, OrganizationInvitation
from app.models.organization import OrganizationMember, Organization
from app.common.security.token_encryption import decrypt_token
from app.modules.auth.oauth_revocation import perform_google_token_revocation

logger = logging.getLogger("beetlelabs.auth.account_deletion")


class AccountDeletionService:
    @classmethod
    async def delete_broker_account(
        cls,
        db: AsyncSession,
        broker_id: UUID
    ) -> Dict[str, Any]:
        """
        Deletes broker account and associated entities.
        Safely revokes Google OAuth tokens if connected.
        """
        # Coerce broker_id to UUID
        if isinstance(broker_id, str):
            try:
                b_uuid = UUID(broker_id)
            except Exception:
                b_uuid = broker_id
        else:
            b_uuid = broker_id

        broker = await db.get(Broker, b_uuid)
        if not broker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found."
            )

        # 1. Identify and revoke external Google OAuth connections
        stmt_cal = select(CalendarAccount).where(CalendarAccount.broker_id == b_uuid)
        cal_res = await db.execute(stmt_cal)
        cal_accounts = cal_res.scalars().all()

        revocation_attempted = False
        revocation_success = False

        for cal_acc in cal_accounts:
            if (cal_acc.provider or "").upper() == "GOOGLE":
                revocation_attempted = True
                raw_token: Optional[str] = None
                try:
                    # Prefer refresh token for comprehensive revocation; fallback to access token
                    if cal_acc.encrypted_refresh_token:
                        raw_token = decrypt_token(cal_acc.encrypted_refresh_token)
                    elif cal_acc.encrypted_access_token:
                        raw_token = decrypt_token(cal_acc.encrypted_access_token)
                except Exception as dec_err:
                    logger.warning(
                        f"[Account Deletion] Token decryption failed for broker_id={broker_id}: {type(dec_err).__name__}"
                    )

                if raw_token:
                    # Attempt synchronous revocation with safe 5s timeout
                    succ, code, err = perform_google_token_revocation(raw_token)
                    revocation_success = succ
                    if not succ:
                        # Enqueue Celery retry task for resilience
                        try:
                            from app.tasks.queue_workers import revoke_google_oauth_token_task
                            revoke_google_oauth_token_task.delay(raw_token)
                            logger.info(f"[Account Deletion] Enqueued async Celery revocation fallback for broker_id={broker_id}")
                        except Exception as cel_err:
                            logger.warning(f"[Account Deletion] Celery queue unavailable: {cel_err}")
                else:
                    revocation_success = True

            # Remove calendar account record
            await db.delete(cal_acc)

        # 2. Clean up Password Reset Tokens
        await db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.broker_id == b_uuid)
        )

        # 3. Clean up Organization Invitations sent by this broker
        await db.execute(
            delete(OrganizationInvitation).where(OrganizationInvitation.invited_by_id == b_uuid)
        )

        # 4. Clean up Organization Membership
        await db.execute(
            delete(OrganizationMember).where(OrganizationMember.broker_id == b_uuid)
        )

        # 5. Clean up Synced User Model if present
        user = await db.get(User, b_uuid)
        if user:
            await db.delete(user)

        # 6. Delete Broker
        await db.delete(broker)

        # 7. Commit local transaction
        await db.commit()

        logger.info(
            f"[Account Deletion] Account deletion completed for broker_id={broker_id}. "
            f"Google revocation attempted={revocation_attempted}, success={revocation_success}"
        )

        return {
            "success": True,
            "message": "Account successfully deleted.",
            "google_revocation_attempted": revocation_attempted,
            "google_revocation_success": revocation_success
        }
