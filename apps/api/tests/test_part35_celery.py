"""
Part 35 — Celery Test Suite: AI Real Estate Revenue Autopilot
=============================================================
Tests Celery task registration, beat schedules, and asynchronous job execution:
1. Celery task registry verification for Revenue Autopilot tasks
2. Celery Beat periodic schedule verification (10-min scan, hourly expiration)
3. Task execution: evaluate_revenue_opportunities_task
4. Task execution: scan_all_tenants_revenue_opportunities_task
5. Task execution: expire_stale_opportunities_task
6. Event task execution: process_price_change_event_task
7. Event task execution: process_site_visit_completed_task
"""
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from app.celery_app import celery_app
from app.modules.revenue_autopilot.tasks import (
    evaluate_revenue_opportunities_task,
    scan_all_tenants_revenue_opportunities_task,
    expire_stale_opportunities_task,
    process_price_change_event_task,
    process_site_visit_completed_task,
)


def test_celery_revenue_tasks_registered():
    """All 5 Revenue Autopilot tasks are registered in Celery app."""
    registered = celery_app.tasks
    expected_tasks = [
        "app.modules.revenue_autopilot.tasks.evaluate_revenue_opportunities_task",
        "app.modules.revenue_autopilot.tasks.scan_all_tenants_revenue_opportunities_task",
        "app.modules.revenue_autopilot.tasks.expire_stale_opportunities_task",
        "app.modules.revenue_autopilot.tasks.process_price_change_event_task",
        "app.modules.revenue_autopilot.tasks.process_site_visit_completed_task",
    ]
    for task_name in expected_tasks:
        assert task_name in registered, f"Celery task '{task_name}' must be registered"


def test_celery_beat_schedule_configured():
    """Periodic beat schedule contains revenue scan (every 10 min) and hourly cleanup."""
    schedule = celery_app.conf.beat_schedule
    assert "scan-revenue-opportunities" in schedule
    assert schedule["scan-revenue-opportunities"]["task"] == "app.modules.revenue_autopilot.tasks.scan_all_tenants_revenue_opportunities_task"

    assert "expire-stale-revenue-opportunities" in schedule
    assert schedule["expire-stale-revenue-opportunities"]["task"] == "app.modules.revenue_autopilot.tasks.expire_stale_opportunities_task"


@pytest.mark.asyncio
async def test_celery_task_evaluate_revenue_opportunities():
    """evaluate_revenue_opportunities_task executes and returns opportunity count."""
    fake_broker_id = str(uuid.uuid4())
    with patch("app.modules.revenue_autopilot.tasks.async_session_maker") as mock_session_maker:
        mock_db = AsyncMock()
        mock_broker = AsyncMock()
        mock_broker.id = uuid.UUID(fake_broker_id)
        mock_db.get.return_value = mock_broker
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        with patch("app.modules.revenue_autopilot.tasks.RevenueAutopilotEngine") as mock_engine_cls:
            mock_engine = AsyncMock()
            mock_engine.evaluate_tenant_opportunities.return_value = [AsyncMock(), AsyncMock()]
            mock_engine_cls.return_value = mock_engine

            res = evaluate_revenue_opportunities_task(fake_broker_id)
            assert res == 2


@pytest.mark.asyncio
async def test_celery_task_scan_all_tenants():
    """scan_all_tenants_revenue_opportunities_task dispatches evaluation for active tenants."""
    fake_b1 = uuid.uuid4()
    fake_b2 = uuid.uuid4()
    with patch("app.modules.revenue_autopilot.tasks.async_session_maker") as mock_session_maker:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [fake_b1, fake_b2]
        mock_db.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_db
        with patch("kombu.connection.Connection.connect"), patch("kombu.messaging.Producer.publish"):
            res = scan_all_tenants_revenue_opportunities_task()
            assert res == 2


@pytest.mark.asyncio
async def test_celery_task_expire_stale():
    """expire_stale_opportunities_task iterates brokers and invalidates expired opportunities."""
    mock_b1 = AsyncMock()
    mock_b1.id = uuid.uuid4()
    with patch("app.modules.revenue_autopilot.tasks.async_session_maker") as mock_session_maker:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_b1]
        mock_db.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        with patch("app.modules.revenue_autopilot.tasks.RevenueAutopilotEngine") as mock_engine_cls:
            mock_engine = AsyncMock()
            mock_engine.invalidate_stale_opportunities.return_value = 3
            mock_engine_cls.return_value = mock_engine

            res = expire_stale_opportunities_task()
            assert res == 3


@pytest.mark.asyncio
async def test_celery_price_change_event():
    """process_price_change_event_task handles price change event for property."""
    fake_prop_id = str(uuid.uuid4())
    fake_broker_id = uuid.uuid4()
    with patch("app.modules.revenue_autopilot.tasks.async_session_maker") as mock_session_maker:
        mock_db = AsyncMock()
        mock_prop = AsyncMock()
        mock_prop.broker_id = fake_broker_id
        mock_broker = AsyncMock()
        mock_db.get.side_effect = [mock_prop, mock_broker]
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        with patch("app.modules.revenue_autopilot.tasks.RevenueAutopilotEngine") as mock_engine_cls:
            mock_engine = AsyncMock()
            mock_engine.evaluate_tenant_opportunities.return_value = [AsyncMock()]
            mock_engine_cls.return_value = mock_engine

            res = process_price_change_event_task(fake_prop_id)
            assert res == 1


@pytest.mark.asyncio
async def test_celery_site_visit_completed_event():
    """process_site_visit_completed_task handles completed site visit meeting."""
    fake_meeting_id = str(uuid.uuid4())
    fake_broker_id = uuid.uuid4()
    with patch("app.modules.revenue_autopilot.tasks.async_session_maker") as mock_session_maker:
        mock_db = AsyncMock()
        mock_meeting = AsyncMock()
        mock_meeting.broker_id = fake_broker_id
        mock_broker = AsyncMock()
        mock_db.get.side_effect = [mock_meeting, mock_broker]
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        with patch("app.modules.revenue_autopilot.tasks.RevenueAutopilotEngine") as mock_engine_cls:
            mock_engine = AsyncMock()
            mock_engine.evaluate_tenant_opportunities.return_value = [AsyncMock()]
            mock_engine_cls.return_value = mock_engine

            res = process_site_visit_completed_task(fake_meeting_id)
            assert res == 1
