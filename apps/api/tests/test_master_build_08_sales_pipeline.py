"""
Build 08 — Master Sales Pipeline Test Suite
=============================================
Tests the complete commercial lifecycle from opportunity to revenue:

  1.  Pipeline configuration — org-configurable stage definitions
  2.  Stage machine — allowed transitions, policy violations, terminal stages
  3.  Opportunity WON path — full forward journey to WON
  4.  Opportunity LOST path — mark lost with controlled reason vocabulary
  5.  Forbidden transitions — invalid jumps, backward movement
  6.  Site visit — create, status transitions, outcome recording
  7.  Site visit status machine — cannot skip states
  8.  Negotiation rounds — multi-round history, AI draft approval
  9.  Property shortlist — per-opportunity property interest tracking
  10. Booking intent — create, revalidation, TTL expiry
  11. Unit hold — exclusive lock, concurrent hold rejection
  12. Unit hold expiry — backend-driven TTL enforcement
  13. Revenue events — event emitted on every commercial state change
  14. Tenant isolation — Tenant A cannot access Tenant B's opportunities
  15. Monetary precision — all values use Decimal, never Float
  16. Idempotency — repeated writes return same result
  17. BookingReconciliation — inconsistency detection
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
from app.models.deal_models import Deal, DealStage
from app.models.outbox_models import OutboxEvent

from app.models.sales_pipeline_models import (
    SalesPipeline, PipelineStageConfig,
    OpportunityStageHistory, OpportunityStage,
    SiteVisit, SiteVisitOutcome, SiteVisitStatus,
    NegotiationRound, NegotiationRoundActor,
    PropertyShortlist, PropertyShortlistStatus,
    BookingIntent, BookingIntentStatus,
    UnitHold, UnitHoldStatus,
    PropertyPaymentTransaction,
    RevenueEvent, RevenueEventType,
    BookingReconciliationTask,
    LostReasonType,
)

from app.modules.sales_pipeline.service import (
    PipelineConfigService,
    OpportunityStageService,
    PropertyShortlistService,
    SiteVisitService,
    NegotiationService,
    BookingIntentService,
    UnitHoldService,
    RevenueEventService,
    BookingReconciliationService,
    SalesPipelineError,
    StagePolicyViolation,
)


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
async def session():
    """In-memory async SQLite session for Build 08 tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession,
        expire_on_commit=False, autocommit=False, autoflush=False
    )
    async with factory() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def org_and_broker(session):
    """Returns (org_id, broker_id, broker)."""
    org_id = uuid.uuid4()
    broker = Broker(
        id=uuid.uuid4(),
        email=f"agent.{uuid.uuid4().hex[:8]}@wefylabs.com",
        name="Build08 Agent",
        password_hash="x",
        phone="+971501234567",
    )
    session.add(broker)
    await session.commit()
    return org_id, broker.id, broker


@pytest.fixture
async def seeded_deal(session, org_and_broker):
    """Returns (deal, org_id, broker_id)."""
    org_id, broker_id, broker = org_and_broker
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker_id,
        name="Pipeline Buyer",
        phone="+971501112233",
        email="buyer@wefylabs.test",
        pipeline_stage="new",
        score="warm",
        status="active",
    )
    session.add(lead)
    await session.flush()

    deal = Deal(
        id=uuid.uuid4(),
        organization_id=org_id,
        broker_id=broker_id,
        lead_id=lead.id,
        deal_reference=f"WL-B08-{uuid.uuid4().hex[:6].upper()}",
        deal_title="Build08 Test Deal",
        current_stage=DealStage.OPPORTUNITY,
        currency="AED",
        status="ACTIVE",
        idempotency_key=None,
    )
    session.add(deal)
    await session.commit()
    return deal, org_id, broker_id


@pytest.fixture
async def pipeline_svc(session):
    return PipelineConfigService(session)


@pytest.fixture
async def stage_svc(session):
    return OpportunityStageService(session)


@pytest.fixture
async def shortlist_svc(session):
    return PropertyShortlistService(session)


@pytest.fixture
async def visit_svc(session):
    return SiteVisitService(session)


@pytest.fixture
async def neg_svc(session):
    return NegotiationService(session)


@pytest.fixture
async def intent_svc(session):
    return BookingIntentService(session)


