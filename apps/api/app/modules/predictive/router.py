"""
Predictive Analytics & MLOps Engine REST API Router
===================================================
REST API endpoints for:
- Real-time Lead Conversion Inference & SHAP Explainability
- Expected Close Date & Sales Cycle Duration
- Multi-Horizon Pipeline Revenue & Commission Forecasting
- Locality Property Demand & Shortage Prediction
- Non-Destructive What-If Simulation Scenarios
- Ground Truth Outcome Recording
- MLOps Model Registry, Approval & Canary Deployments
- Population Stability Index (PSI) Drift Monitoring
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.predictive.service import PredictiveEngineService
from app.modules.predictive.dto.predictive_schemas import (
    LeadPredictionResponse, SalesCyclePredictionResponse,
    RevenueForecastResponse, DemandPredictionResponse,
    ScenarioSimulationRequest, ScenarioSimulationResponse,
    RecordOutcomeRequest, PredictionOutcomeResponse,
    PredictionModelResponse, ModelVersionResponse,
    ApproveModelRequest, DeployModelRequest
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/predictions", tags=["Predictive Analytics & MLOps Engine"])

# ─── Inference Endpoints ───────────────────────────────────────────────────────

@router.get(
    "/leads/{lead_id}",
    response_model=LeadPredictionResponse,
    summary="Get Calibrated Lead Conversion Prediction & SHAP Drivers"
)
async def get_lead_conversion_prediction(
    lead_id: str,
    force_refresh: bool = Query(False),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Returns calibrated conversion probability %, confidence level, and positive/negative feature attributions."""
    service = PredictiveEngineService(db)
    org_id = str(current_broker.organization_id or "org_default")
    try:
        pred = await service.predict_lead_conversion(lead_id, org_id, force_refresh)
        return pred
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"[PREDICTIVE_ROUTER] get_lead_conversion_prediction failed for {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sales-cycle/{lead_id}",
    response_model=SalesCyclePredictionResponse,
    summary="Predict Expected Close Date & Range Bounds"
)
async def get_sales_cycle_prediction(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Predicts expected close date, earliest/latest time window, and expected sales cycle days."""
    service = PredictiveEngineService(db)
    org_id = str(current_broker.organization_id or "org_default")
    try:
        return await service.predict_sales_cycle(lead_id, org_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


# ─── Forecasting Endpoints ─────────────────────────────────────────────────────

@router.get(
    "/revenue",
    response_model=RevenueForecastResponse,
    summary="Get Multi-Horizon Pipeline Revenue Forecast"
)
async def get_revenue_forecast(
    horizon: str = Query("30_DAYS", regex="^(7_DAYS|30_DAYS|60_DAYS|90_DAYS|QUARTER)$"),
    currency: str = Query("AED"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Computes probability-weighted revenue forecast with conservative (P10) and optimistic (P90) bounds."""
    service = PredictiveEngineService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.forecast_revenue(org_id, horizon, currency)


@router.get(
    "/demand",
    response_model=DemandPredictionResponse,
    summary="Get Locality Property Demand & Shortage Risk"
)
async def get_demand_forecast(
    locality: str = Query("Dubai Marina"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Evaluates searcher demand vs active listing supply and detects potential inventory shortage."""
    service = PredictiveEngineService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.forecast_demand(org_id, locality)


# ─── What-If Scenario Simulator ────────────────────────────────────────────────

@router.post(
    "/scenarios",
    response_model=ScenarioSimulationResponse,
    summary="Simulate What-If Revenue Scenario (Non-Destructive)"
)
async def simulate_what_if_scenario(
    req: ScenarioSimulationRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Runs a non-destructive What-If revenue simulation adjusting conversion, response speed, or deal size."""
    service = PredictiveEngineService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.simulate_scenario(
        organization_id=org_id,
        scenario_name=req.scenario_name,
        conversion_rate_delta_pct=req.conversion_rate_delta_pct,
        response_time_reduction_pct=req.response_time_reduction_pct,
        lead_volume_delta_pct=req.lead_volume_delta_pct,
        average_deal_size_delta_pct=req.average_deal_size_delta_pct
    )


# ─── Outcome Recording ─────────────────────────────────────────────────────────

@router.post(
    "/outcomes/{prediction_id}",
    response_model=PredictionOutcomeResponse,
    summary="Record Ground Truth Outcome for Continuous Learning"
)
async def record_outcome(
    prediction_id: str,
    req: RecordOutcomeRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Records the actual conversion / deal loss outcome linked to a historical prediction."""
    service = PredictiveEngineService(db)
    try:
        return await service.record_prediction_outcome(
            prediction_id=prediction_id,
            actual_outcome=req.actual_outcome,
            outcome_revenue_aed=req.outcome_revenue_aed
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


# ─── Model Registry & Governance ───────────────────────────────────────────────

@router.get(
    "/models",
    response_model=List[PredictionModelResponse],
    summary="List Registered ML Models & Deployment Statuses"
)
async def list_models(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists registered predictive models, versions, ROC-AUC scores, and active traffic states."""
    service = PredictiveEngineService(db)
    return await service.list_models()


@router.post(
    "/models/{version_id}/approve",
    response_model=ModelVersionResponse,
    summary="Approve Model Version for Deployment Gate"
)
async def approve_model_version(
    version_id: str,
    req: ApproveModelRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Formally approves an evaluated model version for canary or production rollout."""
    service = PredictiveEngineService(db)
    try:
        return await service.approve_model_version(version_id, req.approved_by, req.approval_notes)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post(
    "/models/{version_id}/deploy",
    response_model=ModelVersionResponse,
    summary="Deploy Model Version (Canary or Full Production)"
)
async def deploy_model_version(
    version_id: str,
    req: DeployModelRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Deploys an approved model to CANARY (partial traffic) or PRODUCTION (100% traffic)."""
    service = PredictiveEngineService(db)
    try:
        return await service.deploy_model_version(version_id, req.deployment_mode, req.traffic_pct)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get(
    "/drift",
    summary="Get Model Population Stability Index (PSI) Drift Report"
)
async def get_drift_report(
    model_version: str = Query("v1.0.0"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Computes PSI drift report between baseline distributions and recent production predictions."""
    service = PredictiveEngineService(db)
    record = await service.monitor_model_drift(model_version)
    return {
        "model_version": record.model_version_tag,
        "psi_score": record.psi_score,
        "drift_detected": record.drift_detected,
        "alert_triggered": record.alert_triggered,
        "evaluated_at": record.evaluated_at.isoformat()
    }
