"""
AI Daily Follow-Up Briefing Service
====================================
Generates deterministic, grounded operational summaries for brokers
using real CRM database records. Zero fabricated metrics or fake meetings.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Activity

logger = logging.getLogger(__name__)


class BriefingService:
    """
    Builds verified daily briefings from live CRM data.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_daily_briefing_data(
        self,
        broker_id: uuid.UUID,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates live metrics for the broker:
        - tasks due today
        - overdue tasks
        - uncontacted hot leads
        - meetings today
        - top priority lead recommendation
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        # 1. Tasks Due Today
        stmt_due_today = select(func.count(Task.id)).where(
            Task.broker_id == broker_id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at >= today_start,
            Task.due_at <= today_end
        )
        res_due = await self.db.execute(stmt_due_today)
        due_today_count = res_due.scalar() or 0

        # 2. Tasks Overdue
        stmt_overdue = select(func.count(Task.id)).where(
            Task.broker_id == broker_id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at < now
        )
        res_overdue = await self.db.execute(stmt_overdue)
        overdue_count = res_overdue.scalar() or 0

        # 3. Meetings Today
        stmt_meetings = select(func.count(Meeting.id)).where(
            Meeting.broker_id == broker_id,
            Meeting.status == "scheduled",
            Meeting.scheduled_at >= today_start,
            Meeting.scheduled_at <= today_end
        )
        res_meetings = await self.db.execute(stmt_meetings)
        meetings_today_count = res_meetings.scalar() or 0

        # 4. Hot leads without recent contact (past 48h)
        forty_eight_h_ago = now - timedelta(hours=48)
        stmt_hot = select(Lead).where(
            Lead.broker_id == broker_id,
            Lead.score == "hot",
            Lead.status.in_(["pending", "active"]),
            Lead.deleted_at.is_(None),
            or_(
                Lead.last_message_at.is_(None),
                Lead.last_message_at <= forty_eight_h_ago
            )
        ).order_by(desc(Lead.budget_max)).limit(5)
        res_hot = await self.db.execute(stmt_hot)
        hot_uncontacted_leads = res_hot.scalars().all()
        hot_uncontacted_count = len(hot_uncontacted_leads)

        # 5. Top Priority Lead
        top_priority_lead = None
        if hot_uncontacted_leads:
            top_lead = hot_uncontacted_leads[0]
            top_priority_lead = {
                "id": str(top_lead.id),
                "name": top_lead.name or "Hot Lead",
                "phone": top_lead.phone,
                "score": top_lead.score,
                "budget_max": top_lead.budget_max,
                "reason": f"HOT score lead with no contact in 48 hours. Budget: {top_lead.budget_max or 'Undisclosed'}."
            }
        else:
            # Check next upcoming task lead
            stmt_next_task = select(Task).where(
                Task.broker_id == broker_id,
                Task.status.in_(["pending", "in_progress"]),
                Task.due_at >= now
            ).order_by(Task.due_at.asc()).limit(1)
            res_nt = await self.db.execute(stmt_next_task)
            next_task = res_nt.scalar_one_or_none()
            if next_task and next_task.lead_id:
                stmt_lead = select(Lead).where(Lead.id == next_task.lead_id)
                res_l = await self.db.execute(stmt_lead)
                tl = res_l.scalar_one_or_none()
                if tl:
                    top_priority_lead = {
                        "id": str(tl.id),
                        "name": tl.name or "Lead",
                        "phone": tl.phone,
                        "score": tl.score,
                        "budget_max": tl.budget_max,
                        "reason": f"Next due task: {next_task.title}"
                    }

        # Format briefing text
        greeting = "Good morning."
        briefing_lines = [
            f"{greeting} Here is your live CRM briefing for today:",
            f"• {due_today_count} follow-up task(s) due today",
            f"• {overdue_count} overdue task(s)",
            f"• {hot_uncontacted_count} HOT lead(s) without recent contact",
            f"• {meetings_today_count} scheduled meeting(s) today"
        ]
        if top_priority_lead:
            briefing_lines.append(f"\nTop Priority: {top_priority_lead['name']} ({top_priority_lead['reason']})")
        else:
            briefing_lines.append("\nYou have no critical urgent pending items at this time.")

        summary_text = "\n".join(briefing_lines)

        return {
            "due_today_count": due_today_count,
            "overdue_count": overdue_count,
            "hot_uncontacted_count": hot_uncontacted_count,
            "meetings_today_count": meetings_today_count,
            "top_priority_lead": top_priority_lead,
            "summary_text": summary_text,
            "generated_at": now.isoformat()
        }
