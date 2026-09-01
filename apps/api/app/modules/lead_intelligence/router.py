"""
Lead Intelligence REST API Router
==================================
Endpoints:
    POST   /api/v1/intelligence/score/{lead_id}         # Trigger scoring pipeline
    GET    /api/v1/intelligence/profile/{lead_id}       # Fetch intelligence profile
    GET    /api/v1/intelligence/recommendations/{lead_id}# Fetch Next Best Actions
    GET    /api/v1/intelligence/explanation/{lead_id}   # Fetch Explainable AI drivers
    POST   /api/v1/intelligence/simulate                # Revenue What-If Simulator
    GET    /api/v1/intelligence/rules                   # List active scoring rules
    POST   /api/v1/intelligence/rules                   # Create/Update scoring rule
    POST   /api/v1/intelligence/replay/{lead_id}        # Replay historical scoring
    GET    /api/v1/intelligence/metrics                 # Monitoring stats
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead_intelligence_models import ScoringRule, PredictionHistory, LeadRecommendation
from app.modules.lead_intelligence.service import LeadIntelligenceService
from app.modules.lead_intelligence.revenue_engine.revenue_calculator import RevenueCalculator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/intelligence", tags=["AI Lead Intelligence & Revenue Engine"])


# ─── DTOs ─────────────────────────────────────────────────────────────────────

class ScoreLeadRequest(BaseModel):
    lead_dto: Dict[str, Any] = Field(..., description="Canonical lead DTO")
    organization_id: str
    trigger_event: Optional[str] = "ManualTrigger"

class SimulateRevenueRequest(BaseModel):
    baseline_weighted_revenue_aed: float = 10_000_000.0
    expected_commission_aed: float = 200_000.0
    response_time_improvement_pct: float = 50.0  # 50% faster
    viewing_booking_increase_pct: float = 20.0    # 20% more viewings

class CreateRuleRequest(BaseModel):
    organization_id: str
    name: str
    condition_json: Dict[str, Any]
    action_type: str = "add_score"  # add_score | subtract_score | set_priority
    action_value: float
    priority: int = 10


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/score/{lead_id}", summary="Trigger AI Lead Scoring & Prediction Pipeline")
async def score_lead(
    lead_id: str,
    request: ScoreLeadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI Lead Scoring pipeline for a lead."""
    try:
        service = LeadIntelligenceService(db=db)
        lead_data = dict(request.lead_dto)
        lead_data["id"] = lead_id
        result = await service.score_lead(
            lead_dto=lead_data,
            organization_id=request.organization_id,
            trigger_event=request.trigger_event or "ManualTrigger",
        )
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"[INTELLIGENCE_ROUTER] score_lead failed for {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/{lead_id}", summary="Fetch Full Intelligence Profile")
async def get_lead_profile(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch complete AI intelligence profile, predictions, and recommendations for a lead."""
    service = LeadIntelligenceService(db=db)
    profile = await service.get_lead_profile(lead_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Intelligence profile for lead {lead_id} not found")
    return {"status": "success", "profile": profile}


@router.get("/recommendations/{lead_id}", summary="Fetch Ranked Next Best Actions")
async def get_recommendations(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch ranked Next Best Actions with % conversion lift and business rationale."""
    result = await db.execute(
        select(LeadRecommendation)
        .where(LeadRecommendation.lead_id == lead_id, LeadRecommendation.status == "active")
        .order_by(LeadRecommendation.rank.asc())
    )
    recs = result.scalars().all()
    return {
        "lead_id": lead_id,
        "count": len(recs),
        "recommendations": [
            {
                "id": r.id,
                "rank": r.rank,
                "action_type": r.action_type,
                "action_title": r.action_title,
                "estimated_conversion_lift": r.estimated_conversion_lift,
                "reasoning": r.reasoning,
            }
            for r in recs
        ],
    }


@router.post("/simulate", summary="Revenue Impact What-If Simulator")
async def simulate_revenue(
    request: SimulateRevenueRequest,
):
    """Run 'What-If' revenue impact simulation (e.g. response time speedup, viewing increases)."""
    calc = RevenueCalculator()
    current_pipeline = {
        "probability_weighted_revenue_aed": request.baseline_weighted_revenue_aed,
        "expected_commission_aed": request.expected_commission_aed,
    }
    sim = calc.simulate_what_if(
        current_pipeline=current_pipeline,
        response_time_improvement_pct=request.response_time_improvement_pct,
        viewing_booking_increase_pct=request.viewing_booking_increase_pct,
    )
    return {"status": "success", "simulation": sim}


@router.get("/rules", summary="List Active Scoring Rules")
async def list_scoring_rules(
    organization_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """List organization-defined scoring rules."""
    result = await db.execute(
        select(ScoringRule)
        .where(ScoringRule.organization_id == organization_id, ScoringRule.is_active == True)
        .order_by(ScoringRule.priority.asc())
    )
    rules = result.scalars().all()
    return {
        "organization_id": organization_id,
        "count": len(rules),
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "condition": r.condition_json,
                "action_type": r.action_type,
                "action_value": r.action_value,
                "priority": r.priority,
            }
            for r in rules
        ],
    }


@router.post("/rules", summary="Create Custom Scoring Rule")
async def create_scoring_rule(
    request: CreateRuleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a custom scoring rule (editable by business users without code deployment)."""
    rule = ScoringRule(
        organization_id=request.organization_id,
        name=request.name,
        condition_json=request.condition_json,
        action_type=request.action_type,
        action_value=request.action_value,
        priority=request.priority,
        is_active=True,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"status": "success", "rule_id": rule.id, "message": "Scoring rule created successfully"}


@router.post("/replay/{lead_id}", summary="Replay Historical Scoring Pass")
async def replay_scoring(
    lead_id: str,
    organization_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Replay scoring pass for historical audit and model verification."""
    result = await db.execute(
        select(PredictionHistory)
        .where(PredictionHistory.lead_id == lead_id, PredictionHistory.organization_id == organization_id)
        .order_by(PredictionHistory.created_at.desc())
    )
    history = result.scalars().all()
    return {
        "lead_id": lead_id,
        "history_count": len(history),
        "passes": [
            {
                "id": h.id,
                "trigger_event": h.trigger_event,
                "lead_score": h.lead_score,
                "conversion_probability": h.conversion_probability,
                "temperature": h.temperature,
                "intent_phase": h.intent_phase,
                "model_version": h.model_version,
                "execution_time_ms": h.execution_time_ms,
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ],
    }


@router.get("/metrics", summary="Intelligence Engine Monitoring Metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
):
    """Get operational monitoring metrics."""
    service = LeadIntelligenceService(db=db)
    metrics = service.metrics_collector.get_metrics()
    return {"status": "success", "metrics": metrics}