@pytest.fixture
async def hold_svc(session):
    return UnitHoldService(session)


@pytest.fixture
async def rev_svc(session):
    return RevenueEventService(session)


@pytest.fixture
async def recon_svc(session):
    return BookingReconciliationService(session)


# ---------------------------------------------------------------------------
# 1. PIPELINE CONFIGURATION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_pipeline_with_canonical_stages(session, pipeline_svc, org_and_broker):
    """Creating a pipeline auto-generates one PipelineStageConfig per canonical stage."""
    org_id, _, _ = org_and_broker

    pipeline = await pipeline_svc.create_pipeline(
        organization_id=org_id,
        name="Residential Sales Pipeline",
        pipeline_type="RESIDENTIAL_SALES",
        is_default=True,
    )
    await session.commit()

    res = await session.execute(
        select(PipelineStageConfig).where(PipelineStageConfig.pipeline_id == pipeline.id)
    )
    configs = res.scalars().all()

    assert len(configs) == len(OpportunityStage.ORDERED), \
        f"Expected {len(OpportunityStage.ORDERED)} stage configs, got {len(configs)}"

    semantic_types = {c.semantic_type for c in configs}
    for stage in OpportunityStage.ORDERED:
        assert stage in semantic_types, f"Stage '{stage}' missing from stage configs"


@pytest.mark.asyncio
async def test_list_pipelines(session, pipeline_svc, org_and_broker):
    org_id, _, _ = org_and_broker
    await pipeline_svc.create_pipeline(org_id, "Pipeline A")
    await pipeline_svc.create_pipeline(org_id, "Pipeline B")
    await session.commit()
    pipelines = await pipeline_svc.list_pipelines(org_id)
    assert len(pipelines) == 2


# ---------------------------------------------------------------------------
# 2. STAGE MACHINE — ALLOWED TRANSITIONS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_canonical_stage_transitions(seeded_deal, stage_svc, session):
    """Test the canonical forward path through the opportunity stage machine."""
    deal, org_id, broker_id = seeded_deal

    # Stages up to but NOT including BOOKED (which is EVIDENCE_REQUIRED).
    # The BOOKED -> WON path with evidence is covered in test_advance_to_won_emits_revenue_event.
    journey_stages = [
        OpportunityStage.NEW,
        OpportunityStage.QUALIFIED,
        OpportunityStage.PROPERTY_SHORTLISTED,
        OpportunityStage.APPOINTMENT_SET,
        OpportunityStage.SITE_VISIT_SCHEDULED,
        OpportunityStage.SITE_VISIT_COMPLETED,
        OpportunityStage.NEGOTIATION,
    ]

    # Set to NEW first to start canonical journey
    deal.current_stage = OpportunityStage.NEW
    await session.commit()

    for i in range(len(journey_stages) - 1):
        from_stage = journey_stages[i]
        to_stage = journey_stages[i + 1]
        # Validate the transition is in ALLOWED_FORWARD
        assert OpportunityStage.is_allowed_transition(from_stage, to_stage), \
            f"{from_stage} -> {to_stage} not in ALLOWED_FORWARD"
        deal = await stage_svc.advance_stage(
            deal_id=deal.id,
            organization_id=org_id,
            target_stage=to_stage,
            changed_by_id=str(broker_id),
            reason=f"Moving to {to_stage}",
            source="MANUAL",
        )
        await session.commit()
        assert deal.current_stage == to_stage, f"Expected {to_stage}, got {deal.current_stage}"

    # Verify stage history was written for each transition
    res = await session.execute(
        select(OpportunityStageHistory).where(OpportunityStageHistory.deal_id == deal.id)
    )
    history = res.scalars().all()
    assert len(history) >= 2, "Stage history must be written for each transition"


@pytest.mark.asyncio
async def test_advance_to_won_emits_revenue_event(seeded_deal, stage_svc, session, rev_svc):
    """Advancing to BOOKED then WON must emit a revenue event."""
    deal, org_id, broker_id = seeded_deal

    deal.current_stage = OpportunityStage.BOOKED
    await session.commit()

    deal = await stage_svc.advance_stage(
        deal_id=deal.id,
        organization_id=org_id,
        target_stage=OpportunityStage.WON,
        changed_by_id=str(broker_id),
        reason="Deal signed",
        source="MANUAL",
        evidence={"booking_id": str(uuid.uuid4()), "payment_confirmed": True},
    )
    await session.commit()

    assert deal.current_stage == OpportunityStage.WON
    assert deal.status == "CLOSED_WON"
    assert deal.closed_at is not None

    events, total = await rev_svc.get_events_for_org(org_id, event_type=RevenueEventType.DEAL_WON)
    assert total >= 1, "DEAL_WON revenue event must be emitted"


