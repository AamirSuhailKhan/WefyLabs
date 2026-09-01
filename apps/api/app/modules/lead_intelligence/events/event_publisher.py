"""
Event Publisher — Redis Pub/Sub for Lead Intelligence Engine
============================================================
Publishes domain events to Redis channel 'beetlelabs:lead_intelligence:events'.
"""
import json
import logging
from typing import Optional, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

INTELLIGENCE_EVENTS_CHANNEL = "beetlelabs:lead_intelligence:events"


class IntelligenceEventPublisher:
    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client

    async def publish(self, event: BaseModel) -> bool:
        if not self.redis:
            logger.debug(f"[INTELLIGENCE_EVENTS] Redis not configured. Event not published: {event.event_type}")
            return False
        try:
            payload = event.model_dump(mode="json")
            await self.redis.publish(INTELLIGENCE_EVENTS_CHANNEL, json.dumps(payload))
            logger.info(f"[INTELLIGENCE_EVENTS] Published: {event.event_type}")
            return True
        except Exception as e:
            logger.warning(f"[INTELLIGENCE_EVENTS] Publish failed for {event.event_type}: {e}")
            return False
