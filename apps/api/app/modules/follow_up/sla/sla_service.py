"""
First-Contact SLA & Qualifying Contact Verification Service
=============================================================
Enforces organization-configurable response SLAs (default: 15 mins).
Detects genuine contact activities (phone calls, emails, messages, meetings)
rather than merely viewing or updating lead metadata.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.crm_models import Task, Activity, Notification
from app.models.crm_intelligence_models import SlaInstance, SlaBreach
from app.models.follow_up_models import FollowUpPolicy
from app.modules.follow_up.idempotency.idempotency_service import IdempotencyService

logger = logging.getLogger(__name__)

QUALIFYING_CONTACT_ACTIVITIES = {
    "call_made",
    "email_sent",
    "message_sent",
    "contact_made",
    "meeting_booked",
    "meeting_held",
    "site_visit_scheduled"
}


class SlaService:
    """
    Manages First-Contact SLAs and verifies contact activity compliance.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_first_contact_sla(
        self,
        lead: Lead,
        policy: Optional[FollowUpPolicy] = None
    ) -> Optional[Task]:
        """
        Starts an active First-Contact SLA timer and creates the initial Contact task.
        Uses database idempotency to prevent duplicate initial tasks.
        """
        org_id = str(lead.broker_id)
        if policy and policy.organization_id:
            org_id = policy.organization_id

        sla_mins = policy.first_contact_sla_minutes if policy else 15
        if getattr(lead, "score", None) == "hot" and policy and hasattr(policy, "hot_lead_sla_minutes"):
            sla_mins = min(sla_mins, policy.hot_lead_sla_minutes)

        idempotency_key = IdempotencyService.build_key(
            organization_id=org_id,
            lead_id=str(lead.id),
            rule_identifier="first_contact_sla",
            trigger_type="lead_created",
            target_window="initial"
        )

        acquired, event = await IdempotencyService.try_acquire_execution(
            db=self.db,
            idempotency_key=idempotency_key,
            organization_id=org_id,
            lead_id=str(lead.id),
            trigger_type="lead_created",
            action_type="create_task"
        )

        if not acquired:
            logger.info(f"[SLA] First-contact task already initiated for Lead {lead.id}.")
            return None

        now = datetime.now(timezone.utc)
        deadline = now + timedelta(minutes=sla_mins)

        # 1. Create SlaInstance
        sla_inst = SlaInstance(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            lead_id=str(lead.id),
            broker_id=str(lead.broker_id) if lead.broker_id else None,
            sla_type="FIRST_RESPONSE",
            target_deadline_utc=deadline,
            status="RUNNING"
        )
        self.db.add(sla_inst)

        # 2. Create Task
        lead_name = lead.name or "New Lead"
        task_priority = "high" if getattr(lead, "score", None) == "hot" else "normal"
        task = Task(
            id=str(uuid.uuid4()),
            broker_id=lead.broker_id,
            lead_id=lead.id,
            organization_id=org_id,
            assigned_broker_id=lead.broker_id,
            title=f"Contact {lead_name}",
            description=f"First contact SLA: {sla_mins}-minute response target for lead {lead_name} ({lead.phone}).",
            due_at=deadline,
            priority=task_priority,
            status="pending"
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # 3. Record Activity
        act = Activity(
            organization_id=org_id,
            actor_id=lead.broker_id,
            lead_id=lead.id,
            activity_type="task_created",
            title="First Contact SLA Task Created",
            description=f"Automated {sla_mins}-min SLA task generated: Contact {lead_name}.",
            activity_data={"sla_minutes": sla_mins, "deadline": deadline.isoformat(), "task_id": task.id}
        )
        self.db.add(act)
        await self.db.commit()

        # Update event ledger
        await IdempotencyService.record_success(
            db=self.db,
            event_id=event.id,
            task_id=task.id,
            details={"sla_minutes": sla_mins, "deadline": deadline.isoformat()}
        )

        logger.info(f"[SLA] Created {sla_mins}m First Contact SLA & Task for Lead {lead.id}.")
        return task

    async def has_qualifying_contact(
        self,
        lead_id: str,
        since_time: Optional[datetime] = None
    ) -> bool:
        """
        Strict verification: Has the broker engaged in actual contact?
        Qualifying events:
        - Activity records: call_made, email_sent, message_sent, contact_made, meeting_booked, meeting_held
        - Completed contact tasks
        Does NOT count mere view_lead or note_added without communication.
        """
        try:
            lead_pk = uuid.UUID(str(lead_id))
        except Exception:
            lead_pk = lead_id

        # 1. Check qualifying activities
        act_conditions = [
            Activity.lead_id == lead_pk,
            Activity.activity_type.in_(QUALIFYING_CONTACT_ACTIVITIES)
        ]
        if since_time:
            act_conditions.append(Activity.created_at >= since_time)

        stmt_act = select(Activity).where(and_(*act_conditions)).limit(1)
        res_act = await self.db.execute(stmt_act)
        if res_act.scalar_one_or_none() is not None:
            return True

        # 2. Check completed contact tasks
        task_conditions = [
            Task.lead_id == lead_pk,
            Task.status == "completed",
            or_(
                Task.title.ilike("%contact%"),
                Task.title.ilike("%call%"),
                Task.title.ilike("%follow-up%"),
                Task.title.ilike("%followup%")
            )
        ]
        if since_time:
            task_conditions.append(Task.completed_at >= since_time)

        stmt_task = select(Task).where(and_(*task_conditions)).limit(1)
        res_task = await self.db.execute(stmt_task)
        if res_task.scalar_one_or_none() is not None:
            return True

        return False

    async def evaluate_sla_breaches(
        self,
        organization_id: Optional[str] = None
    ) -> List[SlaBreach]:
        """
        Scans all running SLA instances where deadline has passed.
        If qualifying contact was made, marks MET.
        If no qualifying contact occurred, marks BREACHED and generates notification.
        """
        now = datetime.now(timezone.utc)
        conditions = [
            SlaInstance.status == "RUNNING",
            SlaInstance.target_deadline_utc <= now
        ]
        if organization_id:
            conditions.append(SlaInstance.organization_id == organization_id)

        stmt = select(SlaInstance).where(and_(*conditions)).limit(200)
        res = await self.db.execute(stmt)
        running_instances = res.scalars().all()

        recorded_breaches: List[SlaBreach] = []

        for inst in running_instances:
            # Verify if contact happened
            start_time = inst.created_at if inst.created_at else None
            contact_made = await self.has_qualifying_contact(inst.lead_id, since_time=start_time)

            if contact_made:
                inst.status = "MET"
                inst.completed_at = now
                logger.info(f"[SLA] Lead {inst.lead_id} met SLA {inst.sla_type} successfully.")
                continue

            # Breached
            inst.status = "BREACHED"
            inst_deadline = inst.target_deadline_utc if inst.target_deadline_utc.tzinfo else inst.target_deadline_utc.replace(tzinfo=timezone.utc)
            overdue_mins = max(1, int((now - inst_deadline).total_seconds() // 60))

            breach = SlaBreach(
                id=str(uuid.uuid4()),
                organization_id=inst.organization_id,
                lead_id=inst.lead_id,
                broker_id=inst.broker_id,
                instance_id=inst.id,
                sla_type=inst.sla_type,
                target_deadline_utc=inst.target_deadline_utc,
                breached_at_utc=now,
                overdue_minutes=overdue_mins,
                escalation_sent=True
            )
            self.db.add(breach)
            recorded_breaches.append(breach)

            # Generate in-app notification if broker exists
            if inst.broker_id:
                try:
                    broker_uuid = uuid.UUID(str(inst.broker_id))
                except Exception:
                    broker_uuid = None

                if broker_uuid:
                    notif = Notification(
                        id=str(uuid.uuid4()),
                        broker_id=broker_uuid,
                        organization_id=inst.organization_id,
                        category="task",
                        title="First Contact SLA Breached",
                        body=f"Response SLA of {inst.sla_type} breached by {overdue_mins} mins for lead {inst.lead_id}.",
                        action_url=f"/dashboard/leads"
                    )
                    self.db.add(notif)

        if running_instances:
            await self.db.commit()

        return recorded_breaches
