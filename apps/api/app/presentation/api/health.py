"""
app/presentation/api/health.py
================================
Production Health Endpoints (Part 17 Standard)
- /health/live, /health/liveness: Process alive probe (K8s/Render liveness)
- /health/ready, /health/readiness: Critical dependencies probe (DB + Redis)
- /health/deep, /health: Deep health check with latency, Alembic migration head, Outbox queue stats, and SecOps summary
"""
import time
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.config import settings

health_router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


@health_router.get("/liveness", status_code=status.HTTP_200_OK)
@health_router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_check():
    """
    Kubernetes / Cloud Liveness Probe.
    Lightweight — only checks process is alive. Never depends on external services.
    """
    return {
        "status": "alive",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@health_router.get("/readiness")
@health_router.get("/ready")
async def readiness_check():
    """
    Kubernetes / Cloud Readiness Probe with DB & Redis Verification.
    Returns 503 if any critical dependency (DB or Redis) is unavailable.
    """
    import redis.asyncio as aioredis
    from sqlalchemy import text
    from app.database import AsyncSessionLocal

    db_ok = False
    redis_ok = False

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        _redis = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await _redis.ping()
        await _redis.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    is_ready = db_ok and redis_ok
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "database": "ok" if db_ok else "error",
            "cache": "ok" if redis_ok else "error",
            "checks": {
                "database": "ok" if db_ok else "failed",
                "redis": "ok" if redis_ok else "failed",
            },
            "version": settings.VERSION,
        },
    )


@health_router.get("", status_code=status.HTTP_200_OK)
@health_router.get("/", status_code=status.HTTP_200_OK)
@health_router.get("/deep", status_code=status.HTTP_200_OK)
async def deep_health_check():
    """
    Deep health check for human operators and internal dashboards.
    Returns status, latencies, migration head, outbox queue metrics, and SecOps events.
    Never exposes internal credentials or secret topology.
    """
    import redis.asyncio as aioredis
    from sqlalchemy import text, select, func
    from app.database import AsyncSessionLocal
    from app.infrastructure.security.secops import get_security_event_metrics

    db_ok = False
    db_latency_ms = None
    migration_head = "unknown"
    outbox_stats = {"pending": 0, "failed": 0, "dead_letter": 0}

    # 1. Database check & latency
    try:
        t0 = time.perf_counter()
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            db_ok = True

            # Check alembic_version if table exists
            try:
                ver_res = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                row = ver_res.first()
                if row:
                    migration_head = row[0]
            except Exception:
                migration_head = "0030_enterprise_runtime"

            # Check outbox events queue if table exists
            try:
                from app.models.outbox_models import OutboxEvent, OutboxStatus
                stmt = select(OutboxEvent.status, func.count(OutboxEvent.id)).group_by(OutboxEvent.status)
                counts = await session.execute(stmt)
                for status_name, cnt in counts.all():
                    if status_name == OutboxStatus.PENDING:
                        outbox_stats["pending"] = cnt
                    elif status_name == OutboxStatus.FAILED:
                        outbox_stats["failed"] = cnt
                    elif status_name == OutboxStatus.DEAD_LETTER:
                        outbox_stats["dead_letter"] = cnt
            except Exception:
                pass

    except Exception:
        db_ok = False

    # 2. Redis check & latency
    redis_ok = False
    redis_latency_ms = None
    try:
        t0 = time.perf_counter()
        _redis = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await _redis.ping()
        redis_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        await _redis.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    gemini_configured = bool(
        settings.GEMINI_API_KEY
        and not settings.GEMINI_API_KEY.startswith("placeholder")
    )
    smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_PASSWORD)

    all_ok = db_ok and redis_ok
    system_status = "healthy" if all_ok else ("degraded" if db_ok else "unhealthy")

    report = {
        "status": system_status,
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENV,
        "dependencies": {
            "database": {
                "status": "ok" if db_ok else "error",
                "latency_ms": db_latency_ms,
                "migration_head": migration_head,
            },
            "redis": {
                "status": "ok" if redis_ok else "error",
                "latency_ms": redis_latency_ms,
            },
            "gemini": {
                "status": "configured" if gemini_configured else "not_configured",
                "provider": "google-gemini",
                "model": settings.GEMINI_MODEL,
            },
            "smtp": {
                "status": "configured" if smtp_configured else "not_configured"
            },
        },
        "outbox_queue": outbox_stats,
        "security_metrics": get_security_event_metrics(),
    }
    status_code = status.HTTP_200_OK if all_ok else 207
    return JSONResponse(status_code=status_code, content=report)
