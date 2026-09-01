"""
TimezoneService — Configuration Hierarchy Resolver
===================================================
NEVER hardcode "Asia/Dubai" or "Asia/Kolkata" as default timezones.
NEVER return a country-specific timezone as the system fallback.

Resolution Hierarchy:
  User → Team → Organization → Market → Country → "UTC"

All timestamps stored in backend MUST be UTC.
Frontend converts to user/organization timezone for display.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

# Safe final fallback — neutral, never country-specific
SYSTEM_DEFAULT_TIMEZONE = "UTC"


@dataclass
class TimezoneContext:
    """
    Context bag for timezone resolution.
    Fill in as many fields as available — resolution traverses from most-specific to least.
    """
    user_timezone: Optional[str] = None         # User preference
    team_timezone: Optional[str] = None         # Team/office setting
    org_timezone: Optional[str] = None          # Organization default_timezone
    market_timezone: Optional[str] = None       # Market.timezone
    country_timezone: Optional[str] = None      # Country.default_timezone
    # Optional: inferred from phone or location (lower precedence)
    inferred_timezone: Optional[str] = None


class TimezoneService:
    """
    Timezone resolution service following the global configuration hierarchy.

    Principle: Do NOT default to any specific country timezone.
    The final fallback is always UTC — caller must localize for display.
    """

    @staticmethod
    def resolve(context: TimezoneContext) -> str:
        """
        Resolve the effective IANA timezone string from context hierarchy.

        Precedence (most → least specific):
          user → team → organization → market → country → inferred → UTC

        Returns a valid IANA timezone string (e.g., "Asia/Dubai", "Asia/Kolkata", "UTC").
        """
        candidates = [
            ("user", context.user_timezone),
            ("team", context.team_timezone),
            ("organization", context.org_timezone),
            ("market", context.market_timezone),
            ("country", context.country_timezone),
            ("inferred", context.inferred_timezone),
        ]

        for source, tz_str in candidates:
            if tz_str:
                validated = TimezoneService._validate_timezone(tz_str)
                if validated:
                    logger.debug(f"[Timezone] Resolved from {source}: {validated}")
                    return validated
                else:
                    logger.warning(f"[Timezone] Invalid timezone '{tz_str}' from {source}, skipping.")

        logger.debug(f"[Timezone] No valid timezone in context — falling back to {SYSTEM_DEFAULT_TIMEZONE}")
        return SYSTEM_DEFAULT_TIMEZONE

    @staticmethod
    def resolve_for_lead(
        lead_country_code: Optional[str] = None,
        lead_locale: Optional[str] = None,
        lead_phone: Optional[str] = None,
        org_timezone: Optional[str] = None,
        market_timezone: Optional[str] = None,
    ) -> str:
        """
        Convenience resolver for lead-level timezone determination.
        Country/market timezones are fetched from the registry — not hardcoded.
        """
        # Infer from phone prefix using the PhoneService dial code map
        inferred = None
        if lead_phone:
            inferred = TimezoneService._infer_from_phone(lead_phone)

        context = TimezoneContext(
            org_timezone=org_timezone,
            market_timezone=market_timezone,
            country_timezone=None,   # Should be populated from Country registry, not hardcoded
            inferred_timezone=inferred,
        )
        return TimezoneService.resolve(context)

    @staticmethod
    def convert_to_local(utc_dt: datetime, timezone_str: str) -> datetime:
        """Convert a UTC datetime to the specified local timezone."""
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        tz = TimezoneService._get_zoneinfo(timezone_str)
        return utc_dt.astimezone(tz)

    @staticmethod
    def convert_to_utc(local_dt: datetime, timezone_str: str) -> datetime:
        """Convert a naive local datetime to UTC."""
        tz = TimezoneService._get_zoneinfo(timezone_str)
        if local_dt.tzinfo is None:
            local_dt = local_dt.replace(tzinfo=tz)
        return local_dt.astimezone(timezone.utc)

    @staticmethod
    def now_in(timezone_str: str) -> datetime:
        """Get current time in the specified timezone."""
        tz = TimezoneService._get_zoneinfo(timezone_str)
        return datetime.now(tz)

    @staticmethod
    def format_local(utc_dt: datetime, timezone_str: str, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
        """Format a UTC datetime in local timezone for display."""
        local_dt = TimezoneService.convert_to_local(utc_dt, timezone_str)
        return local_dt.strftime(fmt)

    @staticmethod
    def _validate_timezone(tz_str: str) -> Optional[str]:
        """Validate a timezone string. Returns the string if valid, None otherwise."""
        try:
            ZoneInfo(tz_str)
            return tz_str
        except (ZoneInfoNotFoundError, KeyError, Exception):
            return None

    @staticmethod
    def _get_zoneinfo(timezone_str: str) -> ZoneInfo:
        """Get ZoneInfo object, falling back to UTC if invalid."""
        try:
            return ZoneInfo(timezone_str)
        except (ZoneInfoNotFoundError, KeyError):
            logger.error(
                f"[Timezone] Invalid timezone '{timezone_str}' — falling back to UTC. "
                "Fix the configuration to use a valid IANA timezone."
            )
            return ZoneInfo("UTC")

    @staticmethod
    def _infer_from_phone(phone: str) -> Optional[str]:
        """
        Infer timezone from E.164 phone number prefix.
        This is low-confidence — only used as a last resort.
        Resolution should prefer market/org config.
        """
        # Minimal lookup — PhoneService provides richer inference
        PHONE_PREFIX_TZ = {
            "+971": "Asia/Dubai",       # UAE
            "+91": "Asia/Kolkata",      # India
            "+966": "Asia/Riyadh",      # Saudi Arabia
            "+974": "Asia/Qatar",       # Qatar
            "+965": "Asia/Kuwait",      # Kuwait
            "+968": "Asia/Muscat",      # Oman
            "+973": "Asia/Bahrain",     # Bahrain
            "+44": "Europe/London",     # UK
            "+1": "America/New_York",   # US/Canada (rough)
            "+61": "Australia/Sydney",  # Australia (rough)
            "+65": "Asia/Singapore",    # Singapore
        }
        for prefix, tz in PHONE_PREFIX_TZ.items():
            if phone.startswith(prefix):
                return tz
        return None
