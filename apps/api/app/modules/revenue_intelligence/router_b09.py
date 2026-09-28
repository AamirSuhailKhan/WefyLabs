"""
Build 09 — Revenue Intelligence Router
=======================================
Canonical analytics API endpoints for the Revenue Intelligence OS.

Endpoints:
  GET  /analytics/revenue               — Revenue ledger summary
  GET  /analytics/overview              — Full revenue overview
  GET  /analytics/funnel                — Canonical funnel analytics
  GET  /analytics/funnel/velocity       — Stage velocity metrics
  GET  /analytics/pipeline              — Pipeline value and weighted pipeline
  POST /analytics/attribution/touchpoint — Record attribution touchpoint
  POST /analytics/attribution/compute    — Compute attribution result
  GET  /analytics/attribution            — Source attribution report
  POST /analytics/forecast               — Generate forecast snapshot
  GET  /analytics/forecast               — List forecast snapshots
  POST /analytics/forecast/{id}/reconcile — Backfill actuals
  GET  /analytics/leakage               — Open leakage events
  POST /analytics/leakage/scan          — Trigger leakage scan
  POST /analytics/leakage/{id}/resolve  — Resolve leakage event
  POST /analytics/anomalies/scan        — Trigger anomaly scan
  GET  /analytics/anomalies             — List anomalies
  POST /analytics/unit-economics        — Compute unit economics
  POST /analytics/reconciliation        — Run reconciliation pass
  GET  /analytics/data-quality          — Data quality report

Security:
  - All endpoints require authenticated broker (JWT)
  - All data is scoped by organization_id from JWT context
  - Financial data requires explicit permission check (revenue_read scope)
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.revenue_intelligence.service_b09 import (
    RevenueIntelligenceServiceV2,
    AttributionModel,
)
from app.modules.revenue_intelligence.dto_b09 import (
    AttributionComputeRequest,
    AttributionResultResponse,
    AnomalyScanResponse,
    ForecastRequest,
    ForecastSnapshotResponse,
    LeakageReportResponse,
    LeakageResolveRequest,
    PipelineSummaryResponse,
    ReconciliationResponse,
    SourceAttributionReportResponse,
    TouchpointCreate,
    TouchpointResponse,
    UnitEconomicsRequest,
    UnitEconomicsResponse,
)

logger = logging.getLogger("wefylabs.revenue_intelligence.router_b09")

router_b09 = APIRouter(
    prefix="/analytics",
    tags=["Revenue Intelligence (Build 09)"],
)


def _parse_date(raw: Optional[str], field_name: str) -> Optional[datetime]:
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
            detail=f"Invalid date format for {field_name}. Use ISO 8601.",
        )


def _get_org_id(broker: Broker) -> uuid.UUID:
    """Extract organization_id from authenticated broker."""
    if hasattr(broker, "organization_id") and broker.organization_id:
        return uuid.UUID(str(broker.organization_id))
    return broker.id


# ──────────────────────────────────────────────────────────────────────────────
# REVENUE LEDGER & OVERVIEW
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.get("/revenue", summary="Canonical Revenue Ledger Summary")
async def get_revenue_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns authoritative revenue metrics from the canonical revenue_events ledger.

    All values are derived from actual RevenueEvent records.
    NULL values indicate the metric cannot be computed (not zero).

    Definition sources: Revenue Semantics Registry (MetricDefinition table).
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.ledger.get_revenue_summary(
        organization_id=org_id,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
        currency=currency,
    )


@router_b09.get("/overview", summary="Revenue Intelligence Overview")
async def get_revenue_overview(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Aggregated revenue overview: ledger + pipeline + leakage.
    All monetary values are Decimal-accurate strings.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.get_revenue_overview(
        organization_id=org_id,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
        currency=currency,
    )


# ──────────────────────────────────────────────────────────────────────────────
# FUNNEL ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.get("/funnel", summary="Canonical Funnel Analytics")
async def get_funnel_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Stage-by-stage funnel from OpportunityStageHistory (Build 08 canonical).
    Returns conversion rates as None when denominator is zero.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.funnel.get_funnel_summary(
        organization_id=org_id,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
    )


@router_b09.get("/funnel/velocity", summary="Funnel Stage Velocity")
async def get_funnel_velocity(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Average time (days) between funnel stage transitions."""
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.funnel.get_funnel_velocity(
        organization_id=org_id,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# PIPELINE ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.get("/pipeline", summary="Pipeline Analytics")
async def get_pipeline_summary(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Pipeline value and weighted pipeline from active opportunities.
    Probability source is documented in the response.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.pipeline.get_pipeline_summary(organization_id=org_id)


# ──────────────────────────────────────────────────────────────────────────────
# ATTRIBUTION
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.post("/attribution/touchpoint", summary="Record Attribution Touchpoint")
async def record_touchpoint(
    payload: TouchpointCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Record an immutable attribution touchpoint for a lead."""
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    tp = await svc.attribution.record_touchpoint(
        organization_id=org_id,
        lead_id=payload.lead_id,
        identity_id=payload.identity_id,
        channel=payload.channel,
        event_type=payload.event_type,
        occurred_at=payload.occurred_at,
        source_name=payload.source_name,
        campaign_id=payload.campaign_id,
        campaign_name=payload.campaign_name,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        actor_id=payload.actor_id,
        payload=payload.payload,
    )
    await db.commit()
    return {"id": str(tp.id), "channel": tp.channel, "occurred_at": tp.occurred_at.isoformat()}


@router_b09.post("/attribution/compute", summary="Compute Attribution Result")
async def compute_attribution(
    payload: AttributionComputeRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Computes and persists attribution result for a lead / revenue event.
    Idempotent: returns existing result if same (event, model, version) already computed.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    amount = Decimal(payload.attributed_amount) if payload.attributed_amount else None
    result = await svc.attribution.compute_attribution(
        organization_id=org_id,
        lead_id=payload.lead_id,
        revenue_event_id=payload.revenue_event_id,
        attributed_amount=amount,
        currency=payload.currency,
        model=payload.model,
        model_version=payload.model_version,
        window_days=payload.window_days,
    )
    await db.commit()
    return {
        "id": str(result.id),
        "attribution_model": result.attribution_model,
        "model_version": result.model_version,
        "touchpoint_count": result.touchpoint_count,
        "first_touch_channel": result.first_touch_channel,
        "last_touch_channel": result.last_touch_channel,
        "breakdown": result.touchpoint_breakdown,
    }


@router_b09.get("/attribution", summary="Source Attribution Report")
async def get_attribution_report(
    model: str = Query(default="FIRST_TOUCH"),
    window_days: int = Query(default=30, ge=1, le=365),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Attribution report aggregated by channel/source.
    Always discloses the attribution model used.
    """
    if model not in AttributionModel.ALL:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid attribution model. Valid: {AttributionModel.ALL}"
        )
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.attribution.get_source_attribution_report(
        organization_id=org_id,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
        model=model,
        window_days=window_days,
    )


# ──────────────────────────────────────────────────────────────────────────────
# FORECASTING
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.post("/forecast", summary="Generate Forecast Snapshot")
async def generate_forecast(
    payload: ForecastRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Generates an immutable forecast snapshot from canonical Deal pipeline.
    All monetary values are Decimal strings. Quality is explicitly stated.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    snapshot = await svc.forecasting.generate_forecast(
        organization_id=org_id,
        period_type=payload.period_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        timezone_name=payload.timezone_name,
        reporting_currency=payload.reporting_currency,
        scenario=payload.scenario,
        method=payload.method,
    )
    await db.commit()
    return {
        "id": str(snapshot.id),
        "period_type": snapshot.period_type,
        "period_start": snapshot.period_start.isoformat(),
        "period_end": snapshot.period_end.isoformat(),
        "scenario": snapshot.scenario,
        "pipeline_value": str(snapshot.pipeline_value) if snapshot.pipeline_value is not None else None,
        "weighted_pipeline": str(snapshot.weighted_pipeline) if snapshot.weighted_pipeline is not None else None,
        "forecast_value": str(snapshot.forecast_value) if snapshot.forecast_value is not None else None,
        "quality": snapshot.quality,
        "quality_notes": snapshot.quality_notes,
        "opportunity_count": snapshot.opportunity_count,
        "method": snapshot.method,
        "method_version": snapshot.method_version,
        "probability_assumptions": snapshot.probability_assumptions,
    }


@router_b09.post("/forecast/{snapshot_id}/reconcile", summary="Backfill Forecast Actuals")
async def reconcile_forecast(
    snapshot_id: uuid.UUID,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Backfills actual revenue for a past forecast period.
    Only updates actual_revenue and forecast_error_pct fields.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    try:
        snap = await svc.forecasting.backfill_actuals(snapshot_id, org_id)
        await db.commit()
        return {
            "id": str(snap.id),
            "is_reconciled": snap.is_reconciled,
            "actual_revenue": str(snap.actual_revenue) if snap.actual_revenue is not None else None,
            "forecast_value": str(snap.forecast_value) if snap.forecast_value is not None else None,
            "forecast_error_pct": str(snap.forecast_error_pct) if snap.forecast_error_pct is not None else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# LEAKAGE
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.get("/leakage", summary="Open Leakage Events")
async def get_leakage_report(
    severity: Optional[str] = Query(None),
    resolved: bool = Query(default=False),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns open (or resolved) leakage events with severity, age, value at risk,
    and recommended actions. estimated_value_at_risk is an ESTIMATE, not confirmed revenue.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.leakage.get_leakage_report(org_id, severity, resolved)


@router_b09.post("/leakage/scan", summary="Trigger Leakage Scan")
async def scan_leakage(
    cooldown_hours: int = Query(default=24, ge=1),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Runs a leakage scan across all Build 08 leakage conditions.
    Suppresses duplicate alerts within cooldown_hours.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    new_events = await svc.leakage.scan_leakage(org_id, cooldown_hours)
    await db.commit()
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "new_leakage_events": len(new_events),
        "conditions_detected": [e.condition for e in new_events],
    }


@router_b09.post("/leakage/{leakage_id}/resolve", summary="Resolve Leakage Event")
async def resolve_leakage(
    leakage_id: uuid.UUID,
    payload: LeakageResolveRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Marks a leakage event as resolved. Only resolution fields are written."""
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    try:
        ev = await svc.leakage.resolve_leakage(
            leakage_id, org_id, payload.resolution_action, payload.resolution_outcome
        )
        await db.commit()
        return {
            "id": str(ev.id),
            "is_resolved": ev.is_resolved,
            "resolution_at": ev.resolution_at.isoformat() if ev.resolution_at else None,
            "resolution_outcome": ev.resolution_outcome,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# ANOMALIES
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.post("/anomalies/scan", summary="Trigger Anomaly Scan")
async def scan_anomalies(
    lookback_days: int = Query(default=30, ge=7),
    threshold_pct: float = Query(default=0.30, ge=0.05, le=1.0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Runs deterministic statistical anomaly scan comparing current vs prior period.
    threshold_pct: fractional deviation (e.g. 0.30 = 30%) to trigger an anomaly.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    anomalies = await svc.anomaly.run_anomaly_scan(
        org_id, lookback_days, Decimal(str(threshold_pct))
    )
    await db.commit()
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "new_anomaly_count": len(anomalies),
        "anomalies": [
            {
                "id": str(a.id),
                "metric": a.metric,
                "severity": a.severity,
                "description": a.description,
                "baseline": str(a.baseline_value) if a.baseline_value else None,
                "observed": str(a.observed_value) if a.observed_value else None,
            }
            for a in anomalies
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# UNIT ECONOMICS
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.post("/unit-economics", summary="Compute Unit Economics")
async def compute_unit_economics(
    payload: UnitEconomicsRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Computes unit economics for a period.
    Supply acquisition_cost, ai_cost, communication_cost for full computation.
    Any absent cost field results in dependent metrics returning null (INSUFFICIENT_DATA).
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    acq_cost = Decimal(payload.acquisition_cost) if payload.acquisition_cost else None
    ai_cost  = Decimal(payload.ai_cost) if payload.ai_cost else None
    comm_cost = Decimal(payload.communication_cost) if payload.communication_cost else None

    rec = await svc.unit_economics.compute_unit_economics(
        organization_id=org_id,
        period_type=payload.period_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        reporting_currency=payload.reporting_currency,
        acquisition_cost=acq_cost,
        ai_cost=ai_cost,
        communication_cost=comm_cost,
    )
    await db.commit()
    return {
        "id": str(rec.id),
        "period": {
            "type": rec.period_type,
            "start": rec.period_start.isoformat(),
            "end": rec.period_end.isoformat(),
        },
        "currency": rec.reporting_currency,
        "revenue": {
            "gross_booking_value": str(rec.gross_booking_value) if rec.gross_booking_value else None,
            "collected_revenue": str(rec.collected_revenue) if rec.collected_revenue else None,
            "net_revenue": str(rec.net_revenue) if rec.net_revenue else None,
            "refunded_amount": str(rec.refunded_amount) if rec.refunded_amount else None,
        },
        "volumes": {
            "total_leads": rec.total_leads,
            "qualified_leads": rec.qualified_leads,
            "total_bookings": rec.total_bookings,
        },
        "economics": {
            "cac": str(rec.cac) if rec.cac else None,
            "cost_per_qualified_lead": str(rec.cost_per_qualified_lead) if rec.cost_per_qualified_lead else None,
            "cost_per_booking": str(rec.cost_per_booking) if rec.cost_per_booking else None,
            "revenue_per_lead": str(rec.revenue_per_lead) if rec.revenue_per_lead else None,
            "revenue_per_booking": str(rec.revenue_per_booking) if rec.revenue_per_booking else None,
            "contribution_margin": str(rec.contribution_margin) if rec.contribution_margin else None,
        },
        "data_quality_notes": rec.data_quality_notes,
    }


# ──────────────────────────────────────────────────────────────────────────────
# RECONCILIATION
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.post("/reconciliation", summary="Run Revenue Reconciliation")
async def run_reconciliation(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Runs revenue reconciliation comparing booking/payment/revenue event records.
    Discrepancies are persisted and can be connected to WorkItems.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    result = await svc.reconciliation.run_reconciliation(
        organization_id=org_id,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
    )
    await db.commit()
    return result


# ──────────────────────────────────────────────────────────────────────────────
# AI REVENUE ANALYST TOOLS
# ──────────────────────────────────────────────────────────────────────────────

@router_b09.get("/ai/revenue-summary", summary="AI Tool: Revenue Summary")
async def ai_revenue_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Structured tool endpoint for the AI Revenue Analyst.
    AI calls this endpoint to get grounded revenue data.
    AI does NOT calculate revenue independently from raw text.
    """
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.ai_get_revenue_summary(
        org_id,
        _parse_date(date_from, "date_from"),
        _parse_date(date_to, "date_to"),
    )


@router_b09.get("/ai/funnel", summary="AI Tool: Funnel Analytics")
async def ai_funnel(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Structured tool endpoint for the AI Revenue Analyst — canonical funnel data."""
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.ai_get_funnel(
        org_id,
        _parse_date(date_from, "date_from"),
        _parse_date(date_to, "date_to"),
    )


@router_b09.get("/ai/leakage", summary="AI Tool: Leakage Summary")
async def ai_leakage(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Structured tool endpoint for the AI Revenue Analyst — leakage data."""
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.ai_get_leakage(org_id)


@router_b09.get("/ai/pipeline", summary="AI Tool: Pipeline Analytics")
async def ai_pipeline(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Structured tool endpoint for the AI Revenue Analyst — pipeline data."""
    org_id = _get_org_id(broker)
    svc = RevenueIntelligenceServiceV2(db)
    return await svc.ai_get_pipeline(org_id)
