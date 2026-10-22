import hashlib
import hmac
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.broker import Broker
from app.models.global_models import ProviderConfiguration
from app.models.organization import Organization, OrganizationMember
from app.models.lead import Lead
from app.models.communication_models import RawCommunicationEvent, WebhookEventClaim
from app.modules.communication.canonical_service import CanonicalCommunicationService


def _scalar_result(items=None, first=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalars.return_value.first.return_value = first
    return result


@pytest.mark.asyncio
async def test_provider_tenant_mapping_uses_signed_phone_number_id_not_sender():
    broker = SimpleNamespace(id="broker-1")
    config = SimpleNamespace(
        organization_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        config_json={"phone_number_id": "phone-id-1"},
    )
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[
        _scalar_result([config]), _scalar_result(first=broker),
        _scalar_result([config]), _scalar_result(first=broker),
    ])
    service = CanonicalCommunicationService()

    tenant_a = await service._resolve_provider_tenant(db, {
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "phone-id-1"},
            "messages": [{"from": "919111111111"}],
        }}]}]
    })
    tenant_b = await service._resolve_provider_tenant(db, {
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "phone-id-1"},
            "messages": [{"from": "919222222222"}],
        }}]}]
    })

    assert tenant_a == tenant_b == ("11111111-1111-4111-8111-111111111111", broker)


@pytest.mark.asyncio
async def test_unmapped_phone_number_fails_closed():
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalar_result([]))
    service = CanonicalCommunicationService()

    with pytest.raises(HTTPException) as exc:
        await service._resolve_provider_tenant(db, {
            "entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "unknown"}}}]}]
        })

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_identical_payload_without_provider_event_id_is_deduplicated(db_session):
    service = CanonicalCommunicationService()
    payload = {"object": "whatsapp_business_account", "entry": []}
    raw_body = json.dumps(payload, separators=(",", ":")).encode()

    first = await service.ingest_inbound_webhook(
        db=db_session,
        provider_name="test_provider",
        raw_body=raw_body,
        headers={},
        parsed_payload=payload,
        enforce_signature=False,
    )
    duplicate = await service.ingest_inbound_webhook(
        db=db_session,
        provider_name="test_provider",
        raw_body=raw_body,
        headers={},
        parsed_payload=payload,
        enforce_signature=False,
    )

    assert first["action"] == "ignored_no_messages"
    assert duplicate["action"] == "duplicate_suppressed"


@pytest.mark.asyncio
async def test_signed_webhook_routes_to_configured_org_not_sender_phone(db_session, monkeypatch):
    secret = "webhook-test-secret-with-sufficient-entropy"
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", secret)
    org_a = Organization(name="Mapped org", slug="mapped-org")
    org_b = Organization(name="Sender phone decoy", slug="sender-phone-decoy")
    broker_a = Broker(id=uuid.uuid4(), email="mapped@example.com", name="Mapped owner")
    broker_b = Broker(
        id=uuid.uuid4(), email="decoy@example.com", name="Phone decoy",
        phone="+919111111111",
    )
    db_session.add_all([org_a, org_b, broker_a, broker_b])
    await db_session.flush()
    db_session.add_all([
        OrganizationMember(organization_id=org_a.id, broker_id=broker_a.id, role="owner"),
        OrganizationMember(organization_id=org_b.id, broker_id=broker_b.id, role="owner"),
        ProviderConfiguration(
            organization_id=org_a.id,
            provider_type="WHATSAPP",
            provider_code="meta_direct",
            config_json={"phone_number_id": "phone-id-mapped"},
            is_active=True,
        ),
    ])
    await db_session.commit()

    payload = {
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "phone-id-mapped"},
            "messages": [{
                "from": "919111111111",
                "id": "wamid.tenant-routing-test",
                "type": "text",
                "text": {"body": "tenant mapping verification"},
            }],
        }}]}]
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    result = await CanonicalCommunicationService().ingest_inbound_webhook(
        db=db_session,
        provider_name="whatsapp_cloud",
        raw_body=raw_body,
        headers={"x-hub-signature-256": signature},
        parsed_payload=payload,
        enforce_signature=True,
    )
    duplicate = await CanonicalCommunicationService().ingest_inbound_webhook(
        db=db_session,
        provider_name="whatsapp_cloud",
        raw_body=raw_body,
        headers={"x-hub-signature-256": signature},
        parsed_payload=payload,
        enforce_signature=True,
    )
    lead = await db_session.get(Lead, uuid.UUID(result["lead_id"]))
    raw_event_count = await db_session.scalar(
        select(func.count()).select_from(RawCommunicationEvent).where(
            RawCommunicationEvent.provider_event_id == "msg_wamid.tenant-routing-test"
        )
    )
    claim_count = await db_session.scalar(
        select(func.count()).select_from(WebhookEventClaim).where(
            WebhookEventClaim.provider_event_id == "msg_wamid.tenant-routing-test"
        )
    )

    assert result["action"] == "message_persisted"
    assert duplicate["action"] == "duplicate_suppressed"
    assert raw_event_count == 2  # Preserve both original and duplicate delivery evidence.
    assert claim_count == 1
    assert lead.organization_id == org_a.id
    assert lead.broker_id == broker_a.id


