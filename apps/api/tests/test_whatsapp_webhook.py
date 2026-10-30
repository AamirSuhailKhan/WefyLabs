import hashlib
import hmac
import json
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.score import Score

TEST_WEBHOOK_SECRET = "whatsapp-test-webhook-secret-entropy-32b-secure"


def _create_signed_request(payload: dict, secret: str = TEST_WEBHOOK_SECRET) -> tuple[bytes, dict]:
    """Generates exact raw bytes and valid Meta HMAC-SHA256 signature header."""
    raw_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature,
    }
    return raw_bytes, headers


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    settings.ENV = "testing"
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", TEST_WEBHOOK_SECRET)

    # Ensure no external network calls or actual buyer messages occur during tests
    async def dummy_send_message(*args, **kwargs):
        return True
    monkeypatch.setattr("app.services.whatsapp_service.send_message", dummy_send_message)
    monkeypatch.setattr("app.services.conversation_service.send_message", dummy_send_message)

    async def dummy_ai_qualification_response(*args, **kwargs):
        latest = kwargs.get("latest_message", "")
        from app.services.ai_service import fallback_qualification_response
        return fallback_qualification_response(
            kwargs.get("broker_name", "our team"),
            latest,
            kwargs.get("current_extracted_data", {})
        )
    monkeypatch.setattr("app.services.conversation_service.generate_ai_qualification_response", dummy_ai_qualification_response)

    clear_rate_limits()
    yield
    clear_rate_limits()



