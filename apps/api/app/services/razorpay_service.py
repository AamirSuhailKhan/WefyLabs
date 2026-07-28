import hmac
import hashlib
import uuid
import logging
from typing import Dict, Any
import razorpay
from app.config import settings

logger = logging.getLogger(__name__)

PLANS: Dict[str, Dict[str, Any]] = {
    "starter_monthly": {"name": "Starter", "amount": 299900, "period": "monthly", "plan_type": "monthly"},
    "starter_annual": {"name": "Starter Annual", "amount": 2999900, "period": "annual", "plan_type": "annual"},
    "pro_monthly": {"name": "Pro", "amount": 499900, "period": "monthly", "plan_type": "monthly"},
    "pro_annual": {"name": "Pro Annual", "amount": 4999900, "period": "annual", "plan_type": "annual"},
}

def get_razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def create_razorpay_customer(name: str, email: str, phone: str) -> str:
    """
    Creates a Razorpay customer record or returns a simulated customer ID if using placeholder test keys.
    """
    if settings.RAZORPAY_KEY_ID == "rzp_test_placeholder" or settings.ENV == "testing":
        sim_id = f"cust_sim_{uuid.uuid4().hex[:10]}"
        logger.info(f"[Razorpay Simulated] Created Customer {sim_id} for {email}")
        return sim_id

    client = get_razorpay_client()
    digits_phone = "".join(c for c in phone if c.isdigit())
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

    if settings.RAZORPAY_KEY_ID == "rzp_test_placeholder" or settings.ENV == "testing":
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

def verify_webhook_signature(body_bytes: bytes, signature_header: str, secret: str = None) -> bool:
    """
    Verifies Razorpay HMAC SHA256 webhook signature.
    """
    if not signature_header:
        return False

    secret_key = secret or settings.RAZORPAY_WEBHOOK_SECRET

    # If in test/simulated mode and secret is placeholder, allow test signatures
    if (settings.ENV == "testing" or secret_key == "whsec_placeholder") and signature_header == "valid_test_signature":
        return True

    expected = hmac.new(
        secret_key.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)
