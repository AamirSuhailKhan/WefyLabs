"""
Identity Cache — Redis caching for Identity nodes, similarity scores, and candidate lists.
TTL strategy: identities cached 1h, candidate lists 10min, similarity scores 30min.
Falls back gracefully when Redis is unavailable.
"""
import json
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

IDENTITY_TTL = 3600         # 1 hour
CANDIDATES_TTL = 600        # 10 minutes
SIMILARITY_TTL = 1800       # 30 minutes


class IdentityCache:
    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client

    async def get_identity(self, identity_id: str) -> Optional[Dict]:
        return await self._get(f"identity:{identity_id}")

    async def set_identity(self, identity_id: str, data: Dict):
        await self._set(f"identity:{identity_id}", data, IDENTITY_TTL)

    async def get_candidates(self, cache_key: str) -> Optional[list]:
        return await self._get(f"candidates:{cache_key}")

    async def set_candidates(self, cache_key: str, data: list):
        await self._set(f"candidates:{cache_key}", data, CANDIDATES_TTL)

    async def invalidate_identity(self, identity_id: str):
        await self._delete(f"identity:{identity_id}")

    async def _get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None
        try:
            raw = await self.redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.debug(f"[IDENTITY_CACHE] Get failed for {key}: {e}")
            return None

    async def _set(self, key: str, value: Any, ttl: int):
        if not self.redis:
            return
        try:
            await self.redis.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.debug(f"[IDENTITY_CACHE] Set failed for {key}: {e}")

    async def _delete(self, key: str):
        if not self.redis:
            return
        try:
            await self.redis.delete(key)
        except Exception:
            pass
