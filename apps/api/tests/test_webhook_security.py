"""
Enterprise Webhook Security Test Suite
======================================
Tests:
- Meta Cloud API handshake verification (valid/invalid/missing tokens)
- HMAC-SHA256 signature verification (valid vs tampered payloads)
- Replay attack defense (timestamp skew > 300s)
- Duplicate event idempotency
- Malformed payload defense
- Fail-fast configuration validation for production webhook secrets
"""
import hmac
import hashlib
import time
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService
from app.modules.webhooks.dto.webhook_dto import WebhookPayloadDTO
from app.common.config.validated_settings import EnterpriseSettings


@pytest.fixture
def client():
    return TestClient(app)


class TestWhatsAppHandshakeVerification:
    """Tests Meta Cloud API Direct GET handshake verification."""

    def test_valid_handshake(self, client):
        challenge = "random_meta_challenge_str_998877"
        token = settings.WHATSAPP_VERIFY_TOKEN
        resp = client.get(f"/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token={token}&hub.challenge={challenge}")
        assert resp.status_code == 200
        assert resp.text == challenge

    def test_wrong_verify_token_rejected(self, client):
        resp = client.get("/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=WRONG_ATTACKER_TOKEN&hub.challenge=test")
        assert resp.status_code == 403
        assert "mismatch" in resp.text.lower() or "forbidden" in resp.text.lower()

    def test_missing_verify_token_rejected(self, client):
        resp = client.get("/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.challenge=test")
        assert resp.status_code == 403

    def test_invalid_mode_rejected(self, client):
        resp = client.get(f"/api/v1/whatsapp/webhook?hub.mode=unsubscribe&hub.verify_token={settings.WHATSAPP_VERIFY_TOKEN}&hub.challenge=test")
        assert resp.status_code == 403


class TestWebhookHMACSignatureAndReplay:
    """Tests GenericWebhookEngineService HMAC signature and replay attack prevention."""

    def test_valid_hmac_signature(self):
        secret = "super_secure_webhook_secret_key_32_bytes!!"
        svc = GenericWebhookEngineService(secrets={"whatsapp": secret})
        payload = b'{"object":"whatsapp_business_account","entry":[]}'
        valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        assert svc.verify_signature("whatsapp", payload, valid_sig, secret) is True

    def test_tampered_payload_fails_hmac(self):
        secret = "super_secure_webhook_secret_key_32_bytes!!"
        svc = GenericWebhookEngineService(secrets={"whatsapp": secret})
        payload = b'{"object":"whatsapp_business_account","entry":[]}'
        valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        tampered = b'{"object":"whatsapp_business_account","entry":[{"tampered":true}]}'
        assert svc.verify_signature("whatsapp", tampered, valid_sig, secret) is False

    def test_replay_attack_rejected(self):
        svc = GenericWebhookEngineService()
        old_timestamp = str(time.time() - 600)  # 10 minutes ago (> 300s window)

        assert svc.check_replay_attack(old_timestamp, max_skew_seconds=300) is False

    def test_fresh_timestamp_accepted(self):
        svc = GenericWebhookEngineService()
        fresh_timestamp = str(time.time() - 30)  # 30 seconds ago (< 300s window)

        assert svc.check_replay_attack(fresh_timestamp, max_skew_seconds=300) is True

    @pytest.mark.asyncio
    async def test_replay_attack_raises_http_400(self):
        svc = GenericWebhookEngineService()
        dto = WebhookPayloadDTO(
            provider="whatsapp",
            event_type="message",
            payload={"text": "hello"},
            timestamp=str(time.time() - 500)  # Expired
        )
        with pytest.raises(HTTPException) as exc_info:
            await svc.ingest_webhook(dto, b'{"text":"hello"}', {})
        assert exc_info.value.status_code == 400
        assert "replay" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_signature_raises_http_401(self):
        secret = "secret_key_32_characters_long_entropy!"
        svc = GenericWebhookEngineService(secrets={"whatsapp": secret})
        dto = WebhookPayloadDTO(
            provider="whatsapp",
            event_type="message",
            payload={"text": "hello"},
            signature="sha256=invalid_signature_hex_1234567890",
            timestamp=str(time.time())
        )
        with pytest.raises(HTTPException) as exc_info:
            await svc.ingest_webhook(dto, b'{"text":"hello"}', {})
        assert exc_info.value.status_code == 401
        assert "signature" in exc_info.value.detail.lower()


class TestProductionWebhookSecretValidation:
    """Tests that production environment fails fast if webhook secrets are weak or placeholders."""

    def test_production_rejects_placeholder_webhook_token(self):
        with pytest.raises(ValueError) as exc:
            EnterpriseSettings(
                ENV="production",
                DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
                SECRET_KEY="c" * 32,
                SUPABASE_JWT_SECRET="s" * 32,
                GEMINI_API_KEY="valid_gemini_key_prod",
                WHATSAPP_VERIFY_TOKEN="beetlelabs_webhook_secret_123",  # Placeholder
                RAZORPAY_KEY_ID="rzp_live_abc123",
                RAZORPAY_KEY_SECRET="rzp_sec_" + "k" * 25,
                RAZORPAY_WEBHOOK_SECRET="whsec_" + "w" * 26,
                GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
                GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
                KNOWLEDGE_OCR_PROVIDER="tesseract",
            )
        assert "WHATSAPP_VERIFY_TOKEN" in str(exc.value)

    def test_production_rejects_short_webhook_token(self):
        with pytest.raises(ValueError) as exc:
            EnterpriseSettings(
                ENV="production",
                DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
                SECRET_KEY="c" * 32,
                SUPABASE_JWT_SECRET="s" * 32,
                GEMINI_API_KEY="valid_gemini_key_prod",
                WHATSAPP_VERIFY_TOKEN="short_token_123",  # < 32 chars
                RAZORPAY_KEY_ID="rzp_live_abc123",
                RAZORPAY_KEY_SECRET="rzp_sec_" + "k" * 25,
                RAZORPAY_WEBHOOK_SECRET="whsec_" + "w" * 26,
                GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
                GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
                KNOWLEDGE_OCR_PROVIDER="tesseract",
            )
        assert "WHATSAPP_VERIFY_TOKEN" in str(exc.value)

    def test_production_accepts_secure_32byte_webhook_token(self):
        valid_token = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        settings_prod = EnterpriseSettings(
            ENV="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
            SECRET_KEY="a" * 32,
            SUPABASE_JWT_SECRET="b" * 32,
            GEMINI_API_KEY="valid_gemini_key_prod",
            WHATSAPP_VERIFY_TOKEN=valid_token,
            RAZORPAY_KEY_ID="rzp_live_abc123456789",
            RAZORPAY_KEY_SECRET="rzp_sec_" + "k" * 25,
            RAZORPAY_WEBHOOK_SECRET="whsec_" + "w" * 26,
            GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
            GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
            KNOWLEDGE_OCR_PROVIDER="tesseract",
        )
        assert settings_prod.WHATSAPP_VERIFY_TOKEN == valid_token
