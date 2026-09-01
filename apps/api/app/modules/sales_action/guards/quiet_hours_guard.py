"""
Part 21.5 — Quiet Hours & Timezone Guard
========================================
Enforces customer-local timezone quiet hours.
Never blindly uses server timezone. Uses global TimezoneService hierarchy:
lead.preferred_locations -> phone prefix -> org default -> market -> UTC.
"""
import logging
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
from typing import Tuple, Optional

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext

logger = logging.getLogger(__name__)

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


class QuietHoursGuard:
    """
    Evaluates customer-local quiet hours and computes next eligible send times.
    """

    @classmethod
    def resolve_timezone(cls, lead: Lead) -> str:
        """Resolves the strongest valid IANA timezone for a lead."""
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

        if not inferred and lead.phone:
            inferred = TimezoneService._infer_from_phone(lead.phone.strip())

        context = TimezoneContext(
            org_timezone=None,
            market_timezone=None,
            inferred_timezone=inferred,
        )
        return TimezoneService.resolve(context)

    @classmethod
    def is_within_quiet_hours(
        cls,
        dt_utc: datetime,
        tz_name: str,
        quiet_start_str: str = "21:00",
        quiet_end_str: str = "08:00"
    ) -> bool:
        """Determines if a UTC datetime is in local quiet hours."""
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

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

    @classmethod
    def evaluate_timing(
        cls,
        lead: Lead,
        policy: Optional[FollowUpPolicy] = None,
        desired_time_utc: Optional[datetime] = None,
    ) -> Tuple[bool, datetime, str, Optional[str]]:
        """
        Returns (is_immediately_permitted, scheduled_for_utc, customer_timezone, reason_if_delayed).
        """
        tz_name = cls.resolve_timezone(lead)
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        quiet_start = policy.quiet_hours_start if policy else "21:00"
        quiet_end = policy.quiet_hours_end if policy else "08:00"

        eval_utc = desired_time_utc or datetime.now(timezone.utc)
        local_dt = eval_utc.astimezone(tz)

        if cls.is_within_quiet_hours(eval_utc, tz_name, quiet_start, quiet_end):
            # Compute next valid morning window at 09:30 AM local time
            if local_dt.hour >= 21:
                target_local = (local_dt + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0)
            else:
                target_local = local_dt.replace(hour=9, minute=30, second=0, microsecond=0)

            scheduled_utc = target_local.astimezone(timezone.utc)
            reason = f"Current time is in customer quiet hours ({quiet_start}-{quiet_end} in {tz_name}). Scheduled for {target_local.strftime('%Y-%m-%d %H:%M')} local time."
            return False, scheduled_utc, tz_name, reason

        return True, eval_utc, tz_name, None
