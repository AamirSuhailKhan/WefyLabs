"""
Part 21.6 — Communication Delivery Celery Background Tasks
===========================================================
Idempotent, tenant-scoped background workers for async communication dispatch,
retry processing with exponential backoff, and dead-letter handling.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("wefylabs.communication.tasks")

try:
    from app.celery_app import celery_app
except ImportError:
    celery_app = None


def _get_async_session():
    from app.database import AsyncSessionLocal
    return AsyncSessionLocal()


if celery_app:
    @celery_app.task(name="communication.process_outbound_queue", bind=True, max_retries=3)
    def process_outbound_queue_task(self, batch_size: int = 50) -> Dict[str, Any]:
        """
        Background task processing pending OutboundQueue entries.
        """
        async def _run():
            async with _get_async_session() as session:
                from sqlalchemy import select, and_
                from app.models.communication_models import OutboundQueue
                from app.modules.communication.channel_manager.manager import get_channel_manager
                from app.modules.communication.delivery_engine.engine import DeliveryEngine

                now_utc = datetime.now(timezone.utc)
                stmt = (
                    select(OutboundQueue)
                    .where(
                        OutboundQueue.status.in_(["pending", "retry"]),
                        (OutboundQueue.next_attempt_at == None) | (OutboundQueue.next_attempt_at <= now_utc),
                    )
                    .order_by(OutboundQueue.priority.asc(), OutboundQueue.created_at.asc())
                    .limit(batch_size)
                )
                res = await session.execute(stmt)
                items = list(res.scalars().all())

                delivery_engine = DeliveryEngine(get_channel_manager())
                processed = 0
                for item in items:
                    try:
                        await delivery_engine.process_queue_item(item, session)
                        processed += 1
                    except Exception as e:
                        logger.error(f"[OutboundQueueTask] Error processing item {item.id}: {e}")

                await session.commit()
                return {"status": "SUCCESS", "processed_count": processed}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            return loop.run_until_complete(_run())
        except Exception as exc:
            logger.error(f"[OutboundQueueTask] Unhandled exception: {exc}")
            raise self.retry(exc=exc, countdown=10)
