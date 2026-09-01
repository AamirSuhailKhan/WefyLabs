"""
BeetleLabs Base Repository
============================
Generic async SQLAlchemy repository enforcing multi-tenant isolation at the query layer.

CRITICAL RULES:
1. Every query automatically filters by organization_id — cannot be bypassed
2. Every query automatically excludes soft-deleted rows
3. Optimistic locking is enforced on every update via version increment
4. No business logic lives here — repositories are pure data access

Usage:
    class LeadRepository(BaseRepository[Lead]):
        _model = Lead

        async def find_by_phone(self, phone: str) -> Optional[Lead]:
            stmt = self._base_query().where(Lead.phone == phone)
            result = await self._session.execute(stmt)
            return result.scalars().first()
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Generic, List, Optional, Type, TypeVar, Any, Dict
from sqlalchemy import select, update, func, Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors.exceptions import (
    NotFoundError, OptimisticLockError, TenantIsolationError
)
from app.common.logger.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class Pagination:
    """Pagination parameters."""
    def __init__(self, page: int = 1, limit: int = 20):
        self.page = max(1, page)
        self.limit = min(200, max(1, limit))
        self.offset = (self.page - 1) * self.limit


class Page(Generic[T]):
    """Paginated response container."""
    def __init__(self, items: List[T], total: int, pagination: Pagination):
        self.items = items
        self.total = total
        self.page = pagination.page
        self.limit = pagination.limit
        self.total_pages = (total + pagination.limit - 1) // pagination.limit if pagination.limit > 0 else 0
        self.has_next = pagination.page < self.total_pages
        self.has_prev = pagination.page > 1


class BaseRepository(Generic[T]):
    """
    Production-grade generic repository with mandatory tenant isolation.

    All subclasses automatically get:
    - organization_id filtering on every query
    - Soft-delete filtering (deleted_at IS NULL)
    - Optimistic locking on updates
    - Audit trail (created_by, updated_by)
    - Paginated list queries
    """

    _model: Type[T]

    def __init__(self, session: AsyncSession, organization_id: str):
        """
        Args:
            session: Async SQLAlchemy session (from UnitOfWork)
            organization_id: Tenant organization ID — baked into every query.
                             Cannot be None. Raises ValueError if not provided.
        """
        if not organization_id:
            raise ValueError("organization_id is required for all repository operations. Tenant isolation cannot be bypassed.")
        self._session = session
        self._org_id = organization_id

    def _base_query(self) -> Select:
        """
        Base SELECT query with mandatory organization_id AND soft-delete filters.
        Every finder method MUST call this as its starting point.
        """
        stmt = select(self._model)
        # Apply organization_id filter
        if hasattr(self._model, "organization_id"):
            stmt = stmt.where(self._model.organization_id == self._org_id)
        # Apply soft-delete filter
        if hasattr(self._model, "deleted_at"):
            stmt = stmt.where(self._model.deleted_at.is_(None))
        return stmt

    async def find_by_id(self, entity_id: Any) -> Optional[T]:
        """
        Find a single entity by primary key within the current tenant.
        Returns None if not found or belongs to a different organization.
        """
        stmt = self._base_query().where(self._model.id == entity_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def find_by_id_or_raise(self, entity_id: Any) -> T:
        """
        Find a single entity by primary key. Raises NotFoundError if missing.
        Use this when the entity MUST exist.
        """
        entity = await self.find_by_id(entity_id)
        if entity is None:
            raise NotFoundError(
                message=f"{self._model.__name__} '{entity_id}' not found."
            )
        return entity

    async def list(self, pagination: Optional[Pagination] = None) -> Page[T]:
        """
        List all non-deleted entities for the current tenant, paginated.
        Subclasses should override with filtered variants.
        """
        pagination = pagination or Pagination()

        # Count query
        count_stmt = (
            select(func.count())
            .select_from(self._model)
        )
        if hasattr(self._model, "organization_id"):
            count_stmt = count_stmt.where(self._model.organization_id == self._org_id)
        if hasattr(self._model, "deleted_at"):
            count_stmt = count_stmt.where(self._model.deleted_at.is_(None))

        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # Data query
        stmt = self._base_query().offset(pagination.offset).limit(pagination.limit)
        if hasattr(self._model, "created_at"):
            stmt = stmt.order_by(self._model.created_at.desc())

        result = await self._session.execute(stmt)
        items = list(result.scalars().all())

        return Page(items=items, total=total, pagination=pagination)

    async def create(self, entity: T, created_by: Optional[str] = None) -> T:
        """
        Persist a new entity. Sets created_by if the model supports it.
        Flushes (not commits) — commit is handled by UnitOfWork.
        """
        if created_by and hasattr(entity, "created_by"):
            entity.created_by = created_by
        if hasattr(entity, "organization_id") and not getattr(entity, "organization_id", None):
            entity.organization_id = self._org_id

        self._session.add(entity)
        await self._session.flush()
        logger.info(
            f"Created {self._model.__name__}",
            extra={"entity_id": str(getattr(entity, "id", "?")), "org_id": self._org_id}
        )
        return entity

    async def update_with_optimistic_lock(
        self,
        entity_id: Any,
        expected_version: int,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> T:
        """
        Updates an entity with optimistic locking.
        Raises OptimisticLockError if version has changed since last read.

        Args:
            entity_id: Primary key of the entity to update
            expected_version: The version value read before this update
            updates: Dict of field → new value
            updated_by: User ID making the change (for audit trail)
        """
        if updated_by:
            updates["updated_by"] = updated_by

        updates["version"] = expected_version + 1
        updates["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(self._model)
            .where(self._model.id == entity_id)
            .where(self._model.organization_id == self._org_id)
            .where(self._model.version == expected_version)
            .values(**updates)
            .returning(self._model)
        )

        result = await self._session.execute(stmt)
        updated = result.scalars().first()

        if updated is None:
            # Could be: wrong version, wrong org, or entity not found
            entity = await self.find_by_id(entity_id)
            if entity is None:
                raise NotFoundError(message=f"{self._model.__name__} '{entity_id}' not found.")
            raise OptimisticLockError()

        await self._session.flush()
        return updated

    async def soft_delete(self, entity_id: Any, deleted_by: Optional[str] = None) -> None:
        """
        Soft-deletes an entity by setting deleted_at and deleted_by.
        Raises NotFoundError if entity does not exist in this tenant.
        """
        entity = await self.find_by_id_or_raise(entity_id)

        if hasattr(entity, "soft_delete"):
            entity.soft_delete(deleted_by_id=deleted_by)
        else:
            entity.deleted_at = datetime.now(timezone.utc)

        await self._session.flush()
        logger.info(
            f"Soft-deleted {self._model.__name__}",
            extra={"entity_id": str(entity_id), "deleted_by": deleted_by, "org_id": self._org_id}
        )

    async def count(self) -> int:
        """Returns total count of non-deleted entities for this tenant."""
        stmt = (
            select(func.count())
            .select_from(self._model)
        )
        if hasattr(self._model, "organization_id"):
            stmt = stmt.where(self._model.organization_id == self._org_id)
        if hasattr(self._model, "deleted_at"):
            stmt = stmt.where(self._model.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one()

    def _assert_same_tenant(self, entity: T) -> None:
        """
        Verifies an entity belongs to the current tenant.
        Call this when accepting entities from external sources.
        """
        entity_org_id = getattr(entity, "organization_id", None)
        if entity_org_id and str(entity_org_id) != str(self._org_id):
            raise TenantIsolationError()
