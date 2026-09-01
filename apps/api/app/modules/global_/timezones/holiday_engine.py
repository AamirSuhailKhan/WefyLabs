"""
HolidayEngine & BusinessDayCalculator
=====================================
Production-grade business day and holiday calculation.
Rules are market-configurable — NOT hardcoded.

UAE: Weekend = Friday + Saturday (days 4 & 5)
India: Weekend = Saturday + Sunday (days 5 & 6)
UK/US: Weekend = Saturday + Sunday (days 5 & 6)

Never hardcode country holidays in application code.
Load from HolidayCalendar DB records.
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.global_models import HolidayCalendar, Holiday, Market
from app.modules.global_.timezones.timezone_service import TimezoneService

logger = logging.getLogger(__name__)


class HolidayEngine:
    """
    Loads and caches holiday calendars from the database.
    Resolution order: Organization calendar → Market calendar → Country calendar
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        # Cache: (market_id or org_id, year) → set of holiday dates
        self._calendar_cache: dict[tuple, Set[date]] = {}

    async def get_holidays(
        self,
        year: int,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Set[date]:
        """
        Return the set of holiday dates for the given year.
        Merges org-level + market-level holidays.
        """
        cache_key = (market_id, organization_id, year)
        if cache_key in self._calendar_cache:
            return self._calendar_cache[cache_key]

        holiday_dates: Set[date] = set()

        # Load market-level and org-level calendars
        conditions = [
            Holiday.__table__.c.id.isnot(None)  # placeholder — join below
        ]

        stmt = (
            select(Holiday)
            .join(HolidayCalendar, Holiday.calendar_id == HolidayCalendar.id)
            .where(and_(
                HolidayCalendar.year == year,
                HolidayCalendar.is_active == True,
            ))
        )

        if market_id:
            # Fetch market-level or org-level calendars for this market
            stmt = stmt.where(
                HolidayCalendar.market_id == market_id
            )
        if organization_id:
            # Also include org-specific overrides
            org_stmt = (
                select(Holiday)
                .join(HolidayCalendar, Holiday.calendar_id == HolidayCalendar.id)
                .where(and_(
                    HolidayCalendar.year == year,
                    HolidayCalendar.is_active == True,
                    HolidayCalendar.organization_id == organization_id,
                ))
            )
            org_result = await self._db.execute(org_stmt)
            for h in org_result.scalars().all():
                holiday_dates.add(h.holiday_date)

        result = await self._db.execute(stmt)
        for h in result.scalars().all():
            holiday_dates.add(h.holiday_date)

        self._calendar_cache[cache_key] = holiday_dates
        return holiday_dates

    async def is_holiday(
        self,
        check_date: date,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> bool:
        """Check if a given date is a public holiday in the market."""
        holidays = await self.get_holidays(check_date.year, market_id, organization_id)
        return check_date in holidays

    def invalidate_cache(self, market_id: Optional[str] = None, year: Optional[int] = None):
        """Invalidate cached holidays — call after holiday calendar updates."""
        keys_to_remove = [
            k for k in self._calendar_cache
            if (market_id is None or k[0] == market_id) and (year is None or k[2] == year)
        ]
        for k in keys_to_remove:
            del self._calendar_cache[k]


class BusinessDayCalculator:
    """
    Market-aware business day calculations.
    Weekend days are loaded from Market.weekend_days — NOT hardcoded.
    Holidays are loaded from HolidayEngine — NOT hardcoded.

    Usage:
        calculator = BusinessDayCalculator(db, market_id="dubai-market-uuid")
        is_biz = await calculator.is_business_day(date(2026, 1, 10))
        next_biz = await calculator.next_business_day(date(2026, 1, 10))
    """

    def __init__(self, db: AsyncSession, market_id: Optional[str] = None, organization_id: Optional[str] = None):
        self._db = db
        self._market_id = market_id
        self._organization_id = organization_id
        self._holiday_engine = HolidayEngine(db)
        self._weekend_days: Optional[Set[int]] = None  # 0=Mon...6=Sun

    async def _get_weekend_days(self) -> Set[int]:
        """Load weekend days from market config — default to Sat+Sun if no market configured."""
        if self._weekend_days is not None:
            return self._weekend_days

        if self._market_id:
            stmt = select(Market).where(Market.id == self._market_id)
            result = await self._db.execute(stmt)
            market = result.scalar_one_or_none()
            if market and market.weekend_days:
                self._weekend_days = set(market.weekend_days)
                return self._weekend_days

        # Neutral default: Saturday + Sunday (international standard)
        # NOT "Asia/Dubai" (Fri+Sat). Market config must specify explicitly.
        self._weekend_days = {5, 6}
        return self._weekend_days

    async def is_business_day(self, check_date: date) -> bool:
        """Returns True if the date is a working business day (not weekend, not holiday)."""
        weekend_days = await self._get_weekend_days()
        if check_date.weekday() in weekend_days:
            return False
        return not await self._holiday_engine.is_holiday(
            check_date, self._market_id, self._organization_id
        )

    async def is_weekend(self, check_date: date) -> bool:
        """Returns True if the date is a weekend in the configured market."""
        weekend_days = await self._get_weekend_days()
        return check_date.weekday() in weekend_days

    async def next_business_day(self, from_date: date, skip_same_day: bool = False) -> date:
        """
        Returns the next business day on or after from_date.
        If skip_same_day=True, returns the next business day AFTER from_date.
        """
        candidate = from_date + timedelta(days=1) if skip_same_day else from_date
        # Safety cap: max 60 days forward (prevents infinite loop on calendar misconfiguration)
        for _ in range(60):
            if await self.is_business_day(candidate):
                return candidate
            candidate += timedelta(days=1)
        logger.error(f"[BusinessDay] Could not find business day within 60 days from {from_date}. Check market calendar configuration.")
        return candidate

    async def add_business_days(self, from_date: date, business_days: int) -> date:
        """
        Add N business days to a date (skipping weekends and holidays).
        Positive values move forward; negative values move backward.
        """
        if business_days == 0:
            return from_date

        direction = 1 if business_days > 0 else -1
        remaining = abs(business_days)
        candidate = from_date

        while remaining > 0:
            candidate += timedelta(days=direction)
            if await self.is_business_day(candidate):
                remaining -= 1

        return candidate

    async def business_hours_between(
        self,
        start: datetime,
        end: datetime,
        work_start_hour: int = 9,
        work_end_hour: int = 18,
    ) -> float:
        """
        Calculate the number of business hours between two datetimes.
        Only counts hours during business days within work_start_hour and work_end_hour.
        """
        if end <= start:
            return 0.0

        total_hours = 0.0
        current = start

        while current.date() <= end.date():
            day = current.date()
            if await self.is_business_day(day):
                day_start = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                day_end = current.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)

                # Clamp to the actual start/end range
                effective_start = max(current if current.date() == start.date() else day_start, day_start)
                effective_end = min(end if current.date() == end.date() else day_end, day_end)

                if effective_end > effective_start:
                    delta_hours = (effective_end - effective_start).total_seconds() / 3600
                    total_hours += delta_hours

            current = (current + timedelta(days=1)).replace(
                hour=work_start_hour, minute=0, second=0, microsecond=0
            )

        return total_hours

    async def sla_deadline(
        self,
        start_datetime: datetime,
        sla_business_hours: int,
        work_start_hour: int = 9,
        work_end_hour: int = 18,
    ) -> datetime:
        """
        Calculate SLA deadline given start datetime and SLA in business hours.
        Used by CRM Intelligence for breach detection.
        """
        remaining_hours = sla_business_hours
        current = start_datetime
        work_hours_per_day = work_end_hour - work_start_hour

        while remaining_hours > 0:
            day = current.date()
            if await self.is_business_day(day):
                day_start = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                day_end = current.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)

                # Start from current or day_start (whichever is later)
                effective_start = max(current, day_start)
                if effective_start >= day_end:
                    # Already past business hours today — move to next day
                    current += timedelta(days=1)
                    current = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                    continue

                available_hours = (day_end - effective_start).total_seconds() / 3600
                if remaining_hours <= available_hours:
                    return effective_start + timedelta(hours=remaining_hours)
                else:
                    remaining_hours -= available_hours
                    current += timedelta(days=1)
                    current = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
            else:
                current += timedelta(days=1)
                current = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)

        return current
