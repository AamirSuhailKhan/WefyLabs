"""
WefyLabs Enterprise RBAC & Fine-Grained Permission Engine
=========================================================
Build 11 Architecture:
- 10 Canonical Roles:
  OWNER, ADMIN, MANAGER, SALES, AGENT, MARKETING, FINANCE, ANALYST, SUPPORT, READ_ONLY
- Granular permissions supporting both dot-notation (e.g. 'lead.read', 'property.write')
  and colon-notation (e.g. 'leads:read', 'deals:create') with bidirectional aliasing.
- Fail-Closed Tenancy: No membership or unknown role = ZERO permissions.
- Privilege Escalation Defense: Server-side evaluation against tenant organization membership.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import List, Optional, Set, Callable
from fastapi import HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.broker import Broker
from app.models.organization import OrganizationMember


class RoleEnum(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    SALES = "SALES"
    AGENT = "AGENT"
    MARKETING = "MARKETING"
    FINANCE = "FINANCE"
    ANALYST = "ANALYST"
    SUPPORT = "SUPPORT"
    READ_ONLY = "READ_ONLY"


class PermissionEnum(str, Enum):
    # Leads
    LEAD_READ = "lead.read"
    LEAD_WRITE = "lead.write"
    LEAD_EXPORT = "lead.export"
    LEAD_DELETE = "lead.delete"
    # Conversations
    CONVERSATION_READ = "conversation.read"
    CONVERSATION_SEND = "conversation.send"
    # Properties
    PROPERTY_READ = "property.read"
    PROPERTY_WRITE = "property.write"
    PROPERTY_DELETE = "property.delete"
    # Opportunities / Deals
    OPPORTUNITY_READ = "opportunity.read"
    OPPORTUNITY_WRITE = "opportunity.write"
    OPPORTUNITY_DELETE = "opportunity.delete"
    # Bookings
    BOOKING_READ = "booking.read"
    BOOKING_CREATE = "booking.create"
    BOOKING_UPDATE = "booking.update"
    # Financials & Payments
    PAYMENT_READ = "payment.read"
    PAYMENT_WRITE = "payment.write"
    REVENUE_READ = "revenue.read"
    REVENUE_EXPORT = "revenue.export"
    # AI & Automation
    AI_USE = "ai.use"
    AI_EXECUTE = "ai.execute"
    WORKFLOW_MANAGE = "workflow.manage"
    INTEGRATION_MANAGE = "integration.manage"
    ORGANIZATION_MANAGE = "organization.manage"
    AUDIT_READ = "audit.read"


# Symmetric permission aliases between dot-notation and legacy/colon-notation
_PERMISSION_ALIASES: dict[str, set[str]] = {
    "lead.read": {"lead.read", "leads:read"},
    "leads:read": {"lead.read", "leads:read"},
    "lead.write": {"lead.write", "leads:create", "leads:update"},
    "leads:create": {"lead.write", "leads:create"},
    "leads:update": {"lead.write", "leads:update"},
    "lead.delete": {"lead.delete", "leads:delete"},
    "leads:delete": {"lead.delete", "leads:delete"},
    "lead.export": {"lead.export", "leads:export"},
    "leads:export": {"lead.export", "leads:export"},

    "conversation.read": {"conversation.read", "conversations:read"},
    "conversations:read": {"conversation.read", "conversations:read"},
    "conversation.send": {"conversation.send", "conversations:send"},
    "conversations:send": {"conversation.send", "conversations:send"},

    "property.read": {"property.read", "properties:read"},
    "properties:read": {"property.read", "properties:read"},
    "property.write": {"property.write", "properties:create", "properties:update"},
    "properties:create": {"property.write", "properties:create"},
    "properties:update": {"property.write", "properties:update"},
    "property.delete": {"property.delete", "properties:delete"},
    "properties:delete": {"property.delete", "properties:delete"},

    "opportunity.read": {"opportunity.read", "deals:read"},
    "deals:read": {"opportunity.read", "deals:read"},
    "opportunity.write": {"opportunity.write", "deals:create", "deals:update"},
    "deals:create": {"opportunity.write", "deals:create"},
    "deals:update": {"opportunity.write", "deals:update"},
    "opportunity.delete": {"opportunity.delete", "deals:delete"},
    "deals:delete": {"opportunity.delete", "deals:delete"},

    "booking.read": {"booking.read", "bookings:read"},
    "bookings:read": {"booking.read", "bookings:read"},
    "booking.create": {"booking.create", "bookings:create"},
    "bookings:create": {"booking.create", "bookings:create"},
    "booking.update": {"booking.update", "bookings:update"},
    "bookings:update": {"booking.update", "bookings:update"},

    "payment.read": {"payment.read", "billing:read"},
    "billing:read": {"payment.read", "billing:read"},
    "payment.write": {"payment.write", "billing:manage"},
    "billing:manage": {"payment.write", "billing:manage"},

    "revenue.read": {"revenue.read", "revenue:read"},
    "revenue:read": {"revenue.read", "revenue:read"},
    "revenue.export": {"revenue.export", "revenue:export"},
    "revenue:export": {"revenue.export", "revenue:export"},

    "ai.use": {"ai.use", "ai:use"},
    "ai:use": {"ai.use", "ai:use"},
    "ai.execute": {"ai.execute", "ai:manage"},
    "ai:manage": {"ai.execute", "ai:manage"},

    "workflow.manage": {"workflow.manage", "workflows:manage"},
    "workflows:manage": {"workflow.manage", "workflows:manage"},
    "integration.manage": {"integration.manage", "integrations:manage"},
    "integrations:manage": {"integration.manage", "integrations:manage"},
    "organization.manage": {"organization.manage", "organization:manage"},
    "organization:manage": {"organization.manage", "organization:manage"},

    "audit.read": {"audit.read", "audit:view"},
    "audit:view": {"audit.read", "audit:view"},
}


# Canonical role permission definitions (containing both dot & colon notation for complete safety)
ROLE_PERMISSIONS: dict[str, list[str]] = {
    RoleEnum.OWNER.value: [
        "*",
        "lead.read", "lead.write", "lead.delete", "lead.export",
        "leads:create", "leads:read", "leads:update", "leads:delete", "leads:export",
        "conversation.read", "conversation.send", "conversations:read", "conversations:send",
        "property.read", "property.write", "property.delete",
        "properties:create", "properties:read", "properties:update", "properties:delete",
        "opportunity.read", "opportunity.write", "opportunity.delete",
        "deals:create", "deals:read", "deals:update", "deals:delete",
        "booking.read", "booking.create", "booking.update",
        "bookings:create", "bookings:read", "bookings:update",
        "payment.read", "payment.write", "billing:read", "billing:manage",
        "revenue.read", "revenue.export", "revenue:read", "revenue:export",
        "ai.use", "ai.execute", "ai:use", "ai:manage",
        "workflow.manage", "workflows:manage",
        "integration.manage", "integrations:manage",
        "organization.manage", "organization:manage",
        "audit.read", "audit:view"
    ],
    RoleEnum.ADMIN.value: [
        "lead.read", "lead.write", "lead.delete", "lead.export",
        "leads:create", "leads:read", "leads:update", "leads:delete", "leads:export",
        "conversation.read", "conversation.send", "conversations:read", "conversations:send",
        "property.read", "property.write", "property.delete",
        "properties:create", "properties:read", "properties:update", "properties:delete",
        "opportunity.read", "opportunity.write", "opportunity.delete",
        "deals:create", "deals:read", "deals:update", "deals:delete",
        "booking.read", "booking.create", "booking.update",
        "bookings:create", "bookings:read", "bookings:update",
        "payment.read", "payment.write", "billing:read", "billing:manage",
        "revenue.read", "revenue.export", "revenue:read", "revenue:export",
        "ai.use", "ai.execute", "ai:use", "ai:manage",
        "workflow.manage", "workflows:manage",
        "integration.manage", "integrations:manage",
        "organization.manage", "organization:manage",
        "audit.read", "audit:view"
    ],
    RoleEnum.MANAGER.value: [
        "lead.read", "lead.write",
        "leads:create", "leads:read", "leads:update",
        "conversation.read", "conversation.send", "conversations:read", "conversations:send",
        "property.read", "property.write",
        "properties:create", "properties:read", "properties:update",
        "opportunity.read", "opportunity.write",
        "deals:create", "deals:read", "deals:update",
        "booking.read", "booking.create", "booking.update",
        "bookings:create", "bookings:read", "bookings:update",
        "revenue.read", "revenue:read",
        "ai.use", "ai.execute", "ai:use",
        "audit.read", "audit:view"
    ],
    RoleEnum.SALES.value: [
        "lead.read", "lead.write",
        "leads:create", "leads:read", "leads:update",
        "conversation.read", "conversation.send", "conversations:read", "conversations:send",
        "property.read", "properties:read",
        "opportunity.read", "opportunity.write",
        "deals:create", "deals:read", "deals:update",
        "booking.read", "booking.create",
        "bookings:create", "bookings:read",
        "ai.use", "ai:use"
    ],
    RoleEnum.AGENT.value: [
        "lead.read", "lead.write",
        "leads:create", "leads:read", "leads:update",
        "conversation.read", "conversation.send", "conversations:read", "conversations:send",
        "property.read", "properties:read",
        "opportunity.read", "opportunity.write",
        "deals:create", "deals:read", "deals:update",
        "booking.read", "booking.create",
        "bookings:create", "bookings:read",
        "ai.use", "ai:use"
    ],
    RoleEnum.MARKETING.value: [
        "lead.read", "lead.write",
        "leads:read", "leads:create", "leads:update",
        "conversation.read", "conversation.send", "conversations:read", "conversations:send",
        "property.read", "properties:read",
        "ai.use", "ai:use"
    ],
    RoleEnum.FINANCE.value: [
        "payment.read", "payment.write", "billing:read", "billing:manage",
        "revenue.read", "revenue.export", "revenue:read", "revenue:export",
        "booking.read", "bookings:read", "booking.update", "bookings:update",
        "opportunity.read", "deals:read",
        "audit.read", "audit:view"
    ],
    RoleEnum.ANALYST.value: [
        "lead.read", "leads:read",
        "property.read", "properties:read",
        "opportunity.read", "deals:read",
        "booking.read", "bookings:read",
        "revenue.read", "revenue.export", "revenue:read", "revenue:export",
        "audit.read", "audit:view"
    ],
    RoleEnum.SUPPORT.value: [
        "lead.read", "leads:read",
        "conversation.read", "conversation.send", "conversations:read", "conversations:send",
        "property.read", "properties:read",
        "booking.read", "bookings:read"
    ],
    RoleEnum.READ_ONLY.value: [
        "lead.read", "leads:read",
        "property.read", "properties:read",
        "opportunity.read", "deals:read",
        "booking.read", "bookings:read",
        "revenue.read", "revenue:read"
    ]
}


class RBACPermissionEvaluator:
    """
    Database-Driven RBAC Permission Evaluator.
    Evaluates granular permission codes against database roles.
    Zero-trust boundary: unassigned, unrecognized, or missing membership fails closed.
    """

    @classmethod
    def matches_permission(cls, user_permissions: List[str], required_permission: str) -> bool:
        """Evaluates whether user has the permission directly, via wildcard, or via alias."""
        if "*" in user_permissions:
            return True
        if required_permission in user_permissions:
            return True
        aliases = _PERMISSION_ALIASES.get(required_permission, {required_permission})
        return any(alias in user_permissions for alias in aliases)

    @classmethod
    async def get_user_permissions(
        cls,
        db: AsyncSession,
        broker_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None
    ) -> List[str]:
        """Retrieves list of active permission codes for a broker within an organization."""
        b_id = uuid.UUID(str(broker_id)) if not isinstance(broker_id, uuid.UUID) else broker_id
        stmt = select(OrganizationMember).where(OrganizationMember.broker_id == b_id)
        if organization_id:
            org_id = uuid.UUID(str(organization_id)) if not isinstance(organization_id, uuid.UUID) else organization_id
            stmt = stmt.where(OrganizationMember.organization_id == org_id)

        res = await db.execute(stmt)
        member = res.scalars().first()

        # Fail-closed: unenrolled broker has zero permissions
        if member is None:
            return []

        role_name = (member.role or "").strip().upper()
        return ROLE_PERMISSIONS.get(role_name, [])

    @classmethod
    async def enforce_permission(
        cls,
        db: AsyncSession,
        broker: Broker,
        required_permission: str,
        organization_id: Optional[uuid.UUID] = None
    ) -> bool:
        """Enforces that authenticated broker possesses required permission code."""
        user_permissions = await cls.get_user_permissions(db, broker.id, organization_id)
        if not cls.matches_permission(user_permissions, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Required permission '{required_permission}' is missing for role."
            )
        return True


def require_permission(*required_permissions: str) -> Callable:
    """
    FastAPI dependency factory enforcing that current broker has required permission(s)
    within the active tenant context.
    """
    from app.dependencies import get_current_tenant, TenantContext, get_current_broker

    async def _dependency(
        tenant: TenantContext = Depends(get_current_tenant),
        db: AsyncSession = Depends(get_db),
        broker: Broker = Depends(get_current_broker),
    ) -> TenantContext:
        org_id = uuid.UUID(tenant.organization_id)
        perms = await RBACPermissionEvaluator.get_user_permissions(db, broker.id, org_id)
        for req in required_permissions:
            if not RBACPermissionEvaluator.matches_permission(perms, req):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access Denied: Required permission '{req}' is missing for role '{tenant.role or 'UNKNOWN'}'."
                )
        return tenant

    return _dependency


def require_role(*allowed_roles: str) -> Callable:
    """
    FastAPI dependency factory enforcing that current broker has one of the specified roles
    within the active tenant context.
    """
    from app.dependencies import get_current_tenant, TenantContext

    normalized_allowed = {r.strip().upper() for r in allowed_roles}

    async def _dependency(
        tenant: TenantContext = Depends(get_current_tenant),
    ) -> TenantContext:
        current_role = (tenant.role or "").strip().upper()
        if not current_role or current_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{current_role or 'NONE'}' is unauthorized. Allowed: {sorted(list(normalized_allowed))}"
            )
        return tenant

    return _dependency
