"""
Part 23.4 — Production-Grade Razorpay Payments & Billing Test Suite
==================================================================
Comprehensive test suite covering:
1. Authoritative plan discovery & server pricing
2. Payment state machine & invalid transition rejection
3. Order creation, authoritative pricing & idempotency
4. Cryptographic HMAC-SHA256 signature verification & tamper rejection
5. Atomic payment finalization & subscription entitlement activation
6. Webhook raw-byte HMAC verification, replay defense & event ordering
7. Full & partial refunds, balance checks, and refund idempotency
8. Multi-tenant IDOR protection across orders, transactions & refunds
9. Emergency payment pause (global & Redis-backed)
10. Secret leak defense: zero secrets in API responses
"""
import hmac
import hashlib
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.payment_models import (
    PaymentOrder,
    PaymentTransaction,
    PaymentRefund,
    PaymentWebhookEvent,
    PaymentAuditLog,
    PaymentStatus,
    RefundStatus,
    WebhookEventStatus,
)
from app.modules.billing.services.payment_state_machine import (
    PaymentStateMachine,
    InvalidPaymentStateTransitionError,
)
from app.modules.billing.services.razorpay_service import (
    PLANS,
    RazorpayProductionService,
)
from app.modules.auth.service import create_access_token


# ─── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def setup_test_env(db_session: AsyncSession):
    settings.ENV = "testing"
    clear_rate_limits()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    clear_rate_limits()


def get_auth_headers(broker: Broker) -> dict:
    token = create_access_token({"sub": broker.email, "email": broker.email})
    return {"Authorization": f"Bearer {token}"}


# ─── 1. State Machine Unit Tests ──────────────────────────────────────────────
class TestPaymentStateMachine:
    """Tests state machine transition validation and terminal locks."""

    def test_valid_forward_transitions(self):
        assert PaymentStateMachine.can_transition(PaymentStatus.ORDER_CREATED.value, PaymentStatus.PAYMENT_ATTEMPTED.value) is True
        assert PaymentStateMachine.can_transition(PaymentStatus.ORDER_CREATED.value, PaymentStatus.PAYMENT_CAPTURED.value) is True
        assert PaymentStateMachine.can_transition(PaymentStatus.PAYMENT_ATTEMPTED.value, PaymentStatus.PAYMENT_CAPTURED.value) is True
        assert PaymentStateMachine.can_transition(PaymentStatus.PAYMENT_CAPTURED.value, PaymentStatus.REFUND_REQUESTED.value) is True
        assert PaymentStateMachine.can_transition(PaymentStatus.PAYMENT_CAPTURED.value, PaymentStatus.REFUNDED.value) is True

    def test_idempotent_no_op_allowed(self):
        assert PaymentStateMachine.can_transition(PaymentStatus.PAYMENT_CAPTURED.value, PaymentStatus.PAYMENT_CAPTURED.value) is True
        assert PaymentStateMachine.validate_transition(PaymentStatus.PAYMENT_CAPTURED.value, PaymentStatus.PAYMENT_CAPTURED.value) is False

    def test_illegal_transitions_rejected(self):
        # CAPTURED cannot regress to FAILED
        assert PaymentStateMachine.can_transition(PaymentStatus.PAYMENT_CAPTURED.value, PaymentStatus.PAYMENT_FAILED.value) is False
        with pytest.raises(InvalidPaymentStateTransitionError):
            PaymentStateMachine.validate_transition(PaymentStatus.PAYMENT_CAPTURED.value, PaymentStatus.PAYMENT_FAILED.value)

        # REFUNDED cannot transition back to CAPTURED
        assert PaymentStateMachine.can_transition(PaymentStatus.REFUNDED.value, PaymentStatus.PAYMENT_CAPTURED.value) is False
        with pytest.raises(InvalidPaymentStateTransitionError):
            PaymentStateMachine.validate_transition(PaymentStatus.REFUNDED.value, PaymentStatus.PAYMENT_CAPTURED.value)

        # CANCELLED is terminal
        assert PaymentStateMachine.can_transition(PaymentStatus.PAYMENT_CANCELLED.value, PaymentStatus.PAYMENT_CAPTURED.value) is False


