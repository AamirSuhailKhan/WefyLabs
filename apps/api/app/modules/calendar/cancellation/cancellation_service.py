"""
Appointment Cancellation Service
================================
Cancels meetings and viewings, deleting external calendar events and cancelling reminders.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.calendar_models import Meeting, MeetingReminder
from app.modules.calendar.providers.provider_interface import CalendarProvider, MockCalendarProvider
from app.modules.calendar.providers.calendar_provider_factory import resolve_calendar_provider
from app.modules.calendar.dto.calendar_schemas import CancellationRequestDTO

logger = logging.getLogger(__name__)

class CancellationService:
    """
    Handles meeting cancellation workflows and external cleanup.
    """

    def __init__(self, db: AsyncSession, provider: Optional[CalendarProvider] = None):
        self.db = db
        self.provider = resolve_calendar_provider(provider)

    async def cancel_meeting(self, meeting_id: str, dto: CancellationRequestDTO) -> bool:
        """
        Cancels meeting, cleans up external calendar event, and logs cancellation reason.
        """
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        res = await self.db.execute(stmt)
        meeting = res.scalar_one_or_none()

        if not meeting:
            raise ValueError(f"Meeting '{meeting_id}' not found.")

        # Cancel external event
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
                logger.debug(f"[CancellationService] Token resolve notice: {exc}")

            await self.provider.cancel_event(
                account_email=account_email,
                external_event_id=meeting.external_event_id,
                access_token=access_token
            )

        meeting.status = "CANCELLED"
        meeting.description = f"{meeting.description or ''}\n[Cancelled by {dto.cancelled_by}]: {dto.reason}".strip()

        # Mark all pending reminders as sent/cancelled
        stmt_rem = (
            update(MeetingReminder)
            .where(MeetingReminder.meeting_id == meeting_id, MeetingReminder.is_sent == False)
            .values(is_sent=True)
        )
        await self.db.execute(stmt_rem)

        await self.db.commit()
        logger.info(f"[CANCELLATION] Cancelled Meeting {meeting_id} (Reason: {dto.reason}).")
        return True
