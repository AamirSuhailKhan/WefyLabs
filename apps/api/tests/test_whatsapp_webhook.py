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

@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", json=payload)
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", json=payload)
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", json=payload)
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/whatsapp/webhook", json=payload)
        assert res.status_code == 200
        assert res.json()["result"]["action"] == "status_update_processed"
        assert res.json()["result"]["message_status"] == "delivered"

    app.dependency_overrides.clear()
