"""
Delivery Engine — Outbound Message Lifecycle
=============================================
Manages the complete outbound message lifecycle:

  QUEUED → SENT → DELIVERED → READ
                ↘ FAILED → RETRY → dead_letter

Step 12 of the 13-step message lifecycle pipeline.

Every outbound message is:
1. Persisted to ChannelMessage (DB)
2. Enqueued to OutboundQueue (DB-persisted, restart-safe)
3. Picked up by OutboundWorker → sent via provider
4. Status callbacks update DeliveryStatusRecord (immutable audit log)
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.communication.provider_adapters.base_provider import (
    OutboundMessageDTO, ProviderResponse
)
from app.modules.communication.channel_manager.manager import ChannelManager
from app.models.communication_models import (
    ChannelMessage, DeliveryStatusRecord, OutboundQueue,
    OmnichannelConversation
)

logger = logging.getLogger(__name__)


class DeliveryEngine:
    """
    Orchestrates outbound message delivery lifecycle.
    Used by router endpoints and workers.
    """

    def __init__(self, channel_manager: ChannelManager):
        self._channel_manager = channel_manager

    async def enqueue(
        self,
        conversation: OmnichannelConversation,
        content: str,
        channel: str,
        recipient_identifier: str,
        db: AsyncSession,
        message_type: str = "text",
        sent_by_ai: bool = False,
        sent_by_agent_id: Optional[str] = None,
        template_id: Optional[str] = None,
        template_variables: Optional[Dict[str, str]] = None,
        content_structured: Optional[Dict[str, Any]] = None,
        priority: int = 5,
    ) -> ChannelMessage:
        """
        Create ChannelMessage + OutboundQueue entry.
        Returns ChannelMessage immediately; delivery is async.
        """
        provider = self._channel_manager.get_provider(channel)
        idempotency_key = hashlib.sha256(
            f"out:{conversation.id}:{uuid.uuid4()}".encode()
        ).hexdigest()[:64]

        # ─── Create ChannelMessage ────────────────────────────────────────────
        msg = ChannelMessage(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            lead_id=conversation.lead_id,
            channel=channel,
            provider_name=provider.provider_name,
            direction="outbound",
            message_type=message_type,
            content=content,
            content_structured=content_structured,
            sender_identifier="system",
            sender_name="WefyLabs AI" if sent_by_ai else "Agent",
            sent_by_ai=sent_by_ai,
            sent_by_agent_id=sent_by_agent_id,
            template_id=template_id,
            idempotency_key=idempotency_key,
            delivery_status="queued",
        )
        db.add(msg)
        await db.flush()

        # ─── Create OutboundQueue Entry ───────────────────────────────────────
        queue_entry = OutboundQueue(
            organization_id=conversation.organization_id,
            message_id=msg.id,
            status="pending",
            provider_name=provider.provider_name,
            channel=channel,
            recipient_identifier=recipient_identifier,
            payload={
                "message_id": msg.id,
                "conversation_id": conversation.id,
                "organization_id": conversation.organization_id,
                "channel": channel,
                "provider_name": provider.provider_name,
                "recipient_identifier": recipient_identifier,
                "content": content,
                "message_type": message_type,
                "content_structured": content_structured,
                "template_id": template_id,
                "template_variables": template_variables,
            },
            priority=priority,
            idempotency_key=idempotency_key,
        )
        db.add(queue_entry)

        # ─── Initial DeliveryStatusRecord ────────────────────────────────────
        status_record = DeliveryStatusRecord(
            message_id=msg.id,
            organization_id=conversation.organization_id,
            status="queued",
            provider_name=provider.provider_name,
        )
        db.add(status_record)

        # Update conversation stats
        conversation.total_messages = (conversation.total_messages or 0) + 1
        conversation.last_message_at = datetime.now(timezone.utc)
        conversation.last_channel = channel
        conversation.last_message_preview = content[:200]

        await db.flush()
        logger.info(
            f"[DeliveryEngine] Enqueued msg_id={msg.id} channel={channel} "
            f"org={conversation.organization_id}"
        )
        return msg

    async def process_queue_item(
        self,
        queue_item: OutboundQueue,
        db: AsyncSession,
    ) -> ProviderResponse:
        """
        Process a single OutboundQueue item.
        Called by OutboundWorker.
        """
        payload = queue_item.payload
        channel = queue_item.channel
        provider_name = queue_item.provider_name

        try:
            provider = self._channel_manager.get_provider(channel, provider_name)
        except ValueError as e:
            await self._mark_failed(db, queue_item, f"no_provider: {e}")
            return ProviderResponse(success=False, status="failed",
                                    error_code="no_provider", error_message=str(e))

        outbound_dto = OutboundMessageDTO(
            message_id=payload.get("message_id", queue_item.message_id),
            conversation_id=payload.get("conversation_id", ""),
            organization_id=payload.get("organization_id", queue_item.organization_id),
            channel=channel,
            provider_name=provider_name,
            recipient_identifier=queue_item.recipient_identifier,
            content=payload.get("content", ""),
            message_type=payload.get("message_type", "text"),
            content_structured=payload.get("content_structured"),
            template_id=payload.get("template_id"),
            template_variables=payload.get("template_variables"),
            idempotency_key=queue_item.idempotency_key,
        )

        start_ms = int(time.time() * 1000)
        result = await provider.send(outbound_dto)
        latency_ms = int(time.time() * 1000) - start_ms

        if result.success:
            await self._mark_sent(db, queue_item, result, latency_ms)
        else:
            await self._schedule_retry(db, queue_item, result)

        return result

    async def update_delivery_status(
        self, db: AsyncSession,
        provider_message_id: str,
        status: str,
        channel: str,
        provider_name: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Called when provider sends a delivery webhook (delivered/read/failed).
        Updates ChannelMessage.delivery_status + creates DeliveryStatusRecord.
        """
        # Find message by provider_message_id
        stmt = select(ChannelMessage).where(
            ChannelMessage.provider_message_id == provider_message_id
        )
        result = await db.execute(stmt)
        msg = result.scalars().first()
        if not msg:
            logger.warning(f"[DeliveryEngine] Cannot find message for provider_id={provider_message_id}")
            return

        now = datetime.now(timezone.utc)
        msg.delivery_status = status
        if status == "delivered":
            msg.delivered_at = now
        elif status == "read":
            msg.read_at = now
        elif status == "failed":
            msg.failed_at = now
            msg.failure_reason = error_message

        # Append immutable status record
        status_rec = DeliveryStatusRecord(
            message_id=msg.id,
            organization_id=msg.organization_id,
            status=status,
            provider_name=provider_name,
            provider_message_id=provider_message_id,
            error_code=error_code,
            error_message=error_message,
        )
        db.add(status_rec)
        await db.flush()

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    async def _mark_sent(self, db: AsyncSession, queue_item: OutboundQueue,
                         result: ProviderResponse, latency_ms: int) -> None:
        now = datetime.now(timezone.utc)
        queue_item.status = "sent"
        queue_item.processed_at = now

        # Update ChannelMessage
        await db.execute(
            update(ChannelMessage)
            .where(ChannelMessage.id == queue_item.message_id)
            .values(
                delivery_status="sent",
                sent_at=now,
                provider_message_id=result.provider_message_id,
            )
        )

        # Status record
        db.add(DeliveryStatusRecord(
            message_id=queue_item.message_id,
            organization_id=queue_item.organization_id,
            status="sent",
            provider_name=queue_item.provider_name,
            provider_message_id=result.provider_message_id,
            latency_ms=latency_ms,
        ))
        await db.flush()

    async def _mark_failed(self, db: AsyncSession, queue_item: OutboundQueue,
                           error: str) -> None:
        queue_item.status = "failed"
        queue_item.last_error = error
        queue_item.processed_at = datetime.now(timezone.utc)

        await db.execute(
            update(ChannelMessage)
            .where(ChannelMessage.id == queue_item.message_id)
            .values(delivery_status="failed", failure_reason=error)
        )
        await db.flush()

    async def _schedule_retry(self, db: AsyncSession, queue_item: OutboundQueue,
                              result: ProviderResponse) -> None:
        """Schedule exponential backoff retry or move to dead_letter."""
        from datetime import timedelta
        retry_count = queue_item.retry_count + 1

        if retry_count > queue_item.max_retries:
            queue_item.status = "dead_letter"
            queue_item.last_error = result.error_message
            await db.execute(
                update(ChannelMessage)
                .where(ChannelMessage.id == queue_item.message_id)
                .values(delivery_status="failed", failure_reason=result.error_message)
            )
            logger.error(
                f"[DeliveryEngine] Message moved to dead_letter msg_id={queue_item.message_id}"
            )
        else:
            # Exponential backoff: 2^n seconds (2, 4, 8, 16, 32 sec)
            backoff_seconds = 2 ** retry_count
            queue_item.status = "retry"
            queue_item.retry_count = retry_count
            queue_item.last_error = result.error_message
            queue_item.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            logger.warning(
                f"[DeliveryEngine] Retry scheduled msg_id={queue_item.message_id} "
                f"attempt={retry_count} backoff={backoff_seconds}s"
            )

        await db.flush()
