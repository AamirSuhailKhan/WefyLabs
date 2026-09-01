"""
Executive & Agent Daily Operational Brief Service
=================================================
Synthesizes real-time operational summaries for Sales Managers (team overview)
and Individual Brokers (daily high-priority task checklist).
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.lead import Lead
from app.models.crm_models import Meeting, Task
from app.models.crm_intelligence_models import (
    ManagerDailyBrief, AgentDailyBrief, LeadRisk, SlaBreach, AgentWorkloadSnapshot
)

logger = logging.getLogger(__name__)

class DailyBriefService:
    """
    Generates real-time operational daily briefings.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_manager_brief(self, organization_id: str) -> ManagerDailyBrief:
        """
        Synthesizes team-wide operational status for sales managers.
        """
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # 1. Today's New Leads
        stmt_new = select(func.count(Lead.id)).where(
            and_(
                Lead.created_at >= start_of_day,
                Lead.deleted_at == None
            )
        )
        res_new = await self.db.execute(stmt_new)
        today_new = res_new.scalar() or 0

        # 2. High-Intent Leads
        stmt_hot = select(func.count(Lead.id)).where(
            and_(
                Lead.score == "hot",
                Lead.deleted_at == None,
                Lead.pipeline_stage.notin_(["closed_won", "closed_lost", "converted", "lost"])
            )
        )
        res_hot = await self.db.execute(stmt_hot)
        hot_count = res_hot.scalar() or 0

        # 3. Active Risks & Breaches
        stmt_risk = select(func.count(LeadRisk.id)).where(
            and_(
                LeadRisk.organization_id == organization_id,
                LeadRisk.status == "ACTIVE"
            )
        )
        res_risk = await self.db.execute(stmt_risk)
        risk_count = res_risk.scalar() or 0

        stmt_breach = select(func.count(SlaBreach.id)).where(
            and_(
                SlaBreach.organization_id == organization_id,
                SlaBreach.breached_at_utc >= start_of_day
            )
        )
        res_breach = await self.db.execute(stmt_breach)
        breach_count = res_breach.scalar() or 0

        # 4. Upcoming Meetings Today
        stmt_mtg = select(func.count(Meeting.id)).where(
            and_(
                Meeting.scheduled_at >= start_of_day,
                Meeting.scheduled_at < end_of_day,
                Meeting.status != "cancelled"
            )
        )
        res_mtg = await self.db.execute(stmt_mtg)
        mtg_count = res_mtg.scalar() or 0

        # 5. Overloaded Agents
        stmt_work = select(AgentWorkloadSnapshot).where(
            and_(
                AgentWorkloadSnapshot.organization_id == organization_id,
                AgentWorkloadSnapshot.workload_status.in_(["OVERLOADED", "CRITICAL"])
            )
        )
        res_work = await self.db.execute(stmt_work)
        overloaded = [
            {"broker_id": w.broker_id, "status": w.workload_status, "capacity": w.capacity_utilization_pct}
            for w in res_work.scalars().all()
        ]

        top_actions = [
            "Review and reassign leads from overloaded agents to prevent response bottlenecks.",
            "Enforce immediate outreach for high-intent leads flagged as neglected.",
            "Verify viewing attendance confirmations for today's scheduled site visits."
        ]

        summary = (
            f"Good morning. Today there are **{today_new} new leads**, **{hot_count} high-intent buyers**, "
            f"and **{mtg_count} property viewings** scheduled. **{risk_count} leads** currently require attention, "
            f"and {len(overloaded)} agent(s) are operating above optimal capacity."
        )

        brief = ManagerDailyBrief(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            brief_date=now,
            today_new_leads=today_new,
            high_intent_leads_count=hot_count,
            at_risk_leads_count=risk_count,
            sla_breaches_count=breach_count,
            upcoming_viewings_count=mtg_count,
            stagnant_deals_count=risk_count,
            revenue_at_risk_aed=float(risk_count * 500_000.0),
            overloaded_agents=overloaded,
            top_manager_actions=top_actions,
            executive_summary=summary
        )
        self.db.add(brief)
        await self.db.commit()
        await self.db.refresh(brief)
        return brief

    async def generate_agent_brief(self, broker_id: str, organization_id: str) -> AgentDailyBrief:
        """
        Synthesizes individual daily focus briefing for an agent.
        """
        import uuid as _uuid
        try:
            b_pk = _uuid.UUID(str(broker_id))
        except Exception:
            b_pk = broker_id

        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # 1. Top Leads to Call
        stmt_leads = select(Lead).where(
            and_(
                Lead.broker_id == b_pk,
                Lead.deleted_at == None,
                Lead.score.in_(["hot", "warm"]),
                Lead.pipeline_stage.notin_(["closed_won", "closed_lost", "converted", "lost"])
            )
        ).limit(5)
        res_leads = await self.db.execute(stmt_leads)
        top_leads = [
            {"lead_id": str(l.id), "name": l.name, "phone": l.phone, "score": l.score, "stage": l.pipeline_stage}
            for l in res_leads.scalars().all()
        ]

        # 2. Meetings Today
        stmt_mtg = select(Meeting).where(
            and_(
                Meeting.broker_id == str(b_pk),
                Meeting.scheduled_at >= start_of_day,
                Meeting.scheduled_at < end_of_day,
                Meeting.status != "cancelled"
            )
        )
        res_mtg = await self.db.execute(stmt_mtg)
        mtgs = [
            {"meeting_id": m.id, "title": m.title, "time": m.scheduled_at.isoformat(), "location": m.location}
            for m in res_mtg.scalars().all()
        ]

        # 3. Overdue & Urgent Tasks
        stmt_tasks = select(Task).where(
            and_(
                Task.broker_id == str(b_pk),
                Task.status == "pending"
            )
        )
        res_tasks = await self.db.execute(stmt_tasks)
        all_tasks = res_tasks.scalars().all()
        overdue_count = len([t for t in all_tasks if t.due_at and (t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)) < now])
        urgent_tasks = [
            {"task_id": t.id, "title": t.title, "priority": t.priority, "due_at": t.due_at.isoformat() if t.due_at else None}
            for t in all_tasks[:5]
        ]

        summary = (
            f"You have **{len(top_leads)} priority buyers** to engage today and **{len(mtgs)} viewing appointments**. "
            f"You have {overdue_count} overdue task(s) requiring immediate resolution."
        )

        brief = AgentDailyBrief(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            broker_id=str(broker_id),
            brief_date=now,
            top_leads_to_call=top_leads,
            upcoming_meetings_today=mtgs,
            overdue_follow_ups_count=overdue_count,
            urgent_tasks=urgent_tasks,
            daily_focus_summary=summary
        )
        self.db.add(brief)
        await self.db.commit()
        await self.db.refresh(brief)
        return brief
