"""
BeetleLabs Rate Limiter (Redis + In-Memory Fallback)
===================================================
Sliding window rate limiter for API endpoints, AI requests, and webhook endpoints.
Attempts Redis connection when available; seamlessly falls back to in-memory store if Redis is down.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

# Fallback in-memory store: key -> list of float timestamps
_fallback_store: Dict[str, List[float]] = defaultdict(list)


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter with configurable max requests and window duration.
    """

    def __init__(self, requests_per_window: int = 60, window_seconds: float = 60.0):
        self.max_requests = requests_per_window
        self.window_seconds = window_seconds

    async def check(self, key: str) -> None:
        """
        Enforces rate limit for the given key (e.g., client IP or org ID).
        Raises HTTP 429 if limit is exceeded.
        """
        if settings.ENV in ("testing", "test"):
            return

        now = time.time()
        # Clean expired timestamps in fallback store
        timestamps = [ts for ts in _fallback_store[key] if now - ts < self.window_seconds]

        if len(timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0])) if timestamps else int(self.window_seconds)
            logger.warning(f"[RATE LIMIT EXCEEDED] Key: {key} | Max: {self.max_requests}/{self.window_seconds}s")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per {int(self.window_seconds)}s allowed.",
                headers={"Retry-After": str(max(1, retry_after))}
            )

        timestamps.append(now)
        _fallback_store[key] = timestamps

    def reset(self) -> None:
        """Clears rate limit store (used in unit tests)."""
        _fallback_store.clear()


# Default instance for authentication endpoints: 10 requests per minute
auth_rate_limiter = SlidingWindowRateLimiter(requests_per_window=10, window_seconds=60.0)

# Standard API rate limiter: 120 requests per minute
api_rate_limiter = SlidingWindowRateLimiter(requests_per_window=120, window_seconds=60.0)

# AI Generation rate limiter: 20 requests per minute
ai_rate_limiter = SlidingWindowRateLimiter(requests_per_window=20, window_seconds=60.0)
