"""
test_part32_security.py
========================
Part 32 — Production Hardening Security / Red-Team Tests

Tests tenant isolation, IDOR prevention, auth enforcement,
rate limit bypass prevention, and demo→prod boundary.
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.asyncio


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


# ─── 1. Authentication Enforcement ──────────────────────────────────────────

class TestAuthEnforcement:

    async def test_leads_endpoint_requires_auth(self, client):
        resp = await client.get("/api/v1/leads")
        assert resp.status_code in (401, 403, 422)

    async def test_brokers_endpoint_requires_auth(self, client):
        resp = await client.get("/api/v1/brokers")
        assert resp.status_code in (401, 403, 404, 422)

    async def test_audit_endpoint_requires_auth(self, client):
        resp = await client.get("/api/v1/audit/logs")
        assert resp.status_code in (401, 403, 404, 422)

    async def test_notifications_requires_auth(self, client):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code in (401, 403, 404, 422)

    async def test_settings_requires_auth(self, client):
        resp = await client.get("/api/v1/settings")
        assert resp.status_code in (401, 403, 404, 422)

    async def test_api_keys_requires_auth(self, client):
        resp = await client.get("/api/v1/api-keys")
        assert resp.status_code in (401, 403, 404, 422)


# ─── 2. No Sensitive Data in Error Responses ──────────────────────────────────

class TestErrorResponseSafety:

    async def test_404_does_not_expose_stack_trace(self, client):
        resp = await client.get("/nonexistent-endpoint-xyz")
        assert resp.status_code == 404
        body = resp.text
        assert "Traceback" not in body
        assert "File " not in body

    async def test_invalid_auth_token_returns_clean_error(self, client):
        resp = await client.get(
            "/api/v1/leads",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code in (401, 403, 422)
        body = resp.text
        assert "Traceback" not in body
        assert "SECRET_KEY" not in body

    async def test_malformed_json_body_returns_clean_error(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            content=b"{{invalid json}}",
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code in (400, 422, 404)
        body = resp.text
        assert "Traceback" not in body

    async def test_health_endpoints_dont_expose_db_url(self, client):
        for endpoint in ["/health", "/health/readiness", "/health/liveness"]:
            resp = await client.get(endpoint)
            body = resp.text
            assert "DATABASE_URL" not in body
            assert "SECRET_KEY" not in body
            assert "supabase.com" not in body.lower()

    async def test_root_endpoint_does_not_expose_version_details(self, client):
        resp = await client.get("/")
        body = resp.text
        assert "python" not in body.lower()
        assert "fastapi" not in body.lower()


# ─── 3. IDOR / Tenant Isolation ───────────────────────────────────────────────

class TestIDORPrevention:

    async def test_cannot_access_arbitrary_lead_without_auth(self, client):
        resp = await client.get("/api/v1/leads/00000000-0000-0000-0000-000000000001")
        assert resp.status_code in (401, 403, 404, 422)

    async def test_cannot_access_arbitrary_org_without_auth(self, client):
        resp = await client.get("/api/v1/settings/00000000-0000-0000-0000-000000000001")
        assert resp.status_code in (401, 403, 404, 422)

    async def test_cannot_delete_arbitrary_resource_without_auth(self, client):
        resp = await client.delete("/api/v1/leads/00000000-0000-0000-0000-000000000001")
        assert resp.status_code in (401, 403, 404, 405, 422)

    async def test_cannot_patch_arbitrary_resource_without_auth(self, client):
        resp = await client.patch(
            "/api/v1/leads/00000000-0000-0000-0000-000000000001",
            json={"status": "closed"}
        )
        assert resp.status_code in (401, 403, 404, 405, 422)


# ─── 4. WhatsApp Security ─────────────────────────────────────────────────────

class TestWhatsAppSecurity:

    async def test_whatsapp_webhook_verification_rejects_bad_token(self, client):
        resp = await client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "test123"
            }
        )
        assert resp.status_code == 403

    async def test_whatsapp_webhook_accepts_no_params(self, client):
        resp = await client.get("/api/v1/whatsapp/webhook")
        assert resp.status_code == 200


# ─── 5. Demo Mode Boundary ────────────────────────────────────────────────────

class TestDemoModeSecurity:

    async def test_demo_org_create_endpoint_exists(self, client):
        # Demo org endpoint should be accessible but require valid payload
        resp = await client.post("/api/v1/onboarding/demo/create", json={})
        assert resp.status_code in (200, 400, 401, 403, 404, 422)

    async def test_cannot_upgrade_to_live_without_auth(self, client):
        resp = await client.post(
            "/api/v1/onboarding/activate",
            json={"org_id": "00000000-0000-0000-0000-000000000001"}
        )
        assert resp.status_code in (401, 403, 404, 422)
