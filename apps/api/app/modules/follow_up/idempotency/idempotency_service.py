"""
Deterministic Idempotency Service for Follow-Up Automation
============================================================
Guarantees at database level that concurrent Celery workers, retries,
or periodic jobs cannot execute the same automation rule twice for
the same lead within the same evaluation window.

Concurrency safety is achieved via two layers:
  1. Process-level asyncio.Lock — serialises coroutines competing for the
     same idempotency key within a single event loop (handles asyncio.gather
     and single-session test scenarios without IntegrityError churn).
  2. Database UNIQUE constraint on idempotency_key — last-resort guard for
     truly concurrent multi-process Celery workers that share the DB but not
     memory.  IntegrityError from that layer is still caught and handled.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.follow_up_models import FollowUpAutomationEvent

logger = logging.getLogger(__name__)

# ── Process-level lock registry ───────────────────────────────────────────────
# Maps idempotency_key → asyncio.Lock so that coroutines racing inside the same
# event loop are serialised before even touching the database.
_KEY_LOCKS: Dict[str, asyncio.Lock] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def _get_key_lock(key: str) -> asyncio.Lock:
    """Return (and lazily create) a per-key asyncio.Lock from the registry."""
    async with _REGISTRY_LOCK:
        if key not in _KEY_LOCKS:
            _KEY_LOCKS[key] = asyncio.Lock()
        return _KEY_LOCKS[key]


class IdempotencyService:
    """
    Manages deterministic deduplication and transactional locking of automation events.
    """

    @staticmethod
    def build_key(
        organization_id: str,
        lead_id: str,
        rule_identifier: str,
        trigger_type: str,
        target_window: str = "default"
    ) -> str:
        """
        Builds a deterministic key:
        org:{organization_id}:lead:{lead_id}:rule:{rule_identifier}:trig:{trigger_type}:win:{target_window}
        """
        return f"org:{organization_id}:lead:{lead_id}:rule:{rule_identifier}:trig:{trigger_type}:win:{target_window}"

    @staticmethod
    async def try_acquire_execution(
        db: AsyncSession,
        idempotency_key: str,
        organization_id: str,
        lead_id: str,
        trigger_type: str,
        action_type: str,
        rule_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[FollowUpAutomationEvent]]:
        """
        Attempts to acquire atomic execution lock.

        Layer 1 — asyncio.Lock: serialises coroutines sharing the same event
        loop so only the first one proceeds to INSERT.

        Layer 2 — DB UNIQUE constraint: catches truly concurrent multi-process
        inserts (e.g. two Celery workers) that bypass the process-level lock.

        Returns:
            (True, event)  — successfully acquired; caller must execute action.
            (False, event) — already acquired by another coroutine/worker.
        """
        stmt = select(FollowUpAutomationEvent).where(
            FollowUpAutomationEvent.idempotency_key == idempotency_key
        )

        # ── Layer 1: process-level asyncio lock ──────────────────────────────
        key_lock = await _get_key_lock(idempotency_key)
        async with key_lock:
            # Fast-check INSIDE the lock — another coroutine may have just committed
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                logger.debug(
                    f"[Idempotency] Key '{idempotency_key}' already exists "
                    f"with status {existing.status}."
                )
                return False, existing

            # Attempt INSERT
            event = FollowUpAutomationEvent(
                id=str(uuid.uuid4()),
                idempotency_key=idempotency_key,
                organization_id=str(organization_id),
                lead_id=str(lead_id),
                rule_id=str(rule_id) if rule_id else None,
                trigger_type=trigger_type,
                action_type=action_type,
                status="PENDING",
                execution_details=details or {},
                retry_count=0
            )
            db.add(event)
            try:
                await db.commit()
                await db.refresh(event)
                logger.info(
                    f"[Idempotency] Acquired lock for key '{idempotency_key}' "
                    f"(event {event.id})."
                )
                return True, event

            except IntegrityError:
                # ── Layer 2: DB-level collision (multi-process) ───────────────
                await db.rollback()
                res2 = await db.execute(stmt)
                concurrent_event = res2.scalar_one_or_none()
                logger.info(
                    f"[Idempotency] DB-level concurrent collision for key "
                    f"'{idempotency_key}'."
                )
                return False, concurrent_event

    @staticmethod
    async def record_success(
        db: AsyncSession,
        event_id: str,
        task_id: Optional[str] = None,
        notification_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[FollowUpAutomationEvent]:
        """Marks event as successfully completed and links created task/notification."""
        stmt = select(FollowUpAutomationEvent).where(FollowUpAutomationEvent.id == event_id)
        res = await db.execute(stmt)
        event = res.scalar_one_or_none()
        if not event:
            return None

        event.status = "COMPLETED"
        if task_id:
            event.task_id = str(task_id)
        if notification_id:
            event.notification_id = str(notification_id)
        if details:
            merged = dict(event.execution_details or {})
            merged.update(details)
            event.execution_details = merged

        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def record_skipped(
        db: AsyncSession,
        event_id: str,
        reason: str
    ) -> Optional[FollowUpAutomationEvent]:
        """Marks event as skipped (e.g. stop condition, fatigue, or opt-out)."""
        stmt = select(FollowUpAutomationEvent).where(FollowUpAutomationEvent.id == event_id)
        res = await db.execute(stmt)
        event = res.scalar_one_or_none()
        if not event:
            return None

        event.status = "SKIPPED"
        details = dict(event.execution_details or {})
        details["skip_reason"] = reason
        event.execution_details = details

        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def record_failure(
        db: AsyncSession,
        event_id: str,
        error_message: str
    ) -> Optional[FollowUpAutomationEvent]:
        """Marks event as failed with error details and increments retry count."""
        stmt = select(FollowUpAutomationEvent).where(FollowUpAutomationEvent.id == event_id)
        res = await db.execute(stmt)
        event = res.scalar_one_or_none()
        if not event:
            return None

        event.status = "FAILED"
        event.error_message = str(error_message)
        event.retry_count = (event.retry_count or 0) + 1

        await db.commit()
        await db.refresh(event)
        return event
