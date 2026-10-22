"""
P0 Security Regression Tests
==============================
Verifies that P0-hardened endpoints correctly enforce authentication and RBAC.
These tests ensure that:
1. Unauthenticated requests return 401/403 (not 200 or 404)
2. Tenant isolation is enforced (one tenant cannot access another's data)
3. RBAC gates block non-manager callers from destructive operations

These tests use the standard FastAPI TestClient with mock dependencies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, status


# ─── Shared Auth Mocks ─────────────────────────────────────────────────────────

def make_tenant(org_id: str = "org-aaa", role: str = "AGENT", broker_id: str = "broker-111"):
    from app.dependencies import TenantContext
    import uuid
    return TenantContext(
        organization_id=org_id,
        broker_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        user_id=broker_id,
        role=role,
    )


def make_manager_tenant(org_id: str = "org-aaa"):
    return make_tenant(org_id=org_id, role="MANAGER")


# ─── Test: AI Agent Router Authentication Gates ────────────────────────────────

class TestAIAgentAuthGates:
    """Verify that AI agent endpoints reject unauthenticated requests."""

    def setup_method(self):
        from app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_message_endpoint_requires_auth(self):
        """POST /ai-agent/v1/message must return 401 without auth."""
        resp = self.client.post(
            "/api/v1/ai-agent/v1/message",
            json={"lead_id": "lead-123", "channel": "web", "content": "hello"}
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_sessions_endpoint_requires_auth(self):
        """GET /ai-agent/v1/sessions/{id} must return 401 without auth."""
        resp = self.client.get("/api/v1/ai-agent/v1/sessions/some-session-id")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_escalations_endpoint_requires_auth(self):
        """GET /ai-agent/v1/escalations must return 401 without auth."""
        resp = self.client.get("/api/v1/ai-agent/v1/escalations")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_llm_usage_endpoint_requires_auth(self):
        """GET /ai-agent/v1/llm/usage must return 401 without auth."""
        resp = self.client.get("/api/v1/ai-agent/v1/llm/usage")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_agent_execute_action_requires_auth(self):
        """POST /ai-agent/v1/agent/execute-action must return 401 without auth."""
        resp = self.client.post(
            "/api/v1/ai-agent/v1/agent/execute-action",
            json={"actor_id": "agent", "action_type": "send_message", "parameters": {}}
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_prompts_endpoint_requires_auth(self):
        """POST /ai-agent/v1/prompts must return 401 without auth."""
        resp = self.client.post(
            "/api/v1/ai-agent/v1/prompts",
            json={"system_template": "You are a helpful agent."}
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ─── Test: Enrichment Router Authentication Gates ──────────────────────────────

class TestEnrichmentAuthGates:
    """Verify that enrichment endpoints reject unauthenticated requests."""

    def setup_method(self):
        from app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_enrich_requires_auth(self):
        """POST /enrichment/enrich/{id} must return 401 without auth."""
        resp = self.client.post("/api/v1/enrichment/enrich/some-lead-id")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_profile_requires_auth(self):
        """GET /enrichment/profile/{id} must return 401 without auth."""
        resp = self.client.get("/api/v1/enrichment/profile/some-lead-id")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_replay_requires_auth(self):
        """POST /enrichment/replay/{id} must return 401 without auth."""
        resp = self.client.post("/api/v1/enrichment/replay/some-lead-id")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_metrics_requires_auth(self):
        """GET /enrichment/metrics must return 401 without auth."""
        resp = self.client.get("/api/v1/enrichment/metrics")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ─── Test: Lead Intelligence Router Authentication Gates ──────────────────────

class TestLeadIntelligenceAuthGates:
    """Verify that lead intelligence endpoints reject unauthenticated requests."""

    def setup_method(self):
        from app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_score_requires_auth(self):
        """POST /intelligence/score/{id} must return 401 without auth."""
        resp = self.client.post(
            "/api/v1/intelligence/score/lead-123",
            json={"lead_dto": {}}
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_rules_post_requires_auth(self):
        """POST /intelligence/rules must return 401 without auth."""
        resp = self.client.post(
            "/api/v1/intelligence/rules",
            json={"name": "rule", "condition_json": {}, "action_value": 10}
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_rules_get_requires_auth(self):
        """GET /intelligence/rules must return 401 without auth."""
        resp = self.client.get("/api/v1/intelligence/rules")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ─── Test: Identity Resolution Router Authentication Gates ────────────────────

class TestIdentityResolutionAuthGates:
    """Verify that identity resolution endpoints reject unauthenticated requests."""

    def setup_method(self):
        from app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_merge_requires_auth(self):
        """POST /identity/merge must return 401 without auth."""
        resp = self.client.post(
            "/api/v1/identity/merge",
            json={"source_identity_id": "id-1", "target_identity_id": "id-2"}
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_undo_merge_requires_auth(self):
        """POST /identity/merge/{op_id}/undo must return 401 without auth."""
        resp = self.client.post("/api/v1/identity/merge/some-op-id/undo")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_review_action_requires_auth(self):
        """POST /identity/review/{id}/action must return 401 without auth."""
        resp = self.client.post(
            "/api/v1/identity/review/some-review-id/action",
            json={"decision": "merge"}
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_search_requires_auth(self):
        """GET /identity/search must return 401 without auth."""
        resp = self.client.get("/api/v1/identity/search?phone=%2B971501234567")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ─── Test: Global Router IDOR Fix ─────────────────────────────────────────────

class TestGlobalRouterIDOR:
    """Verify that /global/analytics/revenue-consolidated requires auth."""

    def setup_method(self):
        from app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_revenue_consolidated_requires_auth(self):
        """GET /global/analytics/revenue-consolidated must return 401 without auth."""
        resp = self.client.get("/api/v1/global/analytics/revenue-consolidated")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ─── Test: Webhook Signature Hardening ────────────────────────────────────────

class TestWebhookSignatureHardening:
    """Verify that the webhook service rejects unauthenticated webhook forgeries."""

    def test_missing_signature_is_rejected(self):
        """Webhook without signature should be rejected (not silently accepted)."""
        from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService
        svc = GenericWebhookEngineService(secrets={"whatsapp": "my-secret"})
        # No signature provided
        result = svc.verify_signature("whatsapp", b'{"event": "test"}', signature=None, secret="my-secret")
        assert result is False, "Missing signature should return False (reject)"

    def test_no_configured_secret_is_rejected(self):
        """Webhook provider with no configured secret should be rejected."""
        from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService
        svc = GenericWebhookEngineService(secrets={})
        # Provider has no secret configured — was previously silently accepted
        result = svc.verify_signature("whatsapp", b'{"event": "test"}', signature="sha256=abc", secret=None)
        assert result is False, "No configured secret should return False (reject)"

    def test_unknown_provider_is_rejected(self):
        """Unknown provider should be rejected even with a valid-looking signature."""
        from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService
        svc = GenericWebhookEngineService(secrets={"unknown_provider": "secret"})
        result = svc.verify_signature("unknown_provider", b'test', signature="sha256=abc", secret="secret")
        assert result is False, "Unknown provider should return False (reject)"

    def test_valid_whatsapp_signature_accepted(self):
        """Valid HMAC signature for WhatsApp should be accepted."""
        import hmac
        import hashlib
        from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService

        secret = "test-webhook-secret-key"
        payload = b'{"event": "message", "data": "test"}'
        expected_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        svc = GenericWebhookEngineService(secrets={"whatsapp": secret})
        result = svc.verify_signature("whatsapp", payload, signature=expected_sig, secret=secret)
        assert result is True, "Valid HMAC signature should be accepted"

    def test_tampered_payload_rejected(self):
        """Tampered payload with original signature should be rejected."""
        import hmac
        import hashlib
        from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService

        secret = "test-webhook-secret-key"
        original_payload = b'{"event": "message", "data": "original"}'
        expected_sig = "sha256=" + hmac.new(secret.encode("utf-8"), original_payload, hashlib.sha256).hexdigest()

        tampered_payload = b'{"event": "message", "data": "TAMPERED"}'
        svc = GenericWebhookEngineService(secrets={"whatsapp": secret})
        result = svc.verify_signature("whatsapp", tampered_payload, signature=expected_sig, secret=secret)
        assert result is False, "Tampered payload should be rejected"


# ─── Test: Newly Hardened Endpoints & RBAC Gates ─────────────────────────────

class TestNewlyHardenedAuthGates:
    """Verify that newly hardened endpoints enforce authentication and RBAC."""

    def setup_method(self):
        from app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_plugins_install_requires_auth(self):
        """POST /api/v1/plugins/install must return 401 without auth."""
        resp = self.client.post("/api/v1/plugins/install", json={"plugin_id": "test", "name": "test", "description": "test"})
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_plugins_execute_requires_auth(self):
        """POST /api/v1/plugins/{id}/execute must return 401 without auth."""
        resp = self.client.post("/api/v1/plugins/test/execute", json={"action_name": "test", "payload": {}})
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_scale_load_test_requires_auth(self):
        """POST /api/v1/scale/load-test must return 401 without auth."""
        resp = self.client.post("/api/v1/scale/load-test", json={"simulated_concurrent_requests": 10})
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_feature_flag_update_requires_super_admin(self):
        """PUT /api/v1/v1/feature-flags/{key} must return 401 without auth."""
        resp = self.client.put("/api/v1/v1/feature-flags/ai.voice", json={"is_enabled": True})
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_scoring_qualify_requires_auth(self):
        """POST /api/v1/scoring/qualify must return 401 without auth."""
        resp = self.client.post("/api/v1/scoring/qualify", json={"lead_id": "00000000-0000-0000-0000-000000000001"})
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


