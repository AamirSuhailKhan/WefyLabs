"""
Predictive Analytics & MLOps Engine Orchestrator Service
========================================================
Coordinates all predictive subsystems:
- Lead & Opportunity Conversion Inference
- Close Date & Sales Cycle Forecasting
- Multi-Horizon Pipeline Revenue & Commission Forecasting
- Locality & Project Property Demand Intelligence
- Non-Destructive What-If Scenario Simulations
- Population Stability Index (PSI) Drift Monitoring
- Ground Truth Outcome Reconciliation
- Model Registry & Approval Governance
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.predictive_models import (
    PredictionInferenceRecord, SalesCyclePredictionSnapshot,
    ForecastSnapshotRecord, DemandPredictionSnapshot,
    ForecastScenarioRecord, PredictionOutcomeRecord,
    PredictionModelEntity, PredictionModelVersionEntity,
    PredictionDriftRecord
)
from app.modules.predictive.conversion.conversion_service import ConversionPredictionService
from app.modules.predictive.close_date.close_date_service import CloseDatePredictionService
from app.modules.predictive.revenue.revenue_forecast_service import RevenueForecastService
from app.modules.predictive.demand.demand_forecast_service import DemandForecastService
from app.modules.predictive.scenarios.scenario_simulator import ScenarioSimulator
from app.modules.predictive.drift.drift_monitor import DriftMonitorService
from app.modules.predictive.outcomes.outcome_tracker import OutcomeTrackerService
from app.modules.predictive.model_registry.model_registry_service import ModelRegistryService

logger = logging.getLogger(__name__)

class PredictiveEngineService:
    """
    Unified entry point for all Predictive Intelligence and MLOps capabilities.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversion_service = ConversionPredictionService(db)
        self.close_date_service = CloseDatePredictionService(db)
        self.revenue_service = RevenueForecastService(db)
        self.demand_service = DemandForecastService(db)
        self.simulator = ScenarioSimulator(db)
        self.drift_service = DriftMonitorService(db)
        self.outcome_tracker = OutcomeTrackerService(db)
        self.registry = ModelRegistryService(db)

    # ─── Conversion & Close Date ───────────────────────────────────────────────

    async def predict_lead_conversion(
        self,
        lead_id: str,
        organization_id: str,
        force_refresh: bool = False
    ) -> PredictionInferenceRecord:
        return await self.conversion_service.predict_lead_conversion(lead_id, organization_id, force_refresh)

    async def predict_sales_cycle(
        self,
        lead_id: str,
        organization_id: str
    ) -> SalesCyclePredictionSnapshot:
        return await self.close_date_service.predict_close_date(lead_id, organization_id)

    # ─── Revenue & Demand Forecasting ──────────────────────────────────────────

    async def forecast_revenue(
        self,
        organization_id: str,
        horizon: str = "30_DAYS",
        reporting_currency: str = "AED"
    ) -> ForecastSnapshotRecord:
        return await self.revenue_service.calculate_revenue_forecast(organization_id, horizon, reporting_currency)

    async def forecast_demand(
        self,
        organization_id: str,
        locality_name: str = "Dubai Marina"
    ) -> DemandPredictionSnapshot:
        return await self.demand_service.calculate_demand_forecast(organization_id, locality_name)

    # ─── What-If Scenarios ─────────────────────────────────────────────────────

    async def simulate_scenario(
        self,
        organization_id: str,
        scenario_name: str,
        conversion_rate_delta_pct: float = 0.0,
        response_time_reduction_pct: float = 0.0,
        lead_volume_delta_pct: float = 0.0,
        average_deal_size_delta_pct: float = 0.0
    ) -> ForecastScenarioRecord:
        return await self.simulator.simulate_scenario(
            organization_id=organization_id,
            scenario_name=scenario_name,
            conversion_rate_delta_pct=conversion_rate_delta_pct,
            response_time_reduction_pct=response_time_reduction_pct,
            lead_volume_delta_pct=lead_volume_delta_pct,
            average_deal_size_delta_pct=average_deal_size_delta_pct
        )

    # ─── Drift & Outcome Reconciliation ────────────────────────────────────────

    async def monitor_model_drift(
        self,
        model_version_tag: str = "v1.0.0"
    ) -> PredictionDriftRecord:
        return await self.drift_service.evaluate_prediction_drift(model_version_tag)

    async def record_prediction_outcome(
        self,
        prediction_id: str,
        actual_outcome: str,
        outcome_revenue_aed: Optional[float] = None
    ) -> PredictionOutcomeRecord:
        return await self.outcome_tracker.record_prediction_outcome(prediction_id, actual_outcome, outcome_revenue_aed)

    # ─── Model Registry Governance ─────────────────────────────────────────────

    async def list_models(self) -> List[PredictionModelEntity]:
        return await self.registry.list_models()

    async def approve_model_version(
        self,
        version_id: str,
        approved_by: str,
        notes: Optional[str] = None
    ) -> PredictionModelVersionEntity:
        return await self.registry.approve_model_version(version_id, approved_by, notes)

    async def deploy_model_version(
        self,
        version_id: str,
        mode: str = "PRODUCTION",
        traffic_pct: float = 100.0
    ) -> PredictionModelVersionEntity:
        return await self.registry.deploy_model_version(version_id, mode, traffic_pct)
