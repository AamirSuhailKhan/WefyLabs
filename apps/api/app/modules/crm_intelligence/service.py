"""
CRM Intelligence & Autonomous Sales Operations Orchestrator Service
===================================================================
Coordinates all intelligence engines:
- Lead Health & Decay
- SLA Monitoring & Escalations
- Pipeline Stagnation & Deal Health
- Agent Capacity & Workload Balancing
- Statistical Anomaly Detection
- Prioritized Next Best Actions & Executions
- AI Sales Insights & Dismissals
- Operational Daily Briefs
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.crm_intelligence_models import (
    LeadHealthSnapshot, LeadRisk, SlaBreach, PipelineHealthSnapshot,
    OpportunityHealthSnapshot, AgentWorkloadSnapshot, AnomalyEvent,
    SalesInsight, OperationalNextBestAction, ActionExecution,
    ManagerDailyBrief, AgentDailyBrief
)
from app.modules.crm_intelligence.lead_health.lead_health_engine import LeadHealthEngine
from app.modules.crm_intelligence.sla_monitoring.sla_engine import SlaMonitoringEngine
from app.modules.crm_intelligence.pipeline_health.pipeline_engine import PipelineIntelligenceEngine
from app.modules.crm_intelligence.workload_intelligence.workload_engine import WorkloadIntelligenceEngine
from app.modules.crm_intelligence.anomaly_detection.anomaly_engine import AnomalyDetectionEngine
from app.modules.crm_intelligence.next_best_action.nba_engine import NextBestActionEngine
from app.modules.crm_intelligence.insight_engine.insight_service import InsightEngineService
from app.modules.crm_intelligence.daily_brief.brief_service import DailyBriefService

logger = logging.getLogger(__name__)

class CRMIntelligenceService:
    """
    Unified entry point for the CRM Intelligence layer.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.health_engine = LeadHealthEngine(db)
        self.sla_engine = SlaMonitoringEngine(db)
        self.pipeline_engine = PipelineIntelligenceEngine(db)
        self.workload_engine = WorkloadIntelligenceEngine(db)
        self.anomaly_engine = AnomalyDetectionEngine(db)
        self.nba_engine = NextBestActionEngine(db)
        self.insight_service = InsightEngineService(db)
        self.brief_service = DailyBriefService(db)

    # ─── Lead Health & Risks ───────────────────────────────────────────────────

    async def get_or_evaluate_lead_health(self, lead_id: str, organization_id: str) -> LeadHealthSnapshot:
        return await self.health_engine.evaluate_lead_health(lead_id, organization_id)

    async def get_at_risk_leads(self, organization_id: str, limit: int = 50) -> List[LeadRisk]:
        stmt = (
            select(LeadRisk)
            .where(and_(LeadRisk.organization_id == organization_id, LeadRisk.status == "ACTIVE"))
            .order_by(LeadRisk.created_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_neglected_leads(self, organization_id: str, limit: int = 50) -> List[LeadRisk]:
        stmt = (
            select(LeadRisk)
            .where(
                and_(
                    LeadRisk.organization_id == organization_id,
                    LeadRisk.risk_type == "NEGLECT",
                    LeadRisk.status == "ACTIVE"
                )
            )
            .order_by(LeadRisk.created_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ─── Pipeline Health ───────────────────────────────────────────────────────

    async def get_pipeline_health(self, organization_id: str) -> List[PipelineHealthSnapshot]:
        return await self.pipeline_engine.evaluate_pipeline_health(organization_id)

    async def get_opportunity_health(self, lead_id: str, organization_id: str) -> OpportunityHealthSnapshot:
        return await self.pipeline_engine.evaluate_opportunity_health(lead_id, organization_id)

    # ─── SLA Intelligence ──────────────────────────────────────────────────────

    async def check_sla_breaches(self, organization_id: Optional[str] = None) -> List[SlaBreach]:
        return await self.sla_engine.check_and_record_breaches(organization_id)

    async def list_sla_breaches(self, organization_id: str, limit: int = 50) -> List[SlaBreach]:
        stmt = (
            select(SlaBreach)
            .where(SlaBreach.organization_id == organization_id)
            .order_by(SlaBreach.breached_at_utc.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ─── Agent Capacity ────────────────────────────────────────────────────────

    async def evaluate_agent_workload(self, broker_id: str, organization_id: str) -> AgentWorkloadSnapshot:
        return await self.workload_engine.evaluate_agent_workload(broker_id, organization_id)

    async def evaluate_all_agents(self, organization_id: str) -> List[AgentWorkloadSnapshot]:
        return await self.workload_engine.evaluate_all_agents(organization_id)

    # ─── Anomaly & Insights ────────────────────────────────────────────────────

    async def detect_anomalies(self, organization_id: str) -> List[AnomalyEvent]:
        return await self.anomaly_engine.detect_anomalies(organization_id)

    async def generate_insights(self, organization_id: str) -> List[SalesInsight]:
        return await self.insight_service.generate_insights(organization_id)

    async def list_active_insights(self, organization_id: str) -> List[SalesInsight]:
        stmt = (
            select(SalesInsight)
            .where(
                and_(
                    SalesInsight.organization_id == organization_id,
                    SalesInsight.is_active == True
                )
            )
            .order_by(SalesInsight.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def dismiss_insight(self, insight_id: str, broker_id: str) -> bool:
        return await self.insight_service.dismiss_insight(insight_id, broker_id)

    async def snooze_insight(self, insight_id: str, broker_id: str, hours: int = 12) -> bool:
        return await self.insight_service.snooze_insight(insight_id, broker_id, hours)

    # ─── Next Best Action ──────────────────────────────────────────────────────

    async def generate_actions_for_lead(self, lead_id: str, organization_id: str) -> List[OperationalNextBestAction]:
        return await self.nba_engine.generate_actions_for_lead(lead_id, organization_id)

    async def execute_action(
        self,
        action_id: str,
        executed_by: str = "BROKER_1CLICK",
        payload: Optional[Dict[str, Any]] = None
    ) -> ActionExecution:
        return await self.nba_engine.execute_action(action_id, executed_by, payload)

    # ─── Daily Operational Briefs ──────────────────────────────────────────────

    async def get_manager_brief(self, organization_id: str) -> ManagerDailyBrief:
        return await self.brief_service.generate_manager_brief(organization_id)

    async def get_agent_brief(self, broker_id: str, organization_id: str) -> AgentDailyBrief:
        return await self.brief_service.generate_agent_brief(broker_id, organization_id)