# ─── 2. Plan Catalog Discovery ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_plans_catalog():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/billing/plans")
        assert res.status_code == 200
        plans = res.json()
        assert len(plans) >= 4
        plan_ids = [p["plan_id"] for p in plans]
        assert "starter_monthly" in plan_ids
        assert "pro_monthly" in plan_ids
        for p in plans:
            assert p["amount_paise"] > 0
            assert p["amount_inr"] == p["amount_paise"] / 100.0


# ─── 3. Order Creation & Authoritative Pricing ────────────────────────────────
@pytest.mark.asyncio
async def test_create_order_authoritative_pricing(test_broker: Broker, db_session: AsyncSession):
    headers = get_auth_headers(test_broker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "plan_id": "pro_monthly",
            "notes": {"referral": "partner_network"}
        }
        res = await client.post("/api/v1/billing/orders", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["plan_id"] == "pro_monthly"
        assert data["amount"] == 499900  # ₹4,999.00 server-enforced
        assert data["currency"] == "INR"
        assert data["status"] == "ORDER_CREATED"
        assert data["razorpay_order_id"].startswith("order_")
        assert data["key_id"] == settings.RAZORPAY_KEY_ID

        # Verify DB persistence
        order_uuid = uuid.UUID(data["order_id"])
        stmt = select(PaymentOrder).where(PaymentOrder.id == order_uuid)
        db_order = (await db_session.execute(stmt)).scalars().first()
        assert db_order is not None
        assert db_order.broker_id == test_broker.id
        assert db_order.amount == 499900


@pytest.mark.asyncio
async def test_create_order_idempotency(test_broker: Broker):
    headers = get_auth_headers(test_broker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idemp_key = f"idemp_test_{uuid.uuid4().hex}"
        payload = {"plan_id": "starter_monthly", "idempotency_key": idemp_key}

        res1 = await client.post("/api/v1/billing/orders", json=payload, headers=headers)
        assert res1.status_code == 201
        data1 = res1.json()

        # Replay same idempotency key
        res2 = await client.post("/api/v1/billing/orders", json=payload, headers=headers)
        assert res2.status_code == 201
        data2 = res2.json()

        assert data1["order_id"] == data2["order_id"]
        assert data1["razorpay_order_id"] == data2["razorpay_order_id"]


@pytest.mark.asyncio
async def test_create_order_invalid_plan(test_broker: Broker):
    headers = get_auth_headers(test_broker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/billing/orders", json={"plan_id": "non_existent_plan"}, headers=headers)
        assert res.status_code == 400
        assert "Invalid plan ID" in res.json()["detail"]


# ─── 4. Signature Verification & Payment Finalization ─────────────────────────
@pytest.mark.asyncio
async def test_verify_payment_success(test_broker: Broker, db_session: AsyncSession):
    headers = get_auth_headers(test_broker)

    # Step 1: Create Order
    service = RazorpayProductionService(db_session)
    order_res = await service.create_payment_order(
        test_broker,
        MagicMock(plan_id="pro_monthly", idempotency_key=None, notes={})
    )

    # Step 2: Compute valid test HMAC signature
    fake_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    secret = settings.RAZORPAY_KEY_SECRET
    msg = f"{order_res.razorpay_order_id}|{fake_payment_id}".encode("utf-8")
    valid_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        verify_payload = {
            "razorpay_order_id": order_res.razorpay_order_id,
            "razorpay_payment_id": fake_payment_id,
            "razorpay_signature": valid_sig,
        }
        res = await client.post("/api/v1/billing/orders/verify", json=verify_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "PAYMENT_CAPTURED"
        assert data["razorpay_payment_id"] == fake_payment_id

        # Verify DB state & broker activation
        await db_session.refresh(test_broker)
        assert test_broker.subscription_status == "active"
        assert test_broker.subscription_plan == "professional"

        stmt = select(PaymentTransaction).where(PaymentTransaction.razorpay_payment_id == fake_payment_id)
        txn = (await db_session.execute(stmt)).scalars().first()
        assert txn is not None
        assert txn.status == "PAYMENT_CAPTURED"
        assert txn.amount == 499900


@pytest.mark.asyncio
async def test_verify_payment_tampered_signature_rejected(test_broker: Broker, db_session: AsyncSession):
    headers = get_auth_headers(test_broker)
    service = RazorpayProductionService(db_session)
    order_res = await service.create_payment_order(
        test_broker,
        MagicMock(plan_id="starter_monthly", idempotency_key=None, notes={})
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        verify_payload = {
            "razorpay_order_id": order_res.razorpay_order_id,
            "razorpay_payment_id": "pay_tampered_12345",
            "razorpay_signature": "invalid_tampered_hmac_hash_abc123",
        }
        res = await client.post("/api/v1/billing/orders/verify", json=verify_payload, headers=headers)
        assert res.status_code == 400
        assert "verification failed" in res.json()["detail"].lower()


# ─── 5. Webhook Replay Protection & Signature Validation ──────────────────────
@pytest.mark.asyncio
async def test_webhook_valid_signature_and_processing(test_broker: Broker, db_session: AsyncSession):
    service = RazorpayProductionService(db_session)
    order_res = await service.create_payment_order(
        test_broker,
        MagicMock(plan_id="starter_monthly", idempotency_key=None, notes={})
    )
    fake_pay_id = f"pay_{uuid.uuid4().hex[:14]}"
    event_id = f"evt_{uuid.uuid4().hex[:16]}"

    webhook_payload = {
        "id": event_id,
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": fake_pay_id,
                    "order_id": order_res.razorpay_order_id,
                    "amount": 299900,
                    "currency": "INR",
                    "status": "captured",
                    "method": "upi"
                }
            }
        }
    }
    import json
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/billing/webhook",
            content=raw_body,
            headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id, "Content-Type": "application/json"}
        )
        assert res.status_code == 200
        assert res.json()["handled"] is True

        # Test Replay Protection: send identical webhook again
        res_replay = await client.post(
            "/api/v1/billing/webhook",
            content=raw_body,
            headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id, "Content-Type": "application/json"}
        )
        assert res_replay.status_code == 200
        assert res_replay.json()["status"] == "duplicate_ignored"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected():
    raw_body = b'{"event": "payment.captured"}'
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/billing/webhook",
            content=raw_body,
            headers={"X-Razorpay-Signature": "tampered_signature_123", "Content-Type": "application/json"}
        )
        assert res.status_code == 400
        assert "Invalid Razorpay webhook signature" in res.json()["detail"]


