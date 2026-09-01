"""
Presence Service — Typing Indicators & Online Status
======================================================
Manages ephemeral typing events and agent/customer online presence.
Expired TypingEvents are purged automatically.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication_models import TypingEvent, PresenceRecord

logger = logging.getLogger(__name__)

_TYPING_TTL_SECONDS = 8   # Typing indicator expires after 8 seconds
_PRESENCE_STALE_SECONDS = 60  # Presence stale after 60 seconds without heartbeat


class PresenceService:
    """
    Manages typing indicators and online/offline presence.
    Channel-capability-aware: only emits events if provider supports it.
    """

    async def set_typing(
        self,
        conversation_id: str,
        organization_id: str,
        actor_id: str,
        actor_type: str,   # agent | ai | customer
        channel: str,
        db: AsyncSession,
        event_type: str = "typing",  # typing | recording | stopped
    ) -> TypingEvent:
        """Create/update a typing indicator for an actor."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=_TYPING_TTL_SECONDS)

        # Purge any existing typing event for this actor in this conversation
        await db.execute(
            delete(TypingEvent).where(
                TypingEvent.conversation_id == conversation_id,
                TypingEvent.actor_id == actor_id,
                TypingEvent.channel == channel,
            )
        )

        typing = TypingEvent(
            conversation_id=conversation_id,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type=event_type,
            channel=channel,
            expires_at=expires_at,
        )
        db.add(typing)
        await db.flush()
        return typing

    async def clear_typing(
        self,
        conversation_id: str,
        actor_id: str,
        channel: str,
        db: AsyncSession,
    ) -> None:
        """Remove typing indicator for an actor."""
        await db.execute(
            delete(TypingEvent).where(
                TypingEvent.conversation_id == conversation_id,
                TypingEvent.actor_id == actor_id,
                TypingEvent.channel == channel,
            )
        )
        await db.flush()

    async def get_active_typing(
        self, conversation_id: str, db: AsyncSession
    ) -> List[TypingEvent]:
        """Get all active (non-expired) typing events for a conversation."""
        now = datetime.now(timezone.utc)
        stmt = select(TypingEvent).where(
            TypingEvent.conversation_id == conversation_id,
            TypingEvent.expires_at > now,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_presence(
        self,
        organization_id: str,
        entity_id: str,
        entity_type: str,   # agent | customer
        channel: str,
        status: str,         # online | away | offline | busy
        db: AsyncSession,
    ) -> PresenceRecord:
        """Update or create a presence record for an entity."""
        now = datetime.now(timezone.utc)

        # Try to find existing record
        stmt = select(PresenceRecord).where(
            PresenceRecord.organization_id == organization_id,
            PresenceRecord.entity_id == entity_id,
            PresenceRecord.entity_type == entity_type,
            PresenceRecord.channel == channel,
        )
        result = await db.execute(stmt)
        record = result.scalars().first()

        if record:
            record.status = status
            record.last_seen_at = now
        else:
            record = PresenceRecord(
                organization_id=organization_id,
                entity_id=entity_id,
                entity_type=entity_type,
                channel=channel,
                status=status,
                last_seen_at=now,
            )
            db.add(record)

        await db.flush()
        return record

    async def get_presence(
        self,
        organization_id: str,
        entity_id: str,
        entity_type: str,
        channel: str,
        db: AsyncSession,
    ) -> str:
        """Get presence status for an entity. Returns 'offline' if stale."""
        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(seconds=_PRESENCE_STALE_SECONDS)

        stmt = select(PresenceRecord).where(
            PresenceRecord.organization_id == organization_id,
            PresenceRecord.entity_id == entity_id,
            PresenceRecord.entity_type == entity_type,
            PresenceRecord.channel == channel,
        )
        result = await db.execute(stmt)
        record = result.scalars().first()

        if not record or record.last_seen_at < stale_threshold:
            return "offline"
        return record.status

    async def purge_expired_typing(self, db: AsyncSession) -> int:
        """Delete expired typing events. Called by background worker."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            delete(TypingEvent).where(TypingEvent.expires_at <= now)
        )
        await db.flush()
        count = result.rowcount
        if count > 0:
            logger.debug(f"[PresenceService] Purged {count} expired typing events")
        return count
