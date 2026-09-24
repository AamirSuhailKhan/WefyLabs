"""
Part 21 — Customer Portal Security Dependencies
===============================================
Strict authorization boundary verifying that all customer requests derive their
identity from cryptographically signed JWTs, NEVER from client-supplied params.
"""
from __future__ import annotations

import uuid
import jwt
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.lead import Lead
from app.models.broker import Broker
from app.modules.portal.dto.portal_schemas import PortalCustomerContext

security = HTTPBearer()


async def get_current_portal_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> PortalCustomerContext:
    """
    Validates Customer Portal JWT from Authorization: Bearer <token> header.
    
    Guarantees:
    - Token must carry role == "portal_customer"
    - Lead must exist in the database and not be soft-deleted
    - organization_id is bound strictly to the server-side Lead record
    - Client-supplied tenant/customer IDs are ignored and untrusted
    """
    token = credentials.credentials
    auth_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or unauthorized customer portal credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256", "RS256"],
            options={"verify_aud": False, "verify_exp": True, "verify_iat": True}
        )
        
        # Verify role is specifically customer
        role = payload.get("role")
        if role != "portal_customer":
            raise auth_exception
            
        lead_id_raw = payload.get("sub") or payload.get("lead_id")
        if not lead_id_raw:
            raise auth_exception
            
        lead_uuid = uuid.UUID(str(lead_id_raw))
    except (jwt.PyJWTError, ValueError, TypeError):
        raise auth_exception

    # Query Lead from DB to verify customer is active and not deleted
    stmt = select(Lead).where(Lead.id == lead_uuid, Lead.deleted_at.is_(None))
    result = await db.execute(stmt)
    lead = result.scalars().first()
    
    if not lead:
        # Return 401 - do not leak whether lead exists
        raise auth_exception

    # Resolve organization_id strictly from the verified Lead and its Broker
    broker_res = await db.execute(select(Broker).where(Broker.id == lead.broker_id))
    broker = broker_res.scalars().first()
    if not broker:
        raise auth_exception

    org_id = broker.organization_id

    return PortalCustomerContext(
        lead_id=str(lead.id),
        organization_id=org_id,
        email=lead.email,
        name=lead.name or "Client",
        phone=lead.phone
    )