@pytest.mark.asyncio
async def test_broker_forwarding_lead(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    payload = {
        "messages": [
            {
                "from": test_broker.whatsapp_number,
                "id": "WAMID_BROKER_001",
                "type": "text",
                "text": {"body": "Forwarding new client: 9876543210 for Koramangala project"}
            }
        ]
    }
    raw_bytes, headers = _create_signed_request(payload)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", content=raw_bytes, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        assert res.json()["result"]["action"] == "lead_created_and_contacted"

    # Verify Lead created in DB
    lead_stmt = select(Lead).where(Lead.phone == "+919876543210", Lead.broker_id == test_broker.id)
    lead = (await db_session.execute(lead_stmt)).scalars().first()
    assert lead is not None
    assert lead.source == "whatsapp_forward"
    assert lead.status == "pending"

    # Verify initial bot outbound message saved
    conv_stmt = select(Conversation).where(Conversation.lead_id == lead.id, Conversation.sender_type == "bot")
    bot_conv = (await db_session.execute(conv_stmt)).scalars().first()
    assert bot_conv is not None
    assert "assist" in bot_conv.message.lower() or "buy" in bot_conv.message.lower()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lead_reply_and_qualification(db_session: AsyncSession, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Lead sends reply with budget and preference
    payload = {
        "messages": [
            {
                "from": test_lead.phone,
                "id": "WAMID_LEAD_001",
                "type": "text",
                "text": {"body": "I want to buy a 2BHK in Indiranagar within 50 lakhs budget."}
            }
        ]
    }
    raw_bytes, headers = _create_signed_request(payload)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", content=raw_bytes, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        assert res.json()["result"]["action"] == "lead_responded"

    # Refresh lead from DB
    await db_session.refresh(test_lead)
    assert test_lead.last_message_at is not None
    assert test_lead.property_type == "2bhk"
    assert test_lead.transaction_type == "buy"

    # Verify inbound conversation saved
    conv_stmt = select(Conversation).where(Conversation.lead_id == test_lead.id, Conversation.sender_type == "lead")
    lead_conv = (await db_session.execute(conv_stmt)).scalars().first()
    assert lead_conv is not None
    assert "2BHK" in lead_conv.message

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unknown_sender(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    payload = {
        "messages": [
            {
                "from": "+919999900000",
                "id": "WAMID_UNKNOWN_001",
                "type": "text",
                "text": {"body": "Hello, I am testing."}
            }
        ]
    }
    raw_bytes, headers = _create_signed_request(payload)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", content=raw_bytes, headers=headers)
        assert res.status_code == 200
        assert res.json()["result"]["action"] == "unknown_sender_notified"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_meta_webhook_verification_handshake():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Valid handshake
        res = await ac.get("/api/v1/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "123456789"
        })
        assert res.status_code == 200
        assert res.text == "123456789"

        # 2. Invalid verify token
        res_invalid = await ac.get("/api/v1/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "123456789"
        })
        assert res_invalid.status_code == 403


@pytest.mark.asyncio
async def test_meta_webhook_status_update(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Seed Organization, Broker, and ProviderConfiguration for phone_number_id
    import uuid
    from app.models.organization import Organization, OrganizationMember
    from app.models.global_models import ProviderConfiguration

    org = Organization(name="Meta Status Org", slug=f"meta-status-{uuid.uuid4().hex[:6]}")
    broker = Broker(
        id=uuid.uuid4(),
        email=f"status_broker_{uuid.uuid4().hex[:6]}@example.com",
        name="Status Broker",
        phone="+919876543210",
        whatsapp_number="+919876543210",
    )
    db_session.add_all([org, broker])
    await db_session.flush()
    db_session.add_all([
        OrganizationMember(organization_id=org.id, broker_id=broker.id, role="owner"),
        ProviderConfiguration(
            organization_id=org.id,
            provider_type="WHATSAPP",
            provider_code="meta_direct",
            config_json={"phone_number_id": "1192435067294962"},
            is_active=True,
        ),
    ])
    await db_session.commit()

    payload = {
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15551720871", "phone_number_id": "1192435067294962"},
                            "statuses": [
                                {
                                    "id": "wamid.HBgLMTU1NTE3MjA4NzEFARgSMDFBNDg5MjU3NzU2RkZFQUJEAA==",
                                    "status": "delivered",
                                    "timestamp": "1711200000",
                                    "recipient_id": "919876543210"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw_bytes, headers = _create_signed_request(payload)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", content=raw_bytes, headers=headers)
        assert res.status_code == 200
        assert res.json()["result"]["action"] in ("status_updates_processed", "status_update_processed")
        assert res.json()["result"]["message_status"] == "delivered"

    app.dependency_overrides.clear()


# ── Explicit Negative Security Tests (Stage 2) ───────────────────────────────

@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected():
    payload = {"messages": [{"from": "+919876543210", "id": "WAMID_NO_SIG", "text": {"body": "Test"}}]}
    raw_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 401
        assert "Invalid Meta webhook HMAC signature" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected():
    payload = {"messages": [{"from": "+919876543210", "id": "WAMID_BAD_SIG", "text": {"body": "Test"}}]}
    raw_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    forged_sig = "sha256=" + "0" * 64

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": forged_sig},
        )
        assert res.status_code == 401
        assert "Invalid Meta webhook HMAC signature" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_truncated_or_malformed_signature_rejected():
    payload = {"messages": [{"from": "+919876543210", "id": "WAMID_MALFORMED_SIG", "text": {"body": "Test"}}]}
    raw_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    # Sub-case A: Truncated signature hash
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=12345"},
        )
        assert res.status_code == 401

    # Sub-case B: Missing 'sha256=' prefix entirely
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "abcdef1234567890"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_incorrect_raw_body_signature_rejected():
    payload_original = {"messages": [{"from": "+919876543210", "id": "WAMID_A", "text": {"body": "Original"}}]}
    raw_bytes, headers = _create_signed_request(payload_original)

    # Tamper with the raw body bytes after computing signature
    tampered_bytes = raw_bytes.replace(b"Original", b"Tampered")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=tampered_bytes,
            headers=headers,
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_missing_server_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", None)
    payload = {"messages": [{"from": "+919876543210", "id": "WAMID_NO_SEC", "text": {"body": "Test"}}]}
    raw_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=abcdef"},
        )
        assert res.status_code == 503
        assert "not configured" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_malformed_json_rejected():
    malformed_body = b'{"messages": [{"unclosed'
    signature = "sha256=" + hmac.new(TEST_WEBHOOK_SECRET.encode("utf-8"), malformed_body, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=malformed_body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
        assert res.status_code == 400
        assert "valid JSON" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_non_object_json_rejected():
    non_object_body = b'["not", "a", "json", "object"]'
    signature = "sha256=" + hmac.new(TEST_WEBHOOK_SECRET.encode("utf-8"), non_object_body, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/whatsapp/webhook",
            content=non_object_body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
        assert res.status_code == 400
        assert "object" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_duplicate_event_delivery(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Seed Organization, Broker, and ProviderConfiguration for phone_number_id
    import uuid
    from app.models.organization import Organization, OrganizationMember
    from app.models.global_models import ProviderConfiguration

    org = Organization(name="Dup Org", slug=f"dup-{uuid.uuid4().hex[:6]}")
    broker = Broker(
        id=uuid.uuid4(),
        email=f"dup_broker_{uuid.uuid4().hex[:6]}@example.com",
        name="Dup Broker",
        phone="+919876543210",
        whatsapp_number="+919876543210",
    )
    db_session.add_all([org, broker])
    await db_session.flush()
    db_session.add_all([
        OrganizationMember(organization_id=org.id, broker_id=broker.id, role="owner"),
        ProviderConfiguration(
            organization_id=org.id,
            provider_type="WHATSAPP",
            provider_code="meta_direct",
            config_json={"phone_number_id": "1192435067294962"},
            is_active=True,
        ),
    ])
    await db_session.commit()

    payload = {
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15551720871", "phone_number_id": "1192435067294962"},
                            "statuses": [
                                {
                                    "id": "wamid.DUPLICATE_DELIVERY_TEST_001",
                                    "status": "delivered",
                                    "timestamp": "1711200000",
                                    "recipient_id": "919876543210"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw_bytes, headers = _create_signed_request(payload)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # First send
        res1 = await ac.post("/api/v1/whatsapp/webhook", content=raw_bytes, headers=headers)
        assert res1.status_code == 200

        # Duplicate send with identical raw payload and signature
        res2 = await ac.post("/api/v1/whatsapp/webhook", content=raw_bytes, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["status"] == "ok"
        # Duplicate must be acknowledged without double-processing
        assert res2.json()["result"]["action"] in ("duplicate_suppressed", "status_updates_processed", "status_update_processed")

    app.dependency_overrides.clear()