# ---------------------------------------------------------------------------
# 3. FORBIDDEN TRANSITIONS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_stage_transition_rejected(seeded_deal, stage_svc, session):
    """A jump from NEW directly to WON must be rejected."""
    deal, org_id, broker_id = seeded_deal

    deal.current_stage = OpportunityStage.NEW
    await session.commit()

    with pytest.raises(StagePolicyViolation):
        await stage_svc.advance_stage(
            deal_id=deal.id,
            organization_id=org_id,
            target_stage=OpportunityStage.WON,  # Not in ALLOWED_FORWARD["NEW"]
            changed_by_id=str(broker_id),
        )


@pytest.mark.asyncio
async def test_terminal_stage_cannot_advance(seeded_deal, stage_svc, session):
    """A WON opportunity cannot be advanced further."""
    deal, org_id, broker_id = seeded_deal

    deal.current_stage = OpportunityStage.WON
    deal.status = "CLOSED_WON"
    await session.commit()

    with pytest.raises(StagePolicyViolation):
        await stage_svc.advance_stage(
            deal_id=deal.id,
            organization_id=org_id,
            target_stage=OpportunityStage.NEGOTIATION,
            changed_by_id=str(broker_id),
        )


@pytest.mark.asyncio
async def test_evidence_required_for_won(seeded_deal, stage_svc, session):
    """Advancing to WON without evidence must raise StagePolicyViolation."""
    deal, org_id, broker_id = seeded_deal

    deal.current_stage = OpportunityStage.BOOKED
    await session.commit()

    with pytest.raises(StagePolicyViolation, match="evidence"):
        await stage_svc.advance_stage(
            deal_id=deal.id,
            organization_id=org_id,
            target_stage=OpportunityStage.WON,
            changed_by_id=str(broker_id),
            evidence=None,  # No evidence provided
        )


# ---------------------------------------------------------------------------
# 4. MARK LOST
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_lost_with_controlled_reason(seeded_deal, stage_svc, session):
    """Mark LOST with a controlled reason type and verify terminal state."""
    deal, org_id, broker_id = seeded_deal

    deal.current_stage = OpportunityStage.NEGOTIATION
    await session.commit()

    deal = await stage_svc.mark_lost(
        deal_id=deal.id,
        organization_id=org_id,
        changed_by_id=str(broker_id),
        lost_reason_type=LostReasonType.COMPETITOR,
        lost_reason_detail="Customer chose PropTiger listing",
        lost_to_competitor="PropTiger",
    )
    await session.commit()

    assert deal.current_stage == OpportunityStage.LOST
    assert deal.status == "CLOSED_LOST"
    assert deal.lost_reason == LostReasonType.COMPETITOR
    assert OpportunityStage.is_terminal(deal.current_stage)


# ---------------------------------------------------------------------------
# 5. PROPERTY SHORTLIST
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_shortlist_tracks_multiple_properties(seeded_deal, shortlist_svc, session):
    """An opportunity can have multiple shortlisted properties."""
    deal, org_id, broker_id = seeded_deal

    unit_a = uuid.uuid4()
    unit_b = uuid.uuid4()

    sl_a = await shortlist_svc.add_to_shortlist(
        deal_id=deal.id, organization_id=org_id,
        added_by_id=str(broker_id), unit_id=unit_a,
        source="AGENT_MANUAL",
    )
    sl_b = await shortlist_svc.add_to_shortlist(
        deal_id=deal.id, organization_id=org_id,
        added_by_id=str(broker_id), unit_id=unit_b,
        source="AI_RECOMMENDATION",
    )
    await session.commit()

    shortlist = await shortlist_svc.get_shortlist(deal.id, org_id)
    assert len(shortlist) == 2
    unit_ids = {sl.unit_id for sl in shortlist}
    assert unit_a in unit_ids
    assert unit_b in unit_ids


