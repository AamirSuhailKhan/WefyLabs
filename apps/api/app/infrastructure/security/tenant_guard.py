"""
WefyLabs Multi-Tenant Security Guard
====================================
Canonical tenant boundary assertions and IDOR defense utilities.
Enforces zero-trust data access: never trust user-supplied tenant parameters;
always assert against verified server-derived TenantContext.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional
from fastapi import HTTPException, status

from app.dependencies import TenantContext
from app.infrastructure.errors.exceptions import ForbiddenException

logger = logging.getLogger("wefylabs.security.tenant_guard")


class TenantSecurityGuard:
    """
    Enforces multi-tenant data isolation and anti-IDOR checks.
    """

    @staticmethod
    def assert_ownership(
        entity: Any,
        tenant: TenantContext,
        *,
        entity_name: str = "Resource",
        org_field: str = "organization_id",
        broker_field: str = "broker_id",
    ) -> None:
        """
        Asserts that the given entity belongs to the active tenant.
        Fails closed with HTTP 403 / ForbiddenException if mismatch detected.
        """
        if not tenant:
            raise ForbiddenException(
                message="Tenant context is missing. Access denied.",
                code="TENANT_CONTEXT_MISSING"
            )

        # Check direct organization_id ownership first
        entity_org_id = getattr(entity, org_field, None)
        if entity_org_id is not None:
            if str(entity_org_id) != str(tenant.organization_id):
                logger.warning(
                    f"[IDOR Violation] Tenant mismatch for {entity_name}: "
                    f"entity_org={entity_org_id} vs active_tenant={tenant.organization_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access to this {entity_name.lower()} is forbidden."
                )
            return

        # If entity only has broker_id (legacy schema), assert against tenant.broker_id
        entity_broker_id = getattr(entity, broker_field, None)
        if entity_broker_id is not None and tenant.broker_id is not None:
            if str(entity_broker_id) != str(tenant.broker_id):
                logger.warning(
                    f"[IDOR Violation] Broker mismatch for {entity_name}: "
                    f"entity_broker={entity_broker_id} vs active_broker={tenant.broker_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access to this {entity_name.lower()} is forbidden."
                )
            return

        # If neither organization_id nor broker_id is verifiable on a tenanted entity:
        # If it's a known tenanted entity type, fail closed.
        if hasattr(entity, org_field) or hasattr(entity, broker_field):
            logger.error(
                f"[Security Anomaly] Entity {entity_name} has unassigned tenant/broker fields. "
                "Failing closed to prevent cross-tenant data leakage."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unassigned {entity_name.lower()} cannot be accessed."
            )

    @staticmethod
    def build_cache_key(
        tenant: TenantContext,
        subsystem: str,
        identifier: str
    ) -> str:
        """
        Builds a canonical tenant-isolated Redis cache key.
        Pattern: wefylabs:{tenant_id}:{subsystem}:{identifier}
        """
        org_id = tenant.organization_id if tenant else "system"
        return f"wefylabs:{org_id}:{subsystem}:{identifier}"

    @staticmethod
    def validate_uuid(value: Any) -> bool:
        """Validates that a string or object is a well-formed UUID."""
        if not value:
            return False
        try:
            uuid.UUID(str(value))
            return True
        except (ValueError, TypeError, AttributeError):
            return False
