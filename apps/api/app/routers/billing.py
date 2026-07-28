import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.subscription import Subscription
from app.schemas.billing import SubscribeRequest, SubscribeResponse, SubscriptionStatusResponse
from app.services.razorpay_service import (
    PLANS,
    create_razorpay_customer,
    create_razorpay_subscription,
    verify_webhook_signature
)

router = APIRouter(prefix="/billing", tags=["Billing"])

@router.post("/subscribe", response_model=SubscribeResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    req: SubscribeRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a Razorpay customer & subscription for a broker.
    Enforces that active subscribers cannot create duplicate active subscriptions.
    """
    target_broker = current_broker
    if req.broker_id and req.broker_id != current_broker.id:
        stmt = select(Broker).where(Broker.id == req.broker_id)
        found = (await db.execute(stmt)).scalars().first()
        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broker not found."
            )
        target_broker = found

    if target_broker.subscription_status == "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Broker already has an active subscription."
        )

    if req.plan_id not in PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan ID '{req.plan_id}'. Choose from: {list(PLANS.keys())}"
        )

    plan_info = PLANS[req.plan_id]

    # Create Razorpay customer if missing
    if not target_broker.razorpay_customer_id:
        cust_id = create_razorpay_customer(
            name=target_broker.name,
            email=target_broker.email,
            phone=target_broker.phone
        )
        target_broker.razorpay_customer_id = cust_id

    # Create Razorpay subscription
    rzp_sub = create_razorpay_subscription(
        plan_id=req.plan_id,
        customer_id=target_broker.razorpay_customer_id
    )

    target_broker.razorpay_subscription_id = rzp_sub["id"]

    # Record DB Subscription
    db_sub = Subscription(
        broker_id=target_broker.id,
        razorpay_subscription_id=rzp_sub["id"],
        amount=plan_info["amount"],
        currency="INR",
        status="created"
    )
    db.add(db_sub)
    await db.commit()
    await db.refresh(db_sub)

    return SubscribeResponse(
        subscription_id=db_sub.id,
        razorpay_subscription_id=rzp_sub["id"],
        short_url=rzp_sub["short_url"],
        amount=plan_info["amount"],
        currency="INR"
    )

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Razorpay Webhook Handler for subscription lifecycle events.
    Verifies HMAC SHA256 signature and processes subscription events idempotently.
    """
    body_bytes = await request.body()
    signature_header = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(body_bytes, signature_header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay webhook signature"
        )

    data = await request.json()
    event_type = data.get("event")
    payload = data.get("payload", {})

    sub_entity = payload.get("subscription", {}).get("entity", {})
    payment_entity = payload.get("payment", {}).get("entity", {})

    rzp_sub_id = sub_entity.get("id") or payment_entity.get("subscription_id")
    rzp_pay_id = payment_entity.get("id")
    plan_id = sub_entity.get("plan_id", "starter_monthly")
    plan_info = PLANS.get(plan_id, PLANS["starter_monthly"])

    if rzp_sub_id:
        # Find broker
        broker_stmt = select(Broker).where(Broker.razorpay_subscription_id == rzp_sub_id)
        broker = (await db.execute(broker_stmt)).scalars().first()

        # Find subscription audit record
        sub_stmt = select(Subscription).where(Subscription.razorpay_subscription_id == rzp_sub_id)
        sub_record = (await db.execute(sub_stmt)).scalars().first()

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

        await db.commit()

    return {"status": "ok", "event": event_type}

@router.get("/status", response_model=SubscriptionStatusResponse, status_code=status.HTTP_200_OK)
async def get_subscription_status(
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Returns current broker subscription status, plan, trial end date, and days remaining.
    """
    return SubscriptionStatusResponse(
        subscription_status=current_broker.subscription_status,
        subscription_plan=current_broker.subscription_plan,
        trial_ends_at=current_broker.trial_ends_at,
        trial_days_remaining=current_broker.trial_days_remaining,
        razorpay_customer_id=current_broker.razorpay_customer_id,
        razorpay_subscription_id=current_broker.razorpay_subscription_id
    )