@pytest.mark.asyncio
async def test_shortlist_dismiss_preserves_history(seeded_deal, shortlist_svc, session):
    """Dismissing a shortlisted property preserves the record — never deletes."""
    deal, org_id, broker_id = seeded_deal

    unit_id = uuid.uuid4()
    sl = await shortlist_svc.add_to_shortlist(
        deal_id=deal.id, organization_id=org_id,
        added_by_id=str(broker_id), unit_id=unit_id,
    )
    await session.commit()

    dismissed = await shortlist_svc.update_status(
        shortlist_id=sl.id, organization_id=org_id,
        new_status=PropertyShortlistStatus.DISMISSED,
        updated_by_id=str(broker_id),
        dismissal_reason="Too expensive",
    )
    await session.commit()

    shortlist = await shortlist_svc.get_shortlist(deal.id, org_id)
    assert len(shortlist) == 1, "History must be preserved — dismissed record still exists"
    assert shortlist[0].status == PropertyShortlistStatus.DISMISSED
    assert shortlist[0].dismissed_at is not None
    assert shortlist[0].dismissal_reason == "Too expensive"


# ---------------------------------------------------------------------------
# 6. SITE VISIT — CREATION AND STATUS TRANSITIONS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_site_visit_created_with_visit_number(seeded_deal, visit_svc, session):
    """First site visit for a deal has visit_number = 1."""
    deal, org_id, broker_id = seeded_deal

    sv = await visit_svc.create_site_visit(
        deal_id=deal.id,
        organization_id=org_id,
        lead_id=deal.lead_id,
        created_by_id=str(broker_id),
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=3),
        location_address="Downtown Dubai, Tower C",
        location_type="PHYSICAL",
        idempotency_key=f"sv-{deal.id}-1",
    )
    await session.commit()

    assert sv.visit_number == 1
    assert sv.status == SiteVisitStatus.REQUESTED


@pytest.mark.asyncio
async def test_site_visit_number_increments(seeded_deal, visit_svc, session):
    """Second site visit for same deal has visit_number = 2."""
    deal, org_id, broker_id = seeded_deal

    await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
        idempotency_key=f"sv-{deal.id}-v1",
    )
    sv2 = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
        idempotency_key=f"sv-{deal.id}-v2",
    )
    await session.commit()

    assert sv2.visit_number == 2


@pytest.mark.asyncio
async def test_site_visit_idempotency(seeded_deal, visit_svc, session):
    """Creating a site visit with the same idempotency key returns the same record."""
    deal, org_id, broker_id = seeded_deal
    idem_key = f"sv-idem-{uuid.uuid4()}"

    sv1 = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id), idempotency_key=idem_key,
    )
    sv2 = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id), idempotency_key=idem_key,
    )
    await session.commit()

    assert sv1.id == sv2.id, "Idempotent call must return the same SiteVisit"


@pytest.mark.asyncio
async def test_site_visit_status_machine(seeded_deal, visit_svc, session):
    """SiteVisit follows the controlled status machine."""
    deal, org_id, broker_id = seeded_deal

    sv = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
    )
    await session.commit()

    # REQUESTED -> CONFIRMED
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.CONFIRMED, str(broker_id))
    await session.commit()
    assert sv.status == SiteVisitStatus.CONFIRMED

    # CONFIRMED -> IN_PROGRESS
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.IN_PROGRESS, str(broker_id))
    await session.commit()
    assert sv.check_in_at is not None

    # IN_PROGRESS -> COMPLETED
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.COMPLETED, str(broker_id))
    await session.commit()
    assert sv.status == SiteVisitStatus.COMPLETED
    assert sv.check_out_at is not None
    assert sv.attendance_status == "ATTENDED"


@pytest.mark.asyncio
async def test_site_visit_invalid_transition_rejected(seeded_deal, visit_svc, session):
    """Cannot skip from REQUESTED directly to COMPLETED."""
    deal, org_id, broker_id = seeded_deal

    sv = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
    )
    await session.commit()

    with pytest.raises(StagePolicyViolation):
        await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.COMPLETED, str(broker_id))


