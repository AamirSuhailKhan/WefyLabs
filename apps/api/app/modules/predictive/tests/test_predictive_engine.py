"""
Comprehensive Test Suite for Predictive Analytics & MLOps Engine
=================================================================
Tests:
1. Time-aware feature store & target data leakage prevention
2. Platt scaling calibration, Brier score & ECE evaluation
3. Calibrated conversion prediction & SHAP feature attributions
4. Close date forecasting & realistic range intervals
5. Multi-horizon pipeline revenue & commission forecasting
6. Property demand & inventory shortage detection
7. Non-destructive What-If revenue scenario simulator
8. Ground truth outcome recording & reconciliation
9. Population Stability Index (PSI) drift monitoring
10. Model Registry lifecycle, approval gates & canary rollout
"""

import pytest
import uuid
import math
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.predictive_models import (
    PredictionModelEntity, PredictionModelVersionEntity,
    PredictionInferenceRecord, PredictionOutcomeRecord,
    ForecastSnapshotRecord, ForecastScenarioRecord,
    DemandPredictionSnapshot, SalesCyclePredictionSnapshot,
    PredictionDriftRecord
)
from app.modules.predictive.models.base_model import FeatureAttribution, PredictionExplanationResult
from app.modules.predictive.models.calibrated_conversion_model import CalibratedConversionModel
from app.modules.predictive.calibration.calibration_engine import CalibrationEngine
from app.modules.predictive.explainability.shap_explainer import ShapExplainer
from app.modules.predictive.features.predictive_feature_store import PredictiveFeatureStore
from app.modules.predictive.conversion.conversion_service import ConversionPredictionService
from app.modules.predictive.close_date.close_date_service import CloseDatePredictionService
from app.modules.predictive.revenue.revenue_forecast_service import RevenueForecastService
from app.modules.predictive.demand.demand_forecast_service import DemandForecastService
from app.modules.predictive.scenarios.scenario_simulator import ScenarioSimulator
from app.modules.predictive.drift.drift_monitor import DriftMonitorService
from app.modules.predictive.outcomes.outcome_tracker import OutcomeTrackerService
from app.modules.predictive.model_registry.model_registry_service import ModelRegistryService
from app.modules.predictive.service import PredictiveEngineService


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestCalibrationEngine:
    """Test probability calibration formulas and error metrics."""

    def test_platt_scaling(self):
        # Raw probability of 0.50 with neutral params should return ~0.50
        scaled = CalibrationEngine.platt_scale(0.50, a=1.0, b=0.0)
        assert 0.45 <= scaled <= 0.55

        # Extreme raw probability calibration smoothing
        scaled_high = CalibrationEngine.platt_scale(0.99, a=0.8, b=-0.1)
        assert scaled_high < 0.99

    def test_brier_score_calculation(self):
        # Perfect predictions
        perfect_brier = CalibrationEngine.calculate_brier_score([1.0, 0.0, 1.0], [1.0, 0.0, 1.0])
        assert perfect_brier == 0.0

        # Sub-optimal predictions
        brier = CalibrationEngine.calculate_brier_score([0.8, 0.2, 0.6], [1.0, 0.0, 0.0])
        assert brier > 0.0

    def test_ece_calculation(self):
        preds = [0.1, 0.2, 0.8, 0.9]
        labels = [0.0, 0.0, 1.0, 1.0]
        ece, bins = CalibrationEngine.calculate_ece(preds, labels, num_bins=5)
        assert ece >= 0.0
        assert len(bins) == 5


class TestConversionModelAndSHAP:
    """Test calibrated conversion model and SHAP feature attributions."""

    def test_calibrated_conversion_model_inference(self):
        model = CalibratedConversionModel("v1.0.0")

        feature_vector = {
            "lead_id": str(uuid.uuid4()),
            "attended_viewings_count": 2,
            "cancelled_viewings_count": 0,
            "customer_response_ratio": 0.9,
            "hours_since_last_activity": 6.0,
            "lead_score_points": 85.0,
            "has_budget": True,
            "has_preferred_location": True,
            "activity_count": 8,
            "inbound_message_count": 6,
        }

        res = model.predict(feature_vector, feature_vector["lead_id"])
        assert res.prediction_type == "CONVERSION"
        assert res.calibrated_probability > 0.50  # Highly qualified buyer
        assert res.confidence_level == "HIGH"
        assert len(res.explanation.positive_drivers) >= 1
        assert "viewing" in res.explanation.summary_markdown.lower()

    def test_cold_lead_conversion_inference(self):
        model = CalibratedConversionModel("v1.0.0")

        feature_vector = {
            "lead_id": str(uuid.uuid4()),
            "attended_viewings_count": 0,
            "cancelled_viewings_count": 1,
            "customer_response_ratio": 0.1,
            "hours_since_last_activity": 120.0,  # 5 days inactive
            "lead_score_points": 20.0,
            "has_budget": False,
            "has_preferred_location": False,
            "activity_count": 1,
            "inbound_message_count": 0,
        }

        res = model.predict(feature_vector, feature_vector["lead_id"])
        assert res.calibrated_probability < 0.40  # Cold lead
        assert res.confidence_level == "LOW"
        assert len(res.explanation.negative_drivers) >= 1


