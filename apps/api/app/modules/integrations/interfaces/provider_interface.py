"""
Integration Framework — Provider Abstraction Layer.
Every third-party integration (Google Calendar, HubSpot, Stripe, Twilio, etc.)
implements IIntegrationProvider. CRM services never call provider APIs directly.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class IIntegrationProvider(ABC):
    """
    Abstract base for all external integration providers.
    Implement this interface to plug any system into BeetleLabs.
    """
    provider_name: str = "base"
    provider_display_name: str = "Base Integration"

    @abstractmethod
    async def connect(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> bool:
        """Authenticate and establish the integration connection."""
        pass

    @abstractmethod
    async def disconnect(self, integration_id: str) -> bool:
        """Gracefully disconnect and invalidate credentials."""
        pass

    @abstractmethod
    async def health_check(self, integration_id: str) -> bool:
        """Test if the integration connection is still active."""
        pass

    @abstractmethod
    async def sync(self, integration_id: str, since_timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Perform a data synchronization operation."""
        pass


class GoogleCalendarProvider(IIntegrationProvider):
    """
    Integration framework adapter for Google Calendar.
    Note: The authoritative production implementation of Google Calendar OAuth,
    FreeBusy availability checking, and event booking is in `app.modules.calendar`
    (see `GoogleCalendarProvider` at `app.modules.calendar.providers.google_provider`).
    """
    provider_name = "google_calendar"
    provider_display_name = "Google Calendar"

    async def connect(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> bool:
        if not credentials or not any(credentials.get(k) for k in ("access_token", "client_id", "token", "refresh_token")):
            return False
        return True

    async def disconnect(self, integration_id: str) -> bool:
        if not integration_id:
            return False
        return True

    async def health_check(self, integration_id: str) -> bool:
        if not integration_id:
            return False
        return False

    async def sync(self, integration_id: str, since_timestamp: Optional[str] = None) -> Dict[str, Any]:
        if not integration_id:
            return {"synced_events": 0, "status": "unconfigured"}
        return {"synced_events": 0, "status": "idle"}


class HubSpotProvider(IIntegrationProvider):
    provider_name = "hubspot"
    provider_display_name = "HubSpot"

    async def connect(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> bool:
        if not credentials or not credentials.get("api_key"):
            return False
        return True

    async def disconnect(self, integration_id: str) -> bool:
        return bool(integration_id)

    async def health_check(self, integration_id: str) -> bool:
        return False

    async def sync(self, integration_id: str, since_timestamp: Optional[str] = None) -> Dict[str, Any]:
        return {"synced_contacts": 0, "synced_deals": 0, "status": "unconfigured"}


class StripeProvider(IIntegrationProvider):
    provider_name = "stripe"
    provider_display_name = "Stripe"

    async def connect(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> bool:
        if not credentials or not (credentials.get("api_key") or credentials.get("secret_key")):
            return False
        return True

    async def disconnect(self, integration_id: str) -> bool:
        return bool(integration_id)

    async def health_check(self, integration_id: str) -> bool:
        return False

    async def sync(self, integration_id: str, since_timestamp: Optional[str] = None) -> Dict[str, Any]:
        return {"synced_payments": 0, "status": "unconfigured"}


# ─── Integration Provider Registry ────────────────────────────────────────────

INTEGRATION_PROVIDER_REGISTRY: Dict[str, IIntegrationProvider] = {
    "google_calendar": GoogleCalendarProvider(),
    "hubspot": HubSpotProvider(),
    "stripe": StripeProvider(),
}


def get_provider(name: str) -> Optional[IIntegrationProvider]:
    return INTEGRATION_PROVIDER_REGISTRY.get(name)
