"""
Escalation & Stale Lead Management Service
===========================================
Monitors high-value and hot leads for response SLA breaches and prolonged
inactivity, escalating directly to managers and creating re-engagement tasks.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.crm_models import Task, Notification, Activity
from app.models.follow_up_models import FollowUpPolicy
from app.modules.follow_up.idempotency.idempotency_service import IdempotencyService
from app.modules.follow_up.sla.sla_service import SlaService

logger = logging.getLogger(__name__)


class EscalationService:
    """
    Detects uncontacted hot leads, prolonged SLA breaches, and stale leads.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.sla_service = SlaService(db)

    async def scan_and_escalate_hot_leads(
        self,
        organization_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scans HOT leads without contact:
        - > 2 hours uncontacted: Broker notification reminder.
        - > 24 hours uncontacted: Manager escalation task and alert.
        """
        now = datetime.now(timezone.utc)
        two_hours_ago = now - timedelta(hours=2)
        twenty_four_hours_ago = now - timedelta(hours=24)

        conditions = [
            Lead.score == "hot",
            Lead.status.in_(["pending", "active"]),
            Lead.deleted_at.is_(None)
        ]

        stmt = select(Lead).where(and_(*conditions)).limit(200)
        res = await self.db.execute(stmt)
        hot_leads = res.scalars().all()

        escalated = []

        for lead in hot_leads:
            org_id = str(lead.broker_id)
            if organization_id and org_id != organization_id:
                continue

            lead_created = lead.created_at
            if lead_created.tzinfo is None:
                lead_created = lead_created.replace(tzinfo=timezone.utc)

            # Check if qualifying contact occurred
            has_contact = await self.sla_service.has_qualifying_contact(str(lead.id), since_time=lead_created)
            if has_contact:
                continue

            lead_name = lead.name or "Hot Lead"
            lead_phone = lead.phone or ""

            # Check 24-hour manager escalation
            if lead_created <= twenty_four_hours_ago:
                idemp_key = IdempotencyService.build_key(
                    organization_id=org_id,
                    lead_id=str(lead.id),
                    rule_identifier="hot_lead_escalation",
                    trigger_type="uncontacted_24h",
                    target_window=now.strftime("%Y-%m-%d")
                )
                acquired, event = await IdempotencyService.try_acquire_execution(
                    db=self.db,
                    idempotency_key=idemp_key,
                    organization_id=org_id,
                    lead_id=str(lead.id),
                    trigger_type="uncontacted_24h",
                    action_type="manager_escalation"
                )
                if acquired:
                    task = Task(
                        id=str(uuid.uuid4()),
                        broker_id=lead.broker_id,
                        lead_id=lead.id,
                        organization_id=org_id,
                        assigned_broker_id=lead.broker_id,
                        title=f"URGENT: Manager Review - Hot Lead {lead_name} Uncontacted >24h",
                        description=f"Hot lead {lead_name} ({lead_phone}) has received zero qualifying contact in 24 hours. Immediate intervention required.",
                        due_at=now,
                        priority="urgent",
                        status="pending"
                    )
                    self.db.add(task)
                    await self.db.commit()
                    await self.db.refresh(task)

                    if lead.broker_id:
                        notif = Notification(
                            id=str(uuid.uuid4()),
                            broker_id=lead.broker_id,
                            organization_id=org_id,
                            category="task",
                            title=f"Manager Escalation: Hot Lead {lead_name}",
                            body=f"Hot lead {lead_name} has had no contact for 24+ hours.",
                            action_url="/dashboard/tasks"
                        )
                        self.db.add(notif)
                        await self.db.commit()

                    await IdempotencyService.record_success(self.db, event.id, task_id=task.id)
                    escalated.append({"lead_id": str(lead.id), "level": "24h_manager_escalation"})

            # Check 2-hour broker reminder
            elif lead_created <= two_hours_ago:
                idemp_key = IdempotencyService.build_key(
                    organization_id=org_id,
                    lead_id=str(lead.id),
                    rule_identifier="hot_lead_reminder",
                    trigger_type="uncontacted_2h",
                    target_window=now.strftime("%Y-%m-%d")
                )
                acquired, event = await IdempotencyService.try_acquire_execution(
                    db=self.db,
                    idempotency_key=idemp_key,
                    organization_id=org_id,
                    lead_id=str(lead.id),
                    trigger_type="uncontacted_2h",
                    action_type="broker_reminder"
                )
                if acquired:
                    if lead.broker_id:
                        notif = Notification(
                            id=str(uuid.uuid4()),
                            broker_id=lead.broker_id,
                            organization_id=org_id,
                            category="task",
                            title=f"Urgent Reminder: Contact Hot Lead {lead_name}",
                            body=f"Hot lead {lead_name} was captured >2 hours ago and remains uncontacted.",
                            action_url="/dashboard/tasks"
                        )
                        self.db.add(notif)
                        await self.db.commit()

                    await IdempotencyService.record_success(self.db, event.id)
                    escalated.append({"lead_id": str(lead.id), "level": "2h_broker_reminder"})

        return escalated

    async def scan_and_reengage_stale_leads(
        self,
        organization_id: Optional[str] = None,
        stale_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Scans leads that have had no activity or messages for stale_days.
        Generates a Re-engagement task with idempotency protection.
        """
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=stale_days)

        conditions = [
            Lead.status.in_(["pending", "active", "qualified"]),
            Lead.deleted_at.is_(None),
            or_(
                Lead.last_message_at.is_(None),
                Lead.last_message_at <= threshold
            ),
            Lead.created_at <= threshold
        ]

        stmt = select(Lead).where(and_(*conditions)).limit(200)
        res = await self.db.execute(stmt)
        stale_leads = res.scalars().all()

        reengaged = []

        for lead in stale_leads:
            org_id = str(lead.broker_id)
            if organization_id and org_id != organization_id:
                continue

            lead_name = lead.name or "Lead"
            lead_phone = lead.phone or ""

            # Check if there is already an open pending re-engagement task
            stmt_task = select(Task).where(
                Task.lead_id == lead.id,
                Task.status == "pending",
                Task.title.ilike("%re-engage%")
            )
            res_t = await self.db.execute(stmt_task)
            if res_t.scalar_one_or_none() is not None:
                continue

            idemp_key = IdempotencyService.build_key(
                organization_id=org_id,
                lead_id=str(lead.id),
                rule_identifier="stale_reengagement",
                trigger_type="stale_lead",
                target_window=now.strftime("%Y-%W") # weekly window
            )

            acquired, event = await IdempotencyService.try_acquire_execution(
                db=self.db,
                idempotency_key=idemp_key,
                organization_id=org_id,
                lead_id=str(lead.id),
                trigger_type="stale_lead",
                action_type="create_task"
            )
            if not acquired:
                continue

            task = Task(
                id=str(uuid.uuid4()),
                broker_id=lead.broker_id,
                lead_id=lead.id,
                organization_id=org_id,
                assigned_broker_id=lead.broker_id,
                title=f"Re-engage {lead_name}",
                description=f"Lead {lead_name} ({lead_phone}) inactive for >{stale_days} days. Share new property options or market update.",
                due_at=now + timedelta(days=1),
                priority="high" if lead.score == "hot" else "normal",
                status="pending"
            )
            self.db.add(task)
            await self.db.commit()
            await self.db.refresh(task)

            await IdempotencyService.record_success(self.db, event.id, task_id=task.id)
            reengaged.append({"lead_id": str(lead.id), "task_id": task.id})

        return reengaged