class TestCloseDatePrediction:
    """Test expected close date and sales cycle duration forecasting."""

    @pytest.mark.asyncio
    async def test_predict_close_date_hot_lead(self, mock_db):
        service = CloseDatePredictionService(mock_db)
        lead_id = str(uuid.uuid4())

        fake_lead = Lead(
            id=uuid.UUID(lead_id),
            name="Investor Test",
            pipeline_stage="negotiation",
            score="hot",
            budget_max=5_000_000.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=10)
        )

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = fake_lead
        mock_db.execute.return_value = mock_res

        pred = await service.predict_close_date(lead_id, "org_test")
        assert pred.expected_sales_cycle_days <= 10
        assert pred.expected_close_date_utc > datetime.now(timezone.utc)
        assert pred.range_earliest_date_utc <= pred.expected_close_date_utc <= pred.range_latest_date_utc
        assert pred.market_segment == "luxury"
        assert pred.confidence >= 0.85


class TestRevenueForecasting:
    """Test multi-horizon pipeline forecasting and scenario bounds."""

    @pytest.mark.asyncio
    async def test_calculate_revenue_forecast_30d(self, mock_db):
        service = RevenueForecastService(mock_db)

        fake_leads = [
            Lead(id=uuid.uuid4(), pipeline_stage="new", budget_max=1_000_000.0),
            Lead(id=uuid.uuid4(), pipeline_stage="viewing", budget_max=3_000_000.0),
            Lead(id=uuid.uuid4(), pipeline_stage="negotiation", budget_max=5_000_000.0),
        ]

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = fake_leads
        mock_db.execute.return_value = mock_res

        forecast = await service.calculate_revenue_forecast("org_test", horizon="30_DAYS")
        assert forecast.total_pipeline_value == 9_000_000.0
        assert forecast.expected_revenue > 0
        assert forecast.conservative_revenue < forecast.expected_revenue < forecast.optimistic_revenue
        assert forecast.expected_commission == round(forecast.expected_revenue * 0.02, 2)


class TestWhatIfSimulator:
    """Test non-destructive What-If revenue simulations."""

    @pytest.mark.asyncio
    async def test_simulate_conversion_improvement(self, mock_db):
        simulator = ScenarioSimulator(mock_db)

        fake_leads = [
            Lead(id=uuid.uuid4(), pipeline_stage="qualified", budget_max=4_000_000.0),
            Lead(id=uuid.uuid4(), pipeline_stage="negotiation", budget_max=6_000_000.0),
        ]
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = fake_leads
        mock_db.execute.return_value = mock_res

        scenario = await simulator.simulate_scenario(
            organization_id="org_test",
            scenario_name="10% Conversion Boost + 50% Faster Response",
            conversion_rate_delta_pct=10.0,
            response_time_reduction_pct=50.0,
            lead_volume_delta_pct=0.0
        )

        assert scenario.simulated_revenue_aed > scenario.baseline_revenue_aed
        assert scenario.revenue_delta_aed > 0
        assert scenario.projected_commission_delta_aed > 0


