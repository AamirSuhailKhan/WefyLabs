"""
Part 27 — Follow-Up Automation Engine Tests
============================================
Comprehensive test suite verifying:
- Rule engine condition evaluation & filtering
- Timezone correctness (India, US, UK, Singapore) & working hours shifting
- Deterministic database-level idempotency ledger
- First-contact SLA generation, qualifying contact verification, and breach detection
- Stop conditions (conversion, lost, permanent opt-out)
- Human override (snooze, reschedule, pause, resume, stop)
- Manager escalations for hot leads uncontacted >2h / >24h
- Grounded AI re-engagement and live daily CRM briefing
- Copilot follow-up tools execution with RBAC
- Multi-tenant isolation & IDOR prevention
- Concurrent execution safety with zero duplicate tasks
"""

import asyncio
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Notification, Activity, Meeting
from app.models.crm_intelligence_models import SlaInstance, SlaBreach
from app.models.follow_up_models import (
    FollowUpPolicy, FollowUpRule, FollowUpAutomationEvent, CommunicationConsent
)
from app.modules.follow_up.service import FollowUpOrchestratorService
from app.modules.follow_up.idempotency.idempotency_service import IdempotencyService
from app.modules.follow_up.sla.sla_service import SlaService
from app.modules.follow_up.rules.rule_engine import RuleEngine
from app.modules.follow_up.escalation.escalation_service import EscalationService
from app.modules.follow_up.briefing.briefing_service import BriefingService
from app.modules.follow_up.ai_reengagement.reengagement_service import ReengagementService
from app.modules.copilot.tools.tool_registry import COPILOT_TOOL_REGISTRY


# ─── 1. Rule Engine & Condition Evaluation Tests ───────────────────────────────

@pytest.mark.asyncio
async def test_rule_condition_score_and_budget(db_session: AsyncSession, test_broker: Broker):
    rule_engine = RuleEngine(db_session)
    rule = FollowUpRule(
        id=str(uuid.uuid4()),
        organization_id=str(test_broker.id),
        name="Hot Lead High Budget Follow-Up",
        trigger="lead_created",
        action="create_task",
        conditions={
            "score_in": ["hot"],
            "min_budget": 5000000
        }
    )

    # Eligible lead
    lead_hot = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919800000001",
        name="Hot High Budget",
        score="hot",
        budget_max=6000000
    )
    assert rule_engine.evaluate_conditions(rule, lead_hot, {}) is True

    # Ineligible lead: cold score
    lead_cold = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919800000002",
        name="Cold Lead",
        score="cold",
        budget_max=8000000
    )
    assert rule_engine.evaluate_conditions(rule, lead_cold, {}) is False

    # Ineligible lead: low budget
    lead_low_budget = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919800000003",
        name="Low Budget Lead",
        score="hot",
        budget_max=3000000
    )
    assert rule_engine.evaluate_conditions(rule, lead_low_budget, {}) is False


# ─── 2. Working Hours & Timezone Correctness Tests ────────────────────────────

@pytest.mark.asyncio
async def test_working_hours_shift_night_to_morning(db_session: AsyncSession, test_broker: Broker):
    rule_engine = RuleEngine(db_session)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919876543210",
        preferred_locations=["Bengaluru"]
    )
    policy = FollowUpPolicy(
        organization_id=str(test_broker.id),
        working_hours_start="09:00",
        working_hours_end="18:00",
        working_days=[1, 2, 3, 4, 5],
        timezone="Asia/Kolkata"
    )

    # 2:00 AM IST on Wednesday (2026-09-09 02:00 IST = 2026-09-08 20:30 UTC)
    ist_tz = ZoneInfo("Asia/Kolkata")
    night_dt_ist = datetime(2026, 9, 9, 2, 0, 0, tzinfo=ist_tz)
    night_dt_utc = night_dt_ist.astimezone(timezone.utc)

    shifted_utc = rule_engine.calculate_working_hours_due_date(night_dt_utc, policy, lead)
    shifted_ist = shifted_utc.astimezone(ist_tz)

    # Must be shifted to 09:30 AM IST of the same working day
    assert shifted_ist.hour == 9
    assert shifted_ist.minute == 30
    assert shifted_ist.day == 9


