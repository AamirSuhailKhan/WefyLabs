"""
Master Build 14 — Competitive Moat, Benchmarking & Intelligence Graph Router
=============================================================================
Canonical REST API endpoints for Master Build 14.

Endpoints:
  POST /intelligence/outcomes                    — Record append-only outcome event
  GET  /intelligence/outcomes                    — List tenant outcome events
  POST /intelligence/learning/signals            — Record raw learning signal
  POST /intelligence/learning/signals/{id}/verify — Verify learning signal (human gate)
  GET  /intelligence/learning/profile            — Fetch organization learning profile
  POST /intelligence/graph/edges                 — Add causal edge to outcome graph
  GET  /intelligence/graph/leads/{lead_id}/journey — Get full lead outcome trajectory
  POST /intelligence/ai-actions                  — Record AI action outcome
  POST /intelligence/ai-actions/{id}/override    — Record human override with reason
  POST /intelligence/objections                  — Record objection and rebuttal
  GET  /intelligence/objections/analytics        — Get objection analytics and winning rebuttals
  POST /intelligence/funnel/transitions          — Record funnel transition
  GET  /intelligence/funnel/metrics              — Funnel velocity, dropoff, and bottlenecks
  POST /intelligence/experiments                 — Create controlled experiment
  POST /intelligence/experiments/{id}/assign     — Assign variant to entity
  POST /intelligence/experiments/{id}/convert    — Record conversion for assigned entity
  GET  /intelligence/experiments/{id}/evaluate   — Evaluate experiment results
  POST /intelligence/benchmarks/definitions      — Create benchmark definition
  POST /intelligence/benchmarks/snapshots/compute — Compute privacy-preserving benchmark snapshot
  GET  /intelligence/benchmarks/compare          — Compare organization to peer cohort
  POST /intelligence/snapshots/generate          — Generate tenant intelligence snapshot
  GET  /intelligence/insights                    — Get prioritized actionable insights
  GET  /intelligence/data-quality/report         — Data quality audit report
  POST /intelligence/policies/registry           — Register policy/prompt/model
  POST /intelligence/policies/registry/{id}/promote — Promote entry through evaluation gates
  POST /intelligence/replay                      — Replay outcome events deterministically
  POST /intelligence/backfill                    — Idempotently backfill from operational tables
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.intelligence.dto import (
    OutcomeEventCreate,
    OutcomeEventResponse,
    LearningEventCreate,
    LearningEventVerifyRequest,
    LearningEventResponse,
    OrganizationLearningProfileResponse,
    SalesOutcomeEdgeCreate,
    SalesOutcomeEdgeResponse,
    GraphPathResponse,
    AIActionOutcomeCreate,
    AIActionOverrideRequest,
    AIActionOutcomeResponse,
    ObjectionRecordCreate,
    ObjectionRecordResponse,
    ObjectionAnalyticsResponse,
    FunnelTransitionCreate,
    FunnelTransitionResponse,
    FunnelMetricsResponse,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentAssignmentRequest,
    ExperimentConversionRequest,
    ExperimentEvaluationResponse,
    BenchmarkDefinitionCreate,
    BenchmarkSnapshotResponse,
    BenchmarkComparisonResponse,
    IntelligenceSnapshotResponse,
    InsightRecordResponse,
    DataQualityReportResponse,
    PolicyRegistryEntryCreate,
    PolicyPromotionRequest,
    PolicyRegistryEntryResponse,
    ReplayRequest,
    ReplayResponse,
    BackfillRequest,
    BackfillResponse,
    ExecutiveIntelligenceResponse,
    ManagerIntelligenceResponse,
    SalesUserIntelligenceResponse,
    MoatMetricsResponse,
    CompetitiveCapabilityMatrixResponse,
    ChannelIntelligenceResponse,
    AgentCoachingResponse,
    OrganizationPlaybookResponse,
)
from app.modules.intelligence.service import IntelligenceService

router = APIRouter(
    prefix="/intelligence",
    tags=["Master Build 14 — Competitive Moat & Intelligence OS"],
)

service = IntelligenceService()


def _get_org_id(broker: Broker) -> str:
    """Extract organization_id from authenticated broker."""
    if hasattr(broker, "organization_id") and broker.organization_id:
        return str(broker.organization_id)
    return str(broker.id)


# ─── 1. Canonical Outcome Events ────────────────────────────────────────────

@router.post("/outcomes", response_model=OutcomeEventResponse, status_code=status.HTTP_201_CREATED)
async def record_outcome(
    payload: OutcomeEventCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    event = await service.record_outcome(db, org_id, payload)
    return OutcomeEventResponse.model_validate(event)


@router.get("/outcomes", response_model=List[OutcomeEventResponse])
async def list_outcomes(
    lead_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    events = await service.list_outcomes(
        db, org_id, lead_id=lead_id, event_type=event_type, entity_type=entity_type, limit=limit
    )
    return [OutcomeEventResponse.model_validate(e) for e in events]


# ─── 2. Learning Events & Verification Gate ─────────────────────────────────

@router.post("/learning/signals", response_model=LearningEventResponse, status_code=status.HTTP_201_CREATED)
async def record_learning_signal(
    payload: LearningEventCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    event = await service.record_learning_signal(db, org_id, payload)
    return LearningEventResponse.model_validate(event)


@router.post("/learning/signals/{id}/verify", response_model=LearningEventResponse)
async def verify_learning_signal(
    id: str,
    payload: LearningEventVerifyRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        event = await service.verify_learning_signal(db, org_id, id, payload.verified_by)
        return LearningEventResponse.model_validate(event)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/learning/profile", response_model=OrganizationLearningProfileResponse)
async def get_learning_profile(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    profile = await service.get_or_create_profile(db, org_id)
    return OrganizationLearningProfileResponse.model_validate(profile)


# ─── 3. Sales Outcome Graph ─────────────────────────────────────────────────

@router.post("/graph/edges", response_model=SalesOutcomeEdgeResponse, status_code=status.HTTP_201_CREATED)
async def add_graph_edge(
    payload: SalesOutcomeEdgeCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    edge = await service.add_graph_edge(db, org_id, payload)
    return SalesOutcomeEdgeResponse.model_validate(edge)


@router.get("/graph/leads/{lead_id}/journey", response_model=GraphPathResponse)
async def get_lead_journey(
    lead_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await service.get_lead_journey(db, org_id, lead_id)


# ─── 4. AI Action Lifecycle & Human Override ────────────────────────────────

@router.post("/ai-actions", response_model=AIActionOutcomeResponse, status_code=status.HTTP_201_CREATED)
async def record_ai_action_outcome(
    payload: AIActionOutcomeCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    action = await service.record_ai_action_outcome(db, org_id, payload)
    return AIActionOutcomeResponse.model_validate(action)


@router.post("/ai-actions/{id}/override", response_model=AIActionOutcomeResponse)
async def record_human_override(
    id: str,
    payload: AIActionOverrideRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        action = await service.record_human_override(
            db, org_id, id, payload.override_reason, payload.corrected_action
        )
        return AIActionOutcomeResponse.model_validate(action)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─── 5. Objection & Funnel Intelligence ─────────────────────────────────────

@router.post("/objections", response_model=ObjectionRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_objection(
    payload: ObjectionRecordCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    record = await service.record_objection(db, org_id, payload)
    return ObjectionRecordResponse.model_validate(record)


@router.get("/objections/analytics", response_model=ObjectionAnalyticsResponse)
async def get_objection_analytics(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await service.get_objection_analytics(db, org_id)


@router.post("/funnel/transitions", response_model=FunnelTransitionResponse, status_code=status.HTTP_201_CREATED)
async def record_funnel_transition(
    payload: FunnelTransitionCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    rec = await service.record_funnel_transition(db, org_id, payload)
    return FunnelTransitionResponse.model_validate(rec)


@router.get("/funnel/metrics", response_model=FunnelMetricsResponse)
async def get_funnel_metrics(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await service.get_funnel_metrics(db, org_id)


# ─── 6. Experimentation Engine ──────────────────────────────────────────────

@router.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    payload: ExperimentCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    exp = await service.create_experiment(db, org_id, payload)
    return ExperimentResponse.model_validate(exp)


@router.post("/experiments/{id}/assign")
async def assign_experiment_variant(
    id: str,
    payload: ExperimentAssignmentRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        var = await service.assign_variant(db, org_id, id, payload.entity_id, payload.entity_type)
        return {"experiment_id": id, "variant_id": var.id, "variant_name": var.name, "is_control": var.is_control}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/experiments/{id}/convert")
async def record_experiment_conversion(
    id: str,
    payload: ExperimentConversionRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    conv = await service.record_conversion(
        db, org_id, id, payload.entity_id, payload.metric_name, payload.metric_value
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity had no active assignment for this experiment.",
        )
    return {"status": "SUCCESS", "conversion_id": conv.id, "variant_id": conv.variant_id}


@router.get("/experiments/{id}/evaluate", response_model=ExperimentEvaluationResponse)
async def evaluate_experiment(
    id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        return await service.evaluate_experiment(db, org_id, id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─── 7. Benchmarking Engine & Privacy ───────────────────────────────────────

@router.post("/benchmarks/definitions", status_code=status.HTTP_201_CREATED)
async def create_benchmark_definition(
    payload: BenchmarkDefinitionCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        bdef = await service.create_benchmark_definition(db, payload, org_id=org_id)
        return {"id": bdef.id, "name": bdef.name, "minimum_cohort_size": bdef.minimum_cohort_size}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/benchmarks/snapshots/compute", response_model=Optional[BenchmarkSnapshotResponse])
async def compute_benchmark_snapshot(
    definition_id: str = Query(...),
    period_days: int = Query(30, ge=1, le=365),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=period_days)
    try:
        snap = await service.compute_benchmark_snapshot(db, definition_id, start, now)
        if not snap:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cohort size is below the required privacy threshold (minimum 5 tenants required).",
            )
        return BenchmarkSnapshotResponse.model_validate(snap)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/benchmarks/compare", response_model=BenchmarkComparisonResponse)
async def compare_to_benchmark(
    metric_name: str = Query("conversion_rate"),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await service.compare_to_benchmark(db, org_id, metric_name)


# ─── 8. Intelligence Snapshots & Insights ───────────────────────────────────

@router.post("/snapshots/generate", response_model=IntelligenceSnapshotResponse)
async def generate_intelligence_snapshot(
    period_type: str = Query("DAILY", pattern="^(DAILY|WEEKLY|MONTHLY)$"),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    snap = await service.generate_intelligence_snapshot(db, org_id, period_type)
    return IntelligenceSnapshotResponse.model_validate(snap)


@router.get("/insights", response_model=List[InsightRecordResponse])
async def get_insights(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    insights = await service.generate_actionable_insights(db, org_id)
    return [InsightRecordResponse.model_validate(i) for i in insights]


# ─── 9. Data Quality & Drift ────────────────────────────────────────────────

@router.get("/data-quality/report", response_model=DataQualityReportResponse)
async def get_data_quality_report(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await service.scan_data_quality(db, org_id)


# ─── 10. Policy & Model Registry with Promotion Gates ───────────────────────

@router.post("/policies/registry", response_model=PolicyRegistryEntryResponse, status_code=status.HTTP_201_CREATED)
async def register_policy_entry(
    payload: PolicyRegistryEntryCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    entry = await service.register_policy_entry(db, org_id, payload)
    return PolicyRegistryEntryResponse.model_validate(entry)


@router.post("/policies/registry/{id}/promote", response_model=PolicyRegistryEntryResponse)
async def promote_policy_entry(
    id: str,
    payload: PolicyPromotionRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        entry = await service.promote_policy_entry(
            db, org_id, id, payload.target_status, payload.eval_score, payload.validation_notes
        )
        return PolicyRegistryEntryResponse.model_validate(entry)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── 11. Replay & Backfill ──────────────────────────────────────────────────

@router.post("/replay", response_model=ReplayResponse)
async def replay_events(
    payload: ReplayRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await service.replay_events(
        db, org_id, payload.start_date, payload.end_date, payload.simulate_only
    )


@router.post("/backfill", response_model=BackfillResponse)
async def backfill_operational_outcomes(
    payload: BackfillRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await service.backfill_operational_outcomes(
        db, org_id, payload.target_sources, payload.batch_size
    )


# ─── 12. Extended Dashboards & Intelligence Endpoints ───────────────────────

@router.get("/dashboards/executive", response_model=ExecutiveIntelligenceResponse)
async def get_executive_intelligence_dashboard(
    period_type: str = Query("MONTHLY", pattern="^(DAILY|WEEKLY|MONTHLY)$"),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Returns executive dashboard with pipeline, revenue, unit economics, and operational bottlenecks."""
    org_id = _get_org_id(broker)
    return await service.get_executive_intelligence(db, org_id, period_type)


