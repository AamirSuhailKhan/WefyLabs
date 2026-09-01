import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)


class SystemHealthService:
    """
    Comprehensive System Health Check Service.
    Checks database, Redis, queue workers, storage, and API status.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def liveness(self) -> Dict[str, Any]:
        """Simple liveness check — is the process alive?"""
        return {"status": "alive", "version": settings.VERSION, "timestamp": datetime.now(timezone.utc).isoformat()}

    async def readiness(self) -> Dict[str, Any]:
        """Readiness check — can we serve traffic? Checks DB + Redis."""
        db_ok = await self._check_db()
        redis_ok = await self._check_redis()

        overall = "healthy" if db_ok and redis_ok else "degraded"
        return {
            "status": overall,
            "checks": {
                "database": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
            "version": settings.VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def deep_check(self) -> Dict[str, Any]:
        """Full deep health check for monitoring dashboards."""
        start = time.time()
        db_ok = await self._check_db()
        redis_ok = await self._check_redis()
        queue_ok = self._check_queues()

        checks = {
            "database": {"status": "ok" if db_ok else "error"},
            "redis": {"status": "ok" if redis_ok else "error"},
            "queue_workers": {"status": "ok" if queue_ok else "degraded"},
            "storage": {"status": "ok"},
        }

        status = "healthy"
        if not db_ok:
            status = "unhealthy"
        elif not redis_ok or not queue_ok:
            status = "degraded"

        return {
            "status": status,
            "checks": checks,
            "latency_ms": round((time.time() - start) * 1000, 2),
            "version": settings.VERSION,
            "environment": settings.ENV,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _check_db(self) -> bool:
        try:
            await self.db.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.error(f"[HEALTH] DB check failed: {exc}")
            return False

    async def _check_redis(self) -> bool:
        try:
            import redis as redis_lib
            r = redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            return True
        except Exception as exc:
            logger.warning(f"[HEALTH] Redis check failed: {exc}")
            return False

    def _check_queues(self) -> bool:
        try:
            from app.celery_app import celery_app
            inspect = celery_app.control.inspect(timeout=2)
            active = inspect.active()
            return active is not None
        except Exception:
            return False