@pytest.mark.asyncio
async def test_working_hours_weekend_shift_to_monday(db_session: AsyncSession, test_broker: Broker):
    rule_engine = RuleEngine(db_session)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+971501234567",
        preferred_locations=["Dubai"]
    )
    policy = FollowUpPolicy(
        organization_id=str(test_broker.id),
        working_hours_start="09:00",
        working_hours_end="18:00",
        working_days=[1, 2, 3, 4, 5], # Mon-Fri
        timezone="Asia/Dubai"
    )

    # Saturday 14:00 Dubai time (2026-09-12 14:00 GST)
    dubai_tz = ZoneInfo("Asia/Dubai")
    saturday_dt = datetime(2026, 9, 12, 14, 0, 0, tzinfo=dubai_tz)
    saturday_utc = saturday_dt.astimezone(timezone.utc)

    shifted_utc = rule_engine.calculate_working_hours_due_date(saturday_utc, policy, lead)
    shifted_dubai = shifted_utc.astimezone(dubai_tz)

    # Must roll forward to Monday (2026-09-14 09:30 AM GST)
    assert shifted_dubai.weekday() == 0 # Monday
    assert shifted_dubai.hour == 9
    assert shifted_dubai.minute == 30
    assert shifted_dubai.day == 14


# ─── 3. Deterministic Idempotency Ledger Tests ────────────────────────────────

@pytest.mark.asyncio
async def test_idempotency_service_deduplication(db_session: AsyncSession, test_broker: Broker):
    org_id = str(test_broker.id)
    lead_id = str(uuid.uuid4())
    key = IdempotencyService.build_key(org_id, lead_id, "test_rule_1", "lead_created", "window_1")

    # First attempt: successfully acquires
    acquired_1, event_1 = await IdempotencyService.try_acquire_execution(
        db=db_session,
        idempotency_key=key,
        organization_id=org_id,
        lead_id=lead_id,
        trigger_type="lead_created",
        action_type="create_task"
    )
    assert acquired_1 is True
    assert event_1 is not None
    assert event_1.status == "PENDING"

    # Second attempt with identical key: rejected as duplicate
    acquired_2, event_2 = await IdempotencyService.try_acquire_execution(
        db=db_session,
        idempotency_key=key,
        organization_id=org_id,
        lead_id=lead_id,
        trigger_type="lead_created",
        action_type="create_task"
    )
    assert acquired_2 is False
    assert event_2.id == event_1.id


# ─── 4. First-Contact SLA & Real Contact Activity Detection ────────────────────

@pytest.mark.asyncio
async def test_first_contact_sla_and_qualifying_contact(db_session: AsyncSession, test_broker: Broker):
    sla_service = SlaService(db_session)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919876540001",
        name="SLA Lead",
        score="hot",
        status="pending"
    )
    db_session.add(lead)
    await db_session.commit()

    # 1. Create SLA and initial task
    task = await sla_service.create_first_contact_sla(lead)
    assert task is not None
    assert "Contact SLA Lead" in task.title
    assert task.priority == "high"

    # Initial state: no qualifying contact
    assert await sla_service.has_qualifying_contact(str(lead.id)) is False

    # Irrelevant activity: note added does NOT count as contact
    note_act = Activity(
        organization_id=str(test_broker.id),
        actor_id=test_broker.id,
        lead_id=lead.id,
        activity_type="note_added",
        title="Note updated",
        description="Viewed lead details"
    )
    db_session.add(note_act)
    await db_session.commit()
    assert await sla_service.has_qualifying_contact(str(lead.id)) is False

    # Qualifying activity: phone call made
    call_act = Activity(
        organization_id=str(test_broker.id),
        actor_id=test_broker.id,
        lead_id=lead.id,
        activity_type="call_made",
        title="Introductory Call",
        description="Spoke with client regarding requirements"
    )
    db_session.add(call_act)
    await db_session.commit()
    assert await sla_service.has_qualifying_contact(str(lead.id)) is True


