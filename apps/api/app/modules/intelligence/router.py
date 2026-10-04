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
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
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


# ─── Sprint 1F: Governed Adaptive Policy Pipeline ───────────────────────────

from pydantic import BaseModel, Field as PydanticField
from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

adaptive_service = AdaptivePolicyService()


class PolicyApprovalRequest(BaseModel):
    eval_score: Decimal = PydanticField(
        ..., ge=Decimal("0"), le=Decimal("1"),
        description="Evaluation score — must be >= 0.85 to approve."
    )
    notes: Optional[str] = None


class PolicyActivationRequest(BaseModel):
    notes: Optional[str] = None


class PolicyRollbackRequest(BaseModel):
    reason: str = PydanticField(..., min_length=10)
    previous_version_policy_id: Optional[str] = None


class EmergencyPauseRequest(BaseModel):
    reason: str = PydanticField(..., min_length=10)


class RolloutStatusResponse(BaseModel):
    policy_entry_id: str
    organization_id: str
    traffic_pct: int
    max_traffic_pct: int
    emergency_pause: bool
    is_rolled_back: bool
    last_increment_at: Optional[datetime]
    fully_deployed_at: Optional[datetime]


class AuditLogEntry(BaseModel):
    id: str
    policy_entry_id: str
    from_status: Optional[str]
    to_status: str
    actor_type: str
    actor_id: Optional[str]
    reason: Optional[str]
    eval_score: Optional[Decimal]
    notes: Optional[str]
    occurred_at: datetime


