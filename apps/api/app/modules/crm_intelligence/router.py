"""
CRM Intelligence & Autonomous Sales Operations REST API Router
==============================================================
Provides production-grade endpoints for lead health, risk detection,
pipeline stagnation, SLA monitoring, agent workloads, AI insights,
Next Best Actions, and Manager/Agent daily operational briefs.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.crm_intelligence.service import CRMIntelligenceService
from app.modules.crm_intelligence.dto.intelligence_schemas import (
    LeadHealthResponse, LeadRiskResponse, PipelineHealthStageResponse,
    OpportunityHealthResponse, SlaBreachResponse, AgentWorkloadResponse,
    SalesInsightResponse, NextBestActionResponse, ActionExecutionRequest,
    ActionExecutionResponse, ManagerBriefResponse, AgentBriefResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/intelligence", tags=["CRM Intelligence & Autonomous Sales Operations Engine"])

# ─── Lead Health & Risks ───────────────────────────────────────────────────────

@router.get(
    "/leads/health/{lead_id}",
    response_model=LeadHealthResponse,
    summary="Evaluate & Get Lead Health Snapshot"
)
async def get_lead_health(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Calculates 9-dimensional health, decay velocity, and neglect detection for a lead."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    try:
        snap = await service.get_or_evaluate_lead_health(lead_id, org_id)
        return snap
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"[INTELLIGENCE_ROUTER] get_lead_health failed for {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/leads/at-risk",
    response_model=List[LeadRiskResponse],
    summary="List Active At-Risk Leads"
)
async def list_at_risk_leads(
    limit: int = Query(50, ge=1, le=200),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Fetches active operational risks (cooling intent, cancelled viewings, SLA breaches)."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    risks = await service.get_at_risk_leads(org_id, limit)
    return risks


@router.get(
    "/leads/neglected",
    response_model=List[LeadRiskResponse],
    summary="List Neglected High-Intent Leads"
)
async def list_neglected_leads(
    limit: int = Query(50, ge=1, le=200),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Fetches high-intent leads that have not received broker engagement within target SLAs."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    neglected = await service.get_neglected_leads(org_id, limit)
    return neglected


# ─── Pipeline Health & Opportunities ──────────────────────────────────────────

@router.get(
    "/pipeline",
    response_model=List[PipelineHealthStageResponse],
    summary="Get Pipeline Velocity, Stagnation & Drop-Off"
)
async def get_pipeline_health(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Computes stage velocity, stagnation counts, drop-off rates, and revenue at risk."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.get_pipeline_health(org_id)


@router.get(
    "/pipeline/opportunities/{lead_id}",
    response_model=OpportunityHealthResponse,
    summary="Evaluate Opportunity / Deal Health"
)
async def get_opportunity_health(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Assesses closing probability, momentum, and stage dwell time for a specific deal."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    try:
        return await service.get_opportunity_health(lead_id, org_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


# ─── SLA Intelligence ──────────────────────────────────────────────────────────

@router.get(
    "/sla/breaches",
    response_model=List[SlaBreachResponse],
    summary="List Recent SLA Breaches"
)
async def list_sla_breaches(
    limit: int = Query(50, ge=1, le=200),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists recorded SLA breaches across response times and viewing follow-ups."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.list_sla_breaches(org_id, limit)


@router.post(
    "/sla/check",
    response_model=List[SlaBreachResponse],
    summary="Trigger Real-Time SLA Breach Scan"
)
async def trigger_sla_check(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Evaluates all running SLA timers and records breaches for overdue instances."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.check_sla_breaches(org_id)


# ─── Agent Workload ───────────────────────────────────────────────────────────

@router.get(
    "/agents/workload",
    response_model=List[AgentWorkloadResponse],
    summary="Get Agent Capacity & Workload Distribution"
)
async def get_agent_workload(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Evaluates active lead loads, overdue task counts, and detects overloaded agents."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.evaluate_all_agents(org_id)


# ─── Insights & Anomaly Detection ──────────────────────────────────────────────

@router.get(
    "/insights",
    response_model=List[SalesInsightResponse],
    summary="Get Active Sales & Operational Insights"
)
async def list_insights(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Fetches active, explainable natural-language sales insights grounded in CRM data."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    await service.generate_insights(org_id)
    return await service.list_active_insights(org_id)


@router.post(
    "/insights/{insight_id}/dismiss",
    summary="Dismiss Sales Insight"
)
async def dismiss_insight(
    insight_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Dismisses an insight and records the override to prevent alert fatigue."""
    service = CRMIntelligenceService(db)
    success = await service.dismiss_insight(insight_id, str(current_broker.id))
    if not success:
        raise HTTPException(status_code=404, detail="Insight not found.")
    return {"status": "success", "message": "Insight dismissed."}


@router.post(
    "/insights/{insight_id}/snooze",
    summary="Snooze Sales Insight"
)
async def snooze_insight(
    insight_id: str,
    hours: int = Query(12, ge=1, le=168),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Snoozes an active insight for N hours."""
    service = CRMIntelligenceService(db)
    success = await service.snooze_insight(insight_id, str(current_broker.id), hours)
    if not success:
        raise HTTPException(status_code=404, detail="Insight not found.")
    return {"status": "success", "message": f"Insight snoozed for {hours} hours."}


# ─── Next Best Actions & Execution ─────────────────────────────────────────────

@router.get(
    "/actions/{lead_id}",
    response_model=List[NextBestActionResponse],
    summary="Generate Next Best Actions for Lead"
)
async def get_next_best_actions(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Generates prioritized Next Best Actions with urgency and potential revenue impact."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    try:
        return await service.generate_actions_for_lead(lead_id, org_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post(
    "/actions/{action_id}/execute",
    response_model=ActionExecutionResponse,
    summary="Execute Next Best Action (1-Click or Automated)"
)
async def execute_action(
    action_id: str,
    req: ActionExecutionRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Executes a recommended Next Best Action and creates underlying CRM activities/tasks."""
    service = CRMIntelligenceService(db)
    try:
        return await service.execute_action(
            action_id=action_id,
            executed_by=req.executed_by,
            payload=req.payload
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


# ─── Daily Operational Brief ───────────────────────────────────────────────────

@router.get(
    "/daily-brief",
    summary="Get Daily Operational Brief"
)
async def get_daily_brief(
    role: str = Query("broker", pattern="^(manager|broker)$"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Returns real-time operational summary (Manager team overview or Broker focus list)."""
    service = CRMIntelligenceService(db)
    org_id = str(current_broker.organization_id or "org_default")
    if role == "manager":
        brief = await service.get_manager_brief(org_id)
        return ManagerBriefResponse.model_validate(brief)
    else:
        brief = await service.get_agent_brief(str(current_broker.id), org_id)
        return AgentBriefResponse.model_validate(brief)