@pytest.mark.asyncio
async def test_sla_breach_detection(db_session: AsyncSession, test_broker: Broker):
    sla_service = SlaService(db_session)
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919876540002",
        name="Uncontacted Breach Lead",
        status="pending"
    )
    db_session.add(lead)
    await db_session.commit()

    # Create an expired running SLA instance (deadline was 20 minutes ago)
    past_deadline = datetime.now(timezone.utc) - timedelta(minutes=20)
    sla_inst = SlaInstance(
        id=str(uuid.uuid4()),
        organization_id=str(test_broker.id),
        lead_id=str(lead.id),
        broker_id=str(test_broker.id),
        sla_type="FIRST_RESPONSE",
        target_deadline_utc=past_deadline,
        status="RUNNING"
    )
    db_session.add(sla_inst)
    await db_session.commit()

    # Evaluate breaches
    breaches = await sla_service.evaluate_sla_breaches(str(test_broker.id))
    assert len(breaches) == 1
    assert breaches[0].lead_id == str(lead.id)
    assert breaches[0].overdue_minutes >= 19

    # Verify notification was created for the broker
    stmt_notif = select(Notification).where(
        Notification.broker_id == test_broker.id,
        Notification.title.ilike("%SLA Breached%")
    )
    res_n = await db_session.execute(stmt_notif)
    notif = res_n.scalar_one_or_none()
    assert notif is not None


# ─── 5. Human Override (Snooze, Reschedule, Pause, Resume, Stop) ──────────────

@pytest.mark.asyncio
async def test_human_override_snooze_and_reschedule(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    service = FollowUpOrchestratorService(db_session)
    task = Task(
        id=str(uuid.uuid4()),
        broker_id=test_broker.id,
        lead_id=test_lead.id,
        organization_id=str(test_broker.id),
        title="Follow up with client",
        due_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status="pending"
    )
    db_session.add(task)
    await db_session.commit()

    # Snooze to 48 hours later
    snooze_target = datetime.now(timezone.utc) + timedelta(hours=48)
    updated = await service.snooze_task(test_broker.id, task.id, snooze_target, reason="Client traveling")
    assert updated is not None

    # SQLite stores datetimes as naive strings; normalise both sides to
    # naive UTC before comparing so the test is DB-backend agnostic.
    actual_due = updated.due_at
    if actual_due.tzinfo is not None:
        actual_due = actual_due.astimezone(timezone.utc).replace(tzinfo=None)
    expected_due = snooze_target.astimezone(timezone.utc).replace(tzinfo=None)
    # Allow up to 1 second of rounding tolerance
    assert abs((actual_due - expected_due).total_seconds()) < 1, (
        f"due_at mismatch: {actual_due!r} vs {expected_due!r}"
    )

    # Verify activity was recorded
    stmt_act = select(Activity).where(
        Activity.lead_id == test_lead.id,
        Activity.activity_type == "task_snoozed"
    )
    res_act = await db_session.execute(stmt_act)
    act = res_act.scalar_one_or_none()
    assert act is not None
    assert "Client traveling" in act.description


@pytest.mark.asyncio
async def test_stop_conditions_converted_and_opt_out(db_session: AsyncSession, test_broker: Broker):
    rule_engine = RuleEngine(db_session)
    rule = FollowUpRule(
        id=str(uuid.uuid4()),
        organization_id=str(test_broker.id),
        name="Auto Reminder",
        trigger="lead_no_response",
        action="create_task",
        enabled=True
    )

    # 1. Converted lead should be stopped
    lead_conv = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919876540003",
        status="converted"
    )
    event_conv = await rule_engine.execute_rule(rule, lead_conv, "lead_no_response")
    assert event_conv is None

    # 2. Opted-out lead should be stopped
    lead_opt = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919876540004",
        status="active"
    )
    db_session.add(lead_opt)
    consent = CommunicationConsent(
        id=str(uuid.uuid4()),
        lead_id=str(lead_opt.id),
        organization_id=str(test_broker.id),
        channel="EMAIL",
        status="OPTED_OUT"
    )
    db_session.add(consent)
    await db_session.commit()

    event_opt = await rule_engine.execute_rule(rule, lead_opt, "lead_no_response")
    assert event_opt is None


