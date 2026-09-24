"""
Part 11 — Revenue Intelligence Router
=======================================
7 FastAPI endpoints providing the Revenue Intelligence Layer.

All endpoints:
  - Require authenticated broker (JWT)
  - Are scoped to the authenticated broker's organization_id
  - Return safe empty state when no data exists (never 500 on zero rows)
  - Label all estimate fields clearly in response bodies
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.revenue_intelligence.service import RevenueIntelligenceService
from app.modules.revenue_intelligence.dto import (
    FunnelSummaryDTO,
    LeakageReportDTO,
    OutcomeSummaryDTO,
    AttributionReportDTO,
    LearningLoopSummaryDTO,
    SnapshotCaptureRequestDTO,
    FunnelSnapshotDTO,
    SnapshotListDTO,
    RevenueOverviewDTO,
    ExtendedLeakageItemDTO,
    DataQualityReportDTO,
    LeadRevenueJourneyDTO,
    PropertyRevenueJourneyDTO,
    TeamIntelligenceDTO,
    PropensityScoreDTO,
)

logger = logging.getLogger("wefylabs.revenue_intelligence.router")

router = APIRouter(
    prefix="/api/v1/revenue-intelligence",
    tags=["Revenue Intelligence"],
)


def _parse_date(raw: Optional[str], field_name: str) -> Optional[datetime]:
    """Parse ISO date string to datetime. Raises 422 on bad format."""
    if raw is None:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date format for '{field_name}'. Use ISO 8601 (e.g. 2026-01-01 or 2026-01-01T00:00:00Z).",
        )


def _snap_to_dto(snap) -> dict:
    return {
        "id": str(snap.id),
        "organization_id": str(snap.organization_id),
        "period_type": snap.period_type,
        "snapshot_date": snap.snapshot_date.isoformat(),
        "total_leads": snap.total_leads,
        "leads_new": snap.leads_new,
        "leads_contacted": snap.leads_contacted,
        "leads_qualified": snap.leads_qualified,
        "leads_site_visit": snap.leads_site_visit,
        "leads_negotiation": snap.leads_negotiation,
        "leads_converted": snap.leads_converted,
        "leads_lost": snap.leads_lost,
        "active_opportunities": snap.active_opportunities,
        "estimated_pipeline_value_estimate": snap.estimated_pipeline_value,
        "confirmed_revenue": snap.confirmed_revenue,
        "metrics": snap.metrics or {},
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
        "updated_at": snap.updated_at.isoformat() if snap.updated_at else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 1. Funnel Summary
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/funnel",
    response_model=FunnelSummaryDTO,
    summary="Revenue Funnel Summary",
    description=(
        "Stage-by-stage lead counts and conversion rates for the authenticated organisation. "
        "All conversion rates are computed from real data — if a stage has zero leads, "
        "the rate to the next stage is returned as null."
    ),
)
async def get_funnel_summary(
    date_from: Optional[str] = Query(None, description="ISO 8601 start date filter"),
    date_to: Optional[str] = Query(None, description="ISO 8601 end date filter"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    svc = RevenueIntelligenceService(db)
    try:
        result = await svc.funnel.get_funnel_summary(
            organization_id=current_broker.id,
            date_from=df,
            date_to=dt,
        )
        return result
    except Exception as exc:
        logger.error(f"[RI:funnel] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Revenue funnel computation failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 2. Leakage Report
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/leakage",
    response_model=LeakageReportDTO,
    summary="Revenue Leakage Report",
    description=(
        "Identifies leads that left the funnel without converting (explicitly lost or stale). "
        "Writes immutable RevenueLeakageEvent rows for new detections. "
        "'estimated_value_at_risk' is derived from lead.budget_max — it is an estimate, "
        "not a confirmed transaction value."
    ),
)
async def get_leakage_report(
    staleness_days: int = Query(14, ge=1, le=365, description="Days without update before a lead is considered stale"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    svc = RevenueIntelligenceService(db)
    try:
        result = await svc.leakage.get_leakage_report(
            organization_id=current_broker.id,
            staleness_days=staleness_days,
            date_from=df,
            date_to=dt,
        )
        await db.commit()
        return result
    except Exception as exc:
        logger.error(f"[RI:leakage] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Leakage detection failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 3. Outcome Summary
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/outcomes",
    response_model=OutcomeSummaryDTO,
    summary="Revenue Outcome Summary",
    description=(
        "Win rate, outcome distribution, and deal counts from revenue_feedback_logs "
        "and deal_transactions. All rates are null when no feedback data exists."
    ),
)
async def get_outcome_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    svc = RevenueIntelligenceService(db)
    try:
        result = await svc.outcomes.get_outcome_summary(
            organization_id=current_broker.id,
            date_from=df,
            date_to=dt,
        )
        return result
    except Exception as exc:
        logger.error(f"[RI:outcomes] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Outcome summary computation failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 4. Source Attribution Report
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/attribution",
    response_model=AttributionReportDTO,
    summary="Lead Source Attribution Report",
    description=(
        "Leads and estimated revenue grouped by acquisition source/channel. "
        "Reads lead.source (already normalized in canonical Lead model). "
        "Does not create a new attribution engine — pure aggregation."
    ),
)
async def get_attribution_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    svc = RevenueIntelligenceService(db)
    try:
        result = await svc.attribution.get_attribution_report(
            organization_id=current_broker.id,
            date_from=df,
            date_to=dt,
        )
        return result
    except Exception as exc:
        logger.error(f"[RI:attribution] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Attribution report computation failed.")


@router.get(
    "/sources",
    response_model=AttributionReportDTO,
    summary="Lead Sources Performance (Alias)",
    description="Alias to /attribution report, fulfilling Part 11 endpoint spec.",
)
async def get_sources_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    return await get_attribution_report(date_from, date_to, db, current_broker)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Learning Loop Summary
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/learning-loop",
    response_model=LearningLoopSummaryDTO,
    summary="Revenue Learning Loop Summary",
    description=(
        "Heuristic summary of top-performing opportunity types and channels. "
        "computation_method='heuristic_aggregation_v1' — deterministic rule-based "
        "aggregation. No machine-learning model is used."
    ),
)
async def get_learning_loop_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    svc = RevenueIntelligenceService(db)
    try:
        result = await svc.learning.get_learning_summary(
            organization_id=current_broker.id,
            date_from=df,
            date_to=dt,
        )
        return result
    except Exception as exc:
        logger.error(f"[RI:learning] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Learning loop summary failed.")


@router.get(
    "/actions",
    response_model=LearningLoopSummaryDTO,
    summary="Action Effectiveness (Alias)",
    description="Alias to /learning-loop summary, fulfilling Part 11 endpoint spec.",
)
async def get_actions_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    return await get_learning_loop_summary(date_from, date_to, db, current_broker)


@router.get(
    "/opportunities",
    summary="Revenue Opportunities Intelligence",
    description="Surfaces summary of active and evaluated revenue opportunities.",
)
async def get_opportunities_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    svc = RevenueIntelligenceService(db)
    try:
        learning = await svc.learning.get_learning_summary(current_broker.id, df, dt)
        return {
            "organization_id": str(current_broker.id),
            "total_opportunities": learning.get("total_opportunities_evaluated", 0),
            "top_opportunity_types": learning.get("top_opportunity_types", []),
            "computation_method": "deterministic_heuristic_v1",
        }
    except Exception as exc:
        logger.error(f"[RI:opportunities] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Revenue opportunities retrieval failed.")


@router.post(
    "/recompute",
    summary="Recompute Derived Revenue Intelligence",
    description="Triggers deterministic recomputation of funnel metrics, snapshots, and leakage events.",
)
async def recompute_intelligence(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    svc = RevenueIntelligenceService(db)
    try:
        await svc.snapshots.capture(current_broker.id, period_type="DAILY")
        await svc.leakage.get_leakage_report(current_broker.id)
        await db.commit()
        return {
            "status": "success",
            "organization_id": str(current_broker.id),
            "recomputed_at": datetime.now(timezone.utc).isoformat(),
            "message": "Revenue intelligence derived state recomputed successfully."
        }
    except Exception as exc:
        logger.error(f"[RI:recompute] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Recomputation failed.")



# ──────────────────────────────────────────────────────────────────────────────
# 6. Capture Snapshot (POST)
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/snapshots/capture",
    response_model=FunnelSnapshotDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Capture Funnel Snapshot",
    description=(
        "Captures the current funnel state as a RevenueFunnelSnapshot. "
        "Idempotent: if a snapshot for today already exists, it is refreshed. "
        "Returns 201 for both create and update."
    ),
)
async def capture_snapshot(
    body: SnapshotCaptureRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    valid_period_types = {"DAILY", "WEEKLY", "MONTHLY"}
    if body.period_type not in valid_period_types:
        raise HTTPException(
            status_code=422,
            detail=f"period_type must be one of {valid_period_types}",
        )
    svc = RevenueIntelligenceService(db)
    try:
        snap = await svc.snapshots.capture(
            organization_id=current_broker.id,
            period_type=body.period_type,
        )
        await db.commit()
        await db.refresh(snap)
        return _snap_to_dto(snap)
    except Exception as exc:
        logger.error(f"[RI:snapshot:capture] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Snapshot capture failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 7. List Snapshots (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/snapshots",
    response_model=SnapshotListDTO,
    summary="List Funnel Snapshots",
    description="Returns historical funnel snapshots for trend analysis. Ordered newest first.",
)
async def list_snapshots(
    period_type: Optional[str] = Query(None, description="Filter by DAILY | WEEKLY | MONTHLY"),
    limit: int = Query(30, ge=1, le=90, description="Max snapshots to return"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    svc = RevenueIntelligenceService(db)
    try:
        snaps, total = await svc.snapshots.list_snapshots(
            organization_id=current_broker.id,
            period_type=period_type,
            limit=limit,
        )
        return {
            "organization_id": str(current_broker.id),
            "total": total,
            "snapshots": [_snap_to_dto(s) for s in snaps],
        }
    except Exception as exc:
        logger.error(f"[RI:snapshot:list] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Snapshot listing failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 8. Revenue Overview (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/overview",
    response_model=RevenueOverviewDTO,
    summary="Revenue Overview & Forecast Baseline",
    description="Returns high-level realized revenue, pipeline estimates, revenue at risk, attribution breakdown, and forecast disclaimer.",
)
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    svc = RevenueIntelligenceService(db)
    try:
        return await svc.overview.get_overview(current_broker.id)
    except Exception as exc:
        logger.error(f"[RI:overview] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Revenue overview failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 9. Extended 15-Category Leakage Items (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/leakage/items",
    response_model=list[ExtendedLeakageItemDTO],
    summary="15-Category Operational Leakage Items",
    description="Surfaces specific leakage items classified across the 15 canonical operational failure modes.",
)
async def get_leakage_items(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    svc = RevenueIntelligenceService(db)
    try:
        return await svc.leakage.get_extended_leakage_items(current_broker.id, limit=limit)
    except Exception as exc:
        logger.error(f"[RI:leakage:items] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Extended leakage retrieval failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 10. Data Quality Audit Panel (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/data-quality",
    response_model=DataQualityReportDTO,
    summary="Data Quality & Completeness Audit",
    description="Audits data completeness across leads, deals, meetings, and opportunities to score data health.",
)
async def get_data_quality(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    svc = RevenueIntelligenceService(db)
    try:
        return await svc.data_quality.get_data_quality_report(current_broker.id)
    except Exception as exc:
        logger.error(f"[RI:data-quality] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Data quality audit failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 11. Lead Revenue Journey (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/journey/lead/{lead_id}",
    response_model=LeadRevenueJourneyDTO,
    summary="Lead Revenue Journey",
    description="Reconstructs chronological touchpoints, actions, AI recommendations, and deal outcomes for an individual lead.",
)
async def get_lead_journey(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid lead UUID format.")

    svc = RevenueIntelligenceService(db)
    try:
        journey = await svc.journeys.get_lead_journey(current_broker.id, lid)
        if not journey:
            raise HTTPException(status_code=404, detail="Lead not found.")
        return journey
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[RI:journey:lead] org={current_broker.id} lead={lead_id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Lead journey reconstruction failed.")


@router.get(
    "/journey/{lead_id}",
    response_model=LeadRevenueJourneyDTO,
    summary="Lead Revenue Journey (Direct Alias)",
)
async def get_lead_journey_alias(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    return await get_lead_journey(lead_id, db, current_broker)



# ──────────────────────────────────────────────────────────────────────────────
# 12. Property Revenue Journey (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/journey/property/{property_id}",
    response_model=PropertyRevenueJourneyDTO,
    summary="Property Revenue Journey",
    description="Reconstructs engagement, matches, visits, deals, and conversion rates for a specific property listing.",
)
async def get_property_journey(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    try:
        pid = uuid.UUID(property_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid property UUID format.")

    svc = RevenueIntelligenceService(db)
    try:
        journey = await svc.journeys.get_property_journey(current_broker.id, pid)
        if not journey:
            raise HTTPException(status_code=404, detail="Property listing not found.")
        return journey
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[RI:journey:property] org={current_broker.id} prop={property_id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Property journey reconstruction failed.")


@router.get(
    "/property/{property_id}",
    response_model=PropertyRevenueJourneyDTO,
    summary="Property Revenue Journey (Direct Alias)",
)
async def get_property_journey_alias(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    return await get_property_journey(property_id, db, current_broker)



# ──────────────────────────────────────────────────────────────────────────────
# 13. Team Operational Intelligence (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/team",
    response_model=TeamIntelligenceDTO,
    summary="Team Operational Intelligence",
    description="Surfaces objective operational metrics per sales representative without subjective rankings.",
)
async def get_team_metrics(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    svc = RevenueIntelligenceService(db)
    try:
        return await svc.team.get_team_metrics(current_broker.id)
    except Exception as exc:
        logger.error(f"[RI:team] org={current_broker.id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Team intelligence retrieval failed.")


# ──────────────────────────────────────────────────────────────────────────────
# 14. Lead Propensity Heuristic (GET)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/propensity/{lead_id}",
    response_model=PropensityScoreDTO,
    summary="Deterministic Lead Propensity Heuristic",
    description="Computes a transparent conversion propensity score based on the explicit 'heuristic_v1' formula with full provenance.",
)
async def get_lead_propensity(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid lead UUID format.")

    svc = RevenueIntelligenceService(db)
    try:
        prop = await svc.propensity.calculate_lead_propensity(current_broker.id, lid)
        if not prop:
            raise HTTPException(status_code=404, detail="Lead not found.")
        return prop
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[RI:propensity] org={current_broker.id} lead={lead_id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Propensity calculation failed.")
