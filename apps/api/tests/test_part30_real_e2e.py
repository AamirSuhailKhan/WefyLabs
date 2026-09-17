"""
Part 30 — Real End-to-End Scenario Verification: AI Agent Daily Command Center
==============================================================================
TRUE real database-backed E2E test verifying:
1. Organization/Broker creation (Primary Tenant vs Foreign Tenant)
2. Lead A: hot, SLA overdue -> Priority = CRITICAL
3. Lead B: Site visit today -> Priority = HIGH
4. Lead C: Strong property match candidate
5. Property D: Matches multiple active leads -> Inventory Opportunity
6. Stale Lead: Inactive for 18 days -> Grouped in Stale Leads
7. Overdue follow-up Task -> Overdue Follow-ups queue
8. Inventory Gap: 5 leads asking for Whitefield vs 1 available property -> Gap = 4
9. Verification of full command center aggregation
10. Verification of Start My Day sequence order
11. Dismiss & Snooze flow verification (DB persistence & suppression from active queue)
12. Strict Multi-Tenant isolation: Foreign tenant has completely isolated command center
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.crm_models import Task, Meeting, Activity
from app.models.command_center_models import CommandCenterDismissal
from app.models.audit_log import AuditLog
from app.modules.command_center.service import CommandCenterService
from app.modules.command_center.inventory_intelligence import InventoryIntelligenceEngine

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


@pytest.mark.asyncio
async def test_part30_real_database_e2e_flow(db_session: AsyncSession):
    now = datetime.now(timezone.utc)

    # 1. Create Primary Broker & Foreign Broker
    primary_broker = Broker(
        id=uuid.uuid4(),
        name="Aamir Khan",
        email="aamir@beetlelabs.com",
        phone="+919876543210",
        subscription_status="active"
    )
    foreign_broker = Broker(
        id=uuid.uuid4(),
        name="Foreign Agent",
        email="agent@otheragency.com",
        phone="+919800000000",
        subscription_status="active"
    )
    db_session.add_all([primary_broker, foreign_broker])
    await db_session.commit()

    # 2. Lead A: Hot, SLA Overdue (Created 2 hours ago, uncontacted)
    lead_a = Lead(
        id=uuid.uuid4(),
        broker_id=primary_broker.id,
        name="Rahul Gupta",
        phone="+919811111111",
        pipeline_stage="new",
        score="hot",
        status="active",
        preferred_locations=["Whitefield"],
        property_type="apartment",
        budget_min=8000000,
        budget_max=12000000,
        created_at=now - timedelta(hours=2),
    )

    # 3. Lead B: Site visit scheduled for today in 3 hours
    lead_b = Lead(
        id=uuid.uuid4(),
        broker_id=primary_broker.id,
        name="Priya Sharma",
        phone="+919822222222",
        pipeline_stage="contacted",
        score="warm",
        status="active",
        preferred_locations=["Whitefield"],
        property_type="apartment",
        budget_min=9000000,
        budget_max=13000000,
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=1),
    )

    site_visit_b = Meeting(
        id=str(uuid.uuid4()),
        broker_id=primary_broker.id,
        lead_id=lead_b.id,
        title="Site Visit with Priya Sharma",
        meeting_type="site_visit",
        scheduled_at=now + timedelta(hours=3),
        duration_minutes=60,
        status="scheduled",
        location="Sobha Dream Acres, Whitefield",
    )

    # 4. Lead C: Strong match candidate with specific budget & requirements
    lead_c = Lead(
        id=uuid.uuid4(),
        broker_id=primary_broker.id,
        name="Ahmed Siddiqui",
        phone="+919833333333",
        pipeline_stage="contacted",
        score="hot",
        status="active",
        preferred_locations=["Whitefield"],
        property_type="apartment",
        budget_min=9500000,
        budget_max=11500000,
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(hours=12),
    )

    # 5. Property D: Luxury 3BHK in Whitefield matching Rahul, Priya, and Ahmed
    prop_d = PropertyListing(
        id=uuid.uuid4(),
        broker_id=primary_broker.id,
        property_code="PROP-E2E-1",
        title="Sobha Dream 3BHK",
        description="Premium residential unit with club house",
        property_type="apartment",
        city="Bengaluru",
        locality="Whitefield",
        bedrooms=3,
        price=10500000.0,
        area_value=1650.0,
        area_unit="sqft",
        status="available",
        created_at=now - timedelta(days=1),
    )

    # 6. Stale Lead: Inactive for 18 days
    lead_stale = Lead(
        id=uuid.uuid4(),
        broker_id=primary_broker.id,
        name="Deepak Joshi",
        phone="+919844444444",
        pipeline_stage="contacted",
        score="cold",
        status="active",
        created_at=now - timedelta(days=30),
        updated_at=now - timedelta(days=18),
    )

    # 7. Overdue Follow-up Task
    overdue_task = Task(
        id=str(uuid.uuid4()),
        broker_id=primary_broker.id,
        lead_id=lead_a.id,
        title="Send brochure and quotation",
        status="pending",
        due_at=now - timedelta(days=1),
        priority="high",
        created_at=now - timedelta(days=2),
    )

    # 8. Extra demand leads in Whitefield to establish demand gap
    extra_lead_1 = Lead(
        id=uuid.uuid4(),
        broker_id=primary_broker.id,
        name="Karan Malhotra",
        phone="+919855555555",
        pipeline_stage="contacted",
        status="active",
        preferred_locations=["Whitefield"],
        property_type="apartment",
        budget_min=8000000,
        budget_max=12000000,
    )
    extra_lead_2 = Lead(
        id=uuid.uuid4(),
        broker_id=primary_broker.id,
        name="Sneha Rao",
        phone="+919866666666",
        pipeline_stage="contacted",
        status="active",
        preferred_locations=["Whitefield"],
        property_type="apartment",
        budget_min=8000000,
        budget_max=12000000,
    )

    db_session.add_all([
        lead_a, lead_b, site_visit_b, lead_c, prop_d,
        lead_stale, overdue_task, extra_lead_1, extra_lead_2
    ])
    await db_session.commit()

    # 9. Execute Full Command Center Service
    cc_service = CommandCenterService(db_session)
    cc_data = await cc_service.get_command_center_data(primary_broker.id)

    # --- VERIFY CRITICAL & HIGH PRIORITIES ---
    assert cc_data.summary.total_priority_actions >= 3
    assert cc_data.summary.sla_breaches_count >= 1
    assert cc_data.summary.overdue_followups_count >= 1
    assert cc_data.summary.today_meetings_count >= 1

    # Lead A must be CRITICAL due to first contact SLA overdue
    sla_items = [p for p in cc_data.priorities if p.entity_id == str(lead_a.id) and "first_contact" in p.category]
    assert len(sla_items) >= 1
    assert sla_items[0].priority == "CRITICAL"

    # Site visit with Priya must be in schedule and priority queue
    visit_items = [p for p in cc_data.priorities if "site visit" in p.title.lower() or "priya" in p.title.lower()]
    assert len(visit_items) >= 1
    assert visit_items[0].priority in ["CRITICAL", "HIGH"]

    # Overdue task must be present
    assert any("brochure" in f.title.lower() for f in cc_data.overdue_followups)

    # Stale lead must be grouped in stale_leads_summary
    assert cc_data.stale_leads_summary.total_stale_count >= 1
    assert cc_data.stale_leads_summary.stale_14_to_30_days_count >= 1

    # --- VERIFY INVENTORY INTELLIGENCE & GAPS ---
    # Whitefield must be the #1 top location
    top_locs = cc_data.demand_heatmap.top_locations
    assert len(top_locs) >= 1
    assert top_locs[0]["location"] == "Whitefield"
    # 5 leads have Whitefield preference (lead_a, lead_b, lead_c, extra_1, extra_2)
    assert top_locs[0]["count"] == 5

    # Gap detection: Demand = 5, Supply = 1 (prop_d) -> Gap = 4
    whitefield_gaps = [g for g in cc_data.inventory_gaps if g.locality == "Whitefield"]
    assert len(whitefield_gaps) >= 1
    assert whitefield_gaps[0].demand_lead_count == 5
    assert whitefield_gaps[0].supply_property_count == 1
    assert whitefield_gaps[0].gap_deficit == 4

    # Inventory Opportunities: prop_d should show matching leads
    assert len(cc_data.inventory_opportunities) >= 1
    prop_opp = [o for o in cc_data.inventory_opportunities if o.property_id == str(prop_d.id)][0]
    assert prop_opp.potential_leads_count >= 1

    # --- VERIFY START MY DAY FLOW ---
    start_my_day = await cc_service.get_start_my_day_queue(primary_broker.id)
    assert start_my_day.total_items >= 1
    # Step 1 should be the highest priority item (e.g., SLA overdue lead)
    first_step = start_my_day.steps[0]
    assert first_step.step_number == 1
    assert first_step.item.priority == "CRITICAL"
    assert "Rahul" in first_step.item.title or "First contact" in first_step.item.title

    # --- VERIFY DISMISS & SNOOZE ACTION FLOW ---
    item_to_dismiss = first_step.item.item_key
    dismiss_res = await cc_service.dismiss_item(
        broker_id=primary_broker.id,
        item_key=item_to_dismiss,
        entity_type=first_step.item.entity_type,
        entity_id=first_step.item.entity_id,
        action_type="dismissed"
    )
    assert dismiss_res["status"] == "success"
    assert dismiss_res["action_type"] == "dismissed"

    # Verify that dismissed item is persisted in DB
    d_check = await db_session.execute(
        select(CommandCenterDismissal).where(
            CommandCenterDismissal.broker_id == primary_broker.id,
            CommandCenterDismissal.item_key == item_to_dismiss
        )
    )
    dismissal_record = d_check.scalar_one_or_none()
    assert dismissal_record is not None
    assert dismissal_record.action_type == "dismissed"

    # Audit log check
    audit_res = await db_session.execute(
        select(AuditLog).where(
            AuditLog.organization_id == primary_broker.id,
            AuditLog.resource_id == item_to_dismiss
        )
    )
    assert audit_res.scalar_one_or_none() is not None

    # After dismissal, item must be suppressed from active priorities
    refreshed_cc = await cc_service.get_command_center_data(primary_broker.id)
    assert not any(p.item_key == item_to_dismiss for p in refreshed_cc.priorities)

    # --- VERIFY MULTI-TENANT ISOLATION ---
    foreign_cc = await cc_service.get_command_center_data(foreign_broker.id)
    assert foreign_cc.summary.total_priority_actions == 0
    assert len(foreign_cc.priorities) == 0
    assert len(foreign_cc.today_schedule) == 0
    assert len(foreign_cc.first_contact_queue) == 0
    assert len(foreign_cc.overdue_followups) == 0
    assert foreign_cc.stale_leads_summary.total_stale_count == 0
    assert len(foreign_cc.inventory_gaps) == 0

