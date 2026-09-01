"""
Part 21.8 — Dead Letter Service
================================
Manages permanently failed events that exhausted retry policy.

INVARIANTS:
  - Dead letters are NEVER silently discarded.
  - Dead letters NEVER store secrets, credentials, raw customer message bodies, or PII.
  - Admin recovery (retry, resolve) requires explicit broker action.
  - Resolution is permanently logged with actor, timestamp, and notes.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autonomous_loop.models import SalesLoopDeadLetter, SalesLoopEvent
from app.modules.autonomous_loop.dto import DeadLetterDTO
from app.modules.autonomous_loop.taxonomies import FailureClass

logger = logging.getLogger(__name__)


class DeadLetterService:
    """Manages dead-letter events and admin recovery."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def admit(
        self,
        event: SalesLoopEvent,
        failure_class: FailureClass,
        safe_error_message: str,
        error_code: Optional[str] = None,
    ) -> SalesLoopDeadLetter:
        """
        Moves a permanently failed event to the dead-letter table.
        Idempotent: if already in dead-letter, updates last_failed_at.
        """
        now_utc = datetime.now(timezone.utc)

        # Check if already in dead-letter
        stmt = select(SalesLoopDeadLetter).where(
            SalesLoopDeadLetter.original_event_id == event.id
        )
        res = await self.db.execute(stmt)
        existing = res.scalars().first()

        if existing:
            existing.retry_count += 1
            existing.last_failed_at = now_utc
            existing.safe_error_message = safe_error_message[:4000]
            existing.failure_class = failure_class.value
            existing.updated_at = now_utc
            await self.db.flush()
            logger.warning(
                f"[DEAD_LETTER] Existing dead-letter updated: event={event.id} "
                f"class={failure_class.value}"
            )
            return existing

        dead_letter = SalesLoopDeadLetter(
            original_event_id=event.id,
            event_type=event.event_type,
            tenant_id=event.tenant_id,
            lead_id=event.lead_id,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            failure_class=failure_class.value,
            error_code=error_code,
            safe_error_message=safe_error_message[:4000],
            retry_count=event.retry_count,
            first_failed_at=now_utc,
            last_failed_at=now_utc,
            is_resolved=False,
            created_at=now_utc,
            updated_at=now_utc,
        )
        self.db.add(dead_letter)
        await self.db.flush()

        logger.error(
            f"[DEAD_LETTER] Event permanently failed: event={event.id} "
            f"type={event.event_type} tenant={event.tenant_id} lead={event.lead_id} "
            f"class={failure_class.value}"
        )
        return dead_letter

    async def list_unresolved(
        self,
        tenant_id: str,
        limit: int = 100,
    ) -> List[DeadLetterDTO]:
        """Lists unresolved dead-letter events for admin review."""
        stmt = (
            select(SalesLoopDeadLetter)
            .where(
                and_(
                    SalesLoopDeadLetter.tenant_id == tenant_id,
                    SalesLoopDeadLetter.is_resolved == False,
                )
            )
            .order_by(SalesLoopDeadLetter.last_failed_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        records = list(res.scalars().all())

        return [
            DeadLetterDTO(
                id=r.id,
                original_event_id=r.original_event_id,
                event_type=r.event_type,
                tenant_id=r.tenant_id,
                lead_id=r.lead_id,
                failure_class=r.failure_class,
                safe_error_message=r.safe_error_message,
                retry_count=r.retry_count,
                first_failed_at=r.first_failed_at,
                last_failed_at=r.last_failed_at,
                is_resolved=r.is_resolved,
                resolved_at=r.resolved_at,
            )
            for r in records
        ]

    async def resolve(
        self,
        dead_letter_id: str,
        tenant_id: str,
        resolved_by: str,
        resolution_notes: str,
    ) -> bool:
        """Marks a dead-letter as resolved by an admin actor."""
        stmt = select(SalesLoopDeadLetter).where(
            and_(
                SalesLoopDeadLetter.id == dead_letter_id,
                SalesLoopDeadLetter.tenant_id == tenant_id,
            )
        )
        res = await self.db.execute(stmt)
        record = res.scalars().first()

        if not record:
            return False

        record.is_resolved = True
        record.resolved_at = datetime.now(timezone.utc)
        record.resolved_by = resolved_by[:100]
        record.resolution_notes = resolution_notes[:4000]
        record.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            f"[DEAD_LETTER] Resolved by {resolved_by}: id={dead_letter_id}"
        )
        return True
