"""
Health Aggregator
=================
Unified health check hub that aggregates readiness/liveness probes
from all critical WefyLabs sub-systems:

  - Database (PostgreSQL)
  - Redis / Cache
  - Celery Worker queues
  - AI Gateway (LLM provider)
  - Search Engine (pgvector / Elasticsearch)
  - External Webhooks
  - SLO compliance

Probe results are cached for 10 s to avoid stampede under load.
"""
import time
import logging
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Callable, Awaitable, Any
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 10


class ComponentStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN   = "unknown"


@dataclass
class ComponentHealth:
    name: str
    status: ComponentStatus
    latency_ms: Optional[float] = None
    detail: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None


@dataclass
class SystemHealth:
    overall: ComponentStatus
    components: Dict[str, ComponentHealth]
    checked_at: str
    version: str = "build-12"

    def is_ready(self) -> bool:
        return self.overall in (ComponentStatus.HEALTHY, ComponentStatus.DEGRADED)

    def is_live(self) -> bool:
        return self.overall != ComponentStatus.UNHEALTHY


ProbeFunc = Callable[[], Awaitable[ComponentHealth]]


class HealthAggregator:
    """
    Aggregates health from registered probe functions.

    Usage:
        agg = HealthAggregator()
        agg.register("database", _check_db)
        health = await agg.check_all()
    """

    def __init__(self):
        self._probes: Dict[str, ProbeFunc] = {}
        self._cache: Optional[SystemHealth] = None
        self._cache_ts: float = 0.0

    def register(self, name: str, probe: ProbeFunc) -> None:
        self._probes[name] = probe
        logger.debug(f"[HEALTH] Registered probe: {name}")

    async def check(self, name: str) -> ComponentHealth:
        probe = self._probes.get(name)
        if not probe:
            return ComponentHealth(
                name=name,
                status=ComponentStatus.UNKNOWN,
                detail="No probe registered",
            )
        try:
            start = time.monotonic()
            result = await asyncio.wait_for(probe(), timeout=5.0)
            elapsed = (time.monotonic() - start) * 1000
            result.latency_ms = round(elapsed, 2)
            return result
        except asyncio.TimeoutError:
            return ComponentHealth(name=name, status=ComponentStatus.UNHEALTHY, error="Probe timeout (5s)")
        except Exception as exc:
            return ComponentHealth(name=name, status=ComponentStatus.UNHEALTHY, error=str(exc))

    async def check_all(self, force: bool = False) -> SystemHealth:
        now = time.monotonic()
        if not force and self._cache and (now - self._cache_ts) < CACHE_TTL_SECONDS:
            return self._cache

        tasks = {name: self.check(name) for name in self._probes}
        results: Dict[str, ComponentHealth] = {}

        for name, coro in tasks.items():
            results[name] = await coro

        # Aggregate overall status
        statuses = [c.status for c in results.values()]
        if all(s == ComponentStatus.HEALTHY for s in statuses):
            overall = ComponentStatus.HEALTHY
        elif any(s == ComponentStatus.UNHEALTHY for s in statuses):
            overall = ComponentStatus.UNHEALTHY
        else:
            overall = ComponentStatus.DEGRADED

        system = SystemHealth(
            overall=overall,
            components=results,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )
        self._cache = system
        self._cache_ts = now
        logger.info(f"[HEALTH] System health: {overall.value} ({len(results)} components)")
        return system

    # ── Built-in lightweight probes ───────────────────────────────────────────

    @staticmethod
    async def _ping_db() -> ComponentHealth:
        """Checks DB connectivity via SQLAlchemy."""
        try:
            from app.core.database import engine
            from sqlalchemy import text
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return ComponentHealth(name="database", status=ComponentStatus.HEALTHY, detail="SELECT 1 OK")
        except Exception as exc:
            return ComponentHealth(name="database", status=ComponentStatus.UNHEALTHY, error=str(exc))

    @staticmethod
    async def _ping_redis() -> ComponentHealth:
        """Checks Redis connectivity."""
        try:
            import redis.asyncio as aioredis
            import os
            r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            await r.ping()
            await r.aclose()
            return ComponentHealth(name="redis", status=ComponentStatus.HEALTHY, detail="PING OK")
        except Exception as exc:
            return ComponentHealth(name="redis", status=ComponentStatus.UNHEALTHY, error=str(exc))

    def register_defaults(self) -> None:
        """Register the standard WefyLabs probes."""
        self.register("database", self._ping_db)
        self.register("redis",    self._ping_redis)


# Global singleton
health_aggregator = HealthAggregator()
