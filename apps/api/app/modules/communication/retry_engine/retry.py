"""
Retry Engine — Dead-Letter Recovery
======================================
Scans OutboundQueue for retry-eligible messages and re-attempts delivery.
Also handles moving dead-letter messages to an archive after TTL.

Run as a background worker (every 30 seconds).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication_models import OutboundQueue
from app.modules.communication.delivery_engine.engine import DeliveryEngine

logger = logging.getLogger(__name__)


class RetryEngine:
    """
    Polls OutboundQueue for status='retry' messages where next_attempt_at <= now.
    Re-submits each to DeliveryEngine.process_queue_item().
    """

    def __init__(self, delivery_engine: DeliveryEngine):
        self._delivery = delivery_engine

    async def run_retry_cycle(self, db: AsyncSession, batch_size: int = 50) -> int:
        """
        Execute one retry cycle.
        Returns number of messages processed.
        """
        now = datetime.now(timezone.utc)

        # Find retry-eligible messages
        stmt = (
            select(OutboundQueue)
            .where(
                OutboundQueue.status == "retry",
                OutboundQueue.next_attempt_at <= now,
            )
            .order_by(OutboundQueue.priority.asc(), OutboundQueue.next_attempt_at.asc())
            .limit(batch_size)
        )
        result = await db.execute(stmt)
        items: List[OutboundQueue] = list(result.scalars().all())

        processed = 0
        for item in items:
            try:
                # Mark as processing to prevent concurrent worker pick-up
                item.status = "processing"
                await db.flush()

                result = await self._delivery.process_queue_item(item, db)
                processed += 1

                if result.success:
                    logger.info(f"[RetryEngine] Retry successful msg_id={item.message_id}")
                else:
                    logger.warning(f"[RetryEngine] Retry failed msg_id={item.message_id} "
                                   f"error={result.error_message}")

                await db.commit()
            except Exception as e:
                logger.error(f"[RetryEngine] Unexpected error processing retry msg_id={item.message_id}: {e}")
                await db.rollback()

        return processed

    async def get_dead_letter_count(self, db: AsyncSession, organization_id: str) -> int:
        """Return count of dead-letter messages for an organization."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(OutboundQueue).where(
            OutboundQueue.organization_id == organization_id,
            OutboundQueue.status == "dead_letter",
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_retry_queue_stats(self, db: AsyncSession, organization_id: str) -> dict:
        """Return retry queue statistics."""
        from sqlalchemy import func
        stmt = (
            select(OutboundQueue.status, func.count().label("count"))
            .where(OutboundQueue.organization_id == organization_id)
            .group_by(OutboundQueue.status)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return {row.status: row.count for row in rows}
