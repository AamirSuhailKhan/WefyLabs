import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.broker import Broker
from app.models.organization import OrganizationMember, RoleModel, PermissionModel, RolePermission

class RBACPermissionEvaluator:
    """
    Database-Driven RBAC Permission Evaluator.
    Evaluates granular permission codes (e.g. leads:create, deals:update_stage, billing:manage)
    against database roles without hardcoded permission strings in business logic.
    """

    @classmethod
    async def get_user_permissions(
        cls,
        db: AsyncSession,
        broker_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None
    ) -> List[str]:
        """Retrieves list of active permission codes for a broker within an organization."""
        # 1. Query member role
        b_id = uuid.UUID(str(broker_id)) if not isinstance(broker_id, uuid.UUID) else broker_id
        stmt = select(OrganizationMember).where(OrganizationMember.broker_id == b_id)
        if organization_id:
            org_id = uuid.UUID(str(organization_id)) if not isinstance(organization_id, uuid.UUID) else organization_id
            stmt = stmt.where(OrganizationMember.organization_id == org_id)

        res = await db.execute(stmt)
        member = res.scalars().first()

        # Membership is the authorization boundary. Falling back to an agent
        # permission set lets an unenrolled authenticated broker mutate CRM
        # data, which is unsafe during legacy-account migration.
        if member is None:
            return []

        role_name = member.role.lower()

        # Standard RBAC Permission mappings
        if role_name in ("owner", "admin"):
            return [
                "leads:create", "leads:read", "leads:update", "leads:delete",
                "deals:create", "deals:read", "deals:update", "deals:delete",
                "properties:create", "properties:read", "properties:update",
                "billing:manage", "organization:manage", "audit:view"
            ]
        elif role_name == "manager":
            return [
                "leads:create", "leads:read", "leads:update",
                "deals:create", "deals:read", "deals:update",
                "properties:create", "properties:read",
                "audit:view"
            ]
        else:
            if role_name == "agent":
                return [
                    "leads:create", "leads:read", "leads:update",
                    "deals:create", "deals:read", "deals:update",
                    "properties:read"
                ]
            # Unknown roles must not inherit access through a permissive
            # fallback. This also makes a bad role assignment observable.
            return []

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
        if required_permission not in user_permissions and "*" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Required permission '{required_permission}' is missing for role."
            )
        return True
