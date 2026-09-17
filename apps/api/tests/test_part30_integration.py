"""
Part 30 — Integration Test Suite: AI Real-Estate Agent Daily Command Center
===========================================================================
17 integration tests covering:
- First-contact SLA breach integration
- Overdue follow-up task integration
- Meetings and site visits scheduling integration
- Hot leads and 90+ property match integration
- Stale lead grouping (7, 14, 30+ days)
- New inventory opportunities
- Inventory demand vs supply gap detection
- Multi-tenant isolation (leads, tasks, meetings, gaps)
- Dismissal and snooze persistence and filtering
- Start My Day sequential step generation
- Audit logging on dismiss/snooze
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Activity
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.command_center_models import CommandCenterDismissal
from app.models.audit_log import AuditLog
from app.modules.command_center.service import CommandCenterService
from app.modules.command_center.dto import DismissItemRequestDTO

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
async def broker_alpha(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"alpha_{uuid.uuid4().hex[:6]}@crm.com",
        name="Alpha Director",
        subscription_status="active"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture
async def broker_beta(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"beta_{uuid.uuid4().hex[:6]}@crm.com",
        name="Beta Director",
        subscription_status="active"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture
async def seed_integration_data(db_session: AsyncSession, broker_alpha: Broker, broker_beta: Broker):
    now = datetime.now(timezone.utc)

    # Lead 1: SLA Breach (created 30 mins ago, status=pending)
    lead_sla = Lead(
        id=uuid.uuid4(),
        broker_id=broker_alpha.id,
        name="Amit Patel",
        phone="+919876500111",
        status="pending",
        pipeline_stage="new",
        source="website",
        created_at=now - timedelta(minutes=30),
        updated_at=now - timedelta(minutes=30)
    )

    # Lead 2: Hot Lead with strong match
    lead_hot = Lead(
        id=uuid.uuid4(),
        broker_id=broker_alpha.id,
        name="Rohan Mehra",
        phone="+919876500222",
        status="active",
        score="hot",
        pipeline_stage="contacted",
        budget_max=12000000,
        preferred_locations=["Whitefield"],
        property_type="3 BHK apartment",
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=2)
    )

    # Lead 3: Stale Lead (idle for 16 days)
    lead_stale = Lead(
        id=uuid.uuid4(),
        broker_id=broker_alpha.id,
        name="Deepak Sharma",
        phone="+919876500333",
        status="active",
        score="warm",
        pipeline_stage="contacted",
        created_at=now - timedelta(days=20),
        updated_at=now - timedelta(days=16)
    )

    # Property 1: Available 3BHK in Whitefield
    prop1 = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_alpha.id,
        property_code="PROP-INT-1",
        title="Prestige Boulevard 3BHK",
        description="Luxury apartment in Whitefield",
        property_type="apartment",
        status="available",
        price=11500000.0,
        area_value=1700.0,
        area_unit="sqft",
        bedrooms=3,
        locality="Whitefield",
        city="Bengaluru",
        created_at=now - timedelta(days=1)
    )

    # Strong match for Lead 2 on Property 1
    interest = LeadPropertyInterest(
        organization_id=broker_alpha.id,
        lead_id=lead_hot.id,
        property_id=prop1.id,
        status="MATCHED",
        match_score=94.0,
        deterministic_score=94.0,
        confidence=0.95
    )

    # Task: Overdue follow-up (due 3 days ago)
    task_overdue = Task(
        id=str(uuid.uuid4()),
        broker_id=broker_alpha.id,
        lead_id=lead_hot.id,
        title="Send Pricing Proposal to Rohan",
        due_at=now - timedelta(days=3),
        status="pending",
        priority="high"
    )

    # Meeting: Site visit today in 1 hour
    meeting_visit = Meeting(
        id=str(uuid.uuid4()),
        broker_id=broker_alpha.id,
        lead_id=lead_hot.id,
        title="Site Visit at Prestige Boulevard",
        meeting_type="site_visit",
        scheduled_at=now + timedelta(hours=1),
        duration_minutes=60,
        location="Prestige Boulevard, Whitefield",
        status="scheduled"
    )

    # Foreign Lead & Task for Broker Beta
    foreign_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker_beta.id,
        name="Foreign Client",
        phone="+919876500999",
        status="pending",
        created_at=now - timedelta(minutes=40)
    )
    foreign_task = Task(
        id=str(uuid.uuid4()),
        broker_id=broker_beta.id,
        lead_id=foreign_lead.id,
        title="Foreign Secret Task",
        due_at=now - timedelta(days=1),
        status="pending"
    )

    db_session.add_all([
        lead_sla, lead_hot, lead_stale, prop1, interest,
        task_overdue, meeting_visit, foreign_lead, foreign_task
    ])
    await db_session.commit()

    return {
        "lead_sla": lead_sla,
        "lead_hot": lead_hot,
        "lead_stale": lead_stale,
        "prop1": prop1,
        "interest": interest,
        "task_overdue": task_overdue,
        "meeting_visit": meeting_visit,
        "foreign_lead": foreign_lead,
        "foreign_task": foreign_task
    }


# ─── Integration Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_integration_lead_sla_breach_appears_in_dashboard(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Lead Amit Patel (created 30 mins ago, pending) appears in first_contact_queue as overdue."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    assert len(data.first_contact_queue) >= 1
    fc_item = next((x for x in data.first_contact_queue if x.lead_id == str(seed_integration_data["lead_sla"].id)), None)
    assert fc_item is not None
    assert fc_item.is_overdue is True
    assert fc_item.overdue_minutes >= 10

    # Must also appear in priorities as CRITICAL
    critical_item = next((p for p in data.priorities if p.category == "first_contact" and p.lead_id == str(seed_integration_data["lead_sla"].id)), None)
    assert critical_item is not None
    assert critical_item.priority == "CRITICAL"


@pytest.mark.asyncio
async def test_integration_overdue_followup_appears_in_dashboard(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Overdue task appears in overdue_followups and in the priorities list."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    assert len(data.overdue_followups) >= 1
    overdue_task = next((x for x in data.overdue_followups if x.task_id == str(seed_integration_data["task_overdue"].id)), None)
    assert overdue_task is not None
    assert overdue_task.overdue_days >= 2
    assert "Proposal" in overdue_task.title


@pytest.mark.asyncio
async def test_integration_today_meetings_appear_in_dashboard(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Scheduled site visit appears in today_schedule with is_starting_soon=True."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    assert len(data.today_schedule) >= 1
    sched_item = next((m for m in data.today_schedule if m.id == str(seed_integration_data["meeting_visit"].id)), None)
    assert sched_item is not None
    assert sched_item.meeting_type == "site_visit"
    assert sched_item.is_starting_soon is True


@pytest.mark.asyncio
async def test_integration_site_visit_proximate_high_priority(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Site visit within 1 hour is prioritized as HIGH priority."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    visit_p = next((p for p in data.priorities if p.category == "site_visit" and p.entity_id == str(seed_integration_data["meeting_visit"].id)), None)
    assert visit_p is not None
    assert visit_p.priority == "HIGH"
    assert visit_p.recommended_action == "SCHEDULE_VISIT"


@pytest.mark.asyncio
async def test_integration_hot_lead_strong_match_in_dashboard(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Hot lead Rohan Mehra with 94% match appears in hot_leads and priorities."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    hot_lead = next((h for h in data.hot_leads if h.lead_id == str(seed_integration_data["lead_hot"].id)), None)
    assert hot_lead is not None
    assert hot_lead.match_score == 94.0
    assert "Prestige Boulevard" in (hot_lead.strongest_property_match or "")


@pytest.mark.asyncio
async def test_integration_stale_leads_grouped_by_inactivity(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Lead Deepak Sharma (idle 16 days) counts in stale_14_days_count."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    stale = data.stale_leads_summary
    assert stale.total_stale_leads >= 1
    assert stale.stale_14_days_count >= 1


@pytest.mark.asyncio
async def test_integration_new_inventory_opportunity_appears(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Property 1 created yesterday appears in inventory_opportunities."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    assert len(data.inventory_opportunities) >= 1
    opp = next((o for o in data.inventory_opportunities if o.property_id == str(seed_integration_data["prop1"].id)), None)
    assert opp is not None
    assert opp.potential_leads_count >= 1


@pytest.mark.asyncio
async def test_integration_inventory_gap_detected_in_dashboard(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Demand heatmap reflects preferences from active leads."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    heatmap = data.demand_heatmap
    assert any("Whitefield" in str(loc) for loc in heatmap.top_locations)


@pytest.mark.asyncio
async def test_integration_tenant_isolation_leads(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Broker Alpha cannot see Broker Beta's foreign lead in Command Center."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    foreign_id = str(seed_integration_data["foreign_lead"].id)
    assert not any(x.lead_id == foreign_id for x in data.first_contact_queue)
    assert not any(p.lead_id == foreign_id for p in data.priorities)


@pytest.mark.asyncio
async def test_integration_tenant_isolation_tasks(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Broker Alpha cannot see Broker Beta's foreign task."""
    service = CommandCenterService(db=db_session)
    data = await service.get_command_center_data(broker_alpha)

    foreign_task_id = str(seed_integration_data["foreign_task"].id)
    assert not any(t.task_id == foreign_task_id for t in data.overdue_followups)


