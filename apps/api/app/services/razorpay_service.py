"""
BeetleLabs Razorpay Service Compatibility Bridge
================================================
Re-exports the production Razorpay service, state machine, and plan catalog
while preserving existing legacy function signatures for backward compatibility.
"""
from __future__ import annotations

import hmac
import hashlib
import uuid
import logging
from typing import Dict, Any, Optional

import razorpay
from app.config import settings

# Re-export from the new production billing module
from app.modules.billing.services.razorpay_service import (
    PLANS,
    RazorpayProductionService,
)
from app.modules.billing.services.payment_state_machine import (
    PaymentStateMachine,
    InvalidPaymentStateTransitionError,
)

logger = logging.getLogger(__name__)


def get_razorpay_client() -> razorpay.Client:
    return RazorpayProductionService.get_client()


def create_razorpay_customer(name: str, email: str, phone: str) -> str:
    """
    Creates a Razorpay customer record or returns a simulated customer ID if using placeholder test keys.
    """
    if RazorpayProductionService.is_simulated_mode():
        sim_id = f"cust_sim_{uuid.uuid4().hex[:10]}"
        logger.info(f"[Razorpay Simulated] Created Customer {sim_id} for {email}")
        return sim_id

    client = get_razorpay_client()
    digits_phone = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits_phone) == 10:
        digits_phone = f"91{digits_phone}"

    res = client.customer.create({
        "name": name,
        "email": email,
        "contact": digits_phone,
        "fail_existing": 0
    })
    return res["id"]


def create_razorpay_subscription(plan_id: str, customer_id: str) -> Dict[str, Any]:
    """
    Creates a Razorpay subscription for the given plan and customer.
    """
    if plan_id not in PLANS:
        raise ValueError(f"Invalid plan ID '{plan_id}'. Valid plans: {list(PLANS.keys())}")

    plan_info = PLANS[plan_id]

    if RazorpayProductionService.is_simulated_mode():
        sub_id = f"sub_sim_{uuid.uuid4().hex[:10]}"
        short_url = f"https://rzp.io/i/{sub_id}"
        logger.info(f"[Razorpay Simulated] Created Subscription {sub_id} for Plan {plan_id}")
        return {
            "id": sub_id,
            "short_url": short_url,
            "status": "created",
            "amount": plan_info["amount"],
            "currency": "INR"
        }

    client = get_razorpay_client()
    res = client.subscription.create({
        "plan_id": plan_id,
        "customer_id": customer_id,
        "total_count": 12 if plan_info["period"] == "monthly" else 1,
        "quantity": 1,
        "customer_notify": 1
    })
    return {
        "id": res["id"],
        "short_url": res.get("short_url", f"https://rzp.io/i/{res['id']}"),
        "status": res.get("status", "created"),
        "amount": plan_info["amount"],
        "currency": "INR"
    }


def verify_webhook_signature(body_bytes: bytes, signature_header: str, secret: Optional[str] = None) -> bool:
    """
    Verifies Razorpay HMAC SHA256 webhook signature.
    """
    return RazorpayProductionService.verify_webhook_signature(body_bytes, signature_header, secret)


def verify_payment_signature(order_id: str, payment_id: str, signature: str, secret: Optional[str] = None) -> bool:
    """
    Verifies Razorpay Checkout payment signature.
    """
    return RazorpayProductionService.verify_payment_signature(order_id, payment_id, signature, secret)
