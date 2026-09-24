"""
Part 12 — Follow-Up Dispatch Worker
===================================
Scheduled Celery task that drives *due* follow-up executions through the
Communication Hub. It never talks to an SMTP / SMS / WhatsApp provider directly,
so delivery, audit, idempotency and the unified conversation timeline stay in one
place (the Hub).

Safety properties
-----------------
* **Opt-in** — the task is scheduled, but performs no work unless
  ``FOLLOWUP_HUB_DISPATCH_ENABLED`` is true, so enabling the beat schedule can
  never cause a surprise mass-send of pre-existing queued rows.
* **Tenant scoped** — every execution is dispatched under its own
  ``organization_id`` (carried on the row).
* **Claimed atomically** — the row is moved ``SCHEDULED → DISPATCHING`` with a
  compare-and-set update before any send, so two workers (or a worker plus a
  manual trigger) cannot both dispatch the same execution.
* **Idempotent** — the Hub is always called with
  ``idempotency_key=f"followup:{execution_id}"``, and ``ChannelMessage`` has a
  unique constraint on that key, so exactly one message can ever be persisted and
  external duplicate sends are impossible even if a claim is retried.
* **Bounded** — ``limit`` caps each batch and the task is time-limited.
* **Fail-safe** — a disabled/unconfigured channel *suppresses* the execution
  (with a reason) instead of silently sending on another channel.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import and_, or_, select, update

logger = logging.getLogger(__name__)

try:  # pragma: no cover - celery is optional in some test/CLI contexts
    from app.celery_app import celery_app
except ImportError:  # pragma: no cover
    celery_app = None


DEFAULT_BATCH_LIMIT = 100
# Transient in-progress marker. ``follow_up_executions.status`` is a free-form
# String column, so no migration is required.
CLAIMED_STATUS = "DISPATCHING"
SCHEDULED_STATUS = "SCHEDULED"
# A claim older than this (measured against the execution's scheduled time) is
# considered abandoned by a crashed worker and may be reclaimed.
STALE_CLAIM_GRACE = timedelta(minutes=15)
TASK_TIME_LIMIT_SECONDS = 300


def _get_async_session():
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal()


async def dispatch_due_follow_up_executions(limit: int = DEFAULT_BATCH_LIMIT) -> Dict[str, Any]:
    """Dispatch every due follow-up execution through the Communication Hub.

    Returns a summary dict. Safe to invoke concurrently and safe to re-invoke:
    claimed rows are not re-claimed and the Hub de-duplicates by idempotency key.
    """
    from app.config import settings
    from app.models.follow_up_models import FollowUpExecution
    from app.modules.communication.channels import ChannelNotSendableError
    from app.modules.follow_up.service import FollowUpOrchestratorService

    summary: Dict[str, Any] = {
        "status": "SUCCESS",
        "enabled": bool(getattr(settings, "FOLLOWUP_HUB_DISPATCH_ENABLED", False)),
        "claimed": 0,
        "dispatched": 0,
        "duplicate": 0,
        "suppressed": 0,
        "skipped": 0,
        "failed": 0,
    }

    if not summary["enabled"]:
        summary["status"] = "SKIPPED_DISABLED"
        logger.info(
            "[FollowUpDispatch] FOLLOWUP_HUB_DISPATCH_ENABLED is false — no follow-up "
            "executions were dispatched."
        )
        return summary

    now_utc = datetime.now(timezone.utc)
    stale_before = now_utc - STALE_CLAIM_GRACE

    async with _get_async_session() as session:
        stmt = (
            select(FollowUpExecution)
            .where(
                or_(
                    and_(
                        FollowUpExecution.status == SCHEDULED_STATUS,
                        FollowUpExecution.scheduled_for_utc <= now_utc,
                    ),
                    and_(
                        FollowUpExecution.status == CLAIMED_STATUS,
                        FollowUpExecution.scheduled_for_utc <= stale_before,
                    ),
                )
            )
            .order_by(FollowUpExecution.scheduled_for_utc.asc())
            .limit(limit)
        )
        due = list((await session.execute(stmt)).scalars().all())
        if not due:
            return summary

        service = FollowUpOrchestratorService(session)

        for execution in due:
            # Snapshot the plain values we need up front: a rollback expires the ORM
            # instance, and reading expired attributes would trigger sync IO.
            execution_id = execution.id
            execution_channel = execution.channel
            organization_id = execution.organization_id
            observed_status = execution.status

            # ── Atomic claim: only the caller that flips the status wins. ─────
            claim = (
                update(FollowUpExecution)
                .where(
                    FollowUpExecution.id == execution_id,
                    FollowUpExecution.status == observed_status,
                )
                .values(status=CLAIMED_STATUS)
            )
            result = await session.execute(claim)
            await session.commit()

            if getattr(result, "rowcount", 0) != 1:
                summary["skipped"] += 1
                continue
            summary["claimed"] += 1

            try:
                outcome = await service.dispatch_execution(execution_id, organization_id)
            except ChannelNotSendableError as exc:
                await session.rollback()
                await session.execute(
                    update(FollowUpExecution)
                    .where(FollowUpExecution.id == execution_id)
                    .values(status="SUPPRESSED", suppression_reason="NO_AVAILABLE_CHANNEL")
                )
                await session.commit()
                summary["suppressed"] += 1
                logger.warning(
                    "[FollowUpDispatch] Execution %s suppressed (channel=%s): %s",
                    execution_id, execution_channel, exc.reason,
                )
            except ValueError as exc:
                # After a successful claim this means "undeliverable as configured"
                # (no body / no recipient) — suppress instead of retrying forever.
                await session.rollback()
                await session.execute(
                    update(FollowUpExecution)
                    .where(FollowUpExecution.id == execution_id)
                    .values(status="SUPPRESSED", suppression_reason=str(exc)[:100])
                )
                await session.commit()
                summary["suppressed"] += 1
                logger.warning(
                    "[FollowUpDispatch] Execution %s suppressed: %s", execution_id, exc
                )
            except Exception as exc:  # noqa: BLE001 - one bad row must not stop the batch
                # Release the claim so a later run retries this execution.
                await session.rollback()
                await session.execute(
                    update(FollowUpExecution)
                    .where(
                        FollowUpExecution.id == execution_id,
                        FollowUpExecution.status == CLAIMED_STATUS,
                    )
                    .values(status=SCHEDULED_STATUS)
                )
                await session.commit()
                summary["failed"] += 1
                logger.error(
                    "[FollowUpDispatch] Execution %s failed: %s", execution_id, exc
                )
            else:
                if outcome.get("status") == "already_dispatched":
                    summary["duplicate"] += 1
                else:
                    summary["dispatched"] += 1

    logger.info("[FollowUpDispatch] %s", summary)
    return summary


if celery_app:
    @celery_app.task(
        name="follow_up.dispatch_due_executions",
        bind=True,
        max_retries=3,
        time_limit=TASK_TIME_LIMIT_SECONDS,
    )
    def dispatch_due_follow_up_executions_task(self, limit: int = DEFAULT_BATCH_LIMIT) -> Dict[str, Any]:
        """Celery wrapper around :func:`dispatch_due_follow_up_executions`."""
        try:
            return asyncio.run(dispatch_due_follow_up_executions(limit=limit))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("[FollowUpDispatch] Task crashed: %s", exc)
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=60)
            return {"status": "FAILED", "error": str(exc)}


__all__ = [
    "dispatch_due_follow_up_executions",
    "dispatch_due_follow_up_executions_task",
    "CLAIMED_STATUS",
    "DEFAULT_BATCH_LIMIT",
]
