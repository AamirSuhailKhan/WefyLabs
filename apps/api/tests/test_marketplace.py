import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_marketplace_listing_and_publishing(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. List marketplace catalog items
        res_list = await ac.get("/api/v1/marketplace/items")
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) >= 1

        # 2. Publish new developer extension
        pub_payload = {
            "name": "Custom Automated WhatsApp Drip Pack",
            "slug": "custom-whatsapp-drip-pack",
            "category": "workflow",
            "description": "Automated WhatsApp sequence for luxury apartment leads.",
            "version": "1.0.0",
            "price_usd": 15.0,
            "manifest_data": {"trigger": "lead_created", "action": "send_whatsapp"}
        }
        res_pub = await ac.post("/api/v1/marketplace/publish", json=pub_payload, headers=headers)
        assert res_pub.status_code == 201
        data_pub = res_pub.json()
        assert data_pub["name"] == "Custom Automated WhatsApp Drip Pack"
        assert data_pub["security_status"] == "verified"

        # 3. Test Security Inspection (Flag malicious code attempts)
        mal_payload = {
            "name": "Malicious Code Package",
            "slug": "malicious-code-pack",
            "category": "extension",
            "description": "Suspicious script",
            "manifest_data": {"code": "eval('secret_key')"}
        }
        res_mal = await ac.post("/api/v1/marketplace/publish", json=mal_payload, headers=headers)
        assert res_mal.status_code == 201
        assert res_mal.json()["security_status"] == "flagged"

    app.dependency_overrides.clear()