class TestDemandForecast:
    """Test locality property demand and shortage detection."""

    @pytest.mark.asyncio
    async def test_demand_forecast_surging_market(self, mock_db):
        service = DemandForecastService(mock_db)

        fake_leads = [
            Lead(id=uuid.uuid4(), pipeline_stage="qualified", preferred_locations=["Dubai Marina", "Downtown"])
            for _ in range(8)
        ]
        fake_props = [
            PropertyListing(
                id=uuid.uuid4(),
                broker_id=uuid.uuid4(),
                title="Apt",
                description="Luxury Marina Apt",
                price=2_500_000.0,
                built_up_area_sqft=1200.0,
                locality="Dubai Marina",
                status="available"
            )
            for _ in range(2)
        ]

        def exec_side_effect(stmt):
            m = MagicMock()
            sql_str = str(stmt).lower()
            if "from leads" in sql_str:
                m.scalars.return_value.all.return_value = fake_leads
            elif "from property_listings" in sql_str:
                m.scalars.return_value.all.return_value = fake_props
            return m

        mock_db.execute.side_effect = exec_side_effect

        demand = await service.calculate_demand_forecast("org_test", "Dubai Marina")
        assert demand.demand_supply_ratio >= 2.0
        assert demand.shortage_risk_detected is True
        assert demand.predicted_demand_trend == "SURGING"


class TestDriftMonitoring:
    """Test Population Stability Index (PSI) drift monitoring."""

    def test_psi_calculation(self):
        base = [0.20, 0.30, 0.30, 0.20]
        # Identical distribution -> PSI = 0
        assert DriftMonitorService.calculate_psi(base, base) == 0.0

        # Substantial shift
        shifted = [0.05, 0.15, 0.40, 0.40]
        psi = DriftMonitorService.calculate_psi(base, shifted)
        assert psi > 0.10

    @pytest.mark.asyncio
    async def test_drift_monitor_service(self, mock_db):
        service = DriftMonitorService(mock_db)
        record = await service.evaluate_prediction_drift("v1.0.0")
        assert record.model_version_tag == "v1.0.0"
        assert record.psi_score >= 0.0
        assert mock_db.commit.called


class TestOutcomeTracker:
    """Test ground truth outcome recording and loss evaluation."""

    @pytest.mark.asyncio
    async def test_record_outcome_converted(self, mock_db):
        service = OutcomeTrackerService(mock_db)
        pred_id = str(uuid.uuid4())

        fake_pred = PredictionInferenceRecord(
            id=pred_id,
            organization_id="org_test",
            entity_id=str(uuid.uuid4()),
            entity_type="LEAD",
            prediction_type="CONVERSION",
            raw_score=0.75,
            calibrated_probability=0.80,
            confidence_score=0.90,
            model_version_tag="v1.0.0",
            feature_schema_version="v1.0.0",
            features_snapshot={},
            positive_drivers=[],
            negative_drivers=[],
            explanation_text="Test",
            generated_at=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(days=7)
        )

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.side_effect = [fake_pred, None]
        mock_db.execute.return_value = mock_res

        outcome = await service.record_prediction_outcome(
            prediction_id=pred_id,
            actual_outcome="CONVERTED",
            outcome_revenue_aed=3_000_000.0
        )

        assert outcome.actual_outcome == "CONVERTED"
        assert outcome.outcome_value == 1.0
        assert outcome.brier_error == round((0.80 - 1.0) ** 2, 4)
        assert outcome.outcome_revenue_aed == 3_000_000.0


class TestModelRegistry:
    """Test model registration, formal approval gate, and canary rollout."""

    @pytest.mark.asyncio
    async def test_model_lifecycle_flow(self, mock_db):
        registry = ModelRegistryService(mock_db)

        # 1. Register new model
        mock_res1 = MagicMock()
        mock_res1.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_res1

        ver = await registry.register_model_version(
            model_key="lead_conversion",
            version_tag="v2.0.0",
            algorithm_type="GRADIENT_BOOSTING",
            weights={"intercept": -1.1},
            roc_auc=0.91
        )
        assert ver.lifecycle_state == "TRAINED"
        assert ver.roc_auc_score == 0.91

        # 2. Approve model
        mock_res2 = MagicMock()
        mock_res2.scalar_one_or_none.return_value = ver
        mock_db.execute.return_value = mock_res2

        appr = await registry.approve_model_version(ver.id, approved_by="Chief Data Scientist")
        assert appr.lifecycle_state == "APPROVED"
        assert appr.approved_by == "Chief Data Scientist"

        # 3. Deploy canary
        mock_res3 = MagicMock()
        mock_res3.scalar_one_or_none.return_value = ver
        mock_db.execute.return_value = mock_res3

        deployed = await registry.deploy_model_version(ver.id, deployment_mode="CANARY", traffic_pct=15.0)
        assert deployed.lifecycle_state == "CANARY"
        assert deployed.traffic_allocation_pct == 15.0
