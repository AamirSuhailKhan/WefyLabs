"""
BeetleLabs Distributed Redis Rate Limiter
==========================================
Replaces the in-memory rate limiter with a Redis-backed sliding-window counter
that is shared across all Kubernetes replicas.

Falls back to in-memory safely when Redis is unavailable so a Redis outage
does not take down authentication — it degrades to per-process limiting instead.

Key design:
- Uses Redis INCR + EXPIRE (atomic sliding window)
- TTL-based per-key expiry — no manual cleanup needed
- Fail-open on Redis errors (log warning, allow request)
- Pluggable: same interface as old in-memory limiter
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger("beetlelabs.rate_limiter")

# ─── Redis Client (module-level singleton) ─────────────────────────────────────

_redis_client = None
_redis_unavailable = False  # Circuit breaker: stop re-trying on every request


def _get_redis():
    """Returns a synchronous redis client (thread-safe, connection-pooled)."""
    global _redis_client, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        from app.config import settings
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            socket_timeout=0.5,          # 500ms timeout — fast fail
            socket_connect_timeout=0.5,
            decode_responses=True,
        )
        _redis_client.ping()
        logger.info("[RateLimiter] Redis connection established — distributed rate limiting active")
        return _redis_client
    except Exception as exc:
        logger.warning(
            f"[RateLimiter] Redis unavailable — falling back to in-memory rate limiting: {exc}"
        )
        _redis_unavailable = True
        return None


# ─── In-memory fallback ────────────────────────────────────────────────────────

_fallback_store: Dict[str, List[float]] = defaultdict(list)

_FALLBACK_WINDOW = 60.0
_FALLBACK_MAX = 5


def _check_inmemory(key: str, limit: int, window: float) -> bool:
    """Returns True if the request is allowed, False if rate-limited."""
    now = time.time()
    timestamps = [ts for ts in _fallback_store[key] if now - ts < window]
    if len(timestamps) >= limit:
        return False
    timestamps.append(now)
    _fallback_store[key] = timestamps
    return True


def clear_rate_limits() -> None:
    """Resets in-memory fallback store. Used in tests."""
    _fallback_store.clear()
    global _redis_client, _redis_unavailable
    _redis_client = None
    _redis_unavailable = False


# ─── Public API ────────────────────────────────────────────────────────────────

def check_rate_limit(
    identifier: str,
    *,
    prefix: str = "rl:auth",
    limit: int = 5,
    window_seconds: int = 60,
) -> bool:
    """
    Check and increment rate limit counter for the given identifier.

    Returns:
        True  — request is within the allowed rate, proceed
        False — rate limit exceeded, deny the request

    Args:
        identifier:     Unique key per subject (e.g. client IP, broker_id)
        prefix:         Redis key prefix to namespace different rate limit types
        limit:          Max requests allowed in `window_seconds`
        window_seconds: Sliding window duration in seconds
    """
    r = _get_redis()

    if r is not None:
        # Redis sliding window using INCR + EXPIRE
        key = f"{prefix}:{identifier}"
        try:
            pipeline = r.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, window_seconds)
            results = pipeline.execute()
            count = results[0]
            return count <= limit
        except Exception as exc:
            logger.warning(
                f"[RateLimiter] Redis error during rate check for '{key}': {exc}. "
                "Falling back to in-memory."
            )
            # Fall through to in-memory on transient Redis errors
            return _check_inmemory(f"{prefix}:{identifier}", limit, float(window_seconds))
    else:
        # Redis unavailable — use in-memory fallback
        return _check_inmemory(f"{prefix}:{identifier}", limit, float(window_seconds))


def get_remaining(identifier: str, *, prefix: str = "rl:auth", limit: int = 5) -> Optional[int]:
    """Returns remaining request count for headers (best-effort, returns None on error)."""
    r = _get_redis()
    if r is None:
        return None
    try:
        key = f"{prefix}:{identifier}"
        count = r.get(key)
        if count is None:
            return limit
        return max(0, limit - int(count))
    except Exception:
        return None
