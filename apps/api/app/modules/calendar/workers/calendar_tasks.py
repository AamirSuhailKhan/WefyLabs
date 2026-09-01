"""
Celery Background Tasks for Calendar & Scheduling Intelligence Engine
======================================================================
Scheduled & on-demand workers for:
- Dispatching due meeting reminders (T-24h, T-2h, T-30m)
- Periodic external calendar synchronization & conflict detection reconciliation
- Releasing expired 5-minute booking holds
- Asynchronous AI pre-meeting preparation brief generation
- Asynchronous no-show risk assessment
"""

import asyncio
import logging
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy import select, and_, update

from app.database import async_session_maker
from app.models.calendar_models import MeetingReminder, MeetingHold, Meeting, CalendarConflict, CalendarEvent
from app.modules.calendar.reminders.reminder_worker import ReminderDispatcher
from app.modules.calendar.preparation.preparation_brief_service import PreparationBriefService
from app.modules.calendar.no_show.no_show_service import NoShowPredictionService
from app.modules.calendar.conflict_resolution.conflict_service import ConflictResolutionService

logger = logging.getLogger(__name__)

def _run_async(coro):
    """Helper to run async coroutines inside synchronous Celery worker threads."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
    return loop.run_until_complete(coro)

@shared_task(name="app.modules.calendar.workers.calendar_tasks.process_due_reminders_task")
def process_due_reminders_task():
    """
    Celery Beat task running every 5 minutes to dispatch due WhatsApp/Email meeting reminders.
    """
    async def _work():
        async with async_session_maker() as db:
            dispatcher = ReminderDispatcher(db)
            count = await dispatcher.process_due_reminders()
            logger.info(f"[Celery:Reminders] Dispatched {count} due appointment reminder(s).")
            return count

    return _run_async(_work())

@shared_task(name="app.modules.calendar.workers.calendar_tasks.cleanup_expired_holds_task")
def cleanup_expired_holds_task():
    """
    Celery Beat task running every 5 minutes to release expired temporary booking holds.
    """
    async def _work():
        now = datetime.now(timezone.utc)
        async with async_session_maker() as db:
            stmt = (
                update(MeetingHold)
                .where(
                    and_(
                        MeetingHold.is_released == False,
                        MeetingHold.expires_at_utc <= now
                    )
                )
                .values(is_released=True)
            )
            res = await db.execute(stmt)
            await db.commit()
            logger.info(f"[Celery:Holds] Cleaned up {res.rowcount} expired booking hold(s).")
            return res.rowcount

    return _run_async(_work())

@shared_task(name="app.modules.calendar.workers.calendar_tasks.reconcile_calendar_conflicts_task")
def reconcile_calendar_conflicts_task():
    """
    Celery Beat task running every 15 minutes to reconcile internal meetings against external busy blocks.
    """
    async def _work():
        now = datetime.now(timezone.utc)
        async with async_session_maker() as db:
            conflict_service = ConflictResolutionService(db)
            # Query confirmed future meetings
            stmt = select(Meeting).where(
                and_(
                    Meeting.status.in_(["CONFIRMED", "RESCHEDULED"]),
                    Meeting.end_utc > now
                )
            ).limit(100)
            res = await db.execute(stmt)
            meetings = res.scalars().all()

            total_conflicts = 0
            for mtg in meetings:
                conflicts = await conflict_service.detect_conflicts_for_meeting(mtg.id)
                total_conflicts += len(conflicts)

            logger.info(f"[Celery:Reconciliation] Reconciled {len(meetings)} meetings, found {total_conflicts} conflict(s).")
            return total_conflicts

    return _run_async(_work())

@shared_task(name="app.modules.calendar.workers.calendar_tasks.generate_meeting_prep_brief_task")
def generate_meeting_prep_brief_task(meeting_id: str):
    """
    On-demand asynchronous worker generating pre-meeting AI briefing notes for sales agent.
    """
    async def _work():
        async with async_session_maker() as db:
            service = PreparationBriefService(db)
            brief = await service.generate_brief(meeting_id)
            logger.info(f"[Celery:PrepBrief] Generated briefing for Meeting {meeting_id}.")
            return brief.id

    return _run_async(_work())

@shared_task(name="app.modules.calendar.workers.calendar_tasks.evaluate_no_show_risk_task")
def evaluate_no_show_risk_task(meeting_id: str):
    """
    On-demand asynchronous worker evaluating no-show probability for newly booked appointment.
    """
    async def _work():
        async with async_session_maker() as db:
            service = NoShowPredictionService(db)
            pred = await service.predict_no_show_risk(meeting_id)
            logger.info(f"[Celery:NoShow] Evaluated risk {pred.risk_level} ({pred.no_show_probability:.2f}) for Meeting {meeting_id}.")
            return {"risk_level": pred.risk_level, "probability": pred.no_show_probability}

    return _run_async(_work())
