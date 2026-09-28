"""
BeetleLabs Production Razorpay Billing & Payments Service
=========================================================
Enterprise-grade integration with Razorpay SDK:
- Server-side authoritative pricing & order generation
- Constant-time HMAC-SHA256 signature verification
- Atomic payment finalization & entitlement provisioning
- Idempotent webhook processing with event replay defense
- Full & partial refunds with amount validation & tenant guards
- Order reconciliation against Razorpay API
- Emergency payment pause enforcement (global & tenant level)
- Zero secret exposure to frontend or logs
"""
from __future__ import annotations

import hmac
import hashlib
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

import razorpay
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.config import settings
from app.models.broker import Broker
from app.models.billing_models import Plan, PlanVersion
from app.models.subscription import Subscription
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
from app.modules.billing.dto.payment_dto import (
    CreatePaymentOrderRequest,
    CreatePaymentOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    CreateRefundRequest,
    CreateRefundResponse,
    ReconcileOrderResponse,
    PlanInfoDTO,
)

logger = logging.getLogger("beetlelabs.billing.razorpay")

# ─── Authoritative Server-Side Plan Catalog ──────────────────────────────────
PLANS: Dict[str, Dict[str, Any]] = {
    "starter_monthly": {
        "name": "Starter Monthly",
        "amount": 299900,  # ₹2,999.00 in paise
        "period": "monthly",
        "plan_type": "starter",
        "price_usd": 39,
        "features": ["100 AI Lead Qualifications/mo", "WhatsApp Automation Lite", "Single Broker Seat", "CRM Pipeline"],
    },
    "starter_annual": {
        "name": "Starter Annual",
        "amount": 2999900,  # ₹29,999.00 in paise (2 months free)
        "period": "annual",
        "plan_type": "starter",
        "price_usd": 390,
        "features": ["100 AI Lead Qualifications/mo", "WhatsApp Automation Lite", "Single Broker Seat", "CRM Pipeline", "2 Months Free"],
    },
    "pro_monthly": {
        "name": "Professional Monthly",
        "amount": 499900,  # ₹4,999.00 in paise
        "period": "monthly",
        "plan_type": "professional",
        "price_usd": 69,
        "features": ["500 AI Lead Qualifications/mo", "Full WhatsApp Bot Engine", "AVM Valuation Engine", "Google Calendar Sync", "5 Team Seats"],
    },
    "pro_annual": {
        "name": "Professional Annual",
        "amount": 4999900,  # ₹49,999.00 in paise
        "period": "annual",
        "plan_type": "professional",
        "price_usd": 690,
        "features": ["500 AI Lead Qualifications/mo", "Full WhatsApp Bot Engine", "AVM Valuation Engine", "Google Calendar Sync", "5 Team Seats", "2 Months Free"],
    },
    "enterprise_annual": {
        "name": "Enterprise Annual",
        "amount": 14999900,  # ₹1,49,999.00 in paise
        "period": "annual",
        "plan_type": "enterprise",
        "price_usd": 1990,
        "features": ["Unlimited AI Qualifications", "Dedicated WhatsApp Number", "Custom AI Prompts", "Multi-Office Hierarchy", "SLA Guarantee", "Dedicated Support"],
    },
}


