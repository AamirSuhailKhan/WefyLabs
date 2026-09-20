import time
import json
import logging
from typing import Dict, Any, Optional, List, Set, Tuple

logger = logging.getLogger(__name__)

# Fallback local memory store for dev / fallback when Redis is unreachable
_memory_cache_store: Dict[str, Tuple[float, str]] = {}
_tag_index: Dict[str, Set[str]] = {}

class CacheTTL:
    PERMISSIONS = 900       # 15 mins
    ORGANIZATIONS = 3600    # 1 hour
    USERS = 1800            # 30 mins
    PROPERTIES = 1800       # 30 mins
    SETTINGS = 3600         # 1 hour
    TAGS = 3600             # 1 hour
    PIPELINES = 3600        # 1 hour
    FEATURE_FLAGS = 300     # 5 mins
    API_KEYS = 900          # 15 mins
    # ─── Search Platform (Part 7) ──────────────────────────────────
    SEARCH_RESULTS = 60     # 60 seconds — frequent query results
    AUTOCOMPLETE = 30       # 30 seconds — sub-100ms target
    FACETS = 120            # 2 minutes — facet aggregations
    SAVED_SEARCHES = 600    # 10 minutes — rarely change


class AsyncQueryCacheService:
    """
    Enterprise Cache Service with TTL support, fallback memory cache,
    and tag-based bulk invalidation.
    """

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        if key not in _memory_cache_store:
            return None
        expires_at, raw_json = _memory_cache_store[key]
        if time.time() > expires_at:
            cls.invalidate(key)
            return None
        try:
            return json.loads(raw_json)
        except Exception:
            return None

    @classmethod
    def set(cls, key: str, data: Any, ttl_seconds: int = 300, tags: Optional[List[str]] = None) -> None:
        expires_at = time.time() + ttl_seconds
        raw_json = json.dumps(data, default=str)
        _memory_cache_store[key] = (expires_at, raw_json)

        if tags:
            for tag in tags:
                if tag not in _tag_index:
                    _tag_index[tag] = set()
                _tag_index[tag].add(key)

    @classmethod
    def invalidate(cls, key: str) -> None:
        _memory_cache_store.pop(key, None)

    @classmethod
    def invalidate_tag(cls, tag: str) -> None:
        """Invalidates all cached keys associated with a specific tag."""
        keys = _tag_index.pop(tag, set())
        for key in keys:
            _memory_cache_store.pop(key, None)
        logger.info(f"[CACHE] Invalidated tag '{tag}' ({len(keys)} keys cleared)")

    @classmethod
    def clear(cls) -> None:
        _memory_cache_store.clear()
        _tag_index.clear()


class QueryCacheWrapper:
    async def get(self, key: str) -> Optional[Any]:
        return AsyncQueryCacheService.get(key)

    async def set(self, key: str, data: Any, ttl_seconds: int = 300, tags: Optional[List[str]] = None) -> None:
        AsyncQueryCacheService.set(key, data, ttl_seconds=ttl_seconds, tags=tags)

    async def invalidate(self, key: str) -> None:
        AsyncQueryCacheService.invalidate(key)

    async def invalidate_by_tag(self, tag: str) -> None:
        AsyncQueryCacheService.invalidate_tag(tag)


_query_cache_instance = QueryCacheWrapper()


def get_query_cache() -> QueryCacheWrapper:
    return _query_cache_instance
