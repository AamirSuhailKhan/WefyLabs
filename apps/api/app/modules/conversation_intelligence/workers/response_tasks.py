"""
Part 21.7 — Asynchronous Celery Tasks for Inbound Customer Response Processing
==============================================================================
Idempotent task execution for inbound message queue processing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.modules.conversation_intelligence.service import ResponseIntelligenceService
from app.modules.conversation_intelligence.dto import InboundCustomerMessage

logger = logging.getLogger(__name__)


@celery_app.task(
    name="conversation_intelligence.process_inbound_customer_response",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def process_inbound_customer_response(self, message_payload: Dict[str, Any]):
    """
    Celery background worker processing inbound customer communications.
    Idempotent and retry-safe.
    """
    logger.info(f"[Celery] Processing inbound response for lead={message_payload.get('lead_id')}")

    async def _async_process():
        async with AsyncSessionLocal() as session:
            service = ResponseIntelligenceService(session)
            msg_dto = InboundCustomerMessage(**message_payload)
            return await service.ingest_inbound_message(msg_dto)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_async_process(), loop)
            return future.result()
        else:
            return asyncio.run(_async_process())
    except Exception as exc:
        logger.error(f"[Celery] Inbound response task error: {exc}", exc_info=True)
        raise self.retry(exc=exc)
