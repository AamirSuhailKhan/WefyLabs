"""
AI Sales Copilot Controlled Tool Layer
======================================
Provides safe, controlled, deterministic tool functions that allow
the AI Copilot to query live CRM Intelligence without direct raw SQL access.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.crm_intelligence_models import (
    LeadHealthSnapshot, LeadRisk, SlaBreach, PipelineHealthSnapshot,
    AgentWorkloadSnapshot, OperationalNextBestAction
)
from app.modules.crm_intelligence.lead_health.lead_health_engine import LeadHealthEngine
from app.modules.crm_intelligence.pipeline_health.pipeline_engine import PipelineIntelligenceEngine
from app.modules.crm_intelligence.workload_intelligence.workload_engine import WorkloadIntelligenceEngine
from app.modules.crm_intelligence.daily_brief.brief_service import DailyBriefService

logger = logging.getLogger(__name__)

class CopilotIntelligenceTools:
    """
    Controlled tool execution layer for the AI Sales Copilot.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_lead_health(self, lead_id: str, organization_id: str) -> Dict[str, Any]:
        """Tool: getLeadHealth(lead_id)"""
        engine = LeadHealthEngine(self.db)
        snap = await engine.evaluate_lead_health(lead_id, organization_id)
        return {
            "lead_id": snap.lead_id,
            "health_state": snap.health_state,
            "health_score": snap.health_score,
            "engagement_health": snap.engagement_health,
            "intent_health": snap.intent_health,
            "response_health": snap.response_health,
            "follow_up_health": snap.follow_up_health,
            "meeting_health": snap.meeting_health,
            "explanation": snap.explanation,
            "decay_detected": snap.decay_detected,
            "neglect_detected": snap.neglect_detected
        }

    async def get_at_risk_leads(self, organization_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Tool: getAtRiskLeads()"""
        stmt = (
            select(LeadRisk)
            .where(and_(LeadRisk.organization_id == organization_id, LeadRisk.status == "ACTIVE"))
            .order_by(LeadRisk.created_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        risks = res.scalars().all()
        return [
            {
                "lead_id": r.lead_id,
                "risk_type": r.risk_type,
                "severity": r.severity,
                "confidence": r.confidence,
                "evidence": r.evidence,
                "recommended_action": r.recommended_recovery_action
            }
            for r in risks
        ]

    async def get_pipeline_health(self, organization_id: str) -> List[Dict[str, Any]]:
        """Tool: getPipelineHealth()"""
        engine = PipelineIntelligenceEngine(self.db)
        snaps = await engine.evaluate_pipeline_health(organization_id)
        return [
            {
                "stage_name": s.stage_name,
                "lead_count": s.lead_count,
                "total_pipeline_value_aed": s.total_pipeline_value_aed,
                "weighted_pipeline_value_aed": s.weighted_pipeline_value_aed,
                "avg_stage_duration_days": s.avg_stage_duration_days,
                "stagnant_leads_count": s.stagnant_leads_count,
                "drop_off_rate_pct": s.drop_off_rate_pct,
                "revenue_at_risk_aed": s.revenue_at_risk_aed
            }
            for s in snaps
        ]

    async def get_sla_breaches(self, organization_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Tool: getSlaBreaches()"""
        stmt = (
            select(SlaBreach)
            .where(SlaBreach.organization_id == organization_id)
            .order_by(SlaBreach.breached_at_utc.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        breaches = res.scalars().all()
        return [
            {
                "lead_id": b.lead_id,
                "broker_id": b.broker_id,
                "sla_type": b.sla_type,
                "overdue_minutes": b.overdue_minutes,
                "breached_at": b.breached_at_utc.isoformat()
            }
            for b in breaches
        ]

    async def get_agent_workload(self, broker_id: str, organization_id: str) -> Dict[str, Any]:
        """Tool: getAgentWorkload(broker_id)"""
        engine = WorkloadIntelligenceEngine(self.db)
        snap = await engine.evaluate_agent_workload(broker_id, organization_id)
        return {
            "broker_id": snap.broker_id,
            "workload_status": snap.workload_status,
            "capacity_utilization_pct": snap.capacity_utilization_pct,
            "active_leads_count": snap.active_leads_count,
            "high_priority_leads_count": snap.high_priority_leads_count,
            "overdue_tasks_count": snap.overdue_tasks_count,
            "scheduled_meetings_today": snap.scheduled_meetings_today,
            "rebalancing_recommended": snap.rebalancing_recommended
        }

    async def get_daily_brief(self, organization_id: str, role: str = "broker", broker_id: Optional[str] = None) -> Dict[str, Any]:
        """Tool: getDailyBrief()"""
        service = DailyBriefService(self.db)
        if role == "manager" or not broker_id:
            brief = await service.generate_manager_brief(organization_id)
            return {
                "role": "manager",
                "executive_summary": brief.executive_summary,
                "today_new_leads": brief.today_new_leads,
                "high_intent_leads": brief.high_intent_leads_count,
                "at_risk_leads": brief.at_risk_leads_count,
                "sla_breaches": brief.sla_breaches_count,
                "top_actions": brief.top_manager_actions
            }
        else:
            brief = await service.generate_agent_brief(broker_id, organization_id)
            return {
                "role": "broker",
                "summary": brief.daily_focus_summary,
                "top_leads_to_call": brief.top_leads_to_call,
                "upcoming_meetings": brief.upcoming_meetings_today,
                "overdue_follow_ups": brief.overdue_follow_ups_count
            }
