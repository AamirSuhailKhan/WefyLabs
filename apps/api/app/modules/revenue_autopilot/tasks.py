"""
Part 35 — Celery Asynchronous Workers for AI Revenue Autopilot
==============================================================
Background tasks for:
- Periodic multi-tenant revenue opportunity evaluation
- Stale opportunity expiration and invalidation
- Event-driven recalculation (price drops, completed site visits, lead updates)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy import select, and_

from app.database import async_session_maker
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.models.crm_models import Meeting
from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine

logger = logging.getLogger("beetlelabs.revenue_autopilot.tasks")


def _run_async(coro):
    """Helper to run async coroutines inside synchronous Celery worker threads."""
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is not None and current_loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    else:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@shared_task(name="app.modules.revenue_autopilot.tasks.evaluate_revenue_opportunities_task")
def evaluate_revenue_opportunities_task(broker_id: str):
    """
    Evaluates active leads and inventory to generate revenue opportunities for a single tenant.
    """
    async def _work():
        async with async_session_maker() as db:
            broker_uuid = uuid.UUID(str(broker_id))
            broker = await db.get(Broker, broker_uuid)
            if not broker:
                logger.warning(f"[Celery:RevenueAutopilot] Broker {broker_id} not found.")
                return 0
            engine = RevenueAutopilotEngine(db)
            generated = await engine.evaluate_tenant_opportunities(broker)
            logger.info(f"[Celery:RevenueAutopilot] Evaluated tenant {broker_id}: {len(generated)} active opportunities.")
            return len(generated)

    return _run_async(_work())


@shared_task(name="app.modules.revenue_autopilot.tasks.scan_all_tenants_revenue_opportunities_task")
def scan_all_tenants_revenue_opportunities_task():
    """
    Celery Beat task running every 10 minutes to trigger revenue evaluation for all active brokers.
    """
    async def _work():
        async with async_session_maker() as db:
            stmt = select(Broker.id).where(Broker.subscription_status.in_(["trial", "active"]))
            broker_ids = list((await db.execute(stmt)).scalars().all())
            dispatched = 0
            for b_id in broker_ids:
                evaluate_revenue_opportunities_task.delay(str(b_id))
                dispatched += 1
            logger.info(f"[Celery:RevenueAutopilot] Dispatched evaluation for {dispatched} tenant(s).")
            return dispatched

    return _run_async(_work())


@shared_task(name="app.modules.revenue_autopilot.tasks.expire_stale_opportunities_task")
def expire_stale_opportunities_task():
    """
    Hourly cleanup task invalidating expired and stale opportunities across all tenants.
    """
    async def _work():
        async with async_session_maker() as db:
            stmt = select(Broker).where(Broker.subscription_status.in_(["trial", "active"]))
            brokers = list((await db.execute(stmt)).scalars().all())
            total_invalidated = 0
            engine = RevenueAutopilotEngine(db)
            for b in brokers:
                count = await engine.invalidate_stale_opportunities(b.id)
                total_invalidated += count
            logger.info(f"[Celery:RevenueAutopilot] Expired/invalidated {total_invalidated} stale opportunities.")
            return total_invalidated

    return _run_async(_work())


@shared_task(name="app.modules.revenue_autopilot.tasks.process_price_change_event_task")
def process_price_change_event_task(property_id: str):
    """
    Triggered when property price changes: recalculates tenant opportunities immediately.
    """
    async def _work():
        async with async_session_maker() as db:
            prop = await db.get(PropertyListing, uuid.UUID(str(property_id)))
            if not prop:
                return 0
            broker = await db.get(Broker, prop.broker_id)
            if not broker:
                return 0
            engine = RevenueAutopilotEngine(db)
            generated = await engine.evaluate_tenant_opportunities(broker)
            logger.info(f"[Celery:RevenueAutopilot] Price change recalculation for property {property_id}: {len(generated)} opportunities.")
            return len(generated)

    return _run_async(_work())


@shared_task(name="app.modules.revenue_autopilot.tasks.process_site_visit_completed_task")
def process_site_visit_completed_task(meeting_id: str):
    """
    Triggered when a site visit is completed: immediately creates follow-up opportunities.
    """
    async def _work():
        async with async_session_maker() as db:
            from app.models.calendar_models import Meeting as SchedulingMeeting
            meeting = await db.get(SchedulingMeeting, str(meeting_id))
            if not meeting:
                meeting = await db.get(Meeting, str(meeting_id))
            if not meeting or not meeting.broker_id:
                return 0
            b_pk = meeting.broker_id if isinstance(meeting.broker_id, uuid.UUID) else uuid.UUID(str(meeting.broker_id))
            broker = await db.get(Broker, b_pk)
            if not broker:
                return 0
            engine = RevenueAutopilotEngine(db)
            generated = await engine.evaluate_tenant_opportunities(broker)
            logger.info(f"[Celery:RevenueAutopilot] Site visit completed recalculation for meeting {meeting_id}: {len(generated)} opportunities.")
            return len(generated)

    return _run_async(_work())
