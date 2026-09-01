"""
Volume 2 PART 2 — Enrichment Event Publisher
"""
import logging
import json
from typing import Any, Dict, Optional
from pydantic import BaseModel
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes enrichment lifecycle events to Redis Pub/Sub & event channels.
    """
    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client

    async def publish(self, channel: str, event: BaseModel) -> bool:
        event_dict = event.model_dump()
        payload_str = json.dumps(event_dict)
        logger.info(f"[ENRICHMENT_EVENT] Publishing to channel '{channel}': {payload_str}")
        
        if self.redis:
            try:
                await self.redis.publish(channel, payload_str)
                return True
            except Exception as e:
                logger.error(f"[ENRICHMENT_EVENT] Failed to publish to Redis: {e}")
                return False
        return True
