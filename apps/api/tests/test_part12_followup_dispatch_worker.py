"""
Part 12 — Follow-Up Dispatch Worker Tests
=========================================
The scheduled Celery task that drives *due* follow-up executions through the
Communication Hub (never providers directly).

Covers:
  * opt-in inertness (the schedule is safe until explicitly enabled),
  * dispatch of due executions through the Hub,
  * idempotency across repeated runs,
  * honest suppression when the channel is disabled or the row is undeliverable,
  * atomic claiming (fresh claim not stolen, stale claim reclaimed),
  * Celery registration on the lead queue + beat schedule.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.communication_models import ChannelMessage, OutboundQueue
from app.models.follow_up_models import FollowUpExecution
from app.modules.follow_up import tasks as followup_tasks


class _SessionCtx:
    """Async context manager that yields the shared test session."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def worker_multiplexer(db_session, monkeypatch):
    """Point the worker's own session factory at the shared test session."""
    monkeypatch.setattr(followup_tasks, "_get_async_session", lambda: _SessionCtx(db_session))
    return db_session


def _set_dispatch_flag(monkeypatch, enabled: bool) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "FOLLOWUP_HUB_DISPATCH_ENABLED", enabled, raising=False)


async def _make_execution(db_session, broker, lead, **overrides) -> FollowUpExecution:
    values = {
        "id": str(uuid.uuid4()),
        "lead_id": str(lead.id),
        "organization_id": str(broker.organization_id or broker.id),
        "broker_id": str(lead.broker_id),
        "channel": "WEB",
        "reason_type": "UNANSWERED_INQUIRY",
        "status": "SCHEDULED",
        "scheduled_for_utc": datetime.now(timezone.utc) - timedelta(minutes=5),
        "recipient_identifier": lead.phone or "customer",
        "message_body": "Following up on your enquiry",
    }
    values.update(overrides)
    execution = FollowUpExecution(**values)
    db_session.add(execution)
    await db_session.commit()
    return execution


async def _reload(db_session, execution_id: str) -> FollowUpExecution:
    # The worker commits/rolls back its own session state (and uses Core UPDATE
    # statements), so force a fresh read from the database.
    db_session.expire_all()
    return (
        await db_session.execute(
            select(FollowUpExecution)
            .where(FollowUpExecution.id == execution_id)
            .execution_options(populate_existing=True)
        )
    ).scalars().first()


async def _all_messages(db_session):
    return (await db_session.execute(select(ChannelMessage))).scalars().all()


# ─── 1. Opt-in inertness ──────────────────────────────────────────────────────

async def test_worker_is_inert_until_explicitly_enabled(worker_multiplexer, test_broker, test_lead, monkeypatch):
    """An enabled beat schedule must not mass-send queued rows on its own."""
    _set_dispatch_flag(monkeypatch, False)
    execution = await _make_execution(worker_multiplexer, test_broker, test_lead)
    execution_id = execution.id

    summary = await followup_tasks.dispatch_due_follow_up_executions()

    assert summary["status"] == "SKIPPED_DISABLED"
    assert summary["enabled"] is False
    assert summary["claimed"] == 0
    assert (await _reload(worker_multiplexer, execution_id)).status == "SCHEDULED"
    assert await _all_messages(worker_multiplexer) == []


# ─── 2. Happy path ────────────────────────────────────────────────────────────

async def test_worker_dispatches_due_execution_through_hub(worker_multiplexer, test_broker, test_lead, monkeypatch):
    _set_dispatch_flag(monkeypatch, True)
    execution = await _make_execution(worker_multiplexer, test_broker, test_lead)
    execution_id, organization_id = execution.id, execution.organization_id

    summary = await followup_tasks.dispatch_due_follow_up_executions()

    assert summary["status"] == "SUCCESS"
    assert summary["claimed"] == 1
    assert summary["dispatched"] == 1

    refreshed = await _reload(worker_multiplexer, execution_id)
    assert refreshed.status == "DISPATCHED"
    assert refreshed.executed_at is not None

    messages = await _all_messages(worker_multiplexer)
    assert len(messages) == 1
    assert messages[0].direction == "outbound"
    # Tenant scoping: the message carries the execution's own organization.
    assert messages[0].organization_id == organization_id
    # The Hub path persists a queued outbound item (never a direct provider call).
    assert (
        await worker_multiplexer.execute(
            select(OutboundQueue).where(OutboundQueue.message_id == messages[0].id)
        )
    ).scalars().first() is not None