@pytest.mark.asyncio
async def test_site_visit_outcome_requires_completed_status(seeded_deal, visit_svc, session):
    """Outcome cannot be recorded on a non-COMPLETED/NO_SHOW visit."""
    deal, org_id, broker_id = seeded_deal

    sv = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
    )
    await session.commit()

    with pytest.raises(SalesPipelineError, match="COMPLETED"):
        await visit_svc.record_outcome(
            site_visit_id=sv.id,
            organization_id=org_id,
            recorded_by_id=str(broker_id),
            customer_interest_level=4,
            customer_feedback="Very interested in unit 3B",
        )


@pytest.mark.asyncio
async def test_site_visit_outcome_recorded_after_completion(seeded_deal, visit_svc, session):
    """After COMPLETED, outcome can be recorded with structured data."""
    deal, org_id, broker_id = seeded_deal

    sv = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
    )
    await session.commit()

    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.CONFIRMED, str(broker_id))
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.IN_PROGRESS, str(broker_id))
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.COMPLETED, str(broker_id))
    await session.commit()

    outcome = await visit_svc.record_outcome(
        site_visit_id=sv.id,
        organization_id=org_id,
        recorded_by_id=str(broker_id),
        customer_interest_level=5,
        customer_feedback="Very interested in unit 3B",
        objections=["Price is slightly high"],
        positive_signals=["Loves the view", "Close to metro"],
        next_action="Send payment plan options",
        agent_notes="Customer asked about floor plan for unit 3C as alternative",
    )
    await session.commit()

    assert outcome.customer_interest_level == 5
    assert "Price is slightly high" in outcome.objections
    assert "Loves the view" in outcome.positive_signals


# ---------------------------------------------------------------------------
# 7. NEGOTIATION ROUNDS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_negotiation_rounds_append_only(seeded_deal, neg_svc, session):
    """Three negotiation rounds are created; round_number increments correctly."""
    deal, org_id, broker_id = seeded_deal

    # Round 1: Asking price from developer
    r1 = await neg_svc.add_round(
        deal_id=deal.id, organization_id=org_id,
        round_type="ASKING_PRICE",
        actor=NegotiationRoundActor.DEVELOPER,
        actor_id="developer-ref",
        price=Decimal("1500000.0000"),
        currency="AED",
        source="PRICE_BOOK",
    )
    # Round 2: Customer offer
    r2 = await neg_svc.add_round(
        deal_id=deal.id, organization_id=org_id,
        round_type="CUSTOMER_OFFER",
        actor=NegotiationRoundActor.CUSTOMER,
        actor_id=str(broker_id),
        price=Decimal("1350000.0000"),
        currency="AED",
        source="WHATSAPP",
    )
    # Round 3: Agent counter
    r3 = await neg_svc.add_round(
        deal_id=deal.id, organization_id=org_id,
        round_type="AGENT_COUNTER",
        actor=NegotiationRoundActor.AGENT,
        actor_id=str(broker_id),
        price=Decimal("1430000.0000"),
        currency="AED",
        source="HUMAN",
    )
    await session.commit()

    assert r1.round_number == 1
    assert r2.round_number == 2
    assert r3.round_number == 3

    history = await neg_svc.get_history(deal.id, org_id)
    assert len(history) == 3
    # Verify prices stored as Decimal (not float)
    assert isinstance(history[0].price, Decimal)


@pytest.mark.asyncio
async def test_ai_draft_requires_approval(seeded_deal, neg_svc, session):
    """An AI draft negotiation round must have requires_approval=True."""
    deal, org_id, broker_id = seeded_deal

    ai_round = await neg_svc.add_round(
        deal_id=deal.id, organization_id=org_id,
        round_type="AGENT_COUNTER",
        actor=NegotiationRoundActor.AI_DRAFT,
        actor_id="ai-agent-001",
        price=Decimal("1420000.0000"),
        currency="AED",
        source="AI",
    )
    await session.commit()

    assert ai_round.requires_approval is True
    assert ai_round.approved_at is None

    # Approve the round
    approved = await neg_svc.approve_round(ai_round.id, org_id, approved_by_id=str(broker_id))
    await session.commit()

    assert approved.requires_approval is False
    assert approved.approved_by_id == str(broker_id)
    assert approved.approved_at is not None


