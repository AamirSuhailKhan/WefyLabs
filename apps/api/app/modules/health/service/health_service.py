"""
Enterprise Subsystem Health Diagnostics Service
================================================
Performs deep component-level health checks across:
- PostgreSQL Database Connection Pool & Ping
- Redis Cache Latency & Memory
- Celery Task Queue Worker status & backlog
- Search Provider Engine status
- AI Engine readiness
- External Integrations readiness
"""
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


class DeepHealthService:
    """Comprehensive multi-subsystem diagnostic health inspector."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_liveness(self) -> Dict[str, Any]:
        """Simple liveness probe — process is alive."""
        return {
            "status": "alive",
            "version": settings.VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def check_readiness(self) -> Dict[str, Any]:
        """Readiness probe — tests DB + Redis dependencies."""
        db_res = await self.check_database()
        redis_res = await self.check_redis()

        is_ready = db_res["status"] == "healthy" and redis_res["status"] == "healthy"
        return {
            "status": "ready" if is_ready else "not_ready",
            "subsystems": {
                "database": db_res["status"],
                "redis": redis_res["status"],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def check_database(self) -> Dict[str, Any]:
        start = time.time()
        try:
            await self.db.execute(text("SELECT 1"))
            latency_ms = round((time.time() - start) * 1000, 2)
            return {"subsystem": "database", "status": "healthy", "latency_ms": latency_ms}
        except Exception as exc:
            return {"subsystem": "database", "status": "unhealthy", "latency_ms": -1.0, "error": str(exc)}

    async def check_redis(self) -> Dict[str, Any]:
        start = time.time()
        try:
            import redis as redis_lib
            r = redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            latency_ms = round((time.time() - start) * 1000, 2)
            info = r.info("memory")
            return {
                "subsystem": "redis",
                "status": "healthy",
                "latency_ms": latency_ms,
                "used_memory_human": info.get("used_memory_human", "N/A"),
            }
        except Exception as exc:
            return {"subsystem": "redis", "status": "degraded", "latency_ms": -1.0, "error": str(exc)}

    async def check_queues(self) -> Dict[str, Any]:
        start = time.time()
        try:
            from app.celery_app import celery_app
            inspect = celery_app.control.inspect(timeout=2)
            active = inspect.active() or {}
            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "subsystem": "queues",
                "status": "healthy" if active else "degraded",
                "latency_ms": latency_ms,
                "active_workers": len(active),
            }
        except Exception as exc:
            return {"subsystem": "queues", "status": "degraded", "latency_ms": -1.0, "error": str(exc)}

    async def check_search(self) -> Dict[str, Any]:
        start = time.time()
        try:
            from app.modules.search.providers.search_providers import PostgreSQLSearchProvider
            provider = PostgreSQLSearchProvider(self.db)
            res = await provider.health()
            latency_ms = round((time.time() - start) * 1000, 2)
            return {"subsystem": "search", "status": res.get("status", "healthy"), "latency_ms": latency_ms}
        except Exception as exc:
            return {"subsystem": "search", "status": "degraded", "latency_ms": -1.0, "error": str(exc)}

    async def check_ai(self) -> Dict[str, Any]:
        """Truthfully evaluates AI reasoning engine configuration."""
        gemini_key = getattr(settings, "GEMINI_API_KEY", "") or ""
        model = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash")
        is_placeholder = any([
            not gemini_key,
            gemini_key.startswith("placeholder"),
            gemini_key.startswith("AIzaSy_placeholder"),
        ])

        if is_placeholder:
            return {
                "subsystem": "ai",
                "status": "CONFIGURATION_REQUIRED",
                "provider": "google_gemini",
                "model": model,
                "details": "GEMINI_API_KEY is not configured.",
            }

        return {
            "subsystem": "ai",
            "status": "LIVE",
            "provider": "google_gemini",
            "model": model,
            "details": "Google Gemini AI provider configured with real credentials.",
        }

    async def check_integrations(self) -> Dict[str, Any]:
        """Truthfully audits external provider integration operational readiness."""
        providers = {}

        # 1. WhatsApp Cloud / 360Dialog
        wa_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
        phone_id = getattr(settings, "PHONE_NUMBER_ID", "") or ""
        is_wa_configured = bool(wa_token and phone_id and "placeholder" not in wa_token.lower())
        providers["whatsapp"] = {
            "channel": "whatsapp",
            "provider": "whatsapp_cloud",
            "status": "LIVE" if is_wa_configured else "CONFIGURATION_REQUIRED",
            "details": "Meta Cloud API credentials ready" if is_wa_configured else "Meta Cloud Token/Phone ID required",
        }

        # 2. Email SMTP (Brevo Free via SMTP / Generic SMTP)
        smtp_host = getattr(settings, "SMTP_HOST", "") or ""
        smtp_user = getattr(settings, "SMTP_USER", "") or getattr(settings, "SMTP_USERNAME", "") or ""
        smtp_pass = getattr(settings, "SMTP_PASSWORD", "") or ""
        is_smtp_configured = bool(
            smtp_host 
            and smtp_user 
            and smtp_pass
            and "placeholder" not in smtp_host.lower()
            and "example.com" not in smtp_host.lower()
            and "placeholder" not in smtp_pass.lower()
            and "mock_password" not in smtp_pass.lower()
        )
        providers["email_smtp"] = {
            "channel": "email",
            "provider": "email_smtp",
            "status": "LIVE" if is_smtp_configured else "CONFIGURATION_REQUIRED",
            "details": "Brevo SMTP credentials ready" if is_smtp_configured else "SMTP host and credentials required",
        }

        # 3. Razorpay Payments
        rzp_key = getattr(settings, "RAZORPAY_KEY_ID", "") or ""
        is_rzp_live = rzp_key.startswith("rzp_live_")
        is_rzp_test = rzp_key.startswith("rzp_test_") and "placeholder" not in rzp_key
        providers["razorpay"] = {
            "channel": "payments",
            "provider": "razorpay",
            "status": "LIVE" if is_rzp_live else ("TEST_MODE" if is_rzp_test else "CONFIGURATION_REQUIRED"),
            "details": "Razorpay live credentials active" if is_rzp_live else "Live Razorpay credentials required",
        }

        # 4. Google Calendar OAuth
        g_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or ""
        is_g_configured = bool(g_client_id and "placeholder" not in g_client_id.lower() and g_client_id.endswith(".apps.googleusercontent.com"))
        providers["google_calendar"] = {
            "channel": "calendar",
            "provider": "google_calendar",
            "status": "LIVE" if is_g_configured else "CONFIGURATION_REQUIRED",
            "details": "Google OAuth client ID configured" if is_g_configured else "Google OAuth Client ID & Secret required",
        }

        all_live = all(p["status"] == "LIVE" for p in providers.values())
        return {
            "subsystem": "integrations",
            "status": "LIVE" if all_live else "CONFIGURATION_REQUIRED",
            "providers": providers,
        }

    async def full_diagnostic(self) -> Dict[str, Any]:
        """Runs all subsystem checks in parallel diagnostic report."""
        db_res = await self.check_database()
        redis_res = await self.check_redis()
        queues_res = await self.check_queues()
        search_res = await self.check_search()
        ai_res = await self.check_ai()
        integrations_res = await self.check_integrations()

        overall = "healthy"
        if db_res["status"] == "unhealthy":
            overall = "unhealthy"
        elif any(r["status"] in ("degraded", "CONFIGURATION_REQUIRED") for r in [redis_res, queues_res, search_res, ai_res]):
            overall = "degraded"

        return {
            "status": overall,
            "version": settings.VERSION,
            "environment": settings.ENV,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subsystems": {
                "database": db_res,
                "redis": redis_res,
                "queues": queues_res,
                "search": search_res,
                "ai": ai_res,
                "integrations": integrations_res,
            }
        }
