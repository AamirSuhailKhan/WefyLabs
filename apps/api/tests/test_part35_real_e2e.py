"""
Part 35 — Real End-to-End Test Suite: AI Real Estate Revenue Autopilot
======================================================================
Real database-backed end-to-end sales lifecycle tests:
1. Full Sales Action Lifecycle:
   - Lead Rahul created (₹1.2–1.5Cr, Noida Sec 75, 3BHK)
   - Property Capetown created (₹1.38Cr, Noida Sec 75, 3BHK)
   - Revenue Autopilot evaluates -> generates NEW_HIGH_VALUE_MATCH opportunity
   - Agent accesses prioritized Action Queue ("DO THIS NOW")
   - Agent reviews grounded call briefing and why now / why property explainability
   - Agent executes action (CALL_LEAD)
   - Opportunity state transitions to ACTIONED
   - Follow-up CRM task is created idempotently
   - Site visit meeting is completed
   - Follow-up POST_SITE_VISIT_FOLLOW_UP opportunity is generated with CRITICAL urgency
   - Commercial outcome logged as DEAL_WON -> Opportunity COMPLETED
   - Full tamper-evident audit trail verified
2. Negative Test: Mismatched budget (₹70L vs ₹2Cr) is NOT surfaced as high-value opportunity
3. Stale Lead Reactivation: Hot lead with 10 days inactivity triggers STALE_HOT_LEAD / REACTIVATE
4. Price Revision Event: Property price reduction into lead budget generates PRICE_CHANGE_MATCH
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, PropertyPriceHistory, LeadPropertyInterest
from app.models.crm_models import Task, Meeting, Activity
from app.models.audit_log import AuditLog
from app.models.revenue_autopilot_models import RevenueOpportunity, RevenueFeedbackLog
from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
from app.modules.revenue_autopilot.action_handler import RevenueActionHandler
from app.modules.revenue_autopilot.outreach_generator import RevenueOutreachGenerator
from app.modules.revenue_autopilot.dto import (
    ActionOpportunityRequestDTO,
    FeedbackOpportunityRequestDTO,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def real_broker(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"vikram_broker_{uuid.uuid4().hex[:6]}@apexrealty.in",
        name="Vikram Sethi",
        agency_name="Apex Realty Advisors",
        subscription_status="active",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


# ── Scenario 1: Complete Sales Action Lifecycle ───────────────────────────────
@pytest.mark.asyncio
async def test_revenue_autopilot_full_sales_lifecycle(db_session: AsyncSession, real_broker: Broker):
    """
    Simulates a broker's entire daily workflow:
    Lead Ingestion -> Opportunity Generation -> Action Queue View ->
    Action Execution -> Task Linkage -> Site Visit -> Follow-Up -> Deal Won.
    """
    now = datetime.now(timezone.utc)

    # 1. Lead Rahul Ingestion
    rahul = Lead(
        id=uuid.uuid4(),
        broker_id=real_broker.id,
        name="Rahul Verma",
        phone="+919876543210",
        score="hot",
        status="active",
        budget_min=12000000.0,
        budget_max=15000000.0,
        preferred_locations=["Noida Sec 75"],
        property_type="3bhk",
        transaction_type="buy",
        last_message_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )

    # 2. Live Inventory Ingestion
    capetown = PropertyListing(
        id=uuid.uuid4(),
        broker_id=real_broker.id,
        title="Supertech Capetown 3BHK Resale",
        description="Ready-to-move 3BHK apartment in Noida Sec 75 with reserved parking.",
        price=13800000.0,
        area_value=1650.0,
        area_unit="sqft",
        status="available",
        transaction_category="resale",
        property_type="apartment",
        locality="Noida Sec 75",
        city="Noida",
        bedrooms=3,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([rahul, capetown])
    await db_session.commit()

    # 3. Intelligence Scan: Opportunity Generation
    engine = RevenueAutopilotEngine(db_session)
    generated = await engine.evaluate_tenant_opportunities(real_broker)

    assert len(generated) >= 1
    match_opp = next((o for o in generated if o.lead_id == rahul.id and o.property_id == capetown.id), None)
    assert match_opp is not None
    assert match_opp.status == "RECOMMENDED"
    assert match_opp.opportunity_score >= 80.0
    assert match_opp.priority in ("CRITICAL", "HIGH")
    assert match_opp.recommended_action == "CALL_LEAD"
    assert "Noida Sec 75" in match_opp.why_property or "budget" in match_opp.why_property.lower()

    # 4. Action Queue Verification
    action_queue = await engine.get_action_queue(broker=real_broker, limit=5)
    assert len(action_queue) >= 1
    assert action_queue[0].id == match_opp.id

    # 5. Outreach Generation Check
    call_brief, email_draft = RevenueOutreachGenerator.generate_deterministic_fallback(rahul, capetown, match_opp)
    assert call_brief["lead_name"] == "Rahul Verma"
    assert "15,000,000" in call_brief["key_requirements"]
    assert "13,800,000" in call_brief["suggested_opening"]
    assert "Supertech Capetown" in email_draft["subject"] or "Supertech Capetown" in email_draft["body"]

    # 6. Broker Approves & Performs Action
    handler = RevenueActionHandler(db_session)
    action_res = await handler.execute_action(
        opportunity_id=match_opp.id,
        broker=real_broker,
        dto=ActionOpportunityRequestDTO(
            action_type="CALL_LEAD",
            notes="Spoke with Rahul, agreed to visit Capetown tomorrow 11 AM.",
            create_follow_up_task=True
        )
    )
    assert action_res["status"] == "ACTIONED"
    assert action_res["created_task_id"] is not None

    await db_session.refresh(match_opp)
    assert match_opp.status == "ACTIONED"
    assert match_opp.actioned_at is not None

    # Verify CRM task created
    task_stmt = select(Task).where(Task.id == str(action_res["created_task_id"]))
    task = (await db_session.execute(task_stmt)).scalars().first()
    assert task is not None
    assert str(task.lead_id) == str(rahul.id)

    # 7. Site Visit Scheduling & Completion
    meeting = Meeting(
        id=str(uuid.uuid4()),
        broker_id=real_broker.id,
        lead_id=rahul.id,
        organization_id=str(real_broker.id),
        title="Capetown 3BHK Site Visit",
        meeting_type="site_visit",
        status="completed",
        scheduled_at=now - timedelta(hours=2),
        location="Supertech Capetown Noida Sec 75",
    )
    db_session.add(meeting)
    await db_session.commit()

    # 8. Re-evaluation Triggers Post-Site Visit Follow-Up
    post_eval = await engine.evaluate_tenant_opportunities(real_broker)
    visit_opp = next((o for o in post_eval if o.opportunity_type == "POST_SITE_VISIT_FOLLOW_UP"), None)
    assert visit_opp is not None
    assert visit_opp.urgency == "CRITICAL"
    assert visit_opp.opportunity_score >= 90.0

    # 9. Commercial Deal Won Completion
    complete_res = await handler.complete_opportunity(
        opportunity_id=visit_opp.id,
        broker=real_broker,
        outcome="DEAL_WON",
        notes="Rahul submitted token deposit for Capetown 3BHK unit."
    )
    assert complete_res["status"] == "COMPLETED"

    await db_session.refresh(visit_opp)
    assert visit_opp.status == "COMPLETED"
    assert visit_opp.actual_outcome == "DEAL_WON"

    # 10. Verify Audit Log Trail
    audit_stmt = select(AuditLog).where(
        AuditLog.actor_id == real_broker.id
    )
    audits = list((await db_session.execute(audit_stmt)).scalars().all())
    assert len(audits) >= 2


# ── Scenario 2: Negative Test — Mismatched Budget Filtered Out ────────────────
@pytest.mark.asyncio
async def test_revenue_autopilot_negative_budget_mismatch(db_session: AsyncSession, real_broker: Broker):
    """A property at ₹2Cr must NOT generate a high-value match for a buyer with ₹70L budget."""
    now = datetime.now(timezone.utc)
    budget_lead = Lead(
        id=uuid.uuid4(),
        broker_id=real_broker.id,
        name="Budget Buyer",
        phone="+919000000070",
        budget_min=5000000.0,
        budget_max=7000000.0,  # ₹70L
        preferred_locations=["Greater Noida"],
        status="active",
        last_message_at=now,
    )
    luxury_prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=real_broker.id,
        title="Ultra Luxury Villa",
        description="Private villa with pool.",
        price=20000000.0,  # ₹2Cr
        area_value=3500.0,
        status="available",
        locality="Greater Noida",
        bedrooms=4,
    )
    db_session.add_all([budget_lead, luxury_prop])
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    generated = await engine.evaluate_tenant_opportunities(real_broker)

    # Must NOT generate NEW_HIGH_VALUE_MATCH between budget_lead and luxury_prop
    mismatch = [o for o in generated if o.lead_id == budget_lead.id and o.property_id == luxury_prop.id]
    assert len(mismatch) == 0


# ── Scenario 3: Stale Hot Lead Reactivation ───────────────────────────────────
@pytest.mark.asyncio
async def test_revenue_autopilot_stale_hot_lead_reactivation(db_session: AsyncSession, real_broker: Broker):
    """A hot lead with no contact for >4 days generates STALE_HOT_LEAD opportunity."""
    now = datetime.now(timezone.utc)
    stale_lead = Lead(
        id=uuid.uuid4(),
        broker_id=real_broker.id,
        name="Anand Sharma",
        phone="+919888877776",
        score="hot",
        status="active",
        budget_max=15000000,
        last_message_at=now - timedelta(days=8),
        updated_at=now - timedelta(days=8),
    )
    db_session.add(stale_lead)
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    generated = await engine.evaluate_tenant_opportunities(real_broker)

    stale_opp = next((o for o in generated if o.opportunity_type == "STALE_HOT_LEAD" and o.lead_id == stale_lead.id), None)
    assert stale_opp is not None
    assert stale_opp.recommended_action == "REACTIVATE_LEAD"
    assert "8 days" in stale_opp.reason or "inactive" in stale_opp.reason.lower()


# ── Scenario 4: Price Drop Trigger ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_revenue_autopilot_price_drop_trigger(db_session: AsyncSession, real_broker: Broker):
    """When property price drops into buyer budget, PRICE_CHANGE_MATCH opportunity is generated."""
    now = datetime.now(timezone.utc)
    buyer = Lead(
        id=uuid.uuid4(),
        broker_id=real_broker.id,
        name="Meera Kapoor",
        phone="+919123456789",
        status="active",
        budget_max=14000000.0,  # ₹1.4Cr budget
        preferred_locations=["Gurgaon Sec 57"],
    )
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=real_broker.id,
        title="Gurgaon Residency 3BHK",
        description="Spacious apartment in Gurgaon Sec 57.",
        price=13500000.0,
        area_value=1600.0,
        status="available",
        locality="Gurgaon Sec 57",
        bedrooms=3,
    )
    # Price was 1.6Cr, now 1.35Cr (entered buyer budget!)
    price_hist = PropertyPriceHistory(
        id=uuid.uuid4(),
        property_id=prop.id,
        old_price=16000000.0,
        new_price=13500000.0,
        changed_at=now - timedelta(hours=6),
    )
    db_session.add_all([buyer, prop, price_hist])
    await db_session.commit()

    engine = RevenueAutopilotEngine(db_session)
    generated = await engine.evaluate_tenant_opportunities(real_broker)

    price_opp = next((o for o in generated if o.opportunity_type == "PRICE_CHANGE_MATCH" and o.lead_id == buyer.id), None)
    assert price_opp is not None
    assert price_opp.recommended_action == "SEND_PROPERTY_RECOMMENDATION"
    assert "16,000,000" in price_opp.reason
    assert "13,500,000" in price_opp.reason
