"""
PART 24.1 — Team Member Invitation Router
========================================
Endpoints for:
- POST /organizations/invitations (Create organization invitation)
- GET /organizations/invitations (List organization invitations)
- DELETE /organizations/invitations/{invitation_id} (Revoke invitation)
- GET /invitations/verify (Verify invitation token - Public)
- POST /invitations/accept (Accept invitation & join team - Public / Authenticated)
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker, optional_security
from app.models.broker import Broker
from app.common.response import APIResponse, create_success_response
from app.modules.auth.invitation_service import InvitationService

router = APIRouter(tags=["Team Invitations"])


class CreateInvitationDTO(BaseModel):
    email: EmailStr
    role: str = Field(default="agent", description="Role to assign: admin | manager | agent")


class AcceptInvitationDTO(BaseModel):
    token: str = Field(..., min_length=10)
    password: Optional[str] = Field(None, min_length=8)
    name: Optional[str] = None
    phone: Optional[str] = None


@router.post("/organizations/invitations")
async def create_organization_invitation(
    dto: CreateInvitationDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Creates a time-bound, role-scoped team member invitation (requires owner or admin)."""
    base_url = str(request.base_url).rstrip("/")
    inv = await InvitationService.create_invitation(
        db=db,
        inviter=current_broker,
        email=dto.email,
        role=dto.role,
        frontend_base_url=base_url
    )
    return create_success_response(data=inv)


@router.get("/organizations/invitations")
async def list_organization_invitations(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Lists all team member invitations for current broker's organization."""
    items = await InvitationService.list_invitations(db=db, inviter=current_broker)
    return create_success_response(data=items)


@router.delete("/organizations/invitations/{invitation_id}")
async def revoke_organization_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Revokes an active team member invitation within caller's organization."""
    res = await InvitationService.revoke_invitation(
        db=db,
        inviter=current_broker,
        invitation_id=invitation_id
    )
    return create_success_response(data=res)


@router.get("/invitations/verify")
async def verify_invitation(
    token: str = Query(..., min_length=10),
    db: AsyncSession = Depends(get_db),
):
    """Public verification endpoint returning invitation and organization context."""
    res = await InvitationService.verify_invitation_token(db=db, token=token)
    return create_success_response(data=res)


@router.post("/invitations/accept")
async def accept_invitation(
    dto: AcceptInvitationDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts an organization invitation.
    Supports either an authenticated session via Bearer token or direct registration.
    """
    # Check if caller has an active bearer token
    current_broker = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token_str = auth_header.replace("Bearer ", "").strip()
        try:
            from app.modules.auth.service import decode_access_token
            payload = decode_access_token(token_str)
            broker_id = payload.get("broker_id") or payload.get("sub")
            if broker_id:
                current_broker = await db.get(Broker, UUID(broker_id))
        except Exception:
            pass

    reg_data = {
        "password": dto.password,
        "name": dto.name,
        "phone": dto.phone
    } if dto.password else None

    res = await InvitationService.accept_invitation(
        db=db,
        token=dto.token,
        current_broker=current_broker,
        registration_data=reg_data
    )
    return create_success_response(data=res)
