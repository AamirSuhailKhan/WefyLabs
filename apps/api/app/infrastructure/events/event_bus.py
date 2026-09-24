import asyncio
import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Callable, Dict, List, Any, Awaitable, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ActorContext(BaseModel):
    user_id: str = "system"
    role: str = "system"
    actor_type: str = "system"  # user | system | ai | webhook

class DomainEvent(BaseModel):
    """Base Enterprise Domain Event emitted across BeetleLabs CRM lifecycle."""
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    organization_id: str = "global"
    workspace_id: str = "default"
    actor: ActorContext = Field(default_factory=ActorContext)
    correlation_id: str = Field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}")
    version: str = "1.0"
    payload: Dict[str, Any] = Field(default_factory=dict)

EventHandler = Callable[[DomainEvent], Awaitable[None]]

class StandardDomainEvents:
    ORGANIZATION_CREATED = "OrganizationCreated"
    USER_CREATED = "UserCreated"
    CONTACT_CREATED = "ContactCreated"
    LEAD_CREATED = "LeadCreated"
    LEAD_UPDATED = "LeadUpdated"
    LEAD_ASSIGNED = "LeadAssigned"
    LEAD_QUALIFIED = "LeadQualified"
    LEAD_MERGED = "LeadMerged"
    CONVERSATION_STARTED = "ConversationStarted"
    CONVERSATION_CLOSED = "ConversationClosed"
    MEETING_BOOKED = "MeetingBooked"
    TASK_CREATED = "TaskCreated"
    TASK_COMPLETED = "TaskCompleted"
    PROPERTY_VIEWED = "PropertyViewed"
    PROPERTY_SHARED = "PropertyShared"
    PIPELINE_CHANGED = "PipelineChanged"
    STAGE_CHANGED = "StageChanged"
    AI_QUALIFICATION_COMPLETED = "AIQualificationCompleted"
    # Canonical Part 1 Customer Intelligence Events
    CONVERSATION_CREATED = "conversation.created"
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_CREATED = "message.created"
    CUSTOMER_REQUIREMENT_UPDATED = "customer.requirement_updated"
    CUSTOMER_PREFERENCE_UPDATED = "customer.preference_updated"
    # Canonical Part 2 Property Intelligence Events
    PROPERTY_CREATED = "property.created"
    PROPERTY_UPDATED = "property.updated"
    PROPERTY_PRICE_CHANGED = "property.price_changed"
    PROPERTY_AVAILABILITY_CHANGED = "property.availability_changed"
    PROPERTY_ARCHIVED = "property.archived"
    # Webhook Integration Events
    WEBHOOK_RECEIVED = "webhook.received"
    WEBHOOK_PROCESSED = "webhook.processed"
    WEBHOOK_FAILED = "webhook.failed"
    WEBHOOK_SIGNATURE_FAILED = "webhook.signature_failed"
    WEBHOOK_REPLAY_BLOCKED = "webhook.replay_blocked"

class DomainEventBus:
    """
    Centralized Enterprise Event Bus powering CRM automation, background queues,
    AI indexing pipelines, analytics, and real-time event streaming.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DomainEventBus, cls).__new__(cls)
            cls._instance._handlers = {}
            cls._instance._wildcard_handlers = []
        return cls._instance

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribes an asynchronous handler to a specific domain event topic."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"[EVENT BUS] Subscribed handler to event topic: '{event_type}'")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribes an asynchronous handler to ALL domain events (e.g. Audit / Analytics / Logging)."""
        self._wildcard_handlers.append(handler)
        logger.info("[EVENT BUS] Subscribed wildcard handler for all domain events")

    async def publish(self, event: DomainEvent) -> None:
        """Publishes a domain event asynchronously to all subscribed listeners."""
        logger.info(
            f"[EVENT PUBLISHED] [{event.event_type}] EventID: {event.event_id} | "
            f"Org: {event.organization_id} | CorrID: {event.correlation_id}"
        )
        
        # Collect topic-specific and wildcard handlers
        handlers = list(self._handlers.get(event.event_type, [])) + list(self._wildcard_handlers)
        if not handlers:
            return

        tasks = []
        for handler in handlers:
            try:
                tasks.append(handler(event))
            except Exception as exc:
                logger.error(f"[EVENT BUS ERROR] Error scheduling handler for {event.event_type}: {exc}", exc_info=True)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.error(f"[EVENT BUS HANDLER FAILURE] Execution error: {res}", exc_info=res)

event_bus = DomainEventBus()
