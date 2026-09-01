import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.infrastructure_models import EventHistory
from app.infrastructure.events.event_bus import DomainEvent, event_bus

logger = logging.getLogger(__name__)


class EventHistoryService:
    """
    Persistent Domain Event Store.
    Every DomainEvent published via the event bus is persisted here.
    Supports replay for rebuilding analytics, re-indexing RAG, and debugging.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def persist(self, event: DomainEvent, producer: str = "api", subscribers: Optional[List[str]] = None) -> EventHistory:
        """Write a domain event to the persistent event history store."""
        try:
            record = EventHistory(
                event_id=event.event_id,
                event_type=event.event_type,
                event_version=event.version,
                organization_id=event.organization_id,
                correlation_id=event.correlation_id,
                producer=producer,
                actor_id=event.actor.user_id,
                actor_type=event.actor.actor_type,
                payload=event.payload,
                processing_status="processed",
                subscribers_notified=subscribers or [],
                published_at=datetime.fromisoformat(event.timestamp),
                processed_at=datetime.now(timezone.utc),
            )
            self.db.add(record)
            await self.db.flush()
            return record
        except Exception as exc:
            logger.error(f"[EVENT HISTORY] Failed to persist event {event.event_id}: {exc}", exc_info=True)
            raise

    async def search(
        self,
        organization_id: Optional[str] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> dict:
        conditions = []
        if organization_id:
            conditions.append(EventHistory.organization_id == organization_id)
        if event_type:
            conditions.append(EventHistory.event_type == event_type)
        if status:
            conditions.append(EventHistory.processing_status == status)

        base = select(EventHistory)
        if conditions:
            base = base.where(and_(*conditions))

        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        offset = (page - 1) * limit
        stmt = base.order_by(EventHistory.created_at.desc()).offset(offset).limit(limit)
        items = list((await self.db.execute(stmt)).scalars().all())

        return {"items": items, "total": total, "page": page, "limit": limit}

    async def replay(self, record_id: str) -> bool:
        """Replay a persisted event by republishing it to the event bus."""
        stmt = select(EventHistory).where(EventHistory.id == record_id)
        record = (await self.db.execute(stmt)).scalars().first()
        if not record:
            raise ValueError(f"Event history record {record_id} not found.")

        from app.infrastructure.events.event_bus import ActorContext
        event = DomainEvent(
            event_id=f"replay_{record.event_id}",
            event_type=record.event_type,
            organization_id=record.organization_id or "global",
            actor=ActorContext(user_id="system", actor_type="system"),
            correlation_id=record.correlation_id or "",
            version=record.event_version,
            payload=record.payload,
        )

        await event_bus.publish(event)

        # Update processing status
        await self.db.execute(
            update(EventHistory)
            .where(EventHistory.id == record_id)
            .values(processing_status="replaying", retry_count=EventHistory.retry_count + 1)
        )
        await self.db.commit()
        logger.info(f"[EVENT HISTORY] Replayed event {record.event_type} (original: {record.event_id})")
        return True
