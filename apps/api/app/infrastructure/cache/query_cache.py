import time
from typing import Dict, Any, Optional, Tuple

_query_cache_store: Dict[str, Tuple[float, Any]] = {}

class AsyncQueryCacheService:
    """
    High-Performance Async Query Caching Service with TTL expiration.
    Reduces database load for static lookups (region metadata, broker defaults, stats).
    """

    @classmethod
    def get(cls, cache_key: str) -> Optional[Any]:
        if cache_key not in _query_cache_store:
            return None
        expires_at, data = _query_cache_store[cache_key]
        if time.time() > expires_at:
            del _query_cache_store[cache_key]
            return None
        return data

    @classmethod
    def set(cls, cache_key: str, data: Any, ttl_seconds: int = 60) -> None:
        expires_at = time.time() + ttl_seconds
        _query_cache_store[cache_key] = (expires_at, data)

    @classmethod
    def invalidate(cls, cache_key: str) -> None:
        _query_cache_store.pop(cache_key, None)

    @classmethod
    def clear(cls) -> None:
        _query_cache_store.clear()