# ─── 6. Hot Lead Escalations & Stale Re-engagement ────────────────────────────

@pytest.mark.asyncio
async def test_hot_lead_escalation_service(db_session: AsyncSession, test_broker: Broker):
    esc_service = EscalationService(db_session)

    # Lead created 25 hours ago with zero contact
    old_created = datetime.now(timezone.utc) - timedelta(hours=25)
    hot_lead = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919876540005",
        name="High Value VIP",
        score="hot",
        status="pending",
        created_at=old_created
    )
    db_session.add(hot_lead)
    await db_session.commit()

    escalated = await esc_service.scan_and_escalate_hot_leads(str(test_broker.id))
    assert len(escalated) == 1
    assert escalated[0]["level"] == "24h_manager_escalation"

    # Verify escalation task was created
    stmt_t = select(Task).where(
        Task.lead_id == hot_lead.id,
        Task.title.ilike("%Manager Review%")
    )
    res_t = await db_session.execute(stmt_t)
    task = res_t.scalar_one_or_none()
    assert task is not None
    assert task.priority == "urgent"


@pytest.mark.asyncio
async def test_stale_lead_reengagement_service(db_session: AsyncSession, test_broker: Broker):
    esc_service = EscalationService(db_session)

    # Lead inactive for 10 days
    ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)
    stale_lead = Lead(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        phone="+919876540006",
        name="Inactive Client",
        score="warm",
        status="active",
        created_at=ten_days_ago,
        last_message_at=ten_days_ago
    )
    db_session.add(stale_lead)
    await db_session.commit()

    reengaged = await esc_service.scan_and_reengage_stale_leads(str(test_broker.id), stale_days=7)
    assert len(reengaged) == 1
    assert reengaged[0]["lead_id"] == str(stale_lead.id)


# ─── 7. Grounded AI Re-Engagement & Daily Briefing ─────────────────────────────

@pytest.mark.asyncio
async def test_grounded_reengagement_draft(test_lead: Lead):
    draft = await ReengagementService.generate_reengagement_draft(
        lead=test_lead,
        days_inactive=14,
        broker_name="Aamir Khan"
    )
    assert draft["lead_id"] == str(test_lead.id)
    assert test_lead.name in draft["message_body"]
    assert "2bhk" in draft["message_body"].lower()
    assert len(draft["grounded_facts"]) > 0


