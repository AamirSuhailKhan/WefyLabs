"""
Part 27 — Real E2E Lead Follow-Up Lifecycle Scenario
======================================================
Tests complete unmocked pipeline flow:
NEW LEAD
  -> Lead Capture & Assignment
  -> First Contact SLA (15m target)
  -> Task Generation
  -> No Response Detection
  -> Overdue & Escalation
  -> AI Re-engagement
  -> Stop Condition (Conversion / Opt-Out)
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Notification, Activity
from app.models.crm_intelligence_models import SlaInstance, SlaBreach
from app.models.follow_up_models import FollowUpPolicy, FollowUpRule
from app.modules.follow_up.service import FollowUpOrchestratorService


@pytest.mark.asyncio
async def test_full_lead_followup_lifecycle_e2e(db_session: AsyncSession):
    # Step 1: Initialize Broker and Organization Policy
    broker = Broker(
        id=uuid.uuid4(),
        email=f"broker_{uuid.uuid4().hex[:6]}@realestate.com",
        name="Vikram Mehta",
        agency_name="Skyline Realty"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    service = FollowUpOrchestratorService(db_session)
    policy = await service.get_or_create_policy(str(broker.id))
    policy.first_contact_sla_minutes = 15
    policy.stale_lead_days = 7
    await db_session.commit()

    # Step 2: Ingest NEW LEAD
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        phone="+919988776655",
        name="Ananya Roy",
        score="hot",
        status="pending",
        pipeline_stage="new",
        budget_max=12000000,
        property_type="3bhk",
        preferred_locations=["Whitefield"]
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)

    # Step 3: Trigger First Contact SLA & Task Generation
    initial_task = await service.sla_service.create_first_contact_sla(lead, policy)
    assert initial_task is not None
    assert "Contact Ananya Roy" in initial_task.title
    assert initial_task.priority == "high"

    # Step 4: Verify active SLA instance
    stmt_sla = select(SlaInstance).where(SlaInstance.lead_id == str(lead.id))
    sla_inst = (await db_session.execute(stmt_sla)).scalar_one_or_none()
    assert sla_inst is not None
    assert sla_inst.status == "RUNNING"

    # Step 5: Simulate Deadline Passing with Zero Contact (SLA Breach)
    sla_inst.target_deadline_utc = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.commit()

    breaches = await service.sla_service.evaluate_sla_breaches(str(broker.id))
    assert len(breaches) >= 1
    assert breaches[0].lead_id == str(lead.id)

    # Step 6: Simulate Hot Lead Uncontacted > 24 Hours (Manager Escalation)
    lead.created_at = datetime.now(timezone.utc) - timedelta(hours=26)
    await db_session.commit()

    escalations = await service.escalation_service.scan_and_escalate_hot_leads(str(broker.id))
    assert len(escalations) >= 1
    assert escalations[0]["level"] == "24h_manager_escalation"

    # Verify manager review task exists
    stmt_esc_task = select(Task).where(
        Task.lead_id == lead.id,
        Task.title.ilike("%Manager Review%")
    )
    esc_task = (await db_session.execute(stmt_esc_task)).scalar_one_or_none()
    assert esc_task is not None
    assert esc_task.priority == "urgent"

    # Step 7: Simulate Stale Lead Inactivity & AI Re-engagement Generation
    lead.created_at = datetime.now(timezone.utc) - timedelta(days=15)
    lead.last_message_at = datetime.now(timezone.utc) - timedelta(days=15)
    await db_session.commit()

    draft = await service.reengagement_service.generate_reengagement_draft(lead=lead, broker_name=broker.name)
    assert "Ananya" in draft["message_body"]
    assert "3bhk" in draft["message_body"].lower()

    # Step 8: Client Converts -> Verify Stop Condition Halts Future Sequences
    lead.status = "converted"
    lead.pipeline_stage = "converted"
    await db_session.commit()

    test_rule = FollowUpRule(
        id=str(uuid.uuid4()),
        organization_id=str(broker.id),
        name="Post-Stale Reminder",
        trigger="lead_no_response",
        action="create_task"
    )
    result_event = await service.rule_engine.execute_rule(test_rule, lead, "lead_no_response")
    # Must be None because lead is converted (Stop condition enforced)
    assert result_event is None
