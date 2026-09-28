"""Canonical tenant isolation helpers.

Organization is the customer tenant. Broker/user is an actor inside a tenant.
Never treat organization_id == broker_id as a valid identity model.
"""
from __future__ import annotations

import uuid
from typing import Optional, Union

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

ALL_TENANTS_SENTINEL = "__all__"


class TenantIsolationError(HTTPException):
    def __init__(self, code: str, message: str, http_status: int = 403):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(
            status_code=http_status,
            detail={"code": code, "message": message},
        )

    def as_http(self) -> HTTPException:
        return self


def as_organization_uuid(value: Union[str, uuid.UUID, None]) -> Optional[uuid.UUID]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    text = str(value).strip()
    if not text or text == ALL_TENANTS_SENTINEL:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def reject_unbounded_tenant(tenant_id: Optional[str]) -> str:
    """Fail closed when a job would process every customer without a dispatcher."""
    if not tenant_id or tenant_id == ALL_TENANTS_SENTINEL:
        raise TenantIsolationError(
            "ORGANIZATION_CONTEXT_REQUIRED",
            "Background work must be scoped to a single organization_id.",
            http_status=409,
        )
    parsed = as_organization_uuid(tenant_id)
    if parsed is None:
        raise TenantIsolationError(
            "INVALID_ORGANIZATION_CONTEXT",
            "organization_id must be a valid UUID.",
            http_status=400,
        )
    return str(parsed)


def require_organization_id(organization_id: Union[str, uuid.UUID, None]) -> uuid.UUID:
    parsed = as_organization_uuid(organization_id)
    if parsed is None:
        raise TenantIsolationError(
            "ORGANIZATION_CONTEXT_REQUIRED",
            "Select an organization before accessing this resource.",
            http_status=409,
        )
    return parsed


async def resolve_organization_id_for_broker(
    db: AsyncSession,
    broker_id: uuid.UUID,
    requested_organization_id: Union[str, uuid.UUID, None] = None,
    allow_fallback: bool = True,
    explicit_org_id: Union[str, uuid.UUID, None] = None,
) -> Optional[uuid.UUID]:
    """Resolve tenant from memberships. Never guess the first org when multiple exist."""
    from app.dependencies import get_ambient_tenant
    from app.models.organization import OrganizationMember

    if requested_organization_id is None and explicit_org_id is not None:
        requested_organization_id = explicit_org_id

    ambient = get_ambient_tenant()
    if requested_organization_id is None and ambient is not None:
        requested_organization_id = ambient.organization_id

    result = await db.execute(
        select(OrganizationMember.organization_id).where(
            OrganizationMember.broker_id == broker_id
        )
    )
    memberships = [row for row in result.scalars().all()]
    membership_ids = {str(value) for value in memberships}

    if not membership_ids:
        if allow_fallback:
            return as_organization_uuid(requested_organization_id) or broker_id
        raise TenantIsolationError(
            "ORGANIZATION_MEMBERSHIP_REQUIRED",
            "No organization membership is available for this account.",
            http_status=403,
        )

    if requested_organization_id is not None:
        selected = as_organization_uuid(requested_organization_id)
        if selected is None:
            raise TenantIsolationError(
                "INVALID_ORGANIZATION_CONTEXT",
                "The organization context must be a valid UUID.",
                http_status=400,
            )
        if str(selected) not in membership_ids:
            raise TenantIsolationError(
                "ORGANIZATION_ACCESS_DENIED",
                "You do not belong to the selected organization.",
                http_status=403,
            )
        return selected

    if len(memberships) != 1:
        raise TenantIsolationError(
            "ORGANIZATION_CONTEXT_REQUIRED",
            "Select an organization before accessing this resource.",
            http_status=409,
        )
    return memberships[0]


def tenant_lead_filter(organization_id: uuid.UUID, broker_id: Optional[uuid.UUID] = None):
    """Dual-read: prefer canonical organization_id, fall back to broker-owned unmigrated rows."""
    from app.models.lead import Lead

    org_match = Lead.organization_id == organization_id
    if broker_id is None:
        return org_match
    legacy = and_(Lead.organization_id.is_(None), Lead.broker_id == broker_id)
    return or_(org_match, legacy)


def lead_belongs_to_tenant(lead, organization_id: uuid.UUID, broker_id: Optional[uuid.UUID] = None) -> bool:
    lead_org = as_organization_uuid(getattr(lead, "organization_id", None))
    if lead_org is not None:
        return lead_org == organization_id
    if broker_id is None:
        return False
    return getattr(lead, "broker_id", None) == broker_id


def property_belongs_to_tenant(listing, organization_id: uuid.UUID, broker_id: Optional[uuid.UUID] = None) -> bool:
    listing_org = as_organization_uuid(getattr(listing, "organization_id", None))
    if listing_org is not None:
        return listing_org == organization_id
    if broker_id is None:
        return False
    return getattr(listing, "broker_id", None) == broker_id