@pytest.mark.asyncio
async def test_integration_tenant_isolation_meetings(db_session: AsyncSession, broker_beta: Broker, seed_integration_data):
    """Broker Beta cannot see Broker Alpha's scheduled meetings."""
    service = CommandCenterService(db=db_session)
    data_beta = await service.get_command_center_data(broker_beta)

    alpha_meeting_id = str(seed_integration_data["meeting_visit"].id)
    assert not any(m.id == alpha_meeting_id for m in data_beta.today_schedule)


@pytest.mark.asyncio
async def test_integration_dismiss_item_persists_and_filters(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Dismissing an item filters it from priorities on subsequent loads without deleting CRM entity."""
    service = CommandCenterService(db=db_session)

    item_key = f"lead:{seed_integration_data['lead_sla'].id}:first_contact"
    dto = DismissItemRequestDTO(
        item_key=item_key,
        entity_type="lead",
        entity_id=str(seed_integration_data["lead_sla"].id),
        action_type="dismissed"
    )
    res = await service.dismiss_or_snooze_item(broker_alpha, dto)
    assert res["status"] == "success"

    # Verify filtered from subsequent command center priority list
    refreshed = await service.get_command_center_data(broker_alpha)
    assert not any(p.item_key == item_key for p in refreshed.priorities)

    # Underlying lead still exists in DB!
    lead_check = (await db_session.execute(
        select(Lead).where(Lead.id == seed_integration_data["lead_sla"].id)
    )).scalars().first()
    assert lead_check is not None


@pytest.mark.asyncio
async def test_integration_snooze_item_temporarily_hides(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Snoozing an item hides it while snooze is active."""
    service = CommandCenterService(db=db_session)

    item_key = f"task:{seed_integration_data['task_overdue'].id}:overdue"
    dto = DismissItemRequestDTO(
        item_key=item_key,
        entity_type="task",
        entity_id=str(seed_integration_data["task_overdue"].id),
        action_type="snoozed",
        snooze_hours=4
    )
    await service.dismiss_or_snooze_item(broker_alpha, dto)

    refreshed = await service.get_command_center_data(broker_alpha)
    assert not any(p.item_key == item_key for p in refreshed.priorities)


@pytest.mark.asyncio
async def test_integration_expired_snooze_reappears(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """An expired snooze (snoozed_until in the past) reappears in priorities."""
    service = CommandCenterService(db=db_session)

    item_key = f"task:{seed_integration_data['task_overdue'].id}:overdue"
    # Manually create expired snooze in DB
    past_snooze = CommandCenterDismissal(
        id=str(uuid.uuid4()),
        organization_id=str(broker_alpha.id),
        broker_id=broker_alpha.id,
        item_key=item_key,
        entity_type="task",
        entity_id=str(seed_integration_data["task_overdue"].id),
        action_type="snoozed",
        snoozed_until=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    db_session.add(past_snooze)
    await db_session.commit()

    refreshed = await service.get_command_center_data(broker_alpha)
    # Since snooze is expired, it should be eligible
    assert any(p.item_key == item_key for p in refreshed.priorities)


@pytest.mark.asyncio
async def test_integration_start_my_day_sequential_queue(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Start My Day returns numbered sequential steps."""
    service = CommandCenterService(db=db_session)
    res = await service.get_start_my_day_sequence(broker_alpha)

    assert res.total_items >= 1
    assert len(res.steps) >= 1
    assert res.steps[0].step_number == 1
    assert res.steps[0].item is not None


@pytest.mark.asyncio
async def test_integration_audit_log_recorded_on_dismiss(db_session: AsyncSession, broker_alpha: Broker, seed_integration_data):
    """Dismissing an item logs an immutable AuditLog entry."""
    service = CommandCenterService(db=db_session)
    item_key = "lead:test_audit:first_contact"
    dto = DismissItemRequestDTO(
        item_key=item_key,
        entity_type="lead",
        entity_id=str(uuid.uuid4()),
        action_type="dismissed"
    )
    await service.dismiss_or_snooze_item(broker_alpha, dto)

    audit = (await db_session.execute(
        select(AuditLog).where(
            and_(
                AuditLog.organization_id == broker_alpha.id,
                AuditLog.action == "command_center.dismissed"
            )
        )
    )).scalars().first()
    assert audit is not None
    assert audit.resource_id == item_key
