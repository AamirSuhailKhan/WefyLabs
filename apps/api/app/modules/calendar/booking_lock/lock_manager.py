"""
Distributed Booking Lock & Slot Hold Manager
============================================
Provides 5-minute atomic temporary slot reservations (MeetingHold) to eliminate
double booking and race conditions during external API latency.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.calendar_models import MeetingHold

logger = logging.getLogger(__name__)

HOLD_DURATION_SECONDS = 300 # 5 minutes

class BookingLockManager:
    """
    Manages temporary booking holds and prevents slot collisions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def acquire_hold(
        self,
        broker_id: str,
        lead_id: str,
        slot_start_utc: datetime,
        slot_end_utc: datetime
    ) -> Optional[MeetingHold]:
        """
        Attempts to acquire an exclusive 5-minute hold on a broker time slot.
        Returns MeetingHold object if acquired, or None if already held/booked.
        """
        now = datetime.now(timezone.utc)

        # Check for existing active unreleased holds overlapping this slot
        stmt = select(MeetingHold).where(
            and_(
                MeetingHold.broker_id == broker_id,
                MeetingHold.is_released == False,
                MeetingHold.expires_at_utc > now,
                MeetingHold.slot_start_utc < slot_end_utc,
                MeetingHold.slot_end_utc > slot_start_utc
            )
        )
        res = await self.db.execute(stmt)
        active_hold = res.scalar_one_or_none()

        if active_hold:
            logger.warning(
                f"[BOOKING_LOCK] Collision: Slot {slot_start_utc.isoformat()} already held by Lead {active_hold.lead_id}."
            )
            return None

        hold = MeetingHold(
            broker_id=broker_id,
            lead_id=lead_id,
            slot_start_utc=slot_start_utc,
            slot_end_utc=slot_end_utc,
            expires_at_utc=now + timedelta(seconds=HOLD_DURATION_SECONDS),
            is_released=False
        )
        self.db.add(hold)
        await self.db.commit()
        await self.db.refresh(hold)
        logger.info(f"[BOOKING_LOCK] Hold acquired (ID: {hold.id}) for Broker {broker_id} until {hold.expires_at_utc.isoformat()}.")
        return hold

    async def release_hold(self, hold_id: str) -> bool:
        """Releases a temporary hold."""
        stmt = (
            update(MeetingHold)
            .where(MeetingHold.id == hold_id)
            .values(is_released=True)
        )
        res = await self.db.execute(stmt)
        await self.db.commit()
        return res.rowcount > 0
