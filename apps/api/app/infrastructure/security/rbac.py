import uuid
from enum import Enum
from typing import Set
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import TenantContext, get_current_broker, get_current_tenant, get_db
from app.infrastructure.errors.exceptions import ForbiddenException
from app.models.broker import Broker
from app.models.organization import OrganizationMember

class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    READ_ONLY = "read_only"

class Permission(str, Enum):
    LEAD_READ = "lead:read"
    LEAD_WRITE = "lead:write"
    LEAD_DELETE = "lead:delete"
    LEAD_EXPORT = "lead:export"
    ORG_MANAGE = "org:manage"
    BILLING_MANAGE = "billing:manage"
    AUDIT_READ = "audit:read"
    API_KEYS_MANAGE = "api_keys:manage"

# Permission Mappings per Role
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.OWNER: {p for p in Permission},
    Role.ADMIN: {
        Permission.LEAD_READ, Permission.LEAD_WRITE, Permission.LEAD_DELETE,
        Permission.LEAD_EXPORT, Permission.ORG_MANAGE, Permission.AUDIT_READ,
        Permission.API_KEYS_MANAGE
    },
    Role.MANAGER: {
        Permission.LEAD_READ, Permission.LEAD_WRITE, Permission.LEAD_EXPORT,
        Permission.AUDIT_READ
    },
    Role.AGENT: {
        Permission.LEAD_READ, Permission.LEAD_WRITE
    },
    Role.READ_ONLY: {
        Permission.LEAD_READ
    }
}

def has_permission(role: Role, required_permission: Permission) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())
    return required_permission in permissions


async def get_current_role(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> Role:
    """Resolve the principal's role in the request's selected organization.

    Authorization must be based on server-side membership, never on a role
    supplied by the browser or a permissive default. A broker can have a
    different role in each organization, so selecting the first membership
    would make authorization nondeterministic and could over-authorize a
    multi-organization user.
    """
    try:
        org_uuid = uuid.UUID(str(tenant.organization_id))
    except (ValueError, AttributeError):
        org_uuid = tenant.organization_id

    result = await db.execute(
        select(OrganizationMember.role).where(
            OrganizationMember.broker_id == current_broker.id,
            OrganizationMember.organization_id == org_uuid,
        )
    )
    stored_role = result.scalars().first()
    if not stored_role:
        raise ForbiddenException(
            message="No organization membership is available for this account.",
            code="ORGANIZATION_MEMBERSHIP_REQUIRED",
        )

    try:
        return Role(str(stored_role).lower())
    except ValueError as exc:
        raise ForbiddenException(
            message="The account has an invalid organization role.",
            code="INVALID_ORGANIZATION_ROLE",
        ) from exc


def require_permission(required_permission: Permission):
    """FastAPI dependency enforcing a server-derived role permission check."""
    async def permission_dependency(current_role: Role = Depends(get_current_role)):
        if not has_permission(current_role, required_permission):
            raise ForbiddenException(
                message=f"Role '{current_role.value}' does not possess required permission '{required_permission.value}'",
                code="INSUFFICIENT_PERMISSIONS"
            )
        return current_role
    return permission_dependency
