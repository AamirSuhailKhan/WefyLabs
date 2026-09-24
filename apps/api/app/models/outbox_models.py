"""
WefyLabs Transactional Outbox Engine
====================================
Guarantees at-least-once, idempotent delivery of domain events, external dispatches,
and background tasks by recording outbox events in the same database transaction as domain changes.

Eliminates dual-write anomalies (e.g., domain write succeeds but notification or Celery task fails).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Integer, DateTime, Text, JSON, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class OutboxStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxEvent(Base):
    """
    Transactional Outbox record.
    Created atomically within the business transaction.
    Polled or dispatched by the outbox processor to downstream queues / subscribers.
    """
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    event_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OutboxStatus.PENDING,
        index=True
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    __table_args__ = (
        Index("ix_outbox_tenant_status", "tenant_id", "status"),
        Index("ix_outbox_status_next_retry", "status", "next_retry_at"),
        Index("ix_outbox_tenant_idempotency", "tenant_id", "idempotency_key"),
    )

    def mark_processing(self) -> None:
        self.status = OutboxStatus.PROCESSING

    def mark_processed(self) -> None:
        self.status = OutboxStatus.PROCESSED
        self.processed_at = datetime.now(timezone.utc)

    def mark_failed(self, error_message: str, next_retry_delay_seconds: int = 10) -> None:
        self.retry_count += 1
        self.last_error = error_message[:2000] if error_message else None
        if self.retry_count >= self.max_retries:
            self.status = OutboxStatus.DEAD_LETTER
            self.next_retry_at = None
        else:
            self.status = OutboxStatus.FAILED
            from datetime import timedelta
            self.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=next_retry_delay_seconds)