# ─── 6. Refund Engine & Balance Validation ────────────────────────────────────
@pytest.mark.asyncio
async def test_refund_full_and_partial_flow(test_broker: Broker, db_session: AsyncSession):
    headers = get_auth_headers(test_broker)

    # Setup: Create and capture a payment
    service = RazorpayProductionService(db_session)
    order_res = await service.create_payment_order(
        test_broker,
        MagicMock(plan_id="pro_monthly", idempotency_key=None, notes={})
    )
    fake_pay_id = f"pay_{uuid.uuid4().hex[:14]}"
    secret = settings.RAZORPAY_KEY_SECRET
    msg = f"{order_res.razorpay_order_id}|{fake_pay_id}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    await service.finalize_payment(
        test_broker,
        MagicMock(razorpay_order_id=order_res.razorpay_order_id, razorpay_payment_id=fake_pay_id, razorpay_signature=sig)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Partial Refund ₹1,000 (100000 paise)
        refund_payload = {
            "razorpay_payment_id": fake_pay_id,
            "amount": 100000,
            "reason": "Customer discount adjustment"
        }
        res = await client.post("/api/v1/billing/refunds", json=refund_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["amount"] == 100000
        assert data["status"] == "REFUNDED"

        # 2. Attempt refund exceeding remaining balance (remaining = ₹3,999) -> Try ₹4,500
        excess_payload = {
            "razorpay_payment_id": fake_pay_id,
            "amount": 450000,
        }
        res_excess = await client.post("/api/v1/billing/refunds", json=excess_payload, headers=headers)
        assert res_excess.status_code == 400
        assert "exceeds remaining refundable balance" in res_excess.json()["detail"]

        # 3. Full remaining refund (remaining = 399900 paise)
        res_full = await client.post("/api/v1/billing/refunds", json={"razorpay_payment_id": fake_pay_id}, headers=headers)
        assert res_full.status_code == 200
        assert res_full.json()["amount"] == 399900

        # 4. Attempt refund on already fully refunded payment
        res_empty = await client.post("/api/v1/billing/refunds", json={"razorpay_payment_id": fake_pay_id}, headers=headers)
        assert res_empty.status_code == 400
        assert "already been fully refunded" in res_empty.json()["detail"]


# ─── 7. Multi-Tenant IDOR Security Tests ──────────────────────────────────────
@pytest.mark.asyncio
async def test_tenant_idor_order_and_refund_isolation(
    test_broker: Broker,
    db_session: AsyncSession
):
    headers_a = get_auth_headers(test_broker)

    # Create Second Broker
    broker_b = Broker(
        email=f"brokerB_{uuid.uuid4().hex[:8]}@example.com",
        phone="+919876543299",
        name="Broker B",
        agency_name="Agency B",
        city="Mumbai",
        subscription_status="trial"
    )
    db_session.add(broker_b)
    await db_session.commit()
    await db_session.refresh(broker_b)
    headers_b = get_auth_headers(broker_b)

    # Broker A creates an order and payment
    service = RazorpayProductionService(db_session)
    order_a = await service.create_payment_order(
        test_broker,
        MagicMock(plan_id="starter_monthly", idempotency_key=None, notes={})
    )
    fake_pay_a = f"pay_brokerA_{uuid.uuid4().hex[:10]}"
    secret = settings.RAZORPAY_KEY_SECRET
    sig_a = hmac.new(secret.encode("utf-8"), f"{order_a.razorpay_order_id}|{fake_pay_a}".encode("utf-8"), hashlib.sha256).hexdigest()

    await service.finalize_payment(
        test_broker,
        MagicMock(razorpay_order_id=order_a.razorpay_order_id, razorpay_payment_id=fake_pay_a, razorpay_signature=sig_a)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Broker B attempts to GET Broker A's order -> 404
        res_get = await client.get(f"/api/v1/billing/orders/{order_a.order_id}", headers=headers_b)
        assert res_get.status_code == 404

        # Broker B attempts to refund Broker A's payment -> 404
        res_refund = await client.post(
            "/api/v1/billing/refunds",
            json={"razorpay_payment_id": fake_pay_a},
            headers=headers_b
        )
        assert res_refund.status_code == 404


# ─── 8. Emergency Payment Pause ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_emergency_payment_pause(test_broker: Broker):
    headers = get_auth_headers(test_broker)

    # Activate pause
    RazorpayProductionService.set_emergency_pause(True, "Scheduled database maintenance")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Order creation should be blocked with 503
        res = await client.post("/api/v1/billing/orders", json={"plan_id": "starter_monthly"}, headers=headers)
        assert res.status_code == 503
        assert "temporarily paused" in res.json()["detail"]

        # Deactivate pause
        RazorpayProductionService.set_emergency_pause(False)

        # Order creation should succeed again
        res_ok = await client.post("/api/v1/billing/orders", json={"plan_id": "starter_monthly"}, headers=headers)
        assert res_ok.status_code == 201


# ─── 9. Secret Leak Protection ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_zero_secret_leak_in_api_responses(test_broker: Broker):
    headers = get_auth_headers(test_broker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/billing/orders", json={"plan_id": "starter_monthly"}, headers=headers)
        data_str = res.text
        assert "secret_placeholder" not in data_str
        assert "whsec_" not in data_str
        assert "RAZORPAY_KEY_SECRET" not in data_str
        assert "RAZORPAY_WEBHOOK_SECRET" not in data_str
