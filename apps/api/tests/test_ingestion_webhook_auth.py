import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.common.security.token_encryption import encrypt_token
from app.database import get_db
from app.main import app
from app.models.ingestion_models import ConnectorConfig
from app.modules.ingestion.dto.canonical_lead_dto import IngestionResponseDTO


@pytest.mark.asyncio
async def test_ingestion_webhook_rejects_arbitrary_connector_and_org(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/v1/ingest/webhook/not-a-configured-connector?org_id=victim-org&source=webhook",
                json={"name": "Injected", "phone": "+15555550123"},
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_ingestion_webhook_uses_connector_tenant_and_validates_hmac(db_session):
    async def override_db():
        yield db_session

    config = ConnectorConfig(
        id="connector-test-1",
        organization_id="trusted-org-id",
        connector_type="webhook",
        name="Test webhook",
        credentials_encrypted=encrypt_token("connector-test-secret"),
        is_active=True,
    )
    db_session.add(config)
    await db_session.commit()

    payload = {"name": "New inquiry", "phone": "+15555550123"}
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(
        b"connector-test-secret", raw_body, hashlib.sha256
    ).hexdigest()
    app.dependency_overrides[get_db] = override_db
    try:
        with patch(
            "app.modules.ingestion.controller.ingestion_controller.LeadIngestionPipeline.ingest_lead",
            new_callable=AsyncMock,
            return_value=IngestionResponseDTO(
                ingestion_id="ing_test",
                status="ingested",
                lead_id="lead_test",
                source="webhook",
                latency_ms=1,
                message="accepted",
            ),
        ) as ingest:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/v1/ingest/webhook/connector-test-1?org_id=attacker-org&source=csv_import",
                    content=raw_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                    },
                )
        assert response.status_code == 200
        assert ingest.await_args.kwargs["organization_id"] == "trusted-org-id"
        assert ingest.await_args.kwargs["source"] == "webhook"
        assert "x-webhook-signature" not in {
            key.lower() for key in ingest.await_args.kwargs["headers"]
        }
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_ingestion_webhook_rejects_bad_signature(db_session):
    async def override_db():
        yield db_session

    db_session.add(ConnectorConfig(
        id="connector-test-2",
        organization_id="trusted-org-id",
        connector_type="webhook",
        name="Test webhook",
        credentials_encrypted=encrypt_token("connector-test-secret"),
        is_active=True,
    ))
    await db_session.commit()
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/v1/ingest/webhook/connector-test-2",
                json={"name": "Injected", "phone": "+15555550123"},
                headers={"X-Webhook-Signature": "sha256=invalid"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
