import time
import logging
from typing import Dict, Any, List, Callable, Awaitable
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class DomainEvent(BaseModel):
    event_id: str
    event_name: str # LeadCreated, LeadQualified, DealWon, DealLost, MessageReceived, WorkflowExecuted, AICompleted
    tenant_id: str
    timestamp: float = Field(default_factory=time.time)
    payload: Dict[str, Any]

class DomainEventBus:
    """
    Enterprise In-Memory & Redis Pub/Sub Domain Event Bus.
    Allows plugins, webhooks, and asynchronous workers to subscribe to core CRM domain events.
    """
    _SUBSCRIBERS: Dict[str, List[Callable[[DomainEvent], Awaitable[None]]]] = {}

    @classmethod
    def subscribe(cls, event_name: str, handler: Callable[[DomainEvent], Awaitable[None]]) -> None:
        name = event_name.lower()
        if name not in cls._SUBSCRIBERS:
            cls._SUBSCRIBERS[name] = []
        cls._SUBSCRIBERS[name].append(handler)
        logger.info(f"[EventBus] Registered subscriber for domain event '{event_name}'")

    @classmethod
    async def publish(cls, event: DomainEvent) -> int:
        name = event.event_name.lower()
        handlers = cls._SUBSCRIBERS.get(name, [])
        count = 0
        for handler in handlers:
            try:
                await handler(event)
                count += 1
            except Exception as e:
                logger.error(f"[EventBus Error] Exception handling event '{event.event_name}': {e}")
        
        # Also trigger wildcard listeners
        wildcard_handlers = cls._SUBSCRIBERS.get("*", [])
        for handler in wildcard_handlers:
            try:
                await handler(event)
                count += 1
            except Exception as e:
                logger.error(f"[EventBus Wildcard Error] {e}")

        return count

    @classmethod
    def clear_subscribers(cls) -> None:
        cls._SUBSCRIBERS.clear()
