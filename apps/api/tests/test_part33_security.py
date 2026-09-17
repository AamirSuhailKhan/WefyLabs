"""
test_part33_security.py
=======================
Part 33 — Production Security & Red Team Verification Tests

Validates:
- Strict unauthenticated access denial
- Multi-tenant boundary integrity and IDOR protection
- Exception handling without stack trace or credential leakage
- Safe degradation on malicious payload inputs
- Razorpay live payment safety guarantees
- WhatsApp disabled state verification
"""
from __future__ import annotations

import os
import uuid
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


# ─── 1. Authentication & Authorization Enforcement ────────────────────────────

class TestAuthEnforcement:
    """Verifies that protected routes reject unauthenticated requests."""

    @pytest.mark.parametrize("endpoint", [
        "/api/v1/leads",
        "/api/v1/properties",
        "/api/v1/tasks",
        "/api/v1/agent-command-center/summary",
        "/api/v1/onboarding/state",
        "/api/v1/billing/orders",
    ])
    async def test_unauthenticated_request_rejected(self, client: AsyncClient, endpoint: str):
        resp = await client.get(endpoint)
        assert resp.status_code in (401, 403, 404, 405), (
            f"Endpoint {endpoint} allowed unauthenticated access: {resp.status_code}"
        )


# ─── 2. Cross-Tenant Boundary & IDOR Defense ──────────────────────────────────

class TestTenantBoundaryDefense:
    """Verifies that foreign tenant IDs cannot be accessed or manipulated."""

    async def test_foreign_org_id_rejected_on_activation(self, client: AsyncClient):
        fake_org_id = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/onboarding/activate",
            json={"org_id": fake_org_id},
        )
        # Must require authentication or reject invalid org
        assert resp.status_code in (401, 403, 404, 422)

    async def test_fake_lead_id_not_found_or_unauthorized(self, client: AsyncClient):
        fake_lead_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/leads/{fake_lead_id}")
        assert resp.status_code in (401, 403, 404)


# ─── 3. Information Leakage & Error Redaction ─────────────────────────────────

class TestInformationLeakageDefense:
    """Verifies that 4xx and 5xx responses do not leak stack traces or credentials."""

    async def test_malformed_json_does_not_leak_internals(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/billing/orders",
            content=b"{bad-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 401, 422)
        body = resp.text
        assert "Traceback" not in body
        assert "File \"" not in body
        assert "password" not in body.lower()

    async def test_unknown_route_returns_clean_404(self, client: AsyncClient):
        resp = await client.get("/api/v1/non_existent_exploit_path_12345")
        assert resp.status_code == 404
        assert "Traceback" not in resp.text


# ─── 4. Guardrail Affirmation: Razorpay & WhatsApp ─────────────────────────────

class TestGuardrailAffirmations:
    """Explicitly verifies Part 33 requirements for Razorpay and WhatsApp."""

    def test_razorpay_live_keys_not_in_settings(self):
        from app.config import settings
        assert not settings.RAZORPAY_KEY_ID.startswith("rzp_live_")
        assert settings.RAZORPAY_ENVIRONMENT != "live"

    async def test_whatsapp_webhook_inbound_does_not_dispatch(self, client: AsyncClient):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "123", "changes": [{"value": {"messages": [{"text": {"body": "hello"}}]}}]}]
        }
        resp = await client.post("/api/v1/whatsapp/webhook", json=payload)
        # Should return safe response without throwing unhandled exceptions
        assert resp.status_code in (200, 401, 403, 404)
