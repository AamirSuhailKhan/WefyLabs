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


# ─── Multi-Tier Enterprise Rate Limiter (Part 17) ─────────────────────────────
from enum import Enum
from fastapi import Request, HTTPException, status


class RateLimitTier(str, Enum):
    PUBLIC = "PUBLIC"              # Anonymous traffic, landing page queries: 30 req/min
    AUTHENTICATED = "AUTHENTICATED" # Standard user CRM interaction: 120 req/min
    AI_EXPENSIVE = "AI_EXPENSIVE"   # Heavy LLM inference, predictive models: 20 req/min
    ADMIN = "ADMIN"                # Super-admin and settings operations: 60 req/min
    WEBHOOK = "WEBHOOK"            # Meta/Google inbound webhooks: 300 req/min
    BACKGROUND = "BACKGROUND"      # Internal background tasks: 600 req/min


TIER_LIMITS: Dict[RateLimitTier, tuple[int, int]] = {
    RateLimitTier.PUBLIC: (30, 60),           # 30 req / 60s
    RateLimitTier.AUTHENTICATED: (120, 60),   # 120 req / 60s
    RateLimitTier.AI_EXPENSIVE: (20, 60),     # 20 req / 60s
    RateLimitTier.ADMIN: (60, 60),            # 60 req / 60s
    RateLimitTier.WEBHOOK: (300, 60),         # 300 req / 60s
    RateLimitTier.BACKGROUND: (600, 60),      # 600 req / 60s
}


def check_tiered_rate_limit(
    tier: RateLimitTier,
    identifier: str,
    tenant_id: Optional[str] = None
) -> tuple[bool, int, int]:
    """
    Checks rate limit for a specific tier.
    Keys are tenant-scoped: wefylabs:{tenant}:{tier}:{identifier}
    Returns: (allowed: bool, current_count: int, limit: int)
    """
    limit, window = TIER_LIMITS.get(tier, (60, 60))
    org = tenant_id if tenant_id else "global"
    prefix = f"wefylabs:{org}:rl:{tier.value.lower()}"

    r = _get_redis()
    key = f"{prefix}:{identifier}"

    if r is not None:
        try:
            pipeline = r.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, window)
            results = pipeline.execute()
            count = results[0]
            return (count <= limit, count, limit)
        except Exception as exc:
            logger.warning(f"[TieredRateLimiter] Redis error: {exc}. Using fallback.")

    # In-memory fallback
    now = time.time()
    timestamps = [ts for ts in _fallback_store[key] if now - ts < window]
    count = len(timestamps) + 1
    if len(timestamps) >= limit:
        return (False, count, limit)
    timestamps.append(now)
    _fallback_store[key] = timestamps
    return (True, count, limit)


def enforce_rate_limit(tier: RateLimitTier):
    """
    FastAPI dependency factory enforcing tiered rate limits on routes.
    """
    async def dependency(request: Request):
        from app.config import settings
        if settings.ENV in ("testing", "test"):
            return

        client_ip = request.client.host if request.client else "127.0.0.1"
        tenant_header = request.headers.get("X-WefyLabs-Organization-Id")
        allowed, count, limit = check_tiered_rate_limit(
            tier=tier,
            identifier=client_ip,
            tenant_id=tenant_header
        )
        if not allowed:
            from app.infrastructure.security.secops import record_security_event, SecurityEventType
            record_security_event(
                SecurityEventType.RATE_LIMIT,
                tenant_id=tenant_header,
                ip=client_ip,
                details=f"Rate limit exceeded on {tier.value} tier ({count}/{limit})"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for tier '{tier.value}'. Maximum {limit} requests per minute.",
                headers={"Retry-After": "60"}
            )
    return dependency

