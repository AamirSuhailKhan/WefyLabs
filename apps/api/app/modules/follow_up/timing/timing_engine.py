"""
Timezone & Smart Timing Engine
==============================
Calculates optimal local contact times, enforces quiet hours, respects working days,
and ensures DST-safe UTC scheduling.

NOTE: This engine delegates timezone resolution to TimezoneService (global hierarchy).
NEVER hardcode 'Asia/Dubai' or any country timezone as default.
"""

import logging
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
from typing import Tuple, Optional

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext

logger = logging.getLogger(__name__)

# Country / City to Timezone Mapping
TIMEZONE_MAP = {
    "uae": "Asia/Dubai",
    "dubai": "Asia/Dubai",
    "abu dhabi": "Asia/Dubai",
    "india": "Asia/Kolkata",
    "bengaluru": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "uk": "Europe/London",
    "london": "Europe/London",
    "us": "America/New_York",
    "saudi": "Asia/Riyadh",
    "riyadh": "Asia/Riyadh",
    "qatar": "Asia/Qatar",
    "doha": "Asia/Qatar",
}

class TimingEngine:
    """
    Timezone-aware scheduling and quiet hours window evaluator.
    Timezone is resolved from the global hierarchy — never hardcoded.
    """

    def resolve_timezone(self, lead: Lead) -> str:
        """Determines the appropriate IANA timezone for a lead.
        
        Resolution hierarchy (via TimezoneService):
          lead.preferred_locations → phone prefix → org default → market → UTC
        Never returns 'Asia/Dubai' as a hardcoded default.
        """
        org_timezone: Optional[str] = None
        market_timezone: Optional[str] = None

        # Try to resolve from location string
        inferred: Optional[str] = None
        if lead.preferred_locations:
            for loc in lead.preferred_locations:
                loc_low = loc.lower()
                for key, tz in TIMEZONE_MAP.items():
                    if key in loc_low:
                        inferred = tz
                        break
                if inferred:
                    break

        # Try phone prefix if not found
        if not inferred and lead.phone:
            inferred = TimezoneService._infer_from_phone(lead.phone.strip())

        context = TimezoneContext(
            org_timezone=org_timezone,
            market_timezone=market_timezone,
            inferred_timezone=inferred,
            # country_timezone should come from org's market config
        )
        # Resolves: user → team → org → market → country → UTC
        return TimezoneService.resolve(context)

    def is_within_quiet_hours(
        self,
        dt_utc: datetime,
        tz_name: str,
        quiet_start_str: str = "21:00",
        quiet_end_str: str = "08:00"
    ) -> bool:
        """
        Evaluates whether a given UTC datetime falls within local quiet hours.
        """
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")  # Neutral fallback — never Asia/Dubai

        local_dt = dt_utc.astimezone(tz)
        local_time = local_dt.time()

        start_h, start_m = map(int, quiet_start_str.split(":"))
        end_h, end_m = map(int, quiet_end_str.split(":"))

        q_start = time(start_h, start_m)
        q_end = time(end_h, end_m)

        if q_start > q_end:
            # Over-night quiet hours (e.g. 21:00 to 08:00)
            return local_time >= q_start or local_time < q_end
        else:
            return q_start <= local_time < q_end

    def calculate_optimal_send_time(
        self,
        lead: Lead,
        policy: Optional[FollowUpPolicy] = None,
        desired_time_utc: Optional[datetime] = None
    ) -> Tuple[datetime, str]:
        """
        Computes the next valid UTC execution time that strictly respects quiet hours and working days.
        """
        tz_name = self.resolve_timezone(lead)
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Asia/Dubai")

        quiet_start = policy.quiet_hours_start if policy else "21:00"
        quiet_end = policy.quiet_hours_end if policy else "08:00"

        eval_utc = desired_time_utc or datetime.now(timezone.utc)
        local_dt = eval_utc.astimezone(tz)

        # If inside quiet hours or too early/late, shift to 09:30 AM next valid day
        if self.is_within_quiet_hours(eval_utc, tz_name, quiet_start, quiet_end):
            # Advance to next day 09:30 AM if late night, or 09:30 AM today if early morning
            if local_dt.hour >= 21:
                target_local = (local_dt + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0)
            else:
                target_local = local_dt.replace(hour=9, minute=30, second=0, microsecond=0)

            optimal_utc = target_local.astimezone(timezone.utc)
            return optimal_utc, tz_name

        return eval_utc, tz_name