@router.get("/dashboards/manager", response_model=ManagerIntelligenceResponse)
async def get_manager_intelligence_dashboard(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Returns manager dashboard with team workload, follow-up risks, and coaching signals."""
    org_id = _get_org_id(broker)
    return await service.get_manager_intelligence(db, org_id)


@router.get("/dashboards/sales", response_model=SalesUserIntelligenceResponse)
async def get_sales_intelligence_dashboard(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Returns agent personal command center with next-best-actions, high-intent leads, and opportunities."""
    org_id = _get_org_id(broker)
    agent_id = str(broker.id)
    return await service.get_sales_user_intelligence(db, org_id, agent_id)


@router.get("/moat/metrics", response_model=MoatMetricsResponse)
async def get_moat_metrics(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Measures 10 data-driven defensibility indicators for WefyLabs Competitive Moat."""
    org_id = _get_org_id(broker)
    return await service.get_moat_metrics(db, org_id)


@router.get("/competitive/matrix", response_model=CompetitiveCapabilityMatrixResponse)
async def get_competitive_matrix(
    broker: Broker = Depends(get_current_broker),
):
    """Returns evidence-backed competitive capability dimensions without synthetic claims."""
    return await service.get_competitive_matrix()


@router.get("/channels/analytics", response_model=ChannelIntelligenceResponse)
async def get_channel_analytics(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Returns comparative channel conversion velocity, volume, and gross margin."""
    org_id = _get_org_id(broker)
    return await service.get_channel_intelligence(db, org_id)


@router.get("/coaching/signals", response_model=AgentCoachingResponse)
async def get_coaching_signals(
    agent_id: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Returns evidence-backed sales coaching insights citing underlying event IDs."""
    org_id = _get_org_id(broker)
    return await service.get_coaching_signals(db, org_id, agent_id)


@router.get("/playbook", response_model=OrganizationPlaybookResponse)
async def get_organization_playbook(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Returns organization-specific playbooks synthesized from verified learning signals."""
    org_id = _get_org_id(broker)
    return await service.get_organization_playbook(db, org_id)