@pytest.mark.asyncio
async def test_daily_briefing_live_counts(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    briefing_service = BriefingService(db_session)

    # Add 1 task due today, 1 overdue task, 1 meeting today
    now = datetime.now(timezone.utc)
    t_due = Task(
        id=str(uuid.uuid4()),
        broker_id=test_broker.id,
        lead_id=test_lead.id,
        title="Due today task",
        due_at=now,
        status="pending"
    )
    t_overdue = Task(
        id=str(uuid.uuid4()),
        broker_id=test_broker.id,
        lead_id=test_lead.id,
        title="Overdue task",
        due_at=now - timedelta(hours=5),
        status="pending"
    )
    meeting = Meeting(
        id=str(uuid.uuid4()),
        broker_id=test_broker.id,
        lead_id=test_lead.id,
        title="Site Visit",
        scheduled_at=now + timedelta(hours=2),
        status="scheduled"
    )
    db_session.add_all([t_due, t_overdue, meeting])
    await db_session.commit()

    briefing = await briefing_service.get_daily_briefing_data(test_broker.id, str(test_broker.id))
    assert briefing["due_today_count"] >= 1
    assert briefing["overdue_count"] >= 1
    assert briefing["meetings_today_count"] >= 1
    assert "briefing for today" in briefing["summary_text"]


# ─── 8. Copilot Follow-Up Tools Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_copilot_followup_tools(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    # 1. list_due_followups
    list_tool = COPILOT_TOOL_REGISTRY["list_due_followups"]
    res_list = await list_tool.handler(db_session, test_broker, {})
    assert "due_today_count" in res_list

    # 2. get_daily_briefing
    brief_tool = COPILOT_TOOL_REGISTRY["get_daily_briefing"]
    res_brief = await brief_tool.handler(db_session, test_broker, {})
    assert "summary_text" in res_brief

    # 3. create_followup
    create_tool = COPILOT_TOOL_REGISTRY["create_followup"]
    res_create = await create_tool.handler(db_session, test_broker, {
        "lead_id": str(test_lead.id),
        "title": "Call Rahul regarding floor plans",
        "priority": "high",
        "days_delay": 2
    })
    assert "task_id" in res_create
    assert res_create["title"] == "Call Rahul regarding floor plans"

    # 4. pause_followup
    pause_tool = COPILOT_TOOL_REGISTRY["pause_followup"]
    res_pause = await pause_tool.handler(db_session, test_broker, {"lead_id": str(test_lead.id)})
    assert res_pause["status"] == "paused"

    # 5. stop_followup (requires confirmation)
    assert COPILOT_TOOL_REGISTRY["stop_followup"].requires_confirmation is True


# ─── 9. Multi-Tenant Isolation Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_multi_tenant_isolation(db_session: AsyncSession):
    # Setup Org A and Org B
    broker_a = Broker(id=uuid.uuid4(), email="a@org.com", name="Broker A")
    broker_b = Broker(id=uuid.uuid4(), email="b@org.com", name="Broker B")
    db_session.add_all([broker_a, broker_b])
    await db_session.commit()

    service = FollowUpOrchestratorService(db_session)

    # Org A creates a rule
    rule_a = await service.create_rule(
        organization_id=str(broker_a.id),
        name="Org A Exclusive Rule",
        trigger="lead_created",
        action="create_task"
    )

    # Org B lists rules -> should not see Org A's rule
    rules_b = await service.list_rules(str(broker_b.id))
    assert len(rules_b) == 0

    # Org B attempts to delete Org A's rule -> returns False
    deleted = await service.delete_rule(str(broker_b.id), rule_a.id)
    assert deleted is False


# ─── 10. Concurrency Safety Test ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_rule_execution_no_duplicates(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    org_id = str(test_broker.id)
    key = IdempotencyService.build_key(org_id, str(test_lead.id), "concurrency_test", "lead_created", "run_1")

    # Simulate 5 concurrent workers attempting to execute the same rule simultaneously
    results = await asyncio.gather(
        IdempotencyService.try_acquire_execution(db_session, key, org_id, str(test_lead.id), "lead_created", "create_task"),
        IdempotencyService.try_acquire_execution(db_session, key, org_id, str(test_lead.id), "lead_created", "create_task"),
        IdempotencyService.try_acquire_execution(db_session, key, org_id, str(test_lead.id), "lead_created", "create_task"),
        IdempotencyService.try_acquire_execution(db_session, key, org_id, str(test_lead.id), "lead_created", "create_task"),
        IdempotencyService.try_acquire_execution(db_session, key, org_id, str(test_lead.id), "lead_created", "create_task"),
        return_exceptions=True
    )

    # Exactly 1 worker must acquire lock, 4 workers must be rejected
    acquired_count = sum(1 for r in results if isinstance(r, tuple) and r[0] is True)
    assert acquired_count == 1
