"""
Part 18 — Real Estate Deal, Booking & Transaction OS: Lifecycle Tests
======================================================================
Tests the complete commercial lifecycle:
  1. Deal creation, reference generation, and stage history
  2. Idempotency on deal mutations
  3. Offer submission, negotiation history versioning, counter & accept
  4. Unit reservation creation with TTL expiry
  5. Human-in-the-loop approval gate for booking confirmation
  6. High-precision commission ledger calculation & splits
  7. Legal closing & title deed handover workflow
  8. Post-sale customer satisfaction, NPS & AI learning signals
  9. Deterministic state machine & irreversible stage guard
  10. Pipeline summary metrics aggregation
"""
import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

import app.models
from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.deal_models import (
    Deal, DealStage, DealStageHistory, DealOffer, DealReservation,
    DealBooking, DealCommission, DealClosing, DealPostSale,
    DealApprovalRequest, DealCommercialAuditLog
)
from app.models.outbox_models import OutboxEvent
from app.modules.deals.services.deal_service import DealService, DealServiceError


@pytest.fixture
async def deal_session():
    """In-memory async SQLite session with full model schema."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    async with session_factory() as session:
        # Seed broker and lead
        broker_id = uuid.uuid4()
        org_id = uuid.uuid4()
        broker = Broker(
            id=broker_id,
            email="broker.test@wefylabs.com",
            name="Aamir Broker",
            password_hash="hash",
            phone="+971501234567"
        )
        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker_id,
            name="High Net Worth Buyer",
            phone="+971509999999",
            email="hnw@investor.ae",
            pipeline_stage="negotiating",
            score="hot",
            status="active"
        )
        session.add(broker)
        session.add(lead)
        await session.commit()
        yield session, str(broker_id), str(org_id), str(lead.id)

    await engine.dispose()


@pytest.mark.asyncio
async def test_deal_creation_and_stage_history(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Palm Jumeirah Villa Purchase",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.OPPORTUNITY,
        agreed_price=Decimal("15000000.0000"),
        currency="AED",
        commission_percentage=Decimal("2.00"),
        tags=["luxury", "villa", "waterfront"],
        idempotency_key="palm-deal-001"
    )

    assert deal is not None
    assert str(deal.organization_id) == org_id
    assert deal.deal_title == "Palm Jumeirah Villa Purchase"
    assert deal.current_stage == DealStage.OPPORTUNITY
    assert deal.status == "ACTIVE"
    assert deal.deal_reference.startswith("WL-")

    # Verify stage history record
    hist_res = await session.execute(
        select(DealStageHistory).where(DealStageHistory.deal_id == deal.id)
    )
    history = hist_res.scalars().all()
    assert len(history) == 1
    assert history[0].to_stage == DealStage.OPPORTUNITY

    # Verify transactional outbox event
    outbox_res = await session.execute(
        select(OutboxEvent).where(OutboxEvent.aggregate_id == str(deal.id))
    )
    events = outbox_res.scalars().all()
    assert len(events) >= 1
    assert events[0].event_type == "deal.created"
    assert events[0].payload["deal_reference"] == deal.deal_reference

    # Verify commercial audit log
    audit_res = await session.execute(
        select(DealCommercialAuditLog).where(DealCommercialAuditLog.deal_id == deal.id)
    )
    logs = audit_res.scalars().all()
    assert len(logs) >= 1
    assert logs[0].event_type == "deal.created"


@pytest.mark.asyncio
async def test_deal_idempotency(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(deal_session[0])

    deal1 = await service.create_deal(
        lead_id=lead_id,
        deal_title="Downtown Duplex",
        broker_id=broker_id,
        organization_id=org_id,
        idempotency_key="idemp-key-999"
    )

    deal2 = await service.create_deal(
        lead_id=lead_id,
        deal_title="Downtown Duplex Duplicate",
        broker_id=broker_id,
        organization_id=org_id,
        idempotency_key="idemp-key-999"
    )

    assert deal1.id == deal2.id
    assert deal1.deal_reference == deal2.deal_reference


@pytest.mark.asyncio
async def test_offer_lifecycle_and_negotiation_versioning(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Marina Penthouse",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.NEGOTIATION
    )

    # 1. Buyer submits initial offer (v1)
    offer_v1 = await service.submit_offer(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        offer_price=Decimal("4800000.0000"),
        currency="AED",
        listing_price=Decimal("5200000.0000"),
        special_conditions="Subject to valuation"
    )
    assert offer_v1.version == 1
    assert offer_v1.status == "SUBMITTED"
    assert offer_v1.offer_price == Decimal("4800000.0000")

    # 2. Seller counters offer
    offer_countered = await service.respond_to_offer(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        action="COUNTER",
        counter_offer_price=Decimal("5000000.0000")
    )
    assert offer_countered.status == "COUNTERED"
    assert offer_countered.counter_offer_price == Decimal("5000000.0000")

    # 3. Buyer submits revised offer (v2) - archives v1 in offer_history
    offer_v2 = await service.submit_offer(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        offer_price=Decimal("4950000.0000"),
        currency="AED"
    )
    assert offer_v2.version == 2
    assert offer_v2.status == "SUBMITTED"
    assert len(offer_v2.offer_history) == 1
    assert offer_v2.offer_history[0]["version"] == 1
    assert offer_v2.offer_history[0]["offer_price"] == 4800000.0

    # 4. Seller accepts revised offer
    offer_accepted = await service.respond_to_offer(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        action="ACCEPT"
    )
    assert offer_accepted.status == "ACCEPTED"
    assert offer_accepted.accepted_at is not None

    # Verify deal agreed price updated to accepted offer price
    await session.refresh(deal)
    assert deal.agreed_price == Decimal("4950000.0000")


@pytest.mark.asyncio
async def test_unit_reservation(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Dubai Hills Estate Villa",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.RESERVATION
    )

    expiry = datetime.now(timezone.utc) + timedelta(days=3)
    res = await service.create_reservation(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        reservation_amount=Decimal("50000.0000"),
        reserved_price=Decimal("7500000.0000"),
        currency="AED",
        expires_at=expiry,
        customer_name="Sheikh Investor",
        customer_phone="+971501112233"
    )

    assert res is not None
    assert res.status == "ACTIVE"
    assert res.reservation_amount == Decimal("50000.0000")
    res_expires = res.expires_at.replace(tzinfo=timezone.utc) if res.expires_at.tzinfo is None else res.expires_at
    assert abs((res_expires - expiry).total_seconds()) < 1

    # Duplicate reservation on same deal is rejected
    with pytest.raises(DealServiceError, match="Reservation already exists"):
        await service.create_reservation(
            deal_id=str(deal.id),
            organization_id=org_id,
            actor_id=broker_id
        )


@pytest.mark.asyncio
async def test_booking_approval_gate_and_confirmation(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Creek Harbour Tower 1",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.RESERVATION
    )

    # 1. Attempting to jump directly to irreversible BOOKING stage without approval fails
    with pytest.raises(DealServiceError, match="requires an approved DealApprovalRequest"):
        await service.advance_stage(
            deal_id=str(deal.id),
            target_stage=DealStage.BOOKING,
            organization_id=org_id,
            actor_id=broker_id
        )

    # 2. Request booking approval (human-in-the-loop gate)
    approval = await service.request_booking_approval(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        booked_price=Decimal("3200000.0000"),
        currency="AED",
        token_amount=Decimal("160000.0000"),
        payment_plan_type="INSTALLMENT",
        idempotency_key="book-req-001"
    )
    assert approval.status == "PENDING"
    assert approval.action_type == "BOOKING_CONFIRM"

    # 3. Manager approves and confirms booking
    booking = await service.approve_and_confirm_booking(
        deal_id=str(deal.id),
        organization_id=org_id,
        reviewer_id=broker_id,
        approval_id=str(approval.id),
        review_notes="Approved token deposit via manager cheque"
    )
    assert booking.status == "CONFIRMED"
    assert booking.booking_reference.startswith("BK-")
    assert booking.token_amount == Decimal("160000.0000")

    # 4. Now stage can advance to BOOKING since approval is verified
    await service.advance_stage(
        deal_id=str(deal.id),
        target_stage=DealStage.BOOKING,
        organization_id=org_id,
        actor_id=broker_id
    )
    await session.refresh(deal)
    assert deal.current_stage == DealStage.BOOKING


@pytest.mark.asyncio
async def test_commission_ledger_calculation(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Business Bay Commercial Floor",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.COMMISSION
    )

    transaction_price = Decimal("10000000.0000")  # 10M AED
    comm_pct = Decimal("2.00")                   # 2% = 200,000 AED gross
    tax = Decimal("10000.0000")                   # 10,000 AED tax

    splits = [
        {"agent_id": broker_id, "role": "listing_agent", "split_pct": 50, "split_amount": 95000.0},
        {"agent_id": str(uuid.uuid4()), "role": "selling_agent", "split_pct": 50, "split_amount": 95000.0}
    ]

    comm = await service.record_commission(
        deal_id=str(deal.id),
        organization_id=org_id,
        broker_id=broker_id,
        actor_id=broker_id,
        transaction_price=transaction_price,
        currency="AED",
        commission_percentage=comm_pct,
        tax_deducted=tax,
        commission_splits=splits,
        invoice_reference="INV-2026-WL-0088",
        idempotency_key="comm-key-01"
    )

    assert comm.gross_commission == Decimal("200000.0000")
    assert comm.net_commission == Decimal("190000.0000")
    assert comm.status == "PENDING"
    assert comm.invoice_reference == "INV-2026-WL-0088"
    assert len(comm.commission_splits) == 2


@pytest.mark.asyncio
async def test_closing_and_deal_won(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Bluewaters Island Luxury Condo",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.CLOSING
    )

    closing = await service.create_closing(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        registration_authority="Dubai Land Department (DLD)",
        registration_number="REG-DLD-98213",
        title_deed_number="TD-2026-004412",
        handover_date=datetime.now(timezone.utc)
    )
    assert closing.status == "IN_PROGRESS"
    assert closing.registration_authority == "Dubai Land Department (DLD)"
    assert len(closing.closing_checklist) == 5

    # Complete closing
    updated_deal = await service.complete_closing(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id
    )
    assert updated_deal.status == "CLOSED_WON"
    assert updated_deal.closed_at is not None
    assert updated_deal.close_reason == "Closing completed"


@pytest.mark.asyncio
async def test_post_sale_and_learning_signals(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Jumeirah Golf Estates Villa",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.POST_SALE
    )

    ps = await service.record_post_sale(
        deal_id=str(deal.id),
        organization_id=org_id,
        actor_id=broker_id,
        customer_satisfaction_score=9,
        nps_score=85,
        feedback_text="Exceptional advisory on off-plan handover and snagging.",
        referral_given=True,
        success_factors=["responsive_ai", "clear_payment_schedule", "seamless_closing"],
        obstacle_factors=["bank_valuation_delay"],
        ai_recommendation_followed=True
    )

    assert ps.customer_satisfaction_score == 9
    assert ps.nps_score == 85
    assert ps.referral_given is True
    assert ps.ai_recommendation_followed is True
    assert "responsive_ai" in ps.success_factors


@pytest.mark.asyncio
async def test_irreversible_stage_backwards_transition_prevented(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    deal = await service.create_deal(
        lead_id=lead_id,
        deal_title="Downtown Tower Deal",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.BOOKING
    )

    # Attempt to transition backwards from irreversible BOOKING to OFFER
    with pytest.raises(DealServiceError, match="is irreversible"):
        await service.advance_stage(
            deal_id=str(deal.id),
            target_stage=DealStage.OFFER,
            organization_id=org_id,
            actor_id=broker_id
        )


@pytest.mark.asyncio
async def test_pipeline_summary_metrics(deal_session):
    session, broker_id, org_id, lead_id = deal_session
    service = DealService(session)

    # Create 2 deals at different stages
    await service.create_deal(
        lead_id=lead_id,
        deal_title="Deal Alpha",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.OPPORTUNITY,
        agreed_price=Decimal("1000000")
    )
    await service.create_deal(
        lead_id=lead_id,
        deal_title="Deal Beta",
        broker_id=broker_id,
        organization_id=org_id,
        current_stage=DealStage.NEGOTIATION,
        agreed_price=Decimal("2000000")
    )

    summary = await service.get_pipeline_summary(broker_id, org_id)
    assert summary["total_active_deals"] >= 2
    assert summary["total_pipeline_value"] >= 3000000.0
    assert summary["deals_by_stage"].get(DealStage.OPPORTUNITY, 0) >= 1
    assert summary["deals_by_stage"].get(DealStage.NEGOTIATION, 0) >= 1
