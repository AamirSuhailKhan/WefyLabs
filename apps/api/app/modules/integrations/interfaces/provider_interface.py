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
    provider_name = "google_calendar"
    provider_display_name = "Google Calendar"

    async def connect(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> bool:
        # TODO: OAuth2 flow with Google Calendar API
        return True

    async def disconnect(self, integration_id: str) -> bool:
        # TODO: Revoke OAuth token
        return True

    async def health_check(self, integration_id: str) -> bool:
        # TODO: Test Google Calendar API connectivity
        return True

    async def sync(self, integration_id: str, since_timestamp: Optional[str] = None) -> Dict[str, Any]:
        # TODO: Sync calendar events as Meetings
        return {"synced_events": 0}


class HubSpotProvider(IIntegrationProvider):
    provider_name = "hubspot"
    provider_display_name = "HubSpot"

    async def connect(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> bool:
        return True

    async def disconnect(self, integration_id: str) -> bool:
        return True

    async def health_check(self, integration_id: str) -> bool:
        return True

    async def sync(self, integration_id: str, since_timestamp: Optional[str] = None) -> Dict[str, Any]:
        return {"synced_contacts": 0, "synced_deals": 0}


class StripeProvider(IIntegrationProvider):
    provider_name = "stripe"
    provider_display_name = "Stripe"

    async def connect(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> bool:
        return True

    async def disconnect(self, integration_id: str) -> bool:
        return True

    async def health_check(self, integration_id: str) -> bool:
        return True

    async def sync(self, integration_id: str, since_timestamp: Optional[str] = None) -> Dict[str, Any]:
        return {"synced_payments": 0}


# ─── Integration Provider Registry ────────────────────────────────────────────

INTEGRATION_PROVIDER_REGISTRY: Dict[str, IIntegrationProvider] = {
    "google_calendar": GoogleCalendarProvider(),
    "hubspot": HubSpotProvider(),
    "stripe": StripeProvider(),
}


def get_provider(name: str) -> Optional[IIntegrationProvider]:
    return INTEGRATION_PROVIDER_REGISTRY.get(name)