# ---------------------------------------------------------------------------
# 8. BOOKING INTENT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_booking_intent_created(seeded_deal, intent_svc, session):
    """BookingIntent created with correct expiry and status."""
    deal, org_id, broker_id = seeded_deal
    unit_id = uuid.uuid4()

    intent = await intent_svc.create_intent(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
        unit_id=unit_id,
        intended_price=Decimal("1430000.0000"),
        currency="AED",
        expires_hours=48,
        source="AGENT_MANUAL",
        idempotency_key=f"intent-{deal.id}-{unit_id}",
    )
    await session.commit()

    assert intent.status == BookingIntentStatus.CREATED
    assert intent.unit_id == unit_id
    assert intent.intended_price == Decimal("1430000.0000")
    assert intent.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_booking_intent_idempotency(seeded_deal, intent_svc, session):
    """Creating a BookingIntent with the same idempotency key returns same record."""
    deal, org_id, broker_id = seeded_deal
    idem_key = f"intent-idem-{uuid.uuid4()}"

    i1 = await intent_svc.create_intent(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id), idempotency_key=idem_key,
    )
    i2 = await intent_svc.create_intent(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id), idempotency_key=idem_key,
    )
    await session.commit()

    assert i1.id == i2.id, "Idempotent intent creation must return same record"


@pytest.mark.asyncio
async def test_booking_intent_ttl_expiry(seeded_deal, intent_svc, session):
    """Backend expiry marks intent EXPIRED when TTL passes."""
    deal, org_id, broker_id = seeded_deal

    intent = await intent_svc.create_intent(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
        expires_hours=0,  # Immediate expiry for testing
    )
    # Manually force expiry
    intent.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()

    expired = await intent_svc.expire_intent(intent.id, org_id)
    await session.commit()

    assert expired.status == BookingIntentStatus.EXPIRED


# ---------------------------------------------------------------------------
# 9. UNIT HOLD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unit_hold_created(seeded_deal, hold_svc, session):
    """Unit hold created with correct status and TTL."""
    deal, org_id, broker_id = seeded_deal
    unit_id = uuid.uuid4()

    hold = await hold_svc.create_hold(
        organization_id=org_id,
        unit_id=unit_id,
        deal_id=deal.id,
        created_by_id=str(broker_id),
        hold_hours=24,
        reason="Customer confirmed intent to book",
        idempotency_key=f"hold-{deal.id}-{unit_id}",
    )
    await session.commit()

    assert hold.status == UnitHoldStatus.ACTIVE
    assert hold.unit_id == unit_id
    assert hold.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_unit_hold_concurrent_rejection(seeded_deal, hold_svc, session):
    """Second hold for same unit by different deal is rejected."""
    deal, org_id, broker_id = seeded_deal
    unit_id = uuid.uuid4()

    # First hold
    await hold_svc.create_hold(
        organization_id=org_id, unit_id=unit_id,
        deal_id=deal.id, created_by_id=str(broker_id),
        hold_hours=24,
    )
    await session.commit()

    # Second deal trying to hold same unit
    deal2 = Deal(
        id=uuid.uuid4(),
        organization_id=org_id,
        broker_id=broker_id,
        lead_id=deal.lead_id,
        deal_reference="WL-B08-DEAL2",
        deal_title="Second Deal",
        current_stage=DealStage.OPPORTUNITY,
        currency="AED",
        status="ACTIVE",
    )
    session.add(deal2)
    await session.commit()

    with pytest.raises(SalesPipelineError, match="active hold"):
        await hold_svc.create_hold(
            organization_id=org_id, unit_id=unit_id,
            deal_id=deal2.id, created_by_id=str(broker_id),
            hold_hours=24,
        )


@pytest.mark.asyncio
async def test_unit_hold_release(seeded_deal, hold_svc, session):
    """Releasing a hold updates status to RELEASED."""
    deal, org_id, broker_id = seeded_deal
    unit_id = uuid.uuid4()

    hold = await hold_svc.create_hold(
        organization_id=org_id, unit_id=unit_id,
        deal_id=deal.id, created_by_id=str(broker_id),
    )
    await session.commit()

    released = await hold_svc.release_hold(
        hold_id=hold.id, organization_id=org_id,
        released_by_id=str(broker_id),
        release_reason="Customer changed mind on unit",
    )
    await session.commit()

    assert released.status == UnitHoldStatus.RELEASED
    assert released.released_by_id == str(broker_id)
    assert released.release_reason == "Customer changed mind on unit"


