"""
Volume 2 PART 5 — AI Agent Monitoring & KPI Tracker
===================================================
Tracks:
- Conversation length & turns
- Qualification conversion rate
- Booking rate & escalation rate
- Avg first response latency (target: < 3s)
- Token usage & USD cost
- Hallucination incidents
"""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Float

from app.models.agent_models import AgentSession, QualificationProfile, Escalation, LLMUsage, ToolExecution


class AgentMonitoringTracker:
    """Aggregates real-time performance and financial metrics for the AI Sales Agent."""

    async def get_summary_stats(self, db: AsyncSession, organization_id: str) -> Dict[str, Any]:
        """Calculates global metrics for an organization's agent instance."""
        # Total sessions
        sess_query = select(func.count(AgentSession.id)).where(AgentSession.organization_id == organization_id)
        res_sess = await db.execute(sess_query)
        total_sessions = res_sess.scalar() or 0

        # Qualified sessions
        qual_query = select(func.count(QualificationProfile.id)).where(
            QualificationProfile.organization_id == organization_id,
            QualificationProfile.is_qualified == True
        )
        res_qual = await db.execute(qual_query)
        qualified_count = res_qual.scalar() or 0

        # Escalations
        esc_query = select(func.count(Escalation.id)).where(Escalation.organization_id == organization_id)
        res_esc = await db.execute(esc_query)
        escalation_count = res_esc.scalar() or 0

        # Total cost and token usage
        cost_query = select(
            func.sum(LLMUsage.cost_usd),
            func.sum(LLMUsage.total_tokens),
            func.avg(LLMUsage.latency_ms)
        ).where(LLMUsage.organization_id == organization_id)
        res_cost = await db.execute(cost_query)
        cost_row = res_cost.first()
        total_cost_usd = float(cost_row[0] or 0.0)
        total_tokens = int(cost_row[1] or 0)
        avg_latency_ms = float(cost_row[2] or 0.0)

        # Qualification Rate %
        qual_rate = round((qualified_count / total_sessions * 100), 2) if total_sessions > 0 else 0.0
        # Escalation Rate %
        esc_rate = round((escalation_count / total_sessions * 100), 2) if total_sessions > 0 else 0.0

        return {
            "total_sessions": total_sessions,
            "qualified_count": qualified_count,
            "qualification_rate_pct": qual_rate,
            "escalation_count": escalation_count,
            "escalation_rate_pct": esc_rate,
            "total_tokens_used": total_tokens,
            "total_cost_usd": round(total_cost_usd, 4),
            "avg_latency_ms": round(avg_latency_ms, 1),
            "performance_target_met": avg_latency_ms < 3000.0 if avg_latency_ms > 0 else True
        }
