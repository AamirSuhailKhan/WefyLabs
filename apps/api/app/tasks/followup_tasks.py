import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.follow_up import FollowUp
from app.models.lead import Lead
from app.services.whatsapp_service import send_message

logger = logging.getLogger(__name__)

def run_async(coro):
    """Utility helper to run async coroutine inside Celery synchronous task."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def async_send_follow_up(follow_up_id_str: str, session: Optional[AsyncSession] = None) -> bool:
    """Async engine logic for sending single follow-up message."""
    follow_up_uuid = uuid.UUID(follow_up_id_str)

    async def _execute(sess: AsyncSession) -> bool:
        stmt = (
            select(FollowUp)
            .where(FollowUp.id == follow_up_uuid)
            .options(selectinload(FollowUp.lead))
        )
        result = await sess.execute(stmt)
        follow_up = result.scalars().first()

        if not follow_up or follow_up.status != "scheduled":
            logger.info(f"[Celery FollowUp Task] FollowUp {follow_up_id_str} not eligible (status: {getattr(follow_up, 'status', None)})")
            return False

        lead = follow_up.lead
        if not lead or lead.deleted_at or lead.status in ("converted", "lost"):
            follow_up.status = "cancelled"
            await sess.commit()
            logger.info(f"[Celery FollowUp Task] Cancelled follow-up {follow_up_id_str} for lead status {getattr(lead, 'status', None)}")
            return False

        # Send WhatsApp message
        success = await send_message(lead.phone, follow_up.message)

        if success:
            follow_up.sent_at = datetime.now(timezone.utc)
            follow_up.status = "sent"
            await sess.commit()
            logger.info(f"[Celery FollowUp Task] Successfully sent follow-up {follow_up_id_str} to {lead.phone}")
            return True
        else:
            follow_up.status = "failed"
            await sess.commit()
            logger.warning(f"[Celery FollowUp Task] Failed sending follow-up {follow_up_id_str}")
            return False

    if session:
        return await _execute(session)
    else:
        async with AsyncSessionLocal() as sess:
            return await _execute(sess)

async def async_check_and_schedule_followups(session: Optional[AsyncSession] = None) -> int:
    """Async engine logic querying due follow-ups and triggering send execution."""
    now = datetime.now(timezone.utc)

    async def _execute(sess: AsyncSession) -> int:
        stmt = select(FollowUp).where(
            FollowUp.scheduled_at <= now,
            FollowUp.status == "scheduled"
        )
        result = await sess.execute(stmt)
        due_followups = result.scalars().all()

        dispatched_count = 0
        for f in due_followups:
            send_follow_up.delay(str(f.id))
            dispatched_count += 1

        logger.info(f"[Celery Beat] Dispatched {dispatched_count} due follow-ups")
        return dispatched_count

    if session:
        return await _execute(session)
    else:
        async with AsyncSessionLocal() as sess:
            return await _execute(sess)

@celery_app.task(bind=True, max_retries=2, default_retry_delay=7200)
def send_follow_up(self, follow_up_id: str):
    """
    Celery task to send a single scheduled follow-up message.
    Retries max 2 times after 2 hours (7200 seconds) if failed.
    """
    try:
        success = run_async(async_send_follow_up(follow_up_id))
        if not success:
            logger.warning(f"[Celery Task] send_follow_up for {follow_up_id} was unsuccessful.")
    except Exception as exc:
        logger.error(f"[Celery Task Error] send_follow_up {follow_up_id}: {exc}")
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(f"[Celery Task Max Retries Exceeded] FollowUp {follow_up_id}")

@celery_app.task
def check_and_schedule_followups():
    """
    Celery beat periodic task running hourly to query due follow-ups.
    """
    return run_async(async_check_and_schedule_followups())
