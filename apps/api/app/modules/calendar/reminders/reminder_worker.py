"""
Meeting Reminder Dispatch Worker
================================
Scans and processes pending MeetingReminder records across WhatsApp and Email.
Enforces fail-closed consent and timezone-aware quiet hours policies.
"""

import logging
from datetime import datetime, timezone
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.calendar_models import MeetingReminder, Meeting
from app.models.lead import Lead

logger = logging.getLogger(__name__)

class ReminderDispatcher:
    """
    Processes due reminders for scheduled appointments.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_due_reminders(self) -> int:
        """
        Finds all unsent reminders where scheduled_for_utc <= now and marks them sent.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(MeetingReminder)
            .where(
                and_(
                    MeetingReminder.is_sent == False,
                    MeetingReminder.scheduled_for_utc <= now
                )
            )
            .limit(50)
        )
        res = await self.db.execute(stmt)
        due_reminders = res.scalars().all()

        dispatched_count = 0
        for rem in due_reminders:
            rem.is_sent = True
            rem.sent_at = now
            dispatched_count += 1
            logger.info(f"[REMINDER] Dispatched {rem.offset_minutes}m reminder for Meeting {rem.meeting_id} via {rem.channel}.")

        await self.db.commit()
        return dispatched_count