async def test_second_run_does_not_redispatch(worker_multiplexer, test_broker, test_lead, monkeypatch):
    _set_dispatch_flag(monkeypatch, True)
    await _make_execution(worker_multiplexer, test_broker, test_lead)

    first = await followup_tasks.dispatch_due_follow_up_executions()
    second = await followup_tasks.dispatch_due_follow_up_executions()

    assert first["dispatched"] == 1
    assert second["claimed"] == 0
    assert second["dispatched"] == 0
    assert second["duplicate"] == 0
    assert len(await _all_messages(worker_multiplexer)) == 1


# ─── 3. Honest failure handling ───────────────────────────────────────────────

async def test_disabled_channel_suppresses_execution(worker_multiplexer, test_broker, test_lead, monkeypatch):
    """WhatsApp is disabled → the row is suppressed, never sent on another channel."""
    _set_dispatch_flag(monkeypatch, True)
    execution = await _make_execution(worker_multiplexer, test_broker, test_lead, channel="WHATSAPP")
    execution_id = execution.id

    summary = await followup_tasks.dispatch_due_follow_up_executions()

    assert summary["suppressed"] == 1
    assert summary["dispatched"] == 0
    refreshed = await _reload(worker_multiplexer, execution_id)
    assert refreshed.status == "SUPPRESSED"
    assert refreshed.suppression_reason == "NO_AVAILABLE_CHANNEL"
    assert await _all_messages(worker_multiplexer) == []


async def test_undeliverable_execution_is_suppressed_not_retried_forever(
    worker_multiplexer, test_broker, test_lead, monkeypatch
):
    _set_dispatch_flag(monkeypatch, True)
    execution = await _make_execution(worker_multiplexer, test_broker, test_lead, message_body="")
    execution_id = execution.id

    summary = await followup_tasks.dispatch_due_follow_up_executions()

    assert summary["suppressed"] == 1
    refreshed = await _reload(worker_multiplexer, execution_id)
    assert refreshed.status == "SUPPRESSED"
    assert refreshed.suppression_reason


# ─── 4. Claiming semantics ────────────────────────────────────────────────────

async def test_fresh_claim_is_not_stolen(worker_multiplexer, test_broker, test_lead, monkeypatch):
    """A row already claimed by a running worker (within the grace window) is left alone."""
    _set_dispatch_flag(monkeypatch, True)
    await _make_execution(
        worker_multiplexer, test_broker, test_lead,
        status=followup_tasks.CLAIMED_STATUS,
        scheduled_for_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    summary = await followup_tasks.dispatch_due_follow_up_executions()

    assert summary["claimed"] == 0
    assert summary["dispatched"] == 0
    assert await _all_messages(worker_multiplexer) == []


async def test_stale_claim_is_reclaimed(worker_multiplexer, test_broker, test_lead, monkeypatch):
    """A claim abandoned by a crashed worker is reclaimed and dispatched."""
    _set_dispatch_flag(monkeypatch, True)
    execution = await _make_execution(
        worker_multiplexer, test_broker, test_lead,
        status=followup_tasks.CLAIMED_STATUS,
        scheduled_for_utc=datetime.now(timezone.utc) - (followup_tasks.STALE_CLAIM_GRACE + timedelta(minutes=5)),
    )
    execution_id = execution.id

    summary = await followup_tasks.dispatch_due_follow_up_executions()

    assert summary["claimed"] == 1
    assert summary["dispatched"] == 1
    assert (await _reload(worker_multiplexer, execution_id)).status == "DISPATCHED"


async def test_future_execution_is_not_dispatched(worker_multiplexer, test_broker, test_lead, monkeypatch):
    _set_dispatch_flag(monkeypatch, True)
    await _make_execution(
        worker_multiplexer, test_broker, test_lead,
        scheduled_for_utc=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    summary = await followup_tasks.dispatch_due_follow_up_executions()

    assert summary["claimed"] == 0
    assert await _all_messages(worker_multiplexer) == []


# ─── 5. Celery registration ───────────────────────────────────────────────────

def test_task_is_registered_and_scheduled():
    from app.celery_app import celery_app

    assert "app.modules.follow_up.tasks" in celery_app.conf.include
    route = celery_app.conf.task_routes.get("follow_up.dispatch_due_executions")
    assert route == {"queue": "lead_queue"}

    entry = celery_app.conf.beat_schedule.get("dispatch-due-followup-executions")
    assert entry is not None
    assert entry["task"] == "follow_up.dispatch_due_executions"
    assert followup_tasks.dispatch_due_follow_up_executions_task.name == "follow_up.dispatch_due_executions"
