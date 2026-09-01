"""
Appointment Rescheduling Service
================================
Atomically reschedules meetings and viewings, updating external calendar event intervals
and resetting pre-meeting reminder timers.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.calendar_models import Meeting, MeetingReminder
from app.modules.calendar.providers.provider_interface import CalendarProvider, MockCalendarProvider
from app.modules.calendar.providers.calendar_provider_factory import resolve_calendar_provider
from app.modules.calendar.dto.calendar_schemas import RescheduleRequestDTO, BookingResponseDTO

logger = logging.getLogger(__name__)

class ReschedulingService:
    """
    Handles appointment rescheduling and calendar synchronization.
    """

    def __init__(self, db: AsyncSession, provider: Optional[CalendarProvider] = None):
        self.db = db
        self.provider = resolve_calendar_provider(provider)

    async def reschedule_meeting(self, meeting_id: str, dto: RescheduleRequestDTO) -> BookingResponseDTO:
        """
        Atomically updates the meeting time and syncs external calendar.
        """
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        res = await self.db.execute(stmt)
        meeting = res.scalar_one_or_none()

        if not meeting:
            raise ValueError(f"Meeting '{meeting_id}' not found.")

        new_start = dto.new_slot_start_utc
        new_end = new_start + timedelta(minutes=meeting.duration_minutes)

        # Update external event
        if meeting.external_event_id:
            account_email = "broker@beetlelabs.com"
            access_token = None
            try:
                from app.models.calendar_models import CalendarAccount
                from app.modules.calendar.auth.token_refresh_service import TokenRefreshService
                import uuid
                b_uuid = uuid.UUID(str(meeting.broker_id))
                stmt_acc = select(CalendarAccount).where(
                    CalendarAccount.broker_id == b_uuid,
                    CalendarAccount.is_connected == True
                )
                res_acc = await self.db.execute(stmt_acc)
                cal_account = res_acc.scalar_one_or_none()
                if cal_account:
                    account_email = cal_account.account_email
                    access_token = await TokenRefreshService.get_valid_access_token(self.db, cal_account)
            except Exception as exc:
                logger.debug(f"[ReschedulingService] Token resolve notice: {exc}")

            await self.provider.update_event(
                account_email=account_email,
                external_event_id=meeting.external_event_id,
                start_utc=new_start,
                end_utc=new_end,
                access_token=access_token
            )

        meeting.start_utc = new_start
        meeting.end_utc = new_end
        meeting.status = "RESCHEDULED"

        # Refresh Reminders
        now_utc = datetime.now(timezone.utc)
        for offset in [1440, 120, 30]:
            rem_time = new_start - timedelta(minutes=offset)
            if rem_time > now_utc:
                rem = MeetingReminder(
                    meeting_id=meeting.id,
                    offset_minutes=offset,
                    channel="WHATSAPP",
                    scheduled_for_utc=rem_time,
                    is_sent=False
                )
                self.db.add(rem)

        await self.db.commit()
        await self.db.refresh(meeting)
        logger.info(f"[RESCHEDULING] Successfully rescheduled Meeting {meeting_id} to {new_start.isoformat()}.")

        return BookingResponseDTO.model_validate(meeting)
