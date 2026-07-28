from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.score import Score
from app.models.follow_up import FollowUp
from app.models.subscription import Subscription

@pytest.mark.asyncio
async def test_create_broker(db_session: AsyncSession):
    broker = Broker(
        email="rajesh@realty.in",
        phone="+919988776655",
        name="Rajesh Verma",
        agency_name="Verma Properties",
        city="Mumbai",
        whatsapp_number="+919988776655",
        subscription_status="trial"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    assert broker.id is not None
    assert broker.email == "rajesh@realty.in"
    assert broker.city == "Mumbai"
    assert broker.subscription_status == "trial"

@pytest.mark.asyncio
async def test_create_lead(db_session: AsyncSession, test_broker: Broker):
    lead = Lead(
        broker_id=test_broker.id,
        phone="+919123456789",
        name="Ananya Sharma",
        source="facebook",
        score="warm",
        score_confidence=0.75,
        budget_min=8000000,
        budget_max=12000000,
        property_type="3bhk",
        transaction_type="buy",
        preferred_locations=["Whitefield"],
        timeline="3_months",
        loan_status="pre_approved",
        status="pending",
        pipeline_stage="new"
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)

    assert lead.id is not None
    assert lead.broker_id == test_broker.id
    assert lead.score == "warm"
    assert lead.score_confidence == 0.75

@pytest.mark.asyncio
async def test_create_conversation(db_session: AsyncSession, test_lead: Lead):
    conv = Conversation(
        lead_id=test_lead.id,
        direction="inbound",
        sender_type="lead",
        message="Hi, is the 2BHK in Indiranagar still available?",
        message_type="text",
        whatsapp_message_id="WAMID_123456"
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    assert conv.id is not None
    assert conv.lead_id == test_lead.id
    assert conv.message_type == "text"

@pytest.mark.asyncio
async def test_create_score(db_session: AsyncSession, test_lead: Lead):
    score = Score(
        lead_id=test_lead.id,
        score="hot",
        confidence=0.95,
        reasoning="High budget, immediate timeline, pre-approved loan.",
        extracted_data={"budget_max": 7500000, "locality": "Indiranagar"}
    )
    db_session.add(score)
    await db_session.commit()
    await db_session.refresh(score)

    assert score.id is not None
    assert score.lead_id == test_lead.id
    assert score.confidence == 0.95

@pytest.mark.asyncio
async def test_create_follow_up(db_session: AsyncSession, test_lead: Lead):
    scheduled_time = datetime.now(timezone.utc) + timedelta(days=1)
    follow_up = FollowUp(
        lead_id=test_lead.id,
        sequence_number=1,
        scheduled_at=scheduled_time,
        status="scheduled",
        message="Hi Test, following up on your Indiranagar inquiry!"
    )
    db_session.add(follow_up)
    await db_session.commit()
    await db_session.refresh(follow_up)

    assert follow_up.id is not None
    assert follow_up.sequence_number == 1
    assert follow_up.status == "scheduled"

@pytest.mark.asyncio
async def test_create_subscription(db_session: AsyncSession, test_broker: Broker):
    subscription = Subscription(
        broker_id=test_broker.id,
        razorpay_payment_id="pay_123456789",
        razorpay_subscription_id="sub_987654321",
        amount=499900,  # 4999.00 INR in paise
        currency="INR",
        status="active",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(subscription)

    assert subscription.id is not None
    assert subscription.broker_id == test_broker.id
    assert subscription.amount == 499900
    assert subscription.status == "active"