@router.post(
    "/policies/registry/{policy_id}/approve",
    summary="[Sprint 1F] Human approval gate — CANDIDATE/EVALUATION → APPROVED",
    status_code=status.HTTP_200_OK,
)
async def approve_policy(
    policy_id: str,
    payload: PolicyApprovalRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Transition a CANDIDATE or EVALUATION policy to APPROVED.

    Requirements:
    - eval_score >= 0.85
    - Authenticated user acts as the human approver (actor_id = broker.id)

    Sprint 1F Gate: G-13
    """
    org_id = _get_org_id(broker)
    actor_id = str(broker.id)
    try:
        entry = await adaptive_service.approve_policy(
            session=db,
            policy_entry_id=policy_id,
            org_id=org_id,
            actor_id=actor_id,
            eval_score=payload.eval_score,
            notes=payload.notes,
        )
        await db.commit()
        return {
            "id": entry.id,
            "status": entry.status,
            "promoted_by": entry.promoted_by,
            "promoted_at": entry.promoted_at.isoformat() if entry.promoted_at else None,
            "quality_score": str(entry.quality_score),
            "message": "Policy approved. Run pilot cohort check, then activate.",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/policies/registry/{policy_id}/pilot-check",
    summary="[Sprint 1F] Run pilot cohort readiness check",
    status_code=status.HTTP_200_OK,
)
async def run_pilot_cohort_check(
    policy_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate whether the organization has sufficient outcome data to
    safely promote a policy to ACTIVE.

    Checks: N≥30 outcomes, ≥7 observation days, no HIGH DQ issues.

    Sprint 1F Gate: G-08
    """
    org_id = _get_org_id(broker)
    guard = await adaptive_service.run_pilot_cohort_check(db, policy_id, org_id)
    await db.commit()
    return {
        "guard_id": guard.id,
        "policy_entry_id": guard.policy_entry_id,
        "organization_id": guard.organization_id,
        "is_cleared": guard.is_cleared,
        "actual_lead_count": guard.actual_lead_count,
        "min_lead_count": guard.min_lead_count,
        "actual_observation_days": guard.actual_observation_days,
        "min_observation_days": guard.min_observation_days,
        "open_high_severity_issues": guard.open_high_severity_issues,
        "check_notes": guard.check_notes,
        "checked_at": guard.checked_at.isoformat(),
    }


@router.post(
    "/policies/registry/{policy_id}/activate",
    summary="[Sprint 1F] Activate policy — APPROVED → ACTIVE + create rollout at 0%",
    status_code=status.HTTP_200_OK,
)
async def activate_policy(
    policy_id: str,
    payload: PolicyActivationRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Promote an APPROVED policy to ACTIVE. Requires a cleared PilotCohortGuard.
    Creates an AdaptivePolicyRollout at 0% traffic — the Celery controller
    advances it 10% per day as guardrails pass.

    Sprint 1F Gates: G-01, G-08
    """
    org_id = _get_org_id(broker)
    actor_id = str(broker.id)
    try:
        entry, guard = await adaptive_service.activate_policy(
            session=db,
            policy_entry_id=policy_id,
            org_id=org_id,
            actor_id=actor_id,
            notes=payload.notes,
        )
        await db.commit()
        return {
            "id": entry.id,
            "status": entry.status,
            "pilot_guard_cleared": guard.is_cleared,
            "message": "Policy activated. Rollout starts at 0% traffic and advances 10%/day.",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/policies/registry/{policy_id}/emergency-pause",
    summary="[Sprint 1F] Emergency pause — halt rollout controller immediately",
    status_code=status.HTTP_200_OK,
)
async def emergency_pause_rollout(
    policy_id: str,
    payload: EmergencyPauseRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Immediately halt the Celery rollout controller for a policy.
    Does NOT change the policy's status in PolicyRegistryEntry.

    Sprint 1F Gate: G-02
    """
    org_id = _get_org_id(broker)
    actor_id = str(broker.id)
    try:
        rollout = await adaptive_service.emergency_pause_rollout(
            session=db,
            policy_entry_id=policy_id,
            org_id=org_id,
            actor_id=actor_id,
            reason=payload.reason,
        )
        await db.commit()
        return {
            "policy_entry_id": policy_id,
            "emergency_pause": rollout.emergency_pause,
            "traffic_pct": rollout.traffic_pct,
            "message": "Rollout controller paused. Use /activate to resume or /rollback to revert.",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/policies/registry/{policy_id}/rollback",
    summary="[Sprint 1F] Rollback — ACTIVE → ROLLED_BACK + optionally restore previous version",
    status_code=status.HTTP_200_OK,
)
async def rollback_policy(
    policy_id: str,
    payload: PolicyRollbackRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Roll back an ACTIVE or APPROVED policy.

    Actions:
    - Sets policy status to ROLLED_BACK
    - Sets rollout traffic_pct = 0
    - Re-activates previous_version_policy_id if supplied

    Sprint 1F Gate: G-07
    """
    org_id = _get_org_id(broker)
    actor_id = str(broker.id)
    try:
        entry = await adaptive_service.rollback_policy(
            session=db,
            policy_entry_id=policy_id,
            org_id=org_id,
            actor_id=actor_id,
            reason=payload.reason,
            previous_version_policy_id=payload.previous_version_policy_id,
        )
        await db.commit()
        return {
            "id": entry.id,
            "status": entry.status,
            "message": "Policy rolled back. Traffic set to 0%. Create a new CANDIDATE to re-deploy.",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/policies/registry/{policy_id}/rollout",
    response_model=RolloutStatusResponse,
    summary="[Sprint 1F] Get rollout status for a policy",
)
async def get_rollout_status(
    policy_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Returns the current progressive rollout state for a policy."""
    from sqlalchemy import select as sa_select
    from app.models.intelligence_models import AdaptivePolicyRollout as APR

    q = sa_select(APR).where(APR.policy_entry_id == policy_id)
    rollout = (await db.execute(q)).scalar_one_or_none()
    if not rollout:
        raise HTTPException(status_code=404, detail=f"No rollout found for policy {policy_id}")
    return RolloutStatusResponse(
        policy_entry_id=rollout.policy_entry_id,
        organization_id=rollout.organization_id,
        traffic_pct=rollout.traffic_pct,
        max_traffic_pct=rollout.max_traffic_pct,
        emergency_pause=rollout.emergency_pause,
        is_rolled_back=rollout.is_rolled_back,
        last_increment_at=rollout.last_increment_at,
        fully_deployed_at=rollout.fully_deployed_at,
    )


@router.get(
    "/policies/registry/{policy_id}/audit-trail",
    response_model=List[AuditLogEntry],
    summary="[Sprint 1F] Complete immutable audit trail for a policy",
)
async def get_policy_audit_trail(
    policy_id: str,
    limit: int = Query(50, ge=1, le=200),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the ordered, immutable audit trail of every status transition
    for a PolicyRegistryEntry.

    Sprint 1F Gate: G-15 — Audit Trail Integrity
    """
    logs = await adaptive_service.get_policy_audit_trail(db, policy_id, limit=limit)
    return [
        AuditLogEntry(
            id=log.id,
            policy_entry_id=log.policy_entry_id,
            from_status=log.from_status,
            to_status=log.to_status,
            actor_type=log.actor_type,
            actor_id=log.actor_id,
            reason=log.reason,
            eval_score=log.eval_score,
            notes=log.notes,
            occurred_at=log.occurred_at,
        )
        for log in logs
    ]


@router.get(
    "/health",
    summary="[Sprint 1F] Intelligence subsystem structured health probe",
)
async def intelligence_health(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Structured health probe for the Revenue Intelligence subsystem.

    Returns:
    - status: OK | DEGRADED | DOWN
    - Individual check results: DB latency, snapshot age, DQ issues
    - last_snapshot_age_hours

    Sprint 1F Gate: G-09
    """
    org_id = _get_org_id(broker)
    return await adaptive_service.get_intelligence_health(db, org_id=org_id)


# ─── Sprint 1F: Revenue Leakage Engine Endpoints (Sections 21 & 22) ───────────

from app.modules.intelligence.revenue_leakage_service import (
    RevenueLeakageService,
    DataQualityOperationsService,
    HumanOverrideLearningService,
)


class LeakageCandidateCreateDTO(BaseModel):
    leakage_type: str = Field(..., description="e.g. UNCONTACTED_LEAD, STALE_QUALIFIED_LEAD, ABANDONED_OFFER")
    stage: str = Field(..., description="Pipeline stage")
    estimated_value: Decimal = Field(..., ge=0, description="Estimated value in AED")
    recommended_intervention: str = Field(..., min_length=5)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    lead_id: Optional[str] = None
    deal_id: Optional[str] = None
    property_id: Optional[str] = None
    owner_id: Optional[str] = None
    currency: str = "AED"
    expiry_hours: int = 72
    experiment_id: Optional[str] = None
    experiment_variant: Optional[str] = None


class LeakageCandidateResolveDTO(BaseModel):
    outcome: str = Field(..., description="Outcome description (e.g. REACTIVATED, VISIT_BOOKED)")
    recovered_value: Optional[Decimal] = None
    notes: Optional[str] = None
    is_dismissed: bool = False


@router.post(
    "/revenue-leakage/candidates",
    status_code=status.HTTP_201_CREATED,
    summary="[Sprint 1F] Create a revenue leakage candidate record",
)
async def create_leakage_candidate(
    payload: LeakageCandidateCreateDTO,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    rec = await RevenueLeakageService.create_leakage_candidate(
        db,
        organization_id=org_id,
        leakage_type=payload.leakage_type,
        stage=payload.stage,
        estimated_value=payload.estimated_value,
        recommended_intervention=payload.recommended_intervention,
        evidence=payload.evidence,
        lead_id=payload.lead_id,
        deal_id=payload.deal_id,
        property_id=payload.property_id,
        owner_id=payload.owner_id or str(broker.id),
        currency=payload.currency,
        expiry_hours=payload.expiry_hours,
        experiment_id=payload.experiment_id,
        experiment_variant=payload.experiment_variant,
    )
    await db.commit()
    return {
        "id": rec.id,
        "leakage_type": rec.leakage_type,
        "stage": rec.stage,
        "estimated_leakage_value": float(rec.estimated_leakage_value),
        "status": rec.status,
        "recommended_intervention": rec.recommended_intervention,
    }


@router.get(
    "/revenue-leakage/candidates",
    summary="[Sprint 1F] List revenue leakage candidates",
)
async def list_leakage_candidates(
    status_filter: Optional[str] = Query(None, alias="status"),
    leakage_type: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    records = await RevenueLeakageService.list_leakage_candidates(
        db,
        organization_id=org_id,
        status=status_filter,
        leakage_type=leakage_type,
        stage=stage,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": r.id,
            "leakage_type": r.leakage_type,
            "stage": r.stage,
            "estimated_leakage_value": float(r.estimated_leakage_value),
            "currency": r.currency,
            "status": r.status,
            "recommended_intervention": r.recommended_intervention,
            "lead_id": r.lead_id,
            "deal_id": r.deal_id,
            "owner_id": r.owner_id,
            "evidence": r.evidence,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            "expiry_at": r.expiry_at.isoformat() if r.expiry_at else None,
        }
        for r in records
    ]


@router.post(
    "/revenue-leakage/candidates/{candidate_id}/engage",
    summary="[Sprint 1F] Engage a revenue leakage candidate",
)
async def engage_leakage_candidate(
    candidate_id: str,
    experiment_id: Optional[str] = None,
    experiment_variant: Optional[str] = None,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        rec = await RevenueLeakageService.engage_leakage_candidate(
            db,
            candidate_id=candidate_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            experiment_id=experiment_id,
            experiment_variant=experiment_variant,
        )
        await db.commit()
        return {"id": rec.id, "status": rec.status, "engaged_at": rec.engaged_at.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/revenue-leakage/candidates/{candidate_id}/resolve",
    summary="[Sprint 1F] Resolve a revenue leakage candidate (recover or dismiss)",
)
async def resolve_leakage_candidate(
    candidate_id: str,
    payload: LeakageCandidateResolveDTO,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        rec = await RevenueLeakageService.resolve_leakage_candidate(
            db,
            candidate_id=candidate_id,
            organization_id=org_id,
            outcome=payload.outcome,
            recovered_value=payload.recovered_value,
            actor_id=str(broker.id),
            notes=payload.notes,
            is_dismissed=payload.is_dismissed,
        )
        await db.commit()
        return {
            "id": rec.id,
            "status": rec.status,
            "outcome": rec.outcome,
            "recovered_value": float(rec.recovered_value) if rec.recovered_value else None,
            "resolved_at": rec.resolved_at.isoformat() if rec.resolved_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/revenue-leakage/summary",
    summary="[Sprint 1F] Revenue leakage and recovery executive summary",
)
async def get_leakage_summary(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await RevenueLeakageService.get_leakage_summary(db, organization_id=org_id)


# ─── Sprint 1F: Data Quality Operations Endpoints (Sections 29 & 30) ───────────


class DQActionDTO(BaseModel):
    notes: Optional[str] = None
    reason: Optional[str] = None
    owner: Optional[str] = None


@router.post(
    "/data-quality/issues/{issue_id}/acknowledge",
    summary="[Sprint 1F] Acknowledge a data quality issue",
)
async def acknowledge_dq_issue(
    issue_id: str,
    payload: DQActionDTO,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        issue = await DataQualityOperationsService.acknowledge_issue(
            db, issue_id=issue_id, organization_id=org_id, actor_id=str(broker.id), owner=payload.owner
        )
        await db.commit()
        return {"id": issue.id, "status": issue.status, "acknowledged_at": issue.acknowledged_at.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/data-quality/issues/{issue_id}/in-review",
    summary="[Sprint 1F] Mark data quality issue in review",
)
async def in_review_dq_issue(
    issue_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        issue = await DataQualityOperationsService.mark_in_review(
            db, issue_id=issue_id, organization_id=org_id, actor_id=str(broker.id)
        )
        await db.commit()
        return {"id": issue.id, "status": issue.status, "in_review_at": issue.in_review_at.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/data-quality/issues/{issue_id}/resolve",
    summary="[Sprint 1F] Mark data quality issue resolved",
)
async def resolve_dq_issue(
    issue_id: str,
    payload: DQActionDTO,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        issue = await DataQualityOperationsService.resolve_issue(
            db, issue_id=issue_id, organization_id=org_id, actor_id=str(broker.id), notes=payload.notes
        )
        await db.commit()
        return {"id": issue.id, "status": issue.status, "resolved_at": issue.resolved_at.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/data-quality/issues/{issue_id}/ignore",
    summary="[Sprint 1F] Suppress/ignore a data quality issue with justification",
)
async def ignore_dq_issue(
    issue_id: str,
    payload: DQActionDTO,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reason is required to ignore an issue")
    try:
        issue = await DataQualityOperationsService.ignore_issue(
            db, issue_id=issue_id, organization_id=org_id, actor_id=str(broker.id), reason=payload.reason
        )
        await db.commit()
        return {"id": issue.id, "status": issue.status, "ignored_reason": issue.ignored_reason}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/data-quality/issues/{issue_id}/reopen",
    summary="[Sprint 1F] Reopen a previously resolved or ignored issue",
)
async def reopen_dq_issue(
    issue_id: str,
    payload: DQActionDTO,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        issue = await DataQualityOperationsService.reopen_issue(
            db, issue_id=issue_id, organization_id=org_id, actor_id=str(broker.id), notes=payload.notes
        )
        await db.commit()
        return {"id": issue.id, "status": issue.status, "reopened_at": issue.reopened_at.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/data-quality/dashboard",
    summary="[Sprint 1F] Operational Data Quality Dashboard",
)
async def get_dq_dashboard(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await DataQualityOperationsService.get_dashboard(db, organization_id=org_id)


# ─── Sprint 1F: Human Override Learning Endpoints (Sections 25 & 26) ───────────


class NBAFeedbackDTO(BaseModel):
    recommendation_id: str
    action: str = Field(..., description="ACCEPTED | DISMISSED | SNOOZED | OVERRIDDEN | EDITED")
    override_category: Optional[str] = Field(
        None,
        description="INCORRECT | NOT_TIMELY | NOT_USEFUL | ALREADY_HANDLED | CUSTOMER_CONTEXT_MISSING | WRONG_PROPERTY | WRONG_CHANNEL | WRONG_PRIORITY | OTHER"
    )
    notes: Optional[str] = None
    recommendation_type: str = "NEXT_BEST_ACTION"
    lead_id: Optional[str] = None


@router.post(
    "/nba/feedback",
    summary="[Sprint 1F] Record human decision or override on AI recommendation",
)
async def record_nba_feedback(
    payload: NBAFeedbackDTO,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    try:
        record = await HumanOverrideLearningService.record_recommendation_feedback(
            db,
            organization_id=org_id,
            recommendation_id=payload.recommendation_id,
            action=payload.action,
            actor_id=str(broker.id),
            override_category=payload.override_category,
            notes=payload.notes,
            recommendation_type=payload.recommendation_type,
            lead_id=payload.lead_id,
        )
        await db.commit()
        return {
            "recommendation_id": record.recommendation_id,
            "human_decision": record.human_decision,
            "human_override": record.human_override,
            "override_category": record.override_category,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/nba/overrides/analysis",
    summary="[Sprint 1F] Analyze why humans override AI recommendations",
)
async def get_override_analysis(
    days: int = Query(30, ge=1, le=365),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _get_org_id(broker)
    return await HumanOverrideLearningService.get_override_analysis(db, organization_id=org_id, days=days)

