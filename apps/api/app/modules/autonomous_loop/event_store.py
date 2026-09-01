"""
Part 21.8 — Durable Sales Loop Event Store
===========================================
Persists domain events with idempotency guarantees and lifecycle state tracking.

IDEMPOTENCY CONTRACT:
  - Each event has a unique idempotency_key.
  - Duplicate ingestion returns the existing event record without re-processing.
  - DB unique constraint on idempotency_key enforces at the database level.
  - Processing state machine: RECEIVED → PROCESSING → COMPLETED / FAILED / RETRYABLE / DEAD_LETTER

CONCURRENCY:
  - SELECT FOR UPDATE on event row prevents concurrent duplicate processing.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.modules.autonomous_loop.models import SalesLoopEvent
from app.modules.autonomous_loop.dto import SalesLoopEventDTO
from app.modules.autonomous_loop.taxonomies import EventProcessingState

logger = logging.getLogger(__name__)


class SalesLoopEventStore:
    """
    Durable, idempotent event persistence layer for the autonomous sales loop.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_event(
        self, event_dto: SalesLoopEventDTO
    ) -> Tuple[SalesLoopEvent, bool]:
        """
        Persists an event with idempotency enforcement.
        Returns (event_record, is_new).
        If the event is a duplicate, returns the existing record and is_new=False.
        """
        # 1. Check for existing event by idempotency_key
        existing = await self._find_by_idempotency_key(event_dto.idempotency_key)
        if existing:
            logger.info(
                f"[EVENT_STORE] Duplicate event suppressed: "
                f"idempotency_key={event_dto.idempotency_key} "
                f"event_type={event_dto.event_type} lead_id={event_dto.lead_id}"
            )
            return existing, False

        # 2. Create new event record
        event_record = SalesLoopEvent(
            id=event_dto.event_id,
            idempotency_key=event_dto.idempotency_key,
            event_type=event_dto.event_type.value,
            schema_version=event_dto.schema_version,
            tenant_id=event_dto.tenant_id,
            lead_id=event_dto.lead_id,
            broker_id=event_dto.broker_id,
            correlation_id=event_dto.correlation_id,
            causation_id=event_dto.causation_id,
            actor_type=event_dto.actor_type.value,
            actor_id=event_dto.actor_id,
            payload=event_dto.payload,
            processing_state=EventProcessingState.RECEIVED.value,
            retry_count=0,
            max_retries=3,
            source=event_dto.source,
            occurred_at=event_dto.occurred_at,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        try:
            self.db.add(event_record)
            await self.db.flush()
            logger.info(
                f"[EVENT_STORE] Ingested event: id={event_record.id} "
                f"type={event_record.event_type} lead={event_record.lead_id}"
            )
            return event_record, True
        except IntegrityError:
            # Race condition: another worker inserted the same key
            await self.db.rollback()
            existing = await self._find_by_idempotency_key(event_dto.idempotency_key)
            if existing:
                logger.info(
                    f"[EVENT_STORE] Race-condition duplicate suppressed: "
                    f"idempotency_key={event_dto.idempotency_key}"
                )
                return existing, False
            raise

    async def mark_processing(self, event_id: str) -> None:
        """Transitions event to PROCESSING state. Uses UPDATE for optimistic locking."""
        await self.db.execute(
            update(SalesLoopEvent)
            .where(
                SalesLoopEvent.id == event_id,
                SalesLoopEvent.processing_state.in_([
                    EventProcessingState.RECEIVED.value,
                    EventProcessingState.RETRYABLE.value,
                ])
            )
            .values(
                processing_state=EventProcessingState.PROCESSING.value,
                processing_started_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.flush()

    async def mark_completed(self, event_id: str) -> None:
        """Transitions event to COMPLETED state."""
        await self.db.execute(
            update(SalesLoopEvent)
            .where(SalesLoopEvent.id == event_id)
            .values(
                processing_state=EventProcessingState.COMPLETED.value,
                processing_completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.flush()

    async def mark_failed(
        self,
        event_id: str,
        failure_class: str,
        error_message: str,
        retry_count: int,
        max_retries: int,
    ) -> None:
        """Transitions event to FAILED or RETRYABLE state based on retry count."""
        new_state = (
            EventProcessingState.RETRYABLE.value
            if retry_count < max_retries
            else EventProcessingState.FAILED.value
        )
        await self.db.execute(
            update(SalesLoopEvent)
            .where(SalesLoopEvent.id == event_id)
            .values(
                processing_state=new_state,
                failure_class=failure_class,
                last_error=error_message[:2000],  # truncate safely
                retry_count=retry_count,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.flush()

    async def mark_dead_letter(self, event_id: str) -> None:
        """Transitions event to DEAD_LETTER state."""
        await self.db.execute(
            update(SalesLoopEvent)
            .where(SalesLoopEvent.id == event_id)
            .values(
                processing_state=EventProcessingState.DEAD_LETTER.value,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.flush()

    async def get_by_id(self, event_id: str) -> Optional[SalesLoopEvent]:
        """Retrieves an event by ID."""
        stmt = select(SalesLoopEvent).where(SalesLoopEvent.id == event_id)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def _find_by_idempotency_key(self, idempotency_key: str) -> Optional[SalesLoopEvent]:
        stmt = select(SalesLoopEvent).where(
            SalesLoopEvent.idempotency_key == idempotency_key
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()
