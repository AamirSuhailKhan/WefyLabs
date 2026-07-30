from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, func
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
    """Reusable declarative mixin for soft deletion support."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        self.deleted_at = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
