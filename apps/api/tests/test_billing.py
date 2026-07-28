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
        assert test_broker.subscription_plan == "monthly"
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

        # 4. subscription.cancelled event
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
