from enum import Enum
from typing import Set, List, Callable
from fastapi import Depends, HTTPException, status
from app.infrastructure.errors.exceptions import ForbiddenException

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

def require_permission(required_permission: Permission):
    """FastAPI Dependency enforcing RBAC permission checks on API routes."""
    async def permission_dependency(current_role: Role = Role.ADMIN):
        if not has_permission(current_role, required_permission):
            raise ForbiddenException(
                message=f"Role '{current_role.value}' does not possess required permission '{required_permission.value}'",
                code="INSUFFICIENT_PERMISSIONS"
            )
        return current_role
    return permission_dependency
