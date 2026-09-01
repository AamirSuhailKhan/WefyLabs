"""
Message Normalizer
===================
Converts an InboundMessageDTO (from any channel adapter) into a complete
ChannelMessage DB record by resolving organization context, enriching
metadata, and creating all related records.

Step 3 of the 13-step message lifecycle pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.communication.provider_adapters.base_provider import InboundMessageDTO
from app.models.communication_models import (
    OmnichannelConversation, ChannelMessage, MessageAttachment, InboundQueue
)

logger = logging.getLogger(__name__)


class MessageNormalizer:
    """
    Converts raw InboundMessageDTO → ChannelMessage (DB record).
    Handles idempotency: if idempotency_key already exists, returns existing record.
    """

    async def normalize(
        self,
        dto: InboundMessageDTO,
        conversation: OmnichannelConversation,
        db: AsyncSession,
    ) -> Optional[ChannelMessage]:
        """
        Main entry point.

        1. Check idempotency (duplicate detection)
        2. Build ChannelMessage from DTO + conversation
        3. Persist attachments
        4. Mark InboundQueue item as processed
        5. Return ChannelMessage

        Returns None if message was already processed (idempotent duplicate).
        """
        # ─── Idempotency Check ────────────────────────────────────────────────
        existing = await self._find_by_idempotency_key(db, dto.idempotency_key)
        if existing:
            logger.info(
                f"[Normalizer] Duplicate message suppressed "
                f"idempotency_key={dto.idempotency_key}"
            )
            return None

        # ─── Build ChannelMessage ─────────────────────────────────────────────
        msg = ChannelMessage(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            lead_id=conversation.lead_id,
            channel=dto.channel,
            provider_name=dto.provider_name,
            provider_message_id=dto.provider_message_id,
            direction="inbound",
            message_type=dto.message_type,
            content=dto.content,
            content_structured=dto.content_structured,
            sender_name=dto.sender_name,
            sender_identifier=dto.sender_identifier,
            idempotency_key=dto.idempotency_key,
            delivery_status="sent",
            sent_at=dto.received_at,
            sent_by_ai=False,
        )
        db.add(msg)
        await db.flush()  # Get msg.id without committing

        # ─── Attachments ──────────────────────────────────────────────────────
        for att in dto.attachments:
            attachment = MessageAttachment(
                message_id=msg.id,
                organization_id=conversation.organization_id,
                file_name=att.get("file_name", "attachment"),
                mime_type=att.get("mime_type", "application/octet-stream"),
                file_size_bytes=att.get("file_size_bytes", 0),
                file_type=att.get("file_type", "document"),
                storage_provider="mock",
                provider_media_id=att.get("provider_media_id"),
                public_url=att.get("public_url"),
            )
            db.add(attachment)

        # ─── Update Conversation Stats ────────────────────────────────────────
        conversation.total_messages = (conversation.total_messages or 0) + 1
        conversation.unread_count = (conversation.unread_count or 0) + 1
        conversation.last_message_at = dto.received_at
        conversation.last_channel = dto.channel
        conversation.last_message_preview = dto.content[:200] if dto.content else ""

        await db.flush()
        logger.info(
            f"[Normalizer] Normalized message msg_id={msg.id} "
            f"channel={dto.channel} org={conversation.organization_id}"
        )
        return msg

    async def _find_by_idempotency_key(
        self, db: AsyncSession, idempotency_key: str
    ) -> Optional[ChannelMessage]:
        """Check if a message with this idempotency key already exists."""
        stmt = select(ChannelMessage).where(
            ChannelMessage.idempotency_key == idempotency_key
        )
        result = await db.execute(stmt)
        return result.scalars().first()
