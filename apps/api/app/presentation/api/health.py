"""
app/presentation/api/health.py
================================
Production Health Endpoints
- /health/liveness: Process alive probe (K8s/Render liveness)
- /health/readiness: Critical dependencies probe (DB + Redis)
- /health: Deep health check with dependency status for operators
"""
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.config import settings

health_router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


@health_router.get("/liveness", status_code=status.HTTP_200_OK)
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
async def health_check():
    """
    Deep health check for human operators and internal dashboards.
    Returns status of all major dependencies.
    Never exposes internal credentials or secret topology.
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

    gemini_configured = bool(
        settings.GEMINI_API_KEY
        and not settings.GEMINI_API_KEY.startswith("placeholder")
    )
    smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_PASSWORD)

    all_ok = db_ok and redis_ok
    report = {
        "status": "ok" if all_ok else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENV,
        "dependencies": {
            "database": {"status": "ok" if db_ok else "error"},
            "redis": {"status": "ok" if redis_ok else "error"},
            "gemini": {"status": "configured" if gemini_configured else "not_configured"},
            "smtp": {"status": "configured" if smtp_configured else "not_configured"},
        },
    }
    status_code = status.HTTP_200_OK if all_ok else 207
    return JSONResponse(status_code=status_code, content=report)
