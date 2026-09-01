"""
Agent Workload & Capacity Intelligence Engine
=============================================
Calculates agent capacity utilization, active lead burdens, task backlogs,
and overload warnings with lead rebalancing recommendations.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting
from app.models.crm_intelligence_models import AgentWorkloadSnapshot

logger = logging.getLogger(__name__)

# Configurable capacity thresholds
DEFAULT_MAX_ACTIVE_LEADS = 35
DEFAULT_MAX_OVERDUE_TASKS = 5

class WorkloadIntelligenceEngine:
    """
    Evaluates sales agent workload and detects burnout / capacity bottlenecks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_agent_workload(self, broker_id: str, organization_id: str) -> AgentWorkloadSnapshot:
        """
        Calculates active leads, overdue tasks, and capacity utilization for an agent.
        """
        import uuid as _uuid
        try:
            b_pk = _uuid.UUID(str(broker_id))
        except Exception:
            b_pk = broker_id

        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # 1. Active Leads
        stmt_leads = select(Lead).where(
            and_(
                Lead.broker_id == b_pk,
                Lead.deleted_at == None,
                Lead.pipeline_stage.notin_(["closed_won", "closed_lost", "converted", "lost"])
            )
        )
        res_leads = await self.db.execute(stmt_leads)
        active_leads = res_leads.scalars().all()
        active_count = len(active_leads)
        high_priority_count = len([l for l in active_leads if l.score == "hot"])

        # 2. Tasks
        stmt_tasks = select(Task).where(Task.broker_id == str(b_pk))
        res_tasks = await self.db.execute(stmt_tasks)
        tasks = res_tasks.scalars().all()
        open_tasks = [t for t in tasks if t.status in ("pending", "in_progress")]
        overdue_tasks = [
            t for t in open_tasks
            if t.due_at and (t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)) < now
        ]

        # 3. Meetings Today
        stmt_mtg = select(func.count(Meeting.id)).where(
            and_(
                Meeting.broker_id == str(b_pk),
                Meeting.scheduled_at >= start_of_day,
                Meeting.scheduled_at < end_of_day,
                Meeting.status != "cancelled"
            )
        )
        res_mtg = await self.db.execute(stmt_mtg)
        meetings_today = res_mtg.scalar() or 0

        # 4. Capacity Utilization %
        lead_load = (active_count / DEFAULT_MAX_ACTIVE_LEADS) * 70.0
        task_load = (len(overdue_tasks) / DEFAULT_MAX_OVERDUE_TASKS) * 20.0
        meeting_load = (meetings_today / 6.0) * 10.0
        capacity_util = min(150.0, max(10.0, lead_load + task_load + meeting_load))

        if capacity_util >= 100.0 or len(overdue_tasks) >= DEFAULT_MAX_OVERDUE_TASKS:
            status = "CRITICAL" if capacity_util >= 120.0 else "OVERLOADED"
            rebalancing = True
        elif capacity_util <= 40.0:
            status = "UNDERLOADED"
            rebalancing = False
        else:
            status = "BALANCED"
            rebalancing = False

        snap = AgentWorkloadSnapshot(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            broker_id=str(broker_id),
            active_leads_count=active_count,
            high_priority_leads_count=high_priority_count,
            open_tasks_count=len(open_tasks),
            overdue_tasks_count=len(overdue_tasks),
            scheduled_meetings_today=meetings_today,
            workload_status=status,
            capacity_utilization_pct=round(capacity_util, 1),
            rebalancing_recommended=rebalancing
        )
        self.db.add(snap)
        await self.db.commit()
        await self.db.refresh(snap)
        logger.info(f"[WORKLOAD] Agent {broker_id}: {status} ({capacity_util:.1f}% capacity).")
        return snap

    async def evaluate_all_agents(self, organization_id: str) -> List[AgentWorkloadSnapshot]:
        """
        Evaluates workload across all active brokers.
        """
        stmt = select(Broker)
        res = await self.db.execute(stmt)
        brokers = res.scalars().all()

        snapshots: List[AgentWorkloadSnapshot] = []
        for b in brokers:
            snap = await self.evaluate_agent_workload(str(b.id), organization_id)
            snapshots.append(snap)
        return snapshots