class RazorpayProductionService:
    """
    Core production payment processing engine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Emergency Pause Check ────────────────────────────────────────────────
    @staticmethod
    def is_emergency_paused() -> bool:
        """Checks if payment processing is globally paused."""
        if getattr(settings, "PAYMENTS_EMERGENCY_PAUSE", False):
            return True
        try:
            from app.common.redis.rate_limiter import _get_redis
            r = _get_redis()
            if r and r.get("payments:emergency_pause") == "1":
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def set_emergency_pause(enabled: bool, reason: Optional[str] = None) -> bool:
        """Enables or disables emergency payment pause in Redis."""
        try:
            from app.common.redis.rate_limiter import _get_redis
            r = _get_redis()
            if r:
                if enabled:
                    r.set("payments:emergency_pause", "1")
                    if reason:
                        r.set("payments:emergency_pause_reason", reason)
                else:
                    r.delete("payments:emergency_pause")
                    r.delete("payments:emergency_pause_reason")
                return True
        except Exception as e:
            logger.warning(f"[EmergencyPause] Redis write failed: {e}")
        return False

    # ─── Client Helper ────────────────────────────────────────────────────────
    @staticmethod
    def get_client() -> razorpay.Client:
        """Returns initialized Razorpay SDK Client."""
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    @staticmethod
    def is_simulated_mode() -> bool:
        """Returns True if operating with simulated test keys or in test env."""
        key_id = (settings.RAZORPAY_KEY_ID or "").strip()
        return (
            settings.ENV in ("testing", "test")
            or key_id == "rzp_test_placeholder"
            or "placeholder" in key_id.lower()
        )

    async def _resolve_amount_from_catalog(self, plan_id: str) -> Optional[int]:
        """Phase 0 P0.4 — resolve the authoritative amount (paise) from the
        canonical DB catalog for a static plan key like 'pro_monthly'.

        Mapping: plan_type + period -> catalog plan code + interval. Returns
        None when the canonical catalog has no matching active version, so the
        caller can decide fallback (non-prod) vs fail-closed (prod).
        """
        plan_info = PLANS.get(plan_id)
        if not plan_info:
            return None
        plan_code = plan_info.get("plan_type")          # starter | professional | enterprise
        catalog_code = {"starter": "starter", "professional": "pro", "enterprise": "enterprise"}.get(plan_code)
        if not catalog_code:
            return None
        interval = "monthly" if plan_info.get("period") == "monthly" else "annual"
        try:
            stmt = (
                select(Plan, PlanVersion)
                .join(PlanVersion, PlanVersion.plan_id == Plan.id)
                .where(
                    and_(
                        Plan.code == catalog_code,
                        Plan.is_active.is_(True),
                        PlanVersion.interval == interval,
                    )
                )
                .order_by(desc(PlanVersion.version))
                .limit(1)
            )
            row = (await self.db.execute(stmt)).first()
            if not row:
                return None
            _plan, version = row
            return int((version.price * 100).to_integral_value())
        except Exception as exc:
            # Catalog unavailable is a hard error in prod, tolerated fallback in tests
            logger.error(f"[Billing] Catalog amount resolution failed for '{plan_id}': {exc}")
            if settings.ENV in ("production", "prod", "staging"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Canonical billing catalog is unavailable. Payment refused."
                )
            return None

    # ─── 1. Order Creation ────────────────────────────────────────────────────
    async def create_payment_order(
        self,
        broker: Broker,
        request: CreatePaymentOrderRequest,
        client_ip: Optional[str] = None
    ) -> CreatePaymentOrderResponse:
        """
        Generates an authoritative Razorpay order with server-calculated pricing.
        Enforces idempotency, tenant binding, and emergency pause checks.
        """
        if self.is_emergency_paused():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing is temporarily paused for system maintenance. Please retry shortly."
            )

        plan_id = request.plan_id
        if plan_id not in PLANS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan ID '{plan_id}'. Valid options: {list(PLANS.keys())}"
            )

        plan_info = PLANS[plan_id]

        # ── Phase 0 P0.4: amount is resolved from the CANONICAL catalog ──────
        # One authority: the database-driven catalog (catalog_service). The
        # static PLANS table is now presentation/metadata only. In production
        # a catalog miss fails closed instead of silently charging a possibly
        # divergent hardcoded price.
        amount_paise = await self._resolve_amount_from_catalog(plan_id)
        if amount_paise is None:
            if settings.ENV in ("production", "prod", "staging"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Plan '{plan_id}' is not present in the canonical catalog. Payment refused."
                )
            amount_paise = plan_info["amount"]
            logger.warning(
                f"[Billing] Plan '{plan_id}' missing from canonical catalog; "
                "falling back to static amount in non-production."
            )

        # ── Idempotency Check ──────────────────────────────────────────────────
        if request.idempotency_key:
            stmt = select(PaymentOrder).where(
                and_(
                    PaymentOrder.broker_id == broker.id,
                    PaymentOrder.idempotency_key == request.idempotency_key
                )
            )
            existing_order = (await self.db.execute(stmt)).scalars().first()
            if existing_order:
                logger.info(f"[Order IDEMPOTENT] Returning existing order {existing_order.razorpay_order_id}")
                return CreatePaymentOrderResponse(
                    order_id=existing_order.id,
                    razorpay_order_id=existing_order.razorpay_order_id,
                    key_id=settings.RAZORPAY_KEY_ID,
                    amount=existing_order.amount,
                    currency=existing_order.currency,
                    plan_id=existing_order.plan_id,
                    plan_name=plan_info["name"],
                    status=existing_order.status,
                    created_at=existing_order.created_at,
                )

        receipt = f"rcpt_{str(broker.id)[:8]}_{uuid.uuid4().hex[:8]}"

        # ── Razorpay Order Creation ───────────────────────────────────────────
        if self.is_simulated_mode():
            rzp_order_id = f"order_sim_{uuid.uuid4().hex[:14]}"
            logger.info(f"[Razorpay Simulated] Created Order {rzp_order_id} for Plan {plan_id} (₹{amount_paise/100})")
        else:
            try:
                client = self.get_client()
                order_payload = {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": receipt,
                    "notes": {
                        "broker_id": str(broker.id),
                        "broker_email": broker.email or "",
                        "plan_id": plan_id,
                        "plan_name": plan_info["name"],
                        **(request.notes or {})
                    }
                }
                rzp_order = client.order.create(order_payload)
                rzp_order_id = rzp_order["id"]
            except Exception as exc:
                logger.error(f"[Razorpay API Error] Order creation failed: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Razorpay order creation failed: {str(exc)}"
                )

        # ── Record in Database ────────────────────────────────────────────────
        payment_order = PaymentOrder(
            broker_id=broker.id,
            organization_id=getattr(broker, "organization_id", None),
            razorpay_order_id=rzp_order_id,
            plan_id=plan_id,
            amount=amount_paise,
            currency="INR",
            status=PaymentStatus.ORDER_CREATED.value,
            idempotency_key=request.idempotency_key,
            receipt=receipt,
            notes=request.notes,
        )
        self.db.add(payment_order)

        # Audit Log
        audit = PaymentAuditLog(
            broker_id=broker.id,
            organization_id=getattr(broker, "organization_id", None),
            event_type="PAYMENT_ORDER_CREATED",
            resource_type="ORDER",
            resource_id=rzp_order_id,
            actor_type="BROKER",
            actor_id=str(broker.id),
            new_state=PaymentStatus.ORDER_CREATED.value,
            details={"plan_id": plan_id, "amount": amount_paise, "currency": "INR"},
            ip_address=client_ip,
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(payment_order)

        return CreatePaymentOrderResponse(
            order_id=payment_order.id,
            razorpay_order_id=payment_order.razorpay_order_id,
            key_id=settings.RAZORPAY_KEY_ID,
            amount=payment_order.amount,
            currency=payment_order.currency,
            plan_id=payment_order.plan_id,
            plan_name=plan_info["name"],
            status=payment_order.status,
            created_at=payment_order.created_at,
        )

    # ─── 2. Signature Verification & Finalization ─────────────────────────────
    @staticmethod
    def verify_payment_signature(
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        secret: Optional[str] = None
    ) -> bool:
        """
        Verifies Razorpay Checkout signature using constant-time HMAC-SHA256.
        Formula: HMAC-SHA256(order_id + "|" + payment_id, secret) == signature
        """
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return False

        secret_key = secret or settings.RAZORPAY_KEY_SECRET

        # Phase 0 P0.4: signature-bypass is TESTING-ONLY. The previous rule also
        # triggered on the literal 'secret_placeholder' credential, which meant a
        # production deployment with a misconfigured secret would accept the
        # magic string 'valid_test_signature' for arbitrary payments.
        if settings.ENV in ("testing", "test") and razorpay_signature == "valid_test_signature":
            return True

        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        expected_sig = hmac.new(secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        return hmac.compare_digest(expected_sig, razorpay_signature)

    async def finalize_payment(
        self,
        broker: Broker,
        request: VerifyPaymentRequest,
        client_ip: Optional[str] = None
    ) -> VerifyPaymentResponse:
        """
        Verifies payment signature, validates state transitions, captures transaction,
        and provisions broker subscription entitlements atomically.
        """
        if self.is_emergency_paused():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment processing is currently paused."
            )

        # ── 1. Cryptographic Signature Verification ───────────────────────────
        is_valid = self.verify_payment_signature(
            request.razorpay_order_id,
            request.razorpay_payment_id,
            request.razorpay_signature
        )
        if not is_valid:
            logger.warning(
                f"[Payment Security] Signature verification failed for order {request.razorpay_order_id}, "
                f"payment {request.razorpay_payment_id} from broker {broker.id}"
            )
            # Record failed audit
            audit = PaymentAuditLog(
                broker_id=broker.id,
                organization_id=getattr(broker, "organization_id", None),
                event_type="PAYMENT_SIGNATURE_FAILED",
                resource_type="PAYMENT",
                resource_id=request.razorpay_payment_id,
                actor_type="BROKER",
                actor_id=str(broker.id),
                details={"order_id": request.razorpay_order_id},
                ip_address=client_ip,
            )
            self.db.add(audit)
            await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed. Untrusted payment payload."
            )

        # ── 2. Order Lookup & Tenant Scoping (IDOR Defense) ───────────────────
        stmt = select(PaymentOrder).where(
            and_(
                PaymentOrder.razorpay_order_id == request.razorpay_order_id,
                PaymentOrder.broker_id == broker.id  # Strict tenant isolation
            )
        )
        order = (await self.db.execute(stmt)).scalars().first()
        if not order:
            logger.error(
                f"[Payment IDOR / NotFound] Order {request.razorpay_order_id} not found for broker {broker.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or does not belong to the authenticated broker."
            )

        # ── 3. State Machine Transition Guard ─────────────────────────────────
        try:
            state_changed = PaymentStateMachine.validate_transition(
                order.status,
                PaymentStatus.PAYMENT_CAPTURED.value,
                str(order.id)
            )
        except InvalidPaymentStateTransitionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc)
            )

        # ── 4. Upsert Payment Transaction ─────────────────────────────────────
        txn_stmt = select(PaymentTransaction).where(
            PaymentTransaction.razorpay_payment_id == request.razorpay_payment_id
        )
        existing_txn = (await self.db.execute(txn_stmt)).scalars().first()

        if existing_txn:
            txn = existing_txn
            txn.status = PaymentStatus.PAYMENT_CAPTURED.value
            txn.captured_at = datetime.now(timezone.utc)
        else:
            txn = PaymentTransaction(
                order_id=order.id,
                broker_id=broker.id,
                organization_id=getattr(broker, "organization_id", None),
                razorpay_payment_id=request.razorpay_payment_id,
                razorpay_order_id=request.razorpay_order_id,
                amount=order.amount,
                currency=order.currency,
                status=PaymentStatus.PAYMENT_CAPTURED.value,
                captured_at=datetime.now(timezone.utc),
            )
            self.db.add(txn)

        if state_changed:
            order.status = PaymentStatus.PAYMENT_CAPTURED.value

        # ── 5. Provision Broker Subscription Entitlements ─────────────────────
        plan_info = PLANS.get(order.plan_id, PLANS["starter_monthly"])
        broker.subscription_status = "active"
        broker.subscription_plan = plan_info["plan_type"]

        # Record in Subscription audit table
        sub_stmt = select(Subscription).where(
            and_(
                Subscription.broker_id == broker.id,
                Subscription.razorpay_payment_id == request.razorpay_payment_id
            )
        )
        existing_sub = (await self.db.execute(sub_stmt)).scalars().first()
        if not existing_sub:
            new_sub = Subscription(
                broker_id=broker.id,
                razorpay_payment_id=request.razorpay_payment_id,
                razorpay_subscription_id=f"sub_ord_{order.razorpay_order_id}",
                amount=order.amount,
                currency=order.currency,
                status="active",
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(new_sub)
        else:
            existing_sub.status = "active"

        # ── 6. Write Audit Log ────────────────────────────────────────────────
        audit = PaymentAuditLog(
            broker_id=broker.id,
            organization_id=getattr(broker, "organization_id", None),
            event_type="PAYMENT_CAPTURED",
            resource_type="TRANSACTION",
            resource_id=request.razorpay_payment_id,
            actor_type="BROKER",
            actor_id=str(broker.id),
            previous_state=order.status if not state_changed else PaymentStatus.ORDER_CREATED.value,
            new_state=PaymentStatus.PAYMENT_CAPTURED.value,
            details={"order_id": str(order.id), "plan_id": order.plan_id, "amount": order.amount},
            ip_address=client_ip,
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(txn)

        logger.info(
            f"[Payment FINALIZED] Payment {request.razorpay_payment_id} captured for Order {order.id}, "
            f"Broker {broker.id} activated on plan '{order.plan_id}'"
        )

        return VerifyPaymentResponse(
            success=True,
            status=PaymentStatus.PAYMENT_CAPTURED.value,
            order_id=order.id,
            transaction_id=txn.id,
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_order_id=request.razorpay_order_id,
            amount=order.amount,
            currency=order.currency,
            plan_id=order.plan_id,
            message="Payment successfully verified and subscription activated.",
        )

    # ─── 3. Webhook Signature & Event Processing ──────────────────────────────
    @staticmethod
    def verify_webhook_signature(body_bytes: bytes, signature_header: str, secret: Optional[str] = None) -> bool:
        """
        Verifies Razorpay HMAC SHA256 webhook signature against raw request body bytes.
        """
        if not signature_header:
            return False

        secret_key = secret or settings.RAZORPAY_WEBHOOK_SECRET

        # Phase 0 P0.4: webhook signature-bypass is TESTING-ONLY (was previously
        # also reachable with the 'whsec_placeholder' credential in any env).
        if settings.ENV in ("testing", "test") and signature_header == "valid_test_signature":
            return True

        expected = hmac.new(
            secret_key.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature_header)

    async def process_webhook_event(
        self,
        raw_body: bytes,
        signature_header: str,
        event_id_header: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes incoming Razorpay webhooks with cryptographic verification,
        event replay defense, and idempotent state synchronization.
        """
        # 1. Verify Signature
        if not self.verify_webhook_signature(raw_body, signature_header):
            logger.warning("[Webhook Security] Invalid Razorpay webhook signature received")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Razorpay webhook signature"
            )

        import json
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed JSON payload: {e}"
            )

        event_type = data.get("event", "unknown")
        payload = data.get("payload", {})

        # Compute or extract unique event ID for replay protection
        event_id = (
            event_id_header
            or data.get("id")
            or f"evt_{hashlib.sha256(raw_body).hexdigest()[:24]}"
        )

        # 2. Replay Defense
        stmt = select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_id == event_id)
        existing_event = (await self.db.execute(stmt)).scalars().first()
        if existing_event:
            logger.info(f"[Webhook REPLAY] Duplicate webhook event {event_id} ignored idempotently")
            return {
                "status": "duplicate_ignored",
                "event_id": event_id,
                "event": event_type,
                "message": "Event was already processed previously."
            }

        # 3. Record Event
        webhook_record = PaymentWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=data,
            status=WebhookEventStatus.RECEIVED.value,
        )
        self.db.add(webhook_record)

        # 4. Handle Specific Event Types
        payment_entity = payload.get("payment", {}).get("entity", {})
        order_entity = payload.get("order", {}).get("entity", {})
        refund_entity = payload.get("refund", {}).get("entity", {})
        sub_entity = payload.get("subscription", {}).get("entity", {})

        rzp_order_id = payment_entity.get("order_id") or order_entity.get("id")
        rzp_pay_id = payment_entity.get("id")

        if event_type in ("payment.captured", "order.paid"):
            if rzp_order_id:
                order_stmt = select(PaymentOrder).where(PaymentOrder.razorpay_order_id == rzp_order_id)
                order = (await self.db.execute(order_stmt)).scalars().first()
                if order:
                    # Validate transition
                    if PaymentStateMachine.can_transition(order.status, PaymentStatus.PAYMENT_CAPTURED.value):
                        order.status = PaymentStatus.PAYMENT_CAPTURED.value

                    # Find broker & activate
                    broker_stmt = select(Broker).where(Broker.id == order.broker_id)
                    broker = (await self.db.execute(broker_stmt)).scalars().first()
                    if broker:
                        plan_info = PLANS.get(order.plan_id, PLANS["starter_monthly"])
                        broker.subscription_status = "active"
                        broker.subscription_plan = plan_info["plan_type"]

                    # Upsert transaction
                    if rzp_pay_id:
                        txn_stmt = select(PaymentTransaction).where(
                            PaymentTransaction.razorpay_payment_id == rzp_pay_id
                        )
                        txn = (await self.db.execute(txn_stmt)).scalars().first()
                        if not txn:
                            txn = PaymentTransaction(
                                order_id=order.id,
                                broker_id=order.broker_id,
                                organization_id=order.organization_id,
                                razorpay_payment_id=rzp_pay_id,
                                razorpay_order_id=rzp_order_id,
                                amount=payment_entity.get("amount", order.amount),
                                currency=payment_entity.get("currency", "INR"),
                                status=PaymentStatus.PAYMENT_CAPTURED.value,
                                method=payment_entity.get("method"),
                                captured_at=datetime.now(timezone.utc),
                            )
                            self.db.add(txn)
                        else:
                            txn.status = PaymentStatus.PAYMENT_CAPTURED.value

        elif event_type == "payment.failed":
            if rzp_order_id and rzp_pay_id:
                order_stmt = select(PaymentOrder).where(PaymentOrder.razorpay_order_id == rzp_order_id)
                order = (await self.db.execute(order_stmt)).scalars().first()
                if order:
                    txn = PaymentTransaction(
                        order_id=order.id,
                        broker_id=order.broker_id,
                        organization_id=order.organization_id,
                        razorpay_payment_id=rzp_pay_id,
                        razorpay_order_id=rzp_order_id,
                        amount=payment_entity.get("amount", order.amount),
                        currency=payment_entity.get("currency", "INR"),
                        status=PaymentStatus.PAYMENT_FAILED.value,
                        error_code=payment_entity.get("error_code"),
                        error_description=payment_entity.get("error_description"),
                    )
                    self.db.add(txn)

        elif event_type in ("refund.created", "refund.processed"):
            rzp_refund_id = refund_entity.get("id")
            refund_pay_id = refund_entity.get("payment_id")
            if rzp_refund_id and refund_pay_id:
                txn_stmt = select(PaymentTransaction).where(
                    PaymentTransaction.razorpay_payment_id == refund_pay_id
                )
                txn = (await self.db.execute(txn_stmt)).scalars().first()
                if txn:
                    ref_stmt = select(PaymentRefund).where(PaymentRefund.razorpay_refund_id == rzp_refund_id)
                    ref = (await self.db.execute(ref_stmt)).scalars().first()
                    if not ref:
                        ref = PaymentRefund(
                            transaction_id=txn.id,
                            order_id=txn.order_id,
                            broker_id=txn.broker_id,
                            organization_id=txn.organization_id,
                            razorpay_refund_id=rzp_refund_id,
                            razorpay_payment_id=refund_pay_id,
                            amount=refund_entity.get("amount", txn.amount),
                            currency=refund_entity.get("currency", "INR"),
                            status=RefundStatus.REFUNDED.value,
                            reason=refund_entity.get("notes", {}).get("reason"),
                        )
                        self.db.add(ref)
                    else:
                        ref.status = RefundStatus.REFUNDED.value

        # ── Handle Subscription Lifecycle Events ──────────────────────────────
        rzp_sub_id = sub_entity.get("id") or payment_entity.get("subscription_id")
        plan_id = sub_entity.get("plan_id", "starter_monthly")
        plan_info = PLANS.get(plan_id, PLANS["starter_monthly"])

        if rzp_sub_id:
            broker_stmt = select(Broker).where(Broker.razorpay_subscription_id == rzp_sub_id)
            broker = (await self.db.execute(broker_stmt)).scalars().first()

            sub_stmt = select(Subscription).where(Subscription.razorpay_subscription_id == rzp_sub_id)
            sub_record = (await self.db.execute(sub_stmt)).scalars().first()

            if event_type == "subscription.activated":
                if broker:
                    broker.subscription_status = "active"
                    broker.subscription_plan = plan_info["plan_type"]
                if sub_record:
                    sub_record.status = "active"
                    sub_record.started_at = datetime.now(timezone.utc)
                    if rzp_pay_id:
                        sub_record.razorpay_payment_id = rzp_pay_id

            elif event_type == "subscription.charged":
                if broker:
                    broker.subscription_status = "active"
                if sub_record and rzp_pay_id:
                    sub_record.razorpay_payment_id = rzp_pay_id
                    sub_record.status = "active"

            elif event_type == "subscription.paused":
                if broker:
                    broker.subscription_status = "paused"
                if sub_record:
                    sub_record.status = "paused"

            elif event_type == "subscription.resumed":
                if broker:
                    broker.subscription_status = "active"
                if sub_record:
                    sub_record.status = "active"

            elif event_type == "subscription.cancelled":
                if broker:
                    broker.subscription_status = "cancelled"
                if sub_record:
                    sub_record.status = "cancelled"
                    sub_record.ended_at = datetime.now(timezone.utc)

            elif event_type == "subscription.expired":
                if broker:
                    broker.subscription_status = "expired"
                if sub_record:
                    sub_record.status = "completed"
                    sub_record.ended_at = datetime.now(timezone.utc)

        webhook_record.status = WebhookEventStatus.PROCESSED.value
        webhook_record.processed_at = datetime.now(timezone.utc)

        await self.db.commit()

        return {
            "status": "ok",
            "event_id": event_id,
            "event": event_type,
            "handled": True
        }

    # ─── 4. Refunds Engine ────────────────────────────────────────────────────
    async def create_refund(
        self,
        broker: Broker,
        request: CreateRefundRequest,
        client_ip: Optional[str] = None
    ) -> CreateRefundResponse:
        """
        Executes full or partial refund with strict tenant authorization,
        amount cap validation, and idempotency protection.
        """
        if self.is_emergency_paused():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Refund operations are temporarily paused."
            )

        # ── 1. Find Transaction & Enforce Tenant Isolation (IDOR) ─────────────
        stmt = select(PaymentTransaction).where(
            and_(
                PaymentTransaction.razorpay_payment_id == request.razorpay_payment_id,
                PaymentTransaction.broker_id == broker.id
            )
        )
        txn = (await self.db.execute(stmt)).scalars().first()
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found or does not belong to this broker."
            )

        if txn.status != PaymentStatus.PAYMENT_CAPTURED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot refund a payment with status '{txn.status}'. Must be '{PaymentStatus.PAYMENT_CAPTURED.value}'."
            )

        # ── 2. Idempotency Check ──────────────────────────────────────────────
        if request.idempotency_key:
            ref_stmt = select(PaymentRefund).where(
                and_(
                    PaymentRefund.broker_id == broker.id,
                    PaymentRefund.idempotency_key == request.idempotency_key
                )
            )
            existing_ref = (await self.db.execute(ref_stmt)).scalars().first()
            if existing_ref:
                logger.info(f"[Refund IDEMPOTENT] Returning existing refund {existing_ref.razorpay_refund_id}")
                return CreateRefundResponse(
                    refund_id=existing_ref.id,
                    razorpay_refund_id=existing_ref.razorpay_refund_id,
                    razorpay_payment_id=existing_ref.razorpay_payment_id,
                    amount=existing_ref.amount,
                    currency=existing_ref.currency,
                    status=existing_ref.status,
                    created_at=existing_ref.created_at,
                    message="Refund already executed (idempotent replay)."
                )

        # ── 3. Calculate Remaining Refundable Amount ──────────────────────────
        refunds_stmt = select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(
            and_(
                PaymentRefund.transaction_id == txn.id,
                PaymentRefund.status == RefundStatus.REFUNDED.value
            )
        )
        already_refunded = (await self.db.execute(refunds_stmt)).scalar() or 0
        remaining_refundable = txn.amount - already_refunded

        if remaining_refundable <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This transaction has already been fully refunded."
            )

        refund_amount = request.amount if request.amount is not None else remaining_refundable
        if refund_amount > remaining_refundable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested refund (₹{refund_amount/100}) exceeds remaining refundable balance (₹{remaining_refundable/100})."
            )

        # ── 4. Execute Refund via Razorpay SDK ────────────────────────────────
        if self.is_simulated_mode():
            rzp_refund_id = f"rfd_sim_{uuid.uuid4().hex[:14]}"
            logger.info(f"[Razorpay Simulated] Refunded ₹{refund_amount/100} for Payment {request.razorpay_payment_id}")
        else:
            try:
                client = self.get_client()
                rzp_res = client.payment.refund(
                    request.razorpay_payment_id,
                    {
                        "amount": refund_amount,
                        "notes": {"reason": request.reason or "Customer request", "broker_id": str(broker.id)}
                    }
                )
                rzp_refund_id = rzp_res["id"]
            except Exception as exc:
                logger.error(f"[Razorpay Refund Error] {exc}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Razorpay refund failed: {str(exc)}"
                )

        # ── 5. Record Refund & Update Order State ─────────────────────────────
        refund_record = PaymentRefund(
            transaction_id=txn.id,
            order_id=txn.order_id,
            broker_id=broker.id,
            organization_id=getattr(broker, "organization_id", None),
            razorpay_refund_id=rzp_refund_id,
            razorpay_payment_id=request.razorpay_payment_id,
            amount=refund_amount,
            currency=txn.currency,
            status=RefundStatus.REFUNDED.value,
            reason=request.reason,
            idempotency_key=request.idempotency_key,
        )
        self.db.add(refund_record)

        # If fully refunded, transition order state
        if (already_refunded + refund_amount) >= txn.amount and txn.order_id:
            order_stmt = select(PaymentOrder).where(PaymentOrder.id == txn.order_id)
            order = (await self.db.execute(order_stmt)).scalars().first()
            if order and PaymentStateMachine.can_transition(order.status, PaymentStatus.REFUNDED.value):
                order.status = PaymentStatus.REFUNDED.value

        # Audit
        audit = PaymentAuditLog(
            broker_id=broker.id,
            organization_id=getattr(broker, "organization_id", None),
            event_type="REFUND_PROCESSED",
            resource_type="REFUND",
            resource_id=rzp_refund_id,
            actor_type="BROKER",
            actor_id=str(broker.id),
            new_state=RefundStatus.REFUNDED.value,
            details={"payment_id": request.razorpay_payment_id, "amount": refund_amount},
            ip_address=client_ip,
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(refund_record)

        return CreateRefundResponse(
            refund_id=refund_record.id,
            razorpay_refund_id=refund_record.razorpay_refund_id,
            razorpay_payment_id=refund_record.razorpay_payment_id,
            amount=refund_record.amount,
            currency=refund_record.currency,
            status=refund_record.status,
            created_at=refund_record.created_at,
            message="Refund successfully processed and settled."
        )

    # ─── 5. Reconciliation Engine ─────────────────────────────────────────────
    async def reconcile_order(self, broker: Broker, order_id_str: str) -> ReconcileOrderResponse:
        """
        Reconciles database order status against the authoritative Razorpay API state.
        Fixes discrepancies caused by network drops between checkout and callback.
        """
        # Find order
        try:
            order_uuid = uuid.UUID(order_id_str)
            stmt = select(PaymentOrder).where(
                and_(PaymentOrder.id == order_uuid, PaymentOrder.broker_id == broker.id)
            )
        except ValueError:
            stmt = select(PaymentOrder).where(
                and_(PaymentOrder.razorpay_order_id == order_id_str, PaymentOrder.broker_id == broker.id)
            )

        order = (await self.db.execute(stmt)).scalars().first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found for reconciliation.")

        if self.is_simulated_mode():
            return ReconcileOrderResponse(
                order_id=str(order.id),
                razorpay_order_id=order.razorpay_order_id,
                db_status=order.status,
                provider_status="simulated_match",
                reconciled=True,
                action_taken="Simulated environment — DB state matches mock provider."
            )

        try:
            client = self.get_client()
            rzp_order = client.order.fetch(order.razorpay_order_id)
            provider_status = rzp_order.get("status", "unknown")  # 'created', 'attempted', 'paid'
            action_taken = "No discrepancy detected."

            if provider_status == "paid" and order.status != PaymentStatus.PAYMENT_CAPTURED.value:
                # Discrepancy detected: order was paid in Razorpay but missed backend callback
                order.status = PaymentStatus.PAYMENT_CAPTURED.value
                broker.subscription_status = "active"
                plan_info = PLANS.get(order.plan_id, PLANS["starter_monthly"])
                broker.subscription_plan = plan_info["plan_type"]

                # Fetch payments for this order
                payments = client.order.payments(order.razorpay_order_id).get("items", [])
                if payments:
                    p = payments[0]
                    txn = PaymentTransaction(
                        order_id=order.id,
                        broker_id=broker.id,
                        organization_id=order.organization_id,
                        razorpay_payment_id=p["id"],
                        razorpay_order_id=order.razorpay_order_id,
                        amount=p.get("amount", order.amount),
                        currency=p.get("currency", "INR"),
                        status=PaymentStatus.PAYMENT_CAPTURED.value,
                        method=p.get("method"),
                        captured_at=datetime.now(timezone.utc),
                    )
                    self.db.add(txn)

                audit = PaymentAuditLog(
                    broker_id=broker.id,
                    organization_id=order.organization_id,
                    event_type="RECONCILIATION_AUTO_RESOLVE",
                    resource_type="ORDER",
                    resource_id=order.razorpay_order_id,
                    actor_type="SYSTEM",
                    previous_state=PaymentStatus.ORDER_CREATED.value,
                    new_state=PaymentStatus.PAYMENT_CAPTURED.value,
                    details={"provider_status": provider_status},
                )
                self.db.add(audit)
                await self.db.commit()
                action_taken = "Order discrepancy auto-resolved: marked PAYMENT_CAPTURED and activated subscription."

            return ReconcileOrderResponse(
                order_id=str(order.id),
                razorpay_order_id=order.razorpay_order_id,
                db_status=order.status,
                provider_status=provider_status,
                reconciled=True,
                action_taken=action_taken
            )
        except Exception as exc:
            logger.error(f"[Reconciliation Error] {exc}")
            raise HTTPException(status_code=502, detail=f"Reconciliation check failed: {str(exc)}")
