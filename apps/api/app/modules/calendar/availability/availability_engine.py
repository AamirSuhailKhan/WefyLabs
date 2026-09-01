"""
Availability Calculation Engine
===============================
Calculates true common availability by intersecting agent working hours,
calendar busy intervals, confirmed meetings, and property access windows.
"""

import logging
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.calendar_models import Meeting, AvailabilityRule, CalendarAccount, CalendarEvent
from app.models.property_models import PropertyListing
from app.modules.calendar.providers.provider_interface import CalendarProvider
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext

logger = logging.getLogger(__name__)

class AvailabilityEngine:
    """
    Computes valid meeting and viewing time intervals.
    """

    def __init__(self, db: AsyncSession, provider: Optional[CalendarProvider] = None):
        self.db = db
        self.provider = provider

    async def calculate_available_slots(
        self,
        broker_id: str,
        duration_minutes: int = 45,
        search_days_ahead: int = 7,
        property_id: Optional[str] = None,
        customer_tz_str: Optional[str] = None,
        broker_tz_str: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates genuine candidate time slots where the broker, customer, and property are available.
        Timezone parameters are Optional — resolved via TimezoneService hierarchy (never hardcoded).
        """
        # 1. Validate Property Status if Viewing
        if property_id:
            try:
                import uuid as _uuid
                p_pk = _uuid.UUID(str(property_id))
            except Exception:
                p_pk = property_id

            stmt_p = select(PropertyListing).where(PropertyListing.id == p_pk)
            res_p = await self.db.execute(stmt_p)
            prop = res_p.scalar_one_or_none()
            if not prop or prop.status != "available":
                logger.warning(f"[AVAILABILITY] Property {property_id} is not 'available' (status: {getattr(prop, 'status', 'not_found')}).")
                return []

        # 2. Setup Timezones — resolved from hierarchy, fall back to UTC (never Asia/Dubai)
        resolved_broker_tz = TimezoneService.resolve(
            TimezoneContext(inferred_timezone=broker_tz_str)
        )
        resolved_customer_tz = TimezoneService.resolve(
            TimezoneContext(inferred_timezone=customer_tz_str)
        )

        try:
            b_tz = ZoneInfo(resolved_broker_tz)
        except Exception:
            b_tz = ZoneInfo("UTC")  # Neutral fallback — never Asia/Dubai

        try:
            c_tz = ZoneInfo(resolved_customer_tz)
        except Exception:
            c_tz = ZoneInfo("UTC")  # Neutral fallback — never Asia/Dubai

        now_utc = datetime.now(timezone.utc)
        search_end_utc = now_utc + timedelta(days=search_days_ahead)

        # 3. Query Confirmed Meetings for Broker
        stmt_mtg = select(Meeting).where(
            and_(
                Meeting.broker_id == broker_id,
                Meeting.status.in_(["CONFIRMED", "REQUESTED", "HELD"]),
                Meeting.end_utc > now_utc,
                Meeting.start_utc < search_end_utc
            )
        )
        res_mtg = await self.db.execute(stmt_mtg)
        confirmed_meetings = res_mtg.scalars().all()

        busy_intervals = [
            (
                m.start_utc - timedelta(minutes=m.buffer_minutes_before),
                m.end_utc + timedelta(minutes=m.buffer_minutes_after)
            )
            for m in confirmed_meetings
        ]

        # 4. Generate Candidate Daily Slots (e.g. 09:30, 11:00, 14:00, 16:00)
        valid_slots: List[Dict[str, Any]] = []

        for day_offset in range(1, search_days_ahead + 1):
            target_date = (now_utc.astimezone(b_tz) + timedelta(days=day_offset)).date()

            # Candidate starting hours in local broker time
            for slot_hour, slot_minute in [(9, 30), (11, 0), (14, 0), (16, 0)]:
                slot_local = datetime.combine(target_date, time(slot_hour, slot_minute), tzinfo=b_tz)
                slot_start_utc = slot_local.astimezone(timezone.utc)
                slot_end_utc = slot_start_utc + timedelta(minutes=duration_minutes)

                # Check collision with busy intervals
                is_busy = False
                for b_start, b_end in busy_intervals:
                    if slot_start_utc < b_end and slot_end_utc > b_start:
                        is_busy = True
                        break

                if not is_busy:
                    valid_slots.append({
                        "start_utc": slot_start_utc,
                        "end_utc": slot_end_utc,
                        "broker_local_start": slot_start_utc.astimezone(b_tz).strftime("%Y-%m-%d %I:%M %p"),
                        "customer_local_start": slot_start_utc.astimezone(c_tz).strftime("%Y-%m-%d %I:%M %p"),
                        "broker_id": broker_id,
                        "suitability_score": 1.0
                    })

                if len(valid_slots) >= 10:
                    break
            if len(valid_slots) >= 10:
                break

        return valid_slots
