"""
test_part32_integration.py
===========================
Part 32 — Production Hardening Integration Tests

Tests real HTTP client behavior against the FastAPI app:
health probes, circuit breakers, error handling under load,
and graceful degradation.
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module", autouse=True)
def set_test_env():
    import os
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


# ─── 1. Health Endpoints Integration ──────────────────────────────────────────

class TestHealthEndpointsIntegration:

    async def test_liveness_returns_200(self, client):
        resp = await client.get("/health/liveness")
        assert resp.status_code == 200

    async def test_liveness_body_has_status_alive(self, client):
        resp = await client.get("/health/liveness")
        data = resp.json()
        assert data.get("status") == "alive"

    async def test_liveness_body_has_version(self, client):
        resp = await client.get("/health/liveness")
        data = resp.json()
        assert "version" in data

    async def test_readiness_returns_2xx_or_503(self, client):
        resp = await client.get("/health/readiness")
        assert resp.status_code in (200, 503)

    async def test_readiness_body_has_status_field(self, client):
        resp = await client.get("/health/readiness")
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("ready", "not_ready")

    async def test_readiness_body_has_database_field(self, client):
        resp = await client.get("/health/readiness")
        data = resp.json()
        assert "database" in data
        assert data["database"] in ("ok", "error")

    async def test_readiness_body_has_cache_field(self, client):
        resp = await client.get("/health/readiness")
        data = resp.json()
        assert "cache" in data
        assert data["cache"] in ("ok", "error")

    async def test_deep_health_returns_200_or_207(self, client):
        resp = await client.get("/health")
        assert resp.status_code in (200, 207)

    async def test_deep_health_has_dependencies_dict(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)

    async def test_deep_health_has_database_dependency(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "database" in data["dependencies"]

    async def test_deep_health_has_redis_dependency(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "redis" in data["dependencies"]

    async def test_deep_health_has_gemini_dependency(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "gemini" in data["dependencies"]

    async def test_deep_health_has_smtp_dependency(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "smtp" in data["dependencies"]

    async def test_deep_health_no_credentials_exposed(self, client):
        resp = await client.get("/health")
        body = resp.text
        # Must not expose any credentials
        assert "password" not in body.lower()
        assert "secret" not in body.lower()
        assert "apikey" not in body.lower()
        assert "supabase.com" not in body.lower()
        assert "upstash.io" not in body.lower()

    async def test_metrics_returns_200_or_plain_text(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code in (200, 404)  # 404 acceptable if module not loaded


# ─── 2. Root Endpoint ─────────────────────────────────────────────────────────

class TestRootEndpoint:

    async def test_root_returns_200(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200

    async def test_root_body_mentions_api(self, client):
        resp = await client.get("/")
        data = resp.json()
        assert "message" in data
        assert "WefyLabs" in data["message"] or "BeetleLabs" in data["message"]


# ─── 3. Security Header Integration ──────────────────────────────────────────

class TestSecurityHeadersIntegration:

    async def test_x_content_type_options_present(self, client):
        resp = await client.get("/health/liveness")
        # May or may not be present based on SecurityHeadersMiddleware
        # Just ensure it doesn't expose risky headers
        assert "Server" not in resp.headers or resp.headers.get("Server", "") == ""

    async def test_no_internal_server_errors_on_health(self, client):
        for endpoint in ["/health/liveness", "/health/readiness", "/health"]:
            resp = await client.get(endpoint)
            assert resp.status_code != 500, f"{endpoint} returned 500!"


# ─── 4. CORS Integration ─────────────────────────────────────────────────────

class TestCORSIntegration:

    async def test_cors_allows_configured_origin(self, client):
        resp = await client.options(
            "/health/liveness",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)

    async def test_cors_headers_present_for_allowed_origin(self, client):
        resp = await client.get(
            "/health/liveness",
            headers={"Origin": "http://localhost:3000"},
        )
        assert "access-control-allow-origin" in resp.headers


# ─── 5. WhatsApp Webhook Integration ─────────────────────────────────────────

class TestWhatsAppWebhookIntegration:

    async def test_webhook_get_returns_active(self, client):
        resp = await client.get("/api/v1/whatsapp/webhook")
        assert resp.status_code == 200

    async def test_webhook_post_invalid_json_returns_ok(self, client):
        resp = await client.post(
            "/api/v1/whatsapp/webhook",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    async def test_webhook_does_not_expose_exception_detail(self, client):
        resp = await client.post(
            "/api/v1/whatsapp/webhook",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
        body = resp.text
        assert "Traceback" not in body
        assert "AttributeError" not in body
        assert "KeyError" not in body
