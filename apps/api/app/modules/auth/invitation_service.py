"""
PART 24.1 — Team Member Email Invitation Service
=================================================
Enterprise team member invitation lifecycle:
- Cryptographically secure single-use tokens (32 bytes urlsafe)
- SHA-256 token hashing in database
- 7-day expiration window
- Strict RBAC enforcement (owner/admin permission: organization:manage)
- Organization isolation and member role validation
- Safe duplicate invitation handling
- Single-use validation upon acceptance
- Integrated with Brevo email dispatch via Celery
"""
import secrets
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.broker import Broker
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.models.invitation_models import OrganizationInvitation
from app.services.rbac_service import RBACPermissionEvaluator
from app.modules.auth.service import hash_password, verify_password, create_access_token

logger = logging.getLogger("beetlelabs.auth.invitations")

ALLOWED_ROLES = {"admin", "manager", "agent"}


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class InvitationService:
    TOKEN_TTL_DAYS = 7

    @classmethod
    def _hash_token(cls, raw_token: str) -> str:
        return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

    @classmethod
    async def _resolve_organization_id(cls, db: AsyncSession, broker: Broker) -> UUID:
        """Determines the effective organization ID for a broker."""
        b_id = UUID(str(broker.id)) if not isinstance(broker.id, UUID) else broker.id
        stmt = select(OrganizationMember).where(OrganizationMember.broker_id == b_id)
        result = await db.execute(stmt)
        member = result.scalars().first()
        if member:
            return UUID(str(member.organization_id)) if not isinstance(member.organization_id, UUID) else member.organization_id

        # Check if an organization exists with ID == broker.id (legacy solo tenant)
        org = await db.get(Organization, b_id)
        if org:
            return org.id

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Broker does not belong to any organization."
        )

    @classmethod
    async def create_invitation(
        cls,
        db: AsyncSession,
        inviter: Broker,
        email: str,
        role: str,
        frontend_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an organization-scoped team member invitation.
        Enforces organization:manage RBAC permission.
        Safely revokes any existing active pending invitation for this email.
        """
        org_id = await cls._resolve_organization_id(db, inviter)

        # Enforce RBAC permission
        await RBACPermissionEvaluator.enforce_permission(
            db=db,
            broker=inviter,
            required_permission="organization:manage",
            organization_id=org_id
        )

        # Validate role
        clean_role = (role or "").strip().lower()
        if clean_role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invitation role '{role}'. Allowed roles: {sorted(list(ALLOWED_ROLES))}."
            )

        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid email address is required."
            )

        # Check if already a member of this organization
        stmt_existing = (
            select(OrganizationMember)
            .join(Broker, Broker.id == OrganizationMember.broker_id)
            .where(
                OrganizationMember.organization_id == org_id,
                func.lower(Broker.email) == clean_email
            )
        )
        res_existing = await db.execute(stmt_existing)
        if res_existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an active member of this organization."
            )

        now = datetime.now(timezone.utc)

        # Handle duplicate active invitations safely: revoke previous pending
        await db.execute(
            update(OrganizationInvitation)
            .where(
                OrganizationInvitation.organization_id == org_id,
                OrganizationInvitation.email == clean_email,
                OrganizationInvitation.status == "pending"
            )
            .values(status="revoked", updated_at=now)
        )

        # Generate secure random token
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(raw_token)
        expires_at = now + timedelta(days=cls.TOKEN_TTL_DAYS)

        invitation = OrganizationInvitation(
            organization_id=org_id,
            invited_by_id=inviter.id,
            email=clean_email,
            role=clean_role,
            token_hash=token_hash,
            expires_at=expires_at,
            status="pending"
        )
        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)

        # Retrieve organization name
        org = await db.get(Organization, org_id)
        org_name = org.name if org else "WefyLabs Agency"

        # Construct invitation link and asset URL
        base_url = (frontend_base_url or getattr(settings, "APP_URL", "http://localhost:3000")).rstrip("/")
        invite_link = f"{base_url}/invite/accept?token={raw_token}"
        asset_url = getattr(settings, "ASSET_URL", None) or f"{base_url}/branding/wefylabs-mark.png"

        # Dispatch invitation email via Celery async worker
        email_data = {
            "recipient": clean_email,
            "subject": f"You're invited to join {org_name} on WefyLabs",
            "content": f"You have been invited to join {org_name} as a {clean_role.capitalize()}. Accept your invitation: {invite_link}",
            "html_content": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1A1A1A;">
                <div style="text-align: center; margin-bottom: 24px;">
                    <img src="{asset_url}" alt="WefyLabs" width="120" style="width: 120px; max-width: 120px; height: auto; display: inline-block; border: 0;" />
                </div>
                <h2 style="color: #1A1A1A; margin-bottom: 16px; margin-top: 0;">Team Invitation</h2>
                <p style="font-size: 15px; line-height: 1.6; color: #4A4A4A;">
                    <strong>{inviter.name or 'A team administrator'}</strong> has invited you to join <strong>{org_name}</strong> on WefyLabs as a <strong>{clean_role.capitalize()}</strong>.
                </p>
                <div style="margin: 28px 0;">
                    <a href="{invite_link}" style="background-color: #1A1A1A; color: #FFFFFF; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                        Accept Invitation &amp; Join Team
                    </a>
                </div>
                <p style="font-size: 13px; color: #6B6B6B; line-height: 1.5;">
                    This invitation link expires in 7 days. If you were not expecting this invitation, you can ignore this email.
                </p>
                <hr style="border: none; border-top: 1px solid #E8E4DE; margin: 24px 0;" />
                <p style="font-size: 11px; color: #A0A0A0;">
                    WefyLabs Autonomous Real Estate CRM &bull; Organization Access Control
                </p>
            </div>
            """,
            "idempotency_key": f"invite:{invitation.id}:{int(now.timestamp())}"
        }

        try:
            from app.tasks.queue_workers import process_email_dispatch
            process_email_dispatch.delay(email_data)
            logger.info(f"[Team Invitation] Enqueued invitation email for {clean_email} to org={org_id}")
        except Exception as e:
            logger.warning(f"[Team Invitation] Celery dispatch unavailable: {e}. Invitation record created.")

        return {
            "id": str(invitation.id),
            "email": invitation.email,
            "role": invitation.role,
            "status": invitation.status,
            "organization_id": str(invitation.organization_id),
            "organization_name": org_name,
            "expires_at": invitation.expires_at.isoformat(),
            "created_at": invitation.created_at.isoformat(),
        }

    @classmethod
    async def list_invitations(
        cls,
        db: AsyncSession,
        inviter: Broker
    ) -> List[Dict[str, Any]]:
        """Lists all invitations for the inviter's organization."""
        org_id = await cls._resolve_organization_id(db, inviter)
        await RBACPermissionEvaluator.enforce_permission(
            db=db,
            broker=inviter,
            required_permission="organization:manage",
            organization_id=org_id
        )

        now = datetime.now(timezone.utc)
        stmt = (
            select(OrganizationInvitation)
            .where(OrganizationInvitation.organization_id == org_id)
            .order_by(OrganizationInvitation.created_at.desc())
        )
        result = await db.execute(stmt)
        invitations = result.scalars().all()

        output = []
        for inv in invitations:
            current_status = inv.status
            if current_status == "pending" and _ensure_utc(inv.expires_at) < now:
                current_status = "expired"

            output.append({
                "id": str(inv.id),
                "email": inv.email,
                "role": inv.role,
                "status": current_status,
                "expires_at": inv.expires_at.isoformat(),
                "created_at": inv.created_at.isoformat(),
                "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
            })
        return output

    @classmethod
    async def revoke_invitation(
        cls,
        db: AsyncSession,
        inviter: Broker,
        invitation_id: UUID
    ) -> Dict[str, Any]:
        """Revokes an active invitation within tenant boundaries."""
        org_id = await cls._resolve_organization_id(db, inviter)
        await RBACPermissionEvaluator.enforce_permission(
            db=db,
            broker=inviter,
            required_permission="organization:manage",
            organization_id=org_id
        )

        stmt = select(OrganizationInvitation).where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == org_id
        )
        res = await db.execute(stmt)
        inv = res.scalars().first()

        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found within your organization."
            )

        if inv.status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revoke an already accepted invitation."
            )

        inv.status = "revoked"
        inv.updated_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(f"[Team Invitation] Revoked invitation {invitation_id} by broker={inviter.id}")
        return {"success": True, "message": "Invitation successfully revoked."}

    @classmethod
    async def verify_invitation_token(
        cls,
        db: AsyncSession,
        token: str
    ) -> Dict[str, Any]:
        """Validates token and returns invitation context without mutating state."""
        if not token or len(token.strip()) < 10:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation token.")

        token_hash = cls._hash_token(token)
        stmt = select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash)
        res = await db.execute(stmt)
        inv = res.scalars().first()

        if not inv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation token not found.")

        if inv.status == "revoked":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has been revoked.")

        if inv.status == "accepted":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been accepted.")

        now = datetime.now(timezone.utc)
        if _ensure_utc(inv.expires_at) < now:
            inv.status = "expired"
            await db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired.")

        org = await db.get(Organization, inv.organization_id)
        org_name = org.name if org else "WefyLabs Agency"

        return {
            "valid": True,
            "email": inv.email,
            "role": inv.role,
            "organization_id": str(inv.organization_id),
            "organization_name": org_name,
            "expires_at": inv.expires_at.isoformat()
        }

    @classmethod
    async def accept_invitation(
        cls,
        db: AsyncSession,
        token: str,
        current_broker: Optional[Broker] = None,
        registration_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Accepts invitation:
        - For authenticated user: associates user with organization and role.
        - For unauthenticated user: registers/authenticates and associates with organization.
        """
        if not token or len(token.strip()) < 10:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation token.")

        token_hash = cls._hash_token(token)
        stmt = select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash)
        res = await db.execute(stmt)
        inv = res.scalars().first()

        if not inv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation token not found.")

        if inv.status == "revoked":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has been revoked.")

        if inv.status == "accepted":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been accepted.")

        now = datetime.now(timezone.utc)
        if _ensure_utc(inv.expires_at) < now:
            inv.status = "expired"
            await db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired.")

        # Flow A: Authenticated Broker is accepting
        if current_broker:
            # Check existing member record
            stmt_mem = select(OrganizationMember).where(
                OrganizationMember.organization_id == inv.organization_id,
                OrganizationMember.broker_id == current_broker.id
            )
            existing_mem = (await db.execute(stmt_mem)).scalars().first()
            if not existing_mem:
                new_mem = OrganizationMember(
                    organization_id=inv.organization_id,
                    broker_id=current_broker.id,
                    role=inv.role
                )
                db.add(new_mem)
            else:
                existing_mem.role = inv.role

            if hasattr(current_broker, "organization_id") and not getattr(current_broker, "organization_id", None):
                setattr(current_broker, "organization_id", inv.organization_id)

            inv.status = "accepted"
            inv.accepted_at = now
            await db.commit()

            return {
                "success": True,
                "message": "Invitation successfully accepted. You are now a team member.",
                "organization_id": str(inv.organization_id),
                "role": inv.role
            }

        # Flow B: Public / Unauthenticated Recipient accepting with credentials
        if not registration_data or not registration_data.get("password"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required to accept invitation and create your account."
            )

        password = registration_data["password"]
        name = registration_data.get("name") or inv.email.split("@")[0].capitalize()
        phone = registration_data.get("phone") or f"+919{secrets.randbelow(899999999) + 100000000}"

        # Check if broker exists with this email
        stmt_b = select(Broker).where(func.lower(Broker.email) == inv.email.lower())
        broker = (await db.execute(stmt_b)).scalars().first()

        if broker:
            # Verify password for existing account
            if not verify_password(password, broker.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="An account with this email already exists. Please verify your password to accept."
                )
        else:
            # Create new Broker
            broker = Broker(
                id=uuid.uuid4(),
                email=inv.email.lower(),
                password_hash=hash_password(password),
                name=name,
                phone=phone,
                whatsapp_number=phone,
                onboarding_status="ONBOARDED"
            )
            db.add(broker)
            await db.flush()

            # Synchronize User model
            user = User(
                id=broker.id,
                email=broker.email,
                password_hash=broker.password_hash,
                name=broker.name,
                phone=broker.phone,
                organization_id=str(inv.organization_id)
            )
            db.add(user)

        # Create or update organization member
        stmt_mem = select(OrganizationMember).where(
            OrganizationMember.organization_id == inv.organization_id,
            OrganizationMember.broker_id == broker.id
        )
        existing_mem = (await db.execute(stmt_mem)).scalars().first()
        if not existing_mem:
            new_mem = OrganizationMember(
                organization_id=inv.organization_id,
                broker_id=broker.id,
                role=inv.role
            )
            db.add(new_mem)
        else:
            existing_mem.role = inv.role

        inv.status = "accepted"
        inv.accepted_at = now
        await db.commit()

        # Issue access token
        access_token = create_access_token(data={
            "sub": str(broker.id),
            "broker_id": str(broker.id),
            "email": broker.email,
            "organization_id": str(inv.organization_id)
        })

        return {
            "success": True,
            "role": inv.role,
            "access_token": access_token,
            "token_type": "bearer",
            "broker": {
                "id": str(broker.id),
                "email": broker.email,
                "name": broker.name,
                "role": inv.role,
                "organization_id": str(inv.organization_id)
            }
        }
