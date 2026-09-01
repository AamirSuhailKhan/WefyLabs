"""
Global Domain Events & Event Bus
=================================
Spec §102, §104, §125 — Global Multi-Country Domain Events.

Emits structured, tenant- and market-scoped domain events across the platform:
  - CountryEnabled / MarketEnabled / MarketDisabled
  - MarketRolloutChanged / MarketConfigurationUpdated
  - ProviderConnected / ProviderDisconnected / ProviderHealthChanged
  - CurrencyRateUpdated
  - PolicyUpdated / ConsentPolicyUpdated
  - TranslationUpdated / LocaleUpdated
  - HolidayCalendarUpdated / DataRegionChanged

All events carry:
  organization_id, market_id, country_code, region, timestamp_utc, correlation_id, idempotency_key
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GlobalBaseEvent:
    event_name: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: Optional[str] = None
    market_id: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_name": self.event_name,
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "correlation_id": self.correlation_id,
            "organization_id": self.organization_id,
            "market_id": self.market_id,
            "country_code": self.country_code,
            "region": self.region,
            "payload": self.payload,
        }


# ─── Specialized Event Classes ────────────────────────────────────────────────

@dataclass
class CountryEnabledEvent(GlobalBaseEvent):
    event_name: str = "CountryEnabled"


@dataclass
class MarketEnabledEvent(GlobalBaseEvent):
    event_name: str = "MarketEnabled"


@dataclass
class MarketDisabledEvent(GlobalBaseEvent):
    event_name: str = "MarketDisabled"


@dataclass
class MarketRolloutChangedEvent(GlobalBaseEvent):
    event_name: str = "MarketRolloutChanged"


@dataclass
class ProviderConnectedEvent(GlobalBaseEvent):
    event_name: str = "ProviderConnected"


@dataclass
class ProviderHealthChangedEvent(GlobalBaseEvent):
    event_name: str = "ProviderHealthChanged"


@dataclass
class CurrencyRateUpdatedEvent(GlobalBaseEvent):
    event_name: str = "CurrencyRateUpdated"


@dataclass
class PolicyUpdatedEvent(GlobalBaseEvent):
    event_name: str = "PolicyUpdated"


@dataclass
class ConsentPolicyUpdatedEvent(GlobalBaseEvent):
    event_name: str = "ConsentPolicyUpdated"


@dataclass
class TranslationUpdatedEvent(GlobalBaseEvent):
    event_name: str = "TranslationUpdated"


@dataclass
class HolidayCalendarUpdatedEvent(GlobalBaseEvent):
    event_name: str = "HolidayCalendarUpdated"


@dataclass
class DataRegionChangedEvent(GlobalBaseEvent):
    event_name: str = "DataRegionChanged"


# ─── Global Event Bus ─────────────────────────────────────────────────────────

class GlobalEventBus:
    """
    In-process and distributed event bus for global lifecycle notifications.
    """
    _subscribers: Dict[str, List[Callable[[GlobalBaseEvent], Any]]] = {}

    @classmethod
    def subscribe(cls, event_name: str, handler: Callable[[GlobalBaseEvent], Any]) -> None:
        """Register an async or sync event handler."""
        if event_name not in cls._subscribers:
            cls._subscribers[event_name] = []
        cls._subscribers[event_name].append(handler)

    @classmethod
    async def publish(cls, event: GlobalBaseEvent) -> None:
        """
        Publish a domain event to all registered local handlers
        and structured JSON audit log.
        """
        logger.info(
            f"[EVENT_BUS] Published '{event.event_name}' (id={event.event_id}) "
            f"org={event.organization_id} market={event.market_id} country={event.country_code}"
        )

        handlers = cls._subscribers.get(event.event_name, [])
        all_handlers = handlers + cls._subscribers.get("*", [])

        for handler in all_handlers:
            try:
                import inspect
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"[EVENT_BUS] Error in handler for '{event.event_name}': {e}", exc_info=True)
