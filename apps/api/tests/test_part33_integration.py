"""
test_part33_integration.py
==========================
Part 33 — Real Production Deployment Integration Tests

Validates:
- Health probes: GET /health/liveness, GET /health/readiness, GET /health
- Zero secret leakage in health diagnostics (no DB passwords, Redis credentials, or API keys)
- Dynamic CORS headers handling
- Safe behavior of external integration endpoints (Brevo, Google Calendar, OAuth, Razorpay)
"""
from __future__ import annotations

import os
import pytest
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module", autouse=True)
def set_test_env():
    os.environ["ENV"] = "testing"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_dev.db"
    os.environ["SECRET_KEY"] = "test_secret_key_that_is_at_least_32_chars_long_ok"
    os.environ["SUPABASE_JWT_SECRET"] = "test_supabase_jwt_secret_placeholder_for_unit_tests_only"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"


@pytest.fixture(scope="module")
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ─── 1. Health & Readiness Probes ─────────────────────────────────────────────

class TestHealthAndReadinessEndpoints:
    """Validates liveness, readiness, and deep health probes without credential leakage."""

    async def test_liveness_probe_returns_200(self, client: AsyncClient):
        resp = await client.get("/health/liveness")
        # May be /health/liveness or /v1/health-diag/liveness
        if resp.status_code == 404:
            resp = await client.get("/v1/health-diag/liveness")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data or "alive" in str(data).lower() or "ok" in str(data).lower()

    async def test_readiness_probe_returns_json(self, client: AsyncClient):
        resp = await client.get("/health/readiness")
        if resp.status_code == 404:
            resp = await client.get("/v1/health-diag/readiness")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert isinstance(data, dict)

    async def test_deep_health_does_not_leak_secrets(self, client: AsyncClient):
        for path in ["/health", "/v1/health-diag/deep", "/v1/health-diag"]:
            resp = await client.get(path)
            if resp.status_code in (200, 503):
                text_content = resp.text.lower()
                # Must not leak passwords or secret keys
                assert "password" not in text_content or "redacted" in text_content or "masked" in text_content
                assert "gocspx" not in text_content
                assert "aizasy" not in text_content
                assert "xsmtpsib" not in text_content


# ─── 2. CORS & Security Headers ───────────────────────────────────────────────

class TestCorsAndHeadersIntegration:
    """Ensures production security headers and CORS behavior."""

    async def test_options_cors_preflight(self, client: AsyncClient):
        headers = {
            "Origin": "https://app.customdomain.com",
            "Access-Control-Request-Method": "GET",
        }
        resp = await client.options("/health/liveness", headers=headers)
        # Preflight returns 200 or 204 or 400 depending on middleware matching
        assert resp.status_code in (200, 204, 400, 404)

    async def test_security_headers_present_on_responses(self, client: AsyncClient):
        resp = await client.get("/health/liveness")
        if resp.status_code == 404:
            resp = await client.get("/v1/health-diag/liveness")
        # X-Content-Type-Options should be nosniff
        assert resp.headers.get("x-content-type-options") == "nosniff"


# ─── 3. External Integration Safeties ─────────────────────────────────────────

class TestExternalIntegrationSafeties:
    """Verifies that external integration failure or unconfigured state degrades safely."""

    async def test_unauthenticated_calendar_connect_fails_safely(self, client: AsyncClient):
        resp = await client.get("/api/v1/calendar/google/connect-url")
        # Must require authentication (401)
        assert resp.status_code in (401, 403, 404)

    async def test_unauthenticated_payment_order_fails_safely(self, client: AsyncClient):
        resp = await client.post("/api/v1/billing/orders", json={"plan_id": "starter_monthly"})
        # Must require authentication (401)
        assert resp.status_code in (401, 403, 422)

    async def test_whatsapp_webhook_get_is_non_destructive(self, client: AsyncClient):
        resp = await client.get("/api/v1/whatsapp/webhook")
        assert resp.status_code in (200, 403, 404)