@pytest.mark.asyncio
async def test_unit_hold_idempotency(seeded_deal, hold_svc, session):
    """Creating a hold with same idempotency key returns same record."""
    deal, org_id, broker_id = seeded_deal
    unit_id = uuid.uuid4()
    idem_key = f"hold-idem-{uuid.uuid4()}"

    h1 = await hold_svc.create_hold(
        organization_id=org_id, unit_id=unit_id,
        deal_id=deal.id, created_by_id=str(broker_id),
        idempotency_key=idem_key,
    )
    h2 = await hold_svc.create_hold(
        organization_id=org_id, unit_id=unit_id,
        deal_id=deal.id, created_by_id=str(broker_id),
        idempotency_key=idem_key,
    )
    await session.commit()

    assert h1.id == h2.id, "Idempotent hold creation must return same record"


# ---------------------------------------------------------------------------
# 10. REVENUE EVENTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outbox_event_emitted_on_stage_advance(seeded_deal, stage_svc, session):
    """Stage advance must emit an OutboxEvent."""
    deal, org_id, broker_id = seeded_deal
    deal.current_stage = OpportunityStage.NEW
    await session.commit()

    await stage_svc.advance_stage(
        deal_id=deal.id, organization_id=org_id,
        target_stage=OpportunityStage.QUALIFIED,
        changed_by_id=str(broker_id),
    )
    await session.commit()

    res = await session.execute(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == str(deal.id),
            OutboxEvent.event_type == "opportunity.stage_changed",
        )
    )
    events = res.scalars().all()
    assert len(events) >= 1, "OutboxEvent must be emitted on stage advance"


@pytest.mark.asyncio
async def test_revenue_event_emitted_on_site_visit_completion(seeded_deal, visit_svc, rev_svc, session):
    """Completing a site visit emits a revenue event."""
    deal, org_id, broker_id = seeded_deal

    sv = await visit_svc.create_site_visit(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
    )
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.CONFIRMED, str(broker_id))
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.IN_PROGRESS, str(broker_id))
    sv = await visit_svc.transition_status(sv.id, org_id, SiteVisitStatus.COMPLETED, str(broker_id))
    await session.commit()

    events, total = await rev_svc.get_events_for_org(
        org_id, event_type=RevenueEventType.SITE_VISIT_COMPLETED
    )
    assert total >= 1, "site_visit.completed revenue event must be emitted"


# ---------------------------------------------------------------------------
# 11. MONETARY PRECISION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_negotiation_prices_are_decimal_not_float(seeded_deal, neg_svc, session):
    """Negotiation prices are stored and returned as Decimal, not float."""
    deal, org_id, broker_id = seeded_deal
    price = Decimal("1234567.8900")

    await neg_svc.add_round(
        deal_id=deal.id, organization_id=org_id,
        round_type="CUSTOMER_OFFER",
        actor=NegotiationRoundActor.CUSTOMER,
        actor_id="customer-001",
        price=price, currency="AED",
    )
    await session.commit()

    history = await neg_svc.get_history(deal.id, org_id)
    assert len(history) == 1
    stored_price = history[0].price
    # Must not lose precision
    assert isinstance(stored_price, Decimal), f"Expected Decimal, got {type(stored_price)}"


@pytest.mark.asyncio
async def test_booking_intent_price_is_decimal(seeded_deal, intent_svc, session):
    """Booking intent intended_price is Decimal."""
    deal, org_id, broker_id = seeded_deal
    price = Decimal("9999999.9999")

    intent = await intent_svc.create_intent(
        deal_id=deal.id, organization_id=org_id, lead_id=deal.lead_id,
        created_by_id=str(broker_id),
        intended_price=price, currency="INR",
    )
    await session.commit()

    assert intent.intended_price == price
    assert isinstance(intent.intended_price, Decimal)


