"""
Calendar Provider Factory & Configuration-Driven Resolution
===========================================================
Resolves appropriate calendar integration provider based on runtime environment
and configuration. Enforces FAIL FAST in production when credentials are missing.
"""

from typing import Optional
import logging
from app.config import settings
from app.modules.calendar.providers.provider_interface import CalendarProvider, MockCalendarProvider
from app.modules.calendar.providers.google_provider import GoogleCalendarProvider

logger = logging.getLogger(__name__)

def resolve_calendar_provider(provider: Optional[CalendarProvider] = None) -> CalendarProvider:
    """
    Configuration-driven calendar provider resolution.
    - If a provider instance is explicitly passed, returns it.
    - In testing / development environments or when CALENDAR_PROVIDER == 'mock': returns MockCalendarProvider().
    - In production / staging environments: verifies Google Calendar credentials.
      If missing or unconfigured, FAILS FAST with RuntimeError instead of silently using MockCalendarProvider.
    """
    if provider is not None:
        return provider

    env = getattr(settings, "ENV", "development").lower()
    provider_name = getattr(settings, "CALENDAR_PROVIDER", None)

    # 1. Explicit mock requested or non-production environment
    if provider_name == "mock" or env in ("testing", "test", "development", "dev"):
        return MockCalendarProvider()

    # 2. Production / Staging requires a real configured provider
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)

    if not client_id or not client_secret or client_id.startswith("placeholder") or client_secret.startswith("placeholder"):
        raise RuntimeError(
            "Production calendar provider unconfigured: Google OAuth credentials (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) missing. "
            "Refusing silent fallback to MockCalendarProvider in production."
        )

    logger.info("[CalendarFactory] Production GoogleCalendarProvider resolved successfully.")
    return GoogleCalendarProvider(client_id=client_id, client_secret=client_secret)
