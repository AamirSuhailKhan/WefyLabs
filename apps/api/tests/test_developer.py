import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.modules.auth.service import create_access_token
from app.core.events.event_bus import DomainEventBus, DomainEvent

@pytest.mark.asyncio
async def test_developer_platform_and_event_bus(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create Developer API Key
        key_payload = {
            "name": "Integration CLI Key",
            "scopes": ["leads:read", "leads:write", "webhooks:manage"]
        }
        res_key = await ac.post("/api/v1/developer/api-keys", json=key_payload, headers=headers)
        assert res_key.status_code == 201
        data_key = res_key.json()
        assert data_key["name"] == "Integration CLI Key"
        assert data_key["raw_api_key"].startswith("btl_live_")

        # 2. List API Keys
        res_list_keys = await ac.get("/api/v1/developer/api-keys", headers=headers)
        assert res_list_keys.status_code == 200
        assert len(res_list_keys.json()) >= 1

        # 3. Register Webhook Subscription
        wh_payload = {
            "target_url": "https://example.com/webhooks/beetlelabs",
            "events": ["LeadCreated", "LeadQualified", "DealWon"]
        }
        res_wh = await ac.post("/api/v1/developer/webhooks", json=wh_payload, headers=headers)
        assert res_wh.status_code == 201
        data_wh = res_wh.json()
        assert data_wh["target_url"] == "https://example.com/webhooks/beetlelabs"
        assert data_wh["secret"].startswith("whsec_")

        # 4. Register Event Subscriber on In-Memory DomainEventBus
        received_events = []

        async def custom_subscriber(event: DomainEvent):
            received_events.append(event)

        DomainEventBus.subscribe("LeadQualified", custom_subscriber)

        # 5. Publish Domain Event via API
        pub_payload = {
            "event_name": "LeadQualified",
            "payload": {"lead_id": "12345", "score": "hot"}
        }
        res_pub = await ac.post("/api/v1/developer/events/publish", json=pub_payload, headers=headers)
        assert res_pub.status_code == 200
        assert res_pub.json()["subscribers_notified"] >= 1
        assert len(received_events) == 1
        assert received_events[0].event_name == "LeadQualified"

    DomainEventBus.clear_subscribers()
    app.dependency_overrides.clear()
