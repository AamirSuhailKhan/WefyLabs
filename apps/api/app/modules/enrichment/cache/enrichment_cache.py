"""
Volume 2 PART 2 — Enrichment Cache (Redis Caching)
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EnrichmentCache:
    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None
        try:
            val = await self.redis.get(f"enrichment:{key}")
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning(f"[ENRICHMENT_CACHE] Get failed for key {key}: {e}")
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> bool:
        if not self.redis:
            return False
        try:
            await self.redis.setex(f"enrichment:{key}", ttl_seconds, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"[ENRICHMENT_CACHE] Set failed for key {key}: {e}")
            return False
