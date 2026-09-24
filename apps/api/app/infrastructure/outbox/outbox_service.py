"""
WefyLabs Outbox Service
=======================
Enterprise implementation of the Transactional Outbox Pattern.
Guarantees event consistency, at-least-once delivery, retry exponential backoff,
and tenant isolation across all domain events.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Callable, Awaitable
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox_models import OutboxEvent, OutboxStatus

logger = logging.getLogger("wefylabs.outbox")


class OutboxService:
    """
    Transactional Outbox operations.
    Integrates directly with the domain AsyncSession to ensure zero dual-write anomalies.
    """

    @staticmethod
    async def record_event(
        db: AsyncSession,
        *,
        tenant_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        max_retries: int = 5,
    ) -> OutboxEvent:
        """
        Record an outbox event atomically within the calling business transaction.
        If idempotency_key is provided and an event already exists for this tenant, returns the existing record.
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for OutboxEvent to guarantee tenant isolation")

        if idempotency_key:
            stmt = select(OutboxEvent).where(
                and_(
                    OutboxEvent.tenant_id == str(tenant_id),
                    OutboxEvent.idempotency_key == str(idempotency_key)
                )
            )
            result = await db.execute(stmt)
            existing = result.scalars().first()
            if existing:
                logger.debug(
                    f"[Outbox] Idempotent duplicate suppressed for tenant={tenant_id} key={idempotency_key}"
                )
                return existing

        event = OutboxEvent(
            id=uuid.uuid4(),
            event_id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=payload or {},
            status=OutboxStatus.PENDING,
            retry_count=0,
            max_retries=max_retries,
            idempotency_key=str(idempotency_key) if idempotency_key else None,
            created_at=datetime.now(timezone.utc)
        )
        db.add(event)
        # Flush to populate defaults and IDs without committing the parent transaction prematurely
        await db.flush()
        return event

    @staticmethod
    async def fetch_due_events(
        db: AsyncSession,
        *,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> List[OutboxEvent]:
        """
        Fetches events due for dispatch (PENDING or FAILED with next_retry_at <= now).
        Supports tenant filtering or global operator polling.
        """
        now = datetime.now(timezone.utc)
        conditions = [
            or_(
                OutboxEvent.status == OutboxStatus.PENDING,
                and_(
                    OutboxEvent.status == OutboxStatus.FAILED,
                    OutboxEvent.next_retry_at <= now
                )
            )
        ]
        if tenant_id:
            conditions.append(OutboxEvent.tenant_id == str(tenant_id))

        stmt = (
            select(OutboxEvent)
            .where(and_(*conditions))
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def dispatch_event(
        db: AsyncSession,
        event: OutboxEvent,
        handler: Callable[[OutboxEvent], Awaitable[bool]]
    ) -> bool:
        """
        Executes the outbox handler for a single event with exponential backoff and error tracking.
        """
        event.mark_processing()
        await db.flush()

        try:
            success = await handler(event)
            if success:
                event.mark_processed()
                await db.flush()
                return True
            else:
                backoff = min(300, 2 ** event.retry_count * 5)
                event.mark_failed("Handler returned False", next_retry_delay_seconds=backoff)
                await db.flush()
                return False
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            backoff = min(300, 2 ** event.retry_count * 5)
            logger.warning(
                f"[Outbox Dispatch Error] event_id={event.event_id} retry={event.retry_count}: {error_msg}"
            )
            event.mark_failed(error_msg, next_retry_delay_seconds=backoff)
            await db.flush()
            return False

    @staticmethod
    async def purge_processed_events(
        db: AsyncSession,
        *,
        retention_days: int = 14,
        tenant_id: Optional[str] = None
    ) -> int:
        """
        Deletes old processed events to maintain database hygiene per data retention policy.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        conditions = [
            OutboxEvent.status == OutboxStatus.PROCESSED,
            OutboxEvent.processed_at <= cutoff
        ]
        if tenant_id:
            conditions.append(OutboxEvent.tenant_id == str(tenant_id))

        stmt = delete(OutboxEvent).where(and_(*conditions))
        result = await db.execute(stmt)
        return result.rowcount or 0
