"""
Event Publisher — Redis Pub/Sub event publishing for identity resolution events.
Falls back gracefully if Redis is unavailable (logs warning, does not raise).
"""
import json
import logging
from typing import Optional, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

IDENTITY_EVENTS_CHANNEL = "beetlelabs:identity_resolution:events"


class IdentityEventPublisher:
    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client

    async def publish(self, event: BaseModel) -> bool:
        if not self.redis:
            logger.debug(f"[IDENTITY_EVENTS] Redis not configured. Event not published: {event.event_type}")
            return False
        try:
            payload = event.model_dump(mode="json")
            await self.redis.publish(IDENTITY_EVENTS_CHANNEL, json.dumps(payload))
            logger.info(f"[IDENTITY_EVENTS] Published: {event.event_type}")
            return True
        except Exception as e:
            logger.warning(f"[IDENTITY_EVENTS] Publish failed for {event.event_type}: {e}")
            return False