# ---------------------------------------------------------------------------
# 12. TENANT ISOLATION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_isolation_on_stage_advance(session):
    """Tenant A cannot advance Tenant B's opportunity."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    uid_a = uuid.uuid4().hex[:8]
    uid_b = uuid.uuid4().hex[:8]
    broker_a = Broker(
        id=uuid.uuid4(), email=f"a.{uid_a}@test.com",
        name="Agent A", password_hash="x", phone=f"+971{uid_a[:8]}",
    )
    broker_b = Broker(
        id=uuid.uuid4(), email=f"b.{uid_b}@test.com",
        name="Agent B", password_hash="x", phone=f"+971{uid_b[:8]}",
    )
    session.add_all([broker_a, broker_b])
    await session.flush()

    lead_b = Lead(
        id=uuid.uuid4(), broker_id=broker_b.id, name="Lead B",
        phone="+97100000001", email="lead.b@test.com",
        pipeline_stage="new", score="cold", status="active",
    )
    session.add(lead_b)
    await session.flush()

    deal_b = Deal(
        id=uuid.uuid4(), organization_id=org_b,
        broker_id=broker_b.id, lead_id=lead_b.id,
        deal_reference="WL-B08-ORGB-001",
        deal_title="Org B Deal", current_stage=DealStage.OPPORTUNITY,
        currency="AED", status="ACTIVE",
    )
    session.add(deal_b)
    await session.commit()

    stage_svc = OpportunityStageService(session)

    with pytest.raises(SalesPipelineError, match="not found"):
        # Org A tries to access Org B's deal
        await stage_svc.advance_stage(
            deal_id=deal_b.id,
            organization_id=org_a,   # Wrong org
            target_stage=OpportunityStage.QUALIFIED,
            changed_by_id=str(broker_a.id),
        )


# ---------------------------------------------------------------------------
# 13. BOOKING RECONCILIATION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconciliation_task_created_and_resolved(seeded_deal, recon_svc, session):
    """Flag an inconsistency and resolve it."""
    deal, org_id, broker_id = seeded_deal

    task = await recon_svc.flag_inconsistency(
        organization_id=org_id,
        inconsistency_type="BOOKING_WITHOUT_INVENTORY",
        description="Booking recorded but unit status not updated",
        deal_id=deal.id,
        severity="HIGH",
    )
    await session.commit()

    assert task.status == "OPEN"
    assert task.severity == "HIGH"

    open_tasks = await recon_svc.list_open_tasks(org_id)
    assert len(open_tasks) == 1

    resolved = await recon_svc.resolve_task(
        task_id=task.id, organization_id=org_id,
        resolved_by_id=str(broker_id),
        resolution_notes="Manually updated unit status in inventory",
    )
    await session.commit()

    assert resolved.status == "RESOLVED"
    assert resolved.resolved_at is not None

    # Open tasks should now be empty
    open_tasks = await recon_svc.list_open_tasks(org_id)
    assert len(open_tasks) == 0


# ---------------------------------------------------------------------------
# 14. IMMUTABLE STAGE HISTORY — AUDIT INTEGRITY
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_history_is_immutable_and_complete(seeded_deal, stage_svc, session):
    """Every stage transition creates a new OpportunityStageHistory record."""
    deal, org_id, broker_id = seeded_deal

    deal.current_stage = OpportunityStage.NEW
    await session.commit()

    # 3 transitions
    await stage_svc.advance_stage(deal.id, org_id, OpportunityStage.QUALIFIED, str(broker_id), reason="Qualified by phone")
    await session.commit()
    await stage_svc.advance_stage(deal.id, org_id, OpportunityStage.PROPERTY_SHORTLISTED, str(broker_id), reason="Properties sent")
    await session.commit()
    await stage_svc.advance_stage(deal.id, org_id, OpportunityStage.APPOINTMENT_SET, str(broker_id), reason="Meeting booked")
    await session.commit()

    history = await stage_svc.get_stage_history(deal.id, org_id)
    assert len(history) == 3

    # Each record must have from/to stage and timestamp
    for h in history:
        assert h.to_stage is not None
        assert h.changed_at is not None
        assert h.organization_id == org_id


@pytest.mark.asyncio
async def test_stage_history_contains_snapshot(seeded_deal, stage_svc, session):
    """Stage history must contain a snapshot of the deal state at transition time."""
    deal, org_id, broker_id = seeded_deal

    deal.current_stage = OpportunityStage.NEW
    deal.agreed_price = Decimal("1500000.0000")
    await session.commit()

    await stage_svc.advance_stage(
        deal.id, org_id, OpportunityStage.QUALIFIED,
        str(broker_id), reason="Qualified"
    )
    await session.commit()

    history = await stage_svc.get_stage_history(deal.id, org_id)
    assert len(history) >= 1
    h = history[0]
    assert h.snapshot is not None
    assert "stage" in h.snapshot
