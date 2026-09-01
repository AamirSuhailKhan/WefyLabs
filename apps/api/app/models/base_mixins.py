"""
BeetleLabs Base Mixins
=======================
Reusable SQLAlchemy 2.0 declarative mixins for enterprise entities.

Every production table uses at minimum TimestampMixin + SoftDeleteMixin.
Enterprise entities use AuditMixin which combines all of them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Integer, String, func, event
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Reusable declarative mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class SoftDeleteMixin:
    """
    Reusable declarative mixin for soft deletion support.
    All queries should filter WHERE deleted_at IS NULL.
    """
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    deleted_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True
    )

    def soft_delete(self, deleted_by_id: Optional[str] = None) -> None:
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by_id

    def restore(self) -> None:
        self.deleted_at = None
        self.deleted_by = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class VersionMixin:
    """
    Optimistic locking via version counter.

    Increment version on every UPDATE with:
        UPDATE entities SET ..., version = version + 1
        WHERE id = $id AND version = $expected_version

    If 0 rows updated → raise OptimisticLockError (HTTP 409 Conflict).
    """
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )


class ActorMixin:
    """
    Records which user created/updated/deleted the entity.
    user IDs are stored as strings to avoid FK constraint complexity in mixins.
    """
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class TenantMixin:
    """
    Reusable declarative mixin for multi-tenant data isolation.
    organization_id is REQUIRED on all tenanted entities.
    workspace_id is optional for sub-tenant partitioning.
    """
    organization_id: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        index=True
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        index=True
    )


class AuditMixin(TimestampMixin, SoftDeleteMixin, VersionMixin, ActorMixin):
    """
    Full enterprise audit mixin.
    Combines: timestamps + soft delete + optimistic locking + actor tracking.
    Use this on all primary business entities (Lead, Contact, Deal, Property).
    """
    pass
