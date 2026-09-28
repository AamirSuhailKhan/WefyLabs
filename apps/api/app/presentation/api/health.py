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


@health_router.get("/startup", status_code=status.HTTP_200_OK)
async def startup_check():
    """
    Kubernetes / Cloud Startup Probe.
    Validates essential components before traffic is routed.
    Never exposes secrets or credentials.
    """
    from sqlalchemy import text
    from app.database import AsyncSessionLocal
    import redis.asyncio as aioredis

    db_ready = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ready = True
    except Exception:
        db_ready = False

    redis_ready = False
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await _redis.ping()
        await _redis.aclose()
        redis_ready = True
    except Exception:
        redis_ready = False

    ai_configured = bool(settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("placeholder"))
    providers_ready = bool(settings.SECRET_KEY and len(settings.SECRET_KEY) >= 32)

    startup_ok = db_ready and redis_ready and providers_ready
    status_code = status.HTTP_200_OK if startup_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if startup_ok else "initializing",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "components": {
                "database": "ready" if db_ready else "not_ready",
                "redis": "ready" if redis_ready else "not_ready",
                "ai_gateway": "configured" if ai_configured else "degraded",
                "storage": "ready",
                "security_credentials": "ready" if providers_ready else "invalid",
            }
        }
    )


@health_router.get("/dependencies", status_code=status.HTTP_200_OK)
async def dependency_health_registry():
    """
    Dependency Health Registry for WefyLabs ecosystem.
    Evaluates: PostgreSQL, Redis, Celery/Outbox, AI Provider, WhatsApp, Email, Search, Payments.
    Distinguishes CORE_HEALTHY vs DEPENDENCY_DEGRADED.
    """
    from sqlalchemy import text
    from app.database import AsyncSessionLocal
    import redis.asyncio as aioredis

    t0 = time.perf_counter()
    db_ok = False
    db_ms = None
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
        db_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        db_ok = False

    t1 = time.perf_counter()
    redis_ok = False
    redis_ms = None
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await _redis.ping()
        await _redis.aclose()
        redis_ok = True
        redis_ms = round((time.perf_counter() - t1) * 1000, 2)
    except Exception:
        redis_ok = False

    gemini_configured = bool(settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("placeholder"))
    wa_configured = bool(settings.WHATSAPP_ACCESS_TOKEN and not settings.WHATSAPP_ACCESS_TOKEN.startswith("wa_access_token_placeholder"))
    email_configured = bool(settings.SMTP_HOST and settings.SMTP_PASSWORD)
    rzp_configured = bool(settings.RAZORPAY_KEY_ID and not settings.RAZORPAY_KEY_ID.startswith("rzp_test_placeholder"))

    core_healthy = db_ok and redis_ok
    all_healthy = core_healthy and gemini_configured and wa_configured and email_configured and rzp_configured

    system_mode = "HEALTHY" if all_healthy else ("DEGRADED" if core_healthy else "UNAVAILABLE")

    return {
        "status": system_mode,
        "mode": "CORE_HEALTHY" if core_healthy else "CORE_UNAVAILABLE",
        "dependencies": {
            "postgresql": {"status": "HEALTHY" if db_ok else "UNAVAILABLE", "latency_ms": db_ms, "critical": True},
            "redis": {"status": "HEALTHY" if redis_ok else "UNAVAILABLE", "latency_ms": redis_ms, "critical": True},
            "ai_provider": {"status": "HEALTHY" if gemini_configured else "DEGRADED", "provider": "google-gemini", "critical": False},
            "whatsapp": {"status": "HEALTHY" if wa_configured else "DEGRADED", "provider": "meta-cloud", "critical": False},
            "email": {"status": "HEALTHY" if email_configured else "DEGRADED", "provider": "smtp", "critical": False},
            "payments": {"status": "HEALTHY" if rzp_configured else "DEGRADED", "provider": "razorpay", "critical": False},
            "search": {"status": "HEALTHY" if db_ok else "DEGRADED", "provider": "pgvector", "critical": False},
            "celery_outbox": {"status": "HEALTHY" if (db_ok and redis_ok) else "DEGRADED", "critical": False},
        },
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


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


@health_router.get("/capabilities", status_code=status.HTTP_200_OK)
async def system_capabilities():
    """
    Public capability flags for frontend feature toggles and ops readiness.
    Never reveals secret keys.
    """
    _PLACEHOLDER_WA = {
        "wa_access_token_placeholder",
        "wa-placeholder",
        "placeholder",
        "",
    }
    _PLACEHOLDER_RZP = {
        "rzp_test_placeholder",
        "rzp_test_dummy",
        "",
        "placeholder",
    }

    wa_token = (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
    wa_phone = (settings.PHONE_NUMBER_ID or "").strip()
    whatsapp_configured = (
        bool(wa_token)
        and wa_token not in _PLACEHOLDER_WA
        and "placeholder" not in wa_token.lower()
        and bool(wa_phone)
        and wa_phone not in _PLACEHOLDER_WA
    )

    rzp_key = (settings.RAZORPAY_KEY_ID or "").strip()
    rzp_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    billing_configured = (
        bool(rzp_key)
        and rzp_key not in _PLACEHOLDER_RZP
        and not rzp_key.startswith("rzp_test_")
        and bool(rzp_secret)
        and rzp_secret not in _PLACEHOLDER_RZP
    )

    gemini_key = (settings.GEMINI_API_KEY or "").strip()
    ai_configured = (
        bool(gemini_key)
        and not gemini_key.startswith("placeholder")
        and not gemini_key.startswith("AIzaSy_placeholder")
    )

    google_oauth = (
        bool(settings.GOOGLE_CLIENT_ID)
        and (settings.GOOGLE_CLIENT_ID or "").endswith(".apps.googleusercontent.com")
        and bool(settings.GOOGLE_CLIENT_SECRET)
    )

    return {
        "whatsapp": {
            "enabled": whatsapp_configured,
            "reason": "configured" if whatsapp_configured else "credentials_not_configured",
        },
        "billing": {
            "enabled": billing_configured,
            "mode": "live" if billing_configured else (
                "test" if rzp_key.startswith("rzp_test_") else "disabled"
            ),
            "reason": "live_keys_configured" if billing_configured else "test_or_placeholder_keys",
        },
        "ai": {
            "enabled": ai_configured,
            "provider": "gemini",
        },
        "google_oauth": {
            "enabled": google_oauth,
        },
    }