@pytest.mark.asyncio
async def test_direct_messages_payload_requires_hmac(monkeypatch):
    secret = "webhook-test-secret-with-sufficient-entropy"
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", secret)
    payload = {"messages": [{"from": "919111111111", "id": "wamid.test", "text": {"body": "hello"}}]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/whatsapp/webhook", json=payload)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_app_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/whatsapp/webhook",
            content=b'{"messages":[]}',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_invalid_hmac_fails_before_tenant_lookup(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "webhook-test-secret-with-sufficient-entropy")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/whatsapp/webhook",
            content=b'{"messages":[]}',
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=invalid"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_json_is_not_acknowledged(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "webhook-test-secret-with-sufficient-entropy")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/whatsapp/webhook",
            content=b"{invalid",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_direct_messages_payload_uses_signed_canonical_pipeline(monkeypatch):
    secret = "webhook-test-secret-with-sufficient-entropy"
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", secret)
    raw_body = json.dumps({
        "messages": [{"from": "919111111111", "id": "wamid.test", "text": {"body": "hello"}}]
    }, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    with patch(
        "app.routers.whatsapp.canonical_communication_service.ingest_inbound_webhook",
        new_callable=AsyncMock,
        return_value={"status": "ok", "action": "ignored_no_messages"},
    ) as ingest:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/whatsapp/webhook",
                content=raw_body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
            )

    assert response.status_code == 200
    assert ingest.await_args.kwargs["enforce_signature"] is True
    assert ingest.await_args.kwargs["parsed_payload"]["messages"][0]["id"] == "wamid.test"


@pytest.mark.asyncio
async def test_processing_failure_is_not_acknowledged_as_success(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "webhook-test-secret-with-sufficient-entropy")
    raw_body = b'{"messages":[]}'
    signature = "sha256=" + hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()

    with patch(
        "app.routers.whatsapp.canonical_communication_service.ingest_inbound_webhook",
        new_callable=AsyncMock,
        side_effect=RuntimeError("simulated processing failure"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/whatsapp/webhook",
                content=raw_body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
            )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_communication_webhook_keeps_canonical_signature_and_tenant_checks(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    class VerifiedProvider:
        provider_name = "whatsapp_cloud"

        async def verify_webhook_signature(self, raw_body, headers):
            return True

        def parse_delivery_status(self, payload):
            return None

    try:
        with patch("app.modules.communication.router._channel_manager.get_provider", return_value=VerifiedProvider()), patch(
            "app.modules.communication.canonical_service.canonical_communication_service.ingest_inbound_webhook",
            new_callable=AsyncMock,
            return_value={"status": "accepted"},
        ) as ingest:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/communication/v2/webhooks/whatsapp",
                    json={"entry": []},
                )

        assert response.status_code == 200
        assert ingest.await_args.kwargs["enforce_signature"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
