"""
Calendar Conflict Detection & Resolution Service
================================================
Detects overlaps between BeetleLabs appointments and newly discovered external calendar events,
flagging collisions for broker review without silent overwriting.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.calendar_models import Meeting, CalendarEvent, CalendarConflict

logger = logging.getLogger(__name__)

class ConflictResolutionService:
    """
    Detects and logs appointment conflicts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_conflicts_for_meeting(self, meeting_id: str) -> List[CalendarConflict]:
        """
        Checks if an existing meeting overlaps with any external busy calendar events.
        """
        stmt_m = select(Meeting).where(Meeting.id == meeting_id)
        res_m = await self.db.execute(stmt_m)
        meeting = res_m.scalar_one_or_none()

        if not meeting:
            return []

        # Find external events overlapping the meeting window
        stmt_evt = select(CalendarEvent).where(
            and_(
                CalendarEvent.start_utc < meeting.end_utc,
                CalendarEvent.end_utc > meeting.start_utc,
                CalendarEvent.is_busy == True
            )
        )
        res_evt = await self.db.execute(stmt_evt)
        overlapping_events = res_evt.scalars().all()

        conflicts: List[CalendarConflict] = []
        for evt in overlapping_events:
            # Check if conflict already logged
            stmt_conf = select(CalendarConflict).where(
                CalendarConflict.meeting_id == meeting.id,
                CalendarConflict.external_event_id == evt.external_event_id
            )
            res_conf = await self.db.execute(stmt_conf)
            if not res_conf.scalar_one_or_none():
                conflict = CalendarConflict(
                    id=str(uuid.uuid4()),
                    meeting_id=meeting.id,
                    external_event_id=evt.external_event_id,
                    conflict_description=f"Overlaps with external calendar event '{evt.title or 'Busy Block'}'",
                    resolution_status="DETECTED",
                    detected_at=datetime.now(timezone.utc)
                )
                self.db.add(conflict)
                conflicts.append(conflict)

        if conflicts:
            await self.db.commit()
            logger.warning(f"[CONFLICT] Logged {len(conflicts)} conflict(s) for Meeting {meeting_id}.")

        return conflicts
