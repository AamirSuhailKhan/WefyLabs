import pytest
import json
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.subscription import Subscription
from app.modules.auth.service import create_access_token

@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()

@pytest.mark.asyncio
async def test_billing_status_and_subscribe_flow(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. GET /api/v1/billing/status
        res_status = await ac.get("/api/v1/billing/status", headers=headers)
        assert res_status.status_code == 200
        st = res_status.json()
        assert st["subscription_status"] == "trial"
        assert st["trial_days_remaining"] >= 6

        # 2. POST /api/v1/billing/subscribe (starter_monthly)
        res_sub = await ac.post(
            "/api/v1/billing/subscribe",
            json={"plan_id": "starter_monthly"},
            headers=headers
        )
        assert res_sub.status_code == 201
        sub_data = res_sub.json()
        assert sub_data["amount"] == 299900
        assert sub_data["currency"] == "INR"
        assert sub_data["razorpay_subscription_id"].startswith("sub_sim_")

        # Verify DB subscription created
        stmt = select(Subscription).where(Subscription.razorpay_subscription_id == sub_data["razorpay_subscription_id"])
        sub_obj = (await db_session.execute(stmt)).scalars().first()
        assert sub_obj is not None
        assert sub_obj.amount == 299900

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_razorpay_webhook_signature_and_events(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Setup simulated subscription on broker
    test_broker.razorpay_subscription_id = "sub_test_9999"
    test_broker.razorpay_customer_id = "cust_test_9999"
    sub_record = Subscription(
        broker_id=test_broker.id,
        razorpay_subscription_id="sub_test_9999",
        amount=299900,
        currency="INR",
        status="created"
    )
    db_session.add(sub_record)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Invalid signature should return 400
        res_invalid = await ac.post(
            "/api/v1/billing/webhook",
            content=json.dumps({"event": "subscription.activated"}),
            headers={"X-Razorpay-Signature": "invalid_sig", "Content-Type": "application/json"}
        )
        assert res_invalid.status_code == 400

        # 2. subscription.activated event
        payload_activated = {
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": "sub_test_9999",
                        "plan_id": "starter_monthly"
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_test_0001"
                    }
                }
            }
        }
        res_activated = await ac.post(
            "/api/v1/billing/webhook",
            content=json.dumps(payload_activated),
            headers={"X-Razorpay-Signature": "valid_test_signature", "Content-Type": "application/json"}
        )
        assert res_activated.status_code == 200

        # Verify broker updated to active
        await db_session.refresh(test_broker)
        await db_session.refresh(sub_record)
        assert test_broker.subscription_status == "active"
        assert test_broker.subscription_plan in ("starter", "monthly")
        assert sub_record.status == "active"

        # 3. Prevent duplicate subscription creation when active
        token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
        res_sub_dup = await ac.post(
            "/api/v1/billing/subscribe",
            json={"plan_id": "pro_monthly"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_sub_dup.status_code == 400
        assert "already has an active subscription" in res_sub_dup.json()["detail"]

        # 4. subscription.paused event
        payload_paused = {
            "event": "subscription.paused",
            "payload": {
                "subscription": {
                    "entity": {"id": "sub_test_9999"}
                }
            }
        }
        res_paused = await ac.post(
            "/api/v1/billing/webhook",
            content=json.dumps(payload_paused),
            headers={"X-Razorpay-Signature": "valid_test_signature", "Content-Type": "application/json"}
        )
        assert res_paused.status_code == 200
        await db_session.refresh(test_broker)
        await db_session.refresh(sub_record)
        assert test_broker.subscription_status == "paused"
        assert sub_record.status == "paused"

        # 5. subscription.resumed event
        payload_resumed = {
            "event": "subscription.resumed",
            "payload": {
                "subscription": {
                    "entity": {"id": "sub_test_9999"}
                }
            }
        }
        res_resumed = await ac.post(
            "/api/v1/billing/webhook",
            content=json.dumps(payload_resumed),
            headers={"X-Razorpay-Signature": "valid_test_signature", "Content-Type": "application/json"}
        )
        assert res_resumed.status_code == 200
        await db_session.refresh(test_broker)
        assert test_broker.subscription_status == "active"

        # 6. subscription.cancelled event
        payload_cancelled = {
            "event": "subscription.cancelled",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": "sub_test_9999"
                    }
                }
            }
        }
        res_cancelled = await ac.post(
            "/api/v1/billing/webhook",
            content=json.dumps(payload_cancelled),
            headers={"X-Razorpay-Signature": "valid_test_signature", "Content-Type": "application/json"}
        )
        assert res_cancelled.status_code == 200

        await db_session.refresh(test_broker)
        assert test_broker.subscription_status == "cancelled"

    app.dependency_overrides.clear()


def test_production_rejects_placeholder_razorpay_credentials():
    from app.common.config.validated_settings import EnterpriseSettings
    with pytest.raises(ValueError) as exc:
        EnterpriseSettings(
            ENV="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
            SECRET_KEY="c" * 32,
            SUPABASE_JWT_SECRET="s" * 32,
            GEMINI_API_KEY="valid_gemini_key_prod",
            WHATSAPP_VERIFY_TOKEN="w" * 32,
            RAZORPAY_KEY_ID="rzp_test_placeholder",  # Placeholder key
            RAZORPAY_KEY_SECRET="secret_placeholder",
            RAZORPAY_WEBHOOK_SECRET="whsec_placeholder",
            GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
            GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
            KNOWLEDGE_OCR_PROVIDER="tesseract",
        )
    assert "RAZORPAY_KEY_ID" in str(exc.value)
    assert "RAZORPAY_KEY_SECRET" in str(exc.value)


def test_production_accepts_valid_razorpay_credentials():
    from app.common.config.validated_settings import EnterpriseSettings
    prod_settings = EnterpriseSettings(
        ENV="production",
        DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
        SECRET_KEY="c" * 32,
        SUPABASE_JWT_SECRET="s" * 32,
        GEMINI_API_KEY="valid_gemini_key_prod",
        WHATSAPP_VERIFY_TOKEN="w" * 32,
        RAZORPAY_KEY_ID="rzp_live_real_production_key_123",
        RAZORPAY_KEY_SECRET="rzp_secret_real_live_prod_key_456",
        RAZORPAY_WEBHOOK_SECRET="whsec_real_production_secret_key_32_chars!",
        GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
        GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
        KNOWLEDGE_OCR_PROVIDER="tesseract",
    )
    assert prod_settings.RAZORPAY_KEY_ID == "rzp_live_real_production_key_123"

