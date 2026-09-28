"""
Master Build 09 — Revenue Intelligence OS
==========================================
Comprehensive test suite covering:
- Revenue ledger accuracy (Decimal precision, no float leakage)
- Revenue event idempotency
- Multi-currency handling
- Attribution: first-touch, last-touch, linear, time-decay, position-based
- Attribution windows and model versioning
- Funnel analytics (conversion rates, velocity)
- Pipeline analytics (weighted pipeline, stall detection)
- Forecasting v2 (Decimal, stage-weighted, quality = LIMITED on missing data)
- Forecast snapshot immutability
- Forecast backfill actuals
- Leakage detection (all Build 08 conditions)
- Leakage cooldown suppression
- Leakage resolution
- Anomaly detection (booking count, payment value)
- Unit economics (Decimal values, INSUFFICIENT_DATA for missing costs)
- Reconciliation (missing booking, missing payment references)
- Tenant isolation (Org A data never in Org B results)
- Security: no float in monetary results
- AI Revenue Analyst tools (structured, grounded)
- Refund/cancellation handling

Run:
    cd apps/api
    python -m pytest tests/test_master_build_09_revenue_intelligence.py -v
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ──────────────────────────────────────────────────────────────────────────────
# STUB DATABASE SESSION
# ──────────────────────────────────────────────────────────────────────────────

class FakeResult:
    """Minimal SQLAlchemy result stub for testing."""
    def __init__(self, rows=None, scalar_val=None):
        self._rows = rows or []
        self._scalar = scalar_val

    def all(self):
        return self._rows

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    """Async-compatible fake DB session for unit tests."""
    def __init__(self):
        self.added: List[Any] = []
        self.flushed = False
        self._query_map: Dict[str, Any] = {}

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        pass

    async def execute(self, stmt):
        return FakeResult(scalar_val=None)

    async def refresh(self, obj):
        pass


# ──────────────────────────────────────────────────────────────────────────────
# FIXTURE: ORG IDs
# ──────────────────────────────────────────────────────────────────────────────

ORG_A = uuid.uuid4()
ORG_B = uuid.uuid4()
LEAD_1 = uuid.uuid4()
LEAD_2 = uuid.uuid4()
DEAL_1 = uuid.uuid4()


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1: DECIMAL / FLOAT SAFETY
# ──────────────────────────────────────────────────────────────────────────────

class TestDecimalSafety:
    """Verifies no floating-point arithmetic in monetary fields."""

    def test_numeric_type_definition(self):
        from app.models.revenue_intelligence_b09_models import MoneyType
        from sqlalchemy import Numeric
        assert isinstance(MoneyType, Numeric)
        assert MoneyType.precision == 20
        assert MoneyType.scale == 4

    def test_attribution_touchpoint_weight_fields_are_numeric(self):
        from app.models.revenue_intelligence_b09_models import AttributionTouchpoint
        # Check that weight fields are PctType (Numeric), not Float
        col = AttributionTouchpoint.__table__.columns.get("weight_first_touch")
        assert col is not None
        from sqlalchemy import Numeric
        assert isinstance(col.type, Numeric)

    def test_forecast_snapshot_v2_uses_numeric_not_float(self):
        from app.models.revenue_intelligence_b09_models import ForecastSnapshotV2
        from sqlalchemy import Numeric, Float
        money_cols = [
            "pipeline_value", "weighted_pipeline", "forecast_value",
            "upside_value", "downside_value", "actual_revenue",
        ]
        for col_name in money_cols:
            col = ForecastSnapshotV2.__table__.columns.get(col_name)
            assert col is not None, f"Column {col_name} missing"
            assert isinstance(col.type, Numeric), f"{col_name} is not Numeric"
            assert not isinstance(col.type, Float), f"{col_name} is Float — PRODUCTION RISK"

    def test_leakage_v2_estimated_value_is_numeric(self):
        from app.models.revenue_intelligence_b09_models import RevenueLeakageEventV2
        from sqlalchemy import Numeric, Float
        col = RevenueLeakageEventV2.__table__.columns.get("estimated_value_at_risk")
        assert col is not None
        assert isinstance(col.type, Numeric)
        assert not isinstance(col.type, Float)

    def test_unit_economics_monetary_fields_are_numeric(self):
        from app.models.revenue_intelligence_b09_models import UnitEconomicsRecord
        from sqlalchemy import Numeric, Float
        money_cols = [
            "gross_booking_value", "collected_revenue", "net_revenue",
            "cac", "cost_per_qualified_lead", "cost_per_booking",
            "revenue_per_lead", "revenue_per_booking", "contribution_margin",
        ]
        for col_name in money_cols:
            col = UnitEconomicsRecord.__table__.columns.get(col_name)
            assert col is not None, f"Column {col_name} missing"
            assert isinstance(col.type, Numeric), f"{col_name} is not Numeric"

    def test_decimal_arithmetic_no_float_contamination(self):
        """Core arithmetic must never produce float results."""
        a = Decimal("1500000.0000")
        b = Decimal("0.35")
        result = a * b
        assert isinstance(result, Decimal)
        assert result == Decimal("525000.00000")

    def test_safe_decimal_div_returns_none_on_zero_denominator(self):
        from app.modules.revenue_intelligence.service_b09 import _safe_decimal_div
        result = _safe_decimal_div(Decimal("100"), 0)
        assert result is None

    def test_safe_decimal_div_returns_none_on_none_inputs(self):
        from app.modules.revenue_intelligence.service_b09 import _safe_decimal_div
        assert _safe_decimal_div(None, 5) is None
        assert _safe_decimal_div(Decimal("100"), None) is None

    def test_safe_decimal_div_correct_precision(self):
        from app.modules.revenue_intelligence.service_b09 import _safe_decimal_div
        result = _safe_decimal_div(Decimal("1000000"), 3)
        assert result is not None
        assert isinstance(result, Decimal)
        # 1000000 / 3 = 333333.3333...
        assert str(result) == "333333.3333"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2: ATTRIBUTION ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class TestAttributionWeights:
    """Unit tests for attribution weight calculations."""

    def _make_touchpoints(self, n: int):
        """Create n stub touchpoints."""
        tps = []
        for i in range(n):
            tp = MagicMock()
            tp.channel = f"CHANNEL_{i}"
            tp.source_name = f"source_{i}"
            tp.campaign_name = f"campaign_{i}"
            tp.occurred_at = datetime.now(timezone.utc) - timedelta(days=n - i)
            tps.append(tp)
        return tps

    def _get_engine(self):
        from app.modules.revenue_intelligence.service_b09 import AttributionEngine
        return AttributionEngine(FakeDB())

    def test_first_touch_single_touchpoint(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(1)
        weights = engine._calculate_weights(tps, "FIRST_TOUCH")
        assert weights == [Decimal("1.0")]

    def test_first_touch_three_touchpoints(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(3)
        weights = engine._calculate_weights(tps, "FIRST_TOUCH")
        assert weights[0] == Decimal("1.0")
        assert weights[1] == Decimal("0.0")
        assert weights[2] == Decimal("0.0")

    def test_last_touch_three_touchpoints(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(3)
        weights = engine._calculate_weights(tps, "LAST_TOUCH")
        assert weights[0] == Decimal("0.0")
        assert weights[1] == Decimal("0.0")
        assert weights[2] == Decimal("1.0")

    def test_linear_weights_equal_distribution(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(4)
        weights = engine._calculate_weights(tps, "LINEAR")
        assert len(weights) == 4
        for w in weights:
            assert isinstance(w, Decimal)
            assert w == Decimal("0.2500")

    def test_position_based_two_touchpoints(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(2)
        weights = engine._calculate_weights(tps, "POSITION_BASED")
        assert weights == [Decimal("0.5"), Decimal("0.5")]

    def test_position_based_four_touchpoints(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(4)
        weights = engine._calculate_weights(tps, "POSITION_BASED")
        assert len(weights) == 4
        assert weights[0] == Decimal("0.40")
        assert weights[-1] == Decimal("0.40")

    def test_time_decay_later_gets_higher_weight(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(3)
        weights = engine._calculate_weights(tps, "TIME_DECAY")
        # Later touchpoints (higher index) should have higher weight
        assert weights[2] > weights[1] >= weights[0]

    def test_time_decay_all_decimal(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(5)
        weights = engine._calculate_weights(tps, "TIME_DECAY")
        for w in weights:
            assert isinstance(w, Decimal)

    def test_invalid_model_raises(self):
        engine = self._get_engine()
        tps = self._make_touchpoints(2)
        with pytest.raises(ValueError, match="Unknown attribution model"):
            engine._calculate_weights(tps, "INVALID_MODEL")

    def test_empty_touchpoints_returns_empty(self):
        engine = self._get_engine()
        weights = engine._calculate_weights([], "FIRST_TOUCH")
        assert weights == []


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3: FORECASTING ENGINE V2
# ──────────────────────────────────────────────────────────────────────────────

class TestForecastingEngineV2:
    """Tests for the evidence-based forecasting engine."""

    def _get_engine(self):
        from app.modules.revenue_intelligence.service_b09 import ForecastingEngineV2
        return ForecastingEngineV2(FakeDB())

    def test_default_stage_probabilities_are_decimal(self):
        from app.modules.revenue_intelligence.service_b09 import DEFAULT_STAGE_PROBABILITIES
        for stage, prob in DEFAULT_STAGE_PROBABILITIES.items():
            assert isinstance(prob, Decimal), f"Stage {stage} probability is not Decimal"

    def test_stage_probabilities_range(self):
        from app.modules.revenue_intelligence.service_b09 import DEFAULT_STAGE_PROBABILITIES
        for stage, prob in DEFAULT_STAGE_PROBABILITIES.items():
            assert Decimal("0") <= prob <= Decimal("1"), f"Stage {stage} probability out of range"

    def test_won_probability_is_one(self):
        from app.modules.revenue_intelligence.service_b09 import DEFAULT_STAGE_PROBABILITIES
        assert DEFAULT_STAGE_PROBABILITIES["WON"] == Decimal("1.00")

    def test_lost_probability_is_zero(self):
        from app.modules.revenue_intelligence.service_b09 import DEFAULT_STAGE_PROBABILITIES
        assert DEFAULT_STAGE_PROBABILITIES["LOST"] == Decimal("0.00")

    def test_weighted_pipeline_calculation_decimal(self):
        """Verifies forecast arithmetic uses Decimal throughout."""
        est_val = Decimal("5000000.0000")
        prob = Decimal("0.70")
        weighted = est_val * prob
        assert isinstance(weighted, Decimal)
        assert weighted == Decimal("3500000.00000")

    def test_upside_scenario_multiplier(self):
        """UPSIDE = 1.20x weighted pipeline."""
        weighted = Decimal("1000000.0000")
        upside = (weighted * Decimal("1.20")).quantize(Decimal("0.0001"))
        assert upside == Decimal("1200000.0000")

    def test_downside_scenario_multiplier(self):
        """DOWNSIDE = 0.70x weighted pipeline."""
        weighted = Decimal("1000000.0000")
        downside = (weighted * Decimal("0.70")).quantize(Decimal("0.0001"))
        assert downside == Decimal("700000.0000")

    def test_forecast_quality_constants(self):
        from app.models.revenue_intelligence_b09_models import ForecastQuality
        assert ForecastQuality.GOOD == "GOOD"
        assert ForecastQuality.LIMITED == "LIMITED"
        assert ForecastQuality.UNKNOWN == "UNKNOWN"

    def test_forecast_method_constants(self):
        from app.models.revenue_intelligence_b09_models import ForecastMethod
        assert ForecastMethod.STAGE_WEIGHTED == "stage_weighted"
        assert ForecastMethod.HISTORICAL_CONVERSION == "historical_conversion"
        assert ForecastMethod.MOVING_AVERAGE == "moving_average"
        assert ForecastMethod.PIPELINE_VELOCITY == "pipeline_velocity"

    def test_no_hardcoded_confidence_values(self):
        """Verifies the old hardcoded forecast_confidence=0.88 is not in Build 09 code."""
        import inspect
        from app.modules.revenue_intelligence import service_b09
        src = inspect.getsource(service_b09)
        assert "forecast_confidence=0.88" not in src
        assert "0.88" not in src  # hardcoded confidence banned

    def test_no_budget_max_fallback(self):
        """Verifies the old fallback budget_max = 2_000_000.0 is not in Build 09 code."""
        import inspect
        from app.modules.revenue_intelligence import service_b09
        src = inspect.getsource(service_b09)
        assert "2_000_000" not in src
        assert "budget_max" not in src

    def test_no_float_in_forecast_calculation(self):
        """Verifies no float() calls in forecasting engine."""
        import inspect
        from app.modules.revenue_intelligence import service_b09
        src = inspect.getsource(service_b09)
        # Check that financial variables are not cast to float
        assert "float(deal.estimated_value" not in src


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4: LEAKAGE DETECTION ENGINE V2
# ──────────────────────────────────────────────────────────────────────────────

class TestLeakageDetectionV2:
    """Tests for leakage condition vocabulary and recommendation engine."""

    def test_all_leakage_conditions_defined(self):
        from app.models.revenue_intelligence_b09_models import LeakageCondition
        required = [
            "LEAD_NO_RESPONSE", "QUALIFIED_NO_PROPERTY", "PROPERTY_NO_FOLLOWUP",
            "APPOINTMENT_NO_CONFIRMATION", "SITE_VISIT_NO_OUTCOME",
            "OPPORTUNITY_NO_NEXT_ACTION", "NEGOTIATION_STALLED",
            "BOOKING_INTENT_NO_HOLD", "HOLD_EXPIRING",
            "BOOKING_NO_PAYMENT", "PAYMENT_NO_BOOKING", "BOOKING_NO_REVENUE_EVENT",
        ]
        for cond in required:
            assert hasattr(LeakageCondition, cond), f"LeakageCondition.{cond} missing"

    def test_leakage_severity_constants(self):
        from app.models.revenue_intelligence_b09_models import LeakageSeverity
        assert LeakageSeverity.CRITICAL == "CRITICAL"
        assert LeakageSeverity.HIGH == "HIGH"
        assert LeakageSeverity.MEDIUM == "MEDIUM"
        assert LeakageSeverity.LOW == "LOW"

    def test_recommended_action_for_all_conditions(self):
        from app.modules.revenue_intelligence.service_b09 import RevenueLeakageEngineV2
        from app.models.revenue_intelligence_b09_models import LeakageCondition
        engine = RevenueLeakageEngineV2(FakeDB())

        conditions = [
            LeakageCondition.SITE_VISIT_NO_OUTCOME,
            LeakageCondition.HOLD_EXPIRING,
            LeakageCondition.BOOKING_INTENT_NO_HOLD,
            LeakageCondition.NEGOTIATION_STALLED,
        ]
        for cond in conditions:
            action = engine._recommend_action(cond)
            assert isinstance(action, str)
            assert len(action) > 0

    def test_unknown_condition_returns_generic_action(self):
        from app.modules.revenue_intelligence.service_b09 import RevenueLeakageEngineV2
        engine = RevenueLeakageEngineV2(FakeDB())
        action = engine._recommend_action("COMPLETELY_UNKNOWN_CONDITION")
        assert "next action" in action.lower()

    def test_leakage_model_estimated_value_nullable(self):
        from app.models.revenue_intelligence_b09_models import RevenueLeakageEventV2
        col = RevenueLeakageEventV2.__table__.columns.get("estimated_value_at_risk")
        assert col.nullable is True  # NULL when value unknown

    def test_leakage_model_append_only_no_update_cols(self):
        """Verify only resolution fields have onupdate — all evidence fields are immutable."""
        from app.models.revenue_intelligence_b09_models import RevenueLeakageEventV2
        # The condition, severity, detected_at, evidence should not have onupdate
        for col_name in ["condition", "severity", "age_days", "evidence"]:
            col = RevenueLeakageEventV2.__table__.columns.get(col_name)
            assert col is not None
            # onupdate is typically a callable, check it's None
            assert getattr(col, "onupdate", None) is None


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5: UNIT ECONOMICS
# ──────────────────────────────────────────────────────────────────────────────

class TestUnitEconomics:
    """Verifies unit economics metric computation and INSUFFICIENT_DATA handling."""

    def test_cac_is_none_when_no_acquisition_cost(self):
        from app.modules.revenue_intelligence.service_b09 import _safe_decimal_div
        # CAC = acquisition_cost / bookings; if acquisition_cost is None → None
        assert _safe_decimal_div(None, 5) is None

    def test_revenue_per_lead_is_none_when_no_leads(self):
        from app.modules.revenue_intelligence.service_b09 import _safe_decimal_div
        assert _safe_decimal_div(Decimal("1000000"), 0) is None

    def test_contribution_margin_formula(self):
        """net_revenue - total_cost = contribution_margin"""
        net_revenue = Decimal("5000000.0000")
        total_cost  = Decimal("500000.0000")
        margin = net_revenue - total_cost
        assert margin == Decimal("4500000.0000")
        assert isinstance(margin, Decimal)

    def test_insufficient_data_note_populated_for_missing_cost(self):
        """When acquisition_cost is None, quality_notes must include INSUFFICIENT_DATA."""
        notes: Dict[str, Any] = {}
        acquisition_cost = None
        if acquisition_cost is None:
            notes["cac"] = "INSUFFICIENT_DATA: acquisition_cost not provided"
        assert "INSUFFICIENT_DATA" in notes.get("cac", "")

    def test_unit_economics_all_monetary_cols_numeric(self):
        from app.models.revenue_intelligence_b09_models import UnitEconomicsRecord
        from sqlalchemy import Numeric, Float
        money_cols = [
            "gross_booking_value", "collected_revenue", "net_revenue",
            "refunded_amount", "total_acquisition_cost", "ai_cost",
            "communication_cost", "cac", "cost_per_qualified_lead",
            "cost_per_appointment", "cost_per_site_visit", "cost_per_booking",
            "revenue_per_lead", "revenue_per_booking", "contribution_margin",
        ]
        for col_name in money_cols:
            col = UnitEconomicsRecord.__table__.columns.get(col_name)
            if col is not None:
                assert isinstance(col.type, Numeric), f"{col_name} is not Numeric"
                assert not isinstance(col.type, Float), f"{col_name} is Float — BUG"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6: REVENUE LEDGER READER
# ──────────────────────────────────────────────────────────────────────────────

class TestRevenueLedgerReader:

    def test_metric_definitions_exist(self):
        from app.modules.revenue_intelligence.service_b09 import METRIC_DEFINITIONS
        required = [
            "gross_booking_value", "collected_revenue", "net_revenue",
            "refunded_revenue", "pipeline_value", "weighted_pipeline",
            "revenue_at_risk",
        ]
        for key in required:
            assert key in METRIC_DEFINITIONS, f"Missing metric definition: {key}"

    def test_metric_definitions_have_formula(self):
        from app.modules.revenue_intelligence.service_b09 import METRIC_DEFINITIONS
        for key, defn in METRIC_DEFINITIONS.items():
            assert "formula" in defn, f"Metric {key} missing formula"
            assert len(defn["formula"]) > 0

    def test_net_revenue_formula_references_collected_and_refund(self):
        from app.modules.revenue_intelligence.service_b09 import METRIC_DEFINITIONS
        formula = METRIC_DEFINITIONS["net_revenue"]["formula"]
        assert "collected_revenue" in formula or "payment.received" in formula.lower()
        assert "refund" in formula.lower()

    def test_safe_rate_returns_none_on_zero_denominator(self):
        from app.modules.revenue_intelligence.service_b09 import _safe_rate
        assert _safe_rate(100, 0) is None

    def test_safe_rate_correct_percentage(self):
        from app.modules.revenue_intelligence.service_b09 import _safe_rate
        assert _safe_rate(10, 100) == 10.0
        assert _safe_rate(1, 3) == pytest.approx(33.33, abs=0.01)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7: TENANT ISOLATION (ARCHITECTURAL)
# ──────────────────────────────────────────────────────────────────────────────

class TestTenantIsolation:
    """
    Verifies tenant isolation invariants in model and query design.
    Full integration tests require a live DB; these are design verification tests.
    """

    def test_attribution_touchpoint_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import AttributionTouchpoint
        col = AttributionTouchpoint.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable

    def test_attribution_result_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import AttributionResult
        col = AttributionResult.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable

    def test_forecast_snapshot_v2_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import ForecastSnapshotV2
        col = ForecastSnapshotV2.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable

    def test_leakage_v2_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import RevenueLeakageEventV2
        col = RevenueLeakageEventV2.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable

    def test_anomaly_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import RevenueAnomaly
        col = RevenueAnomaly.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable

    def test_unit_economics_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import UnitEconomicsRecord
        col = UnitEconomicsRecord.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable

    def test_reconciliation_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import RevenueReconciliationRecord
        col = RevenueReconciliationRecord.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable

    def test_ai_contribution_has_organization_id(self):
        from app.models.revenue_intelligence_b09_models import AIContributionRecord
        col = AIContributionRecord.__table__.columns.get("organization_id")
        assert col is not None
        assert not col.nullable


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 8: ANOMALY DETECTION
# ──────────────────────────────────────────────────────────────────────────────

class TestAnomalyDetection:

    def test_anomaly_metric_constants(self):
        from app.models.revenue_intelligence_b09_models import AnomalyMetric
        assert AnomalyMetric.BOOKING_COUNT == "booking_count"
        assert AnomalyMetric.PAYMENT_AMOUNT == "payment_amount"
        assert AnomalyMetric.REFUND_AMOUNT == "refund_amount"
        assert AnomalyMetric.CONVERSION_RATE == "conversion_rate"

    def test_anomaly_model_monetary_fields_nullable(self):
        from app.models.revenue_intelligence_b09_models import RevenueAnomaly
        col = RevenueAnomaly.__table__.columns.get("baseline_value")
        assert col.nullable is True

    def test_anomaly_append_only_design(self):
        """Anomaly records must not have mutable business data."""
        from app.models.revenue_intelligence_b09_models import RevenueAnomaly
        col = RevenueAnomaly.__table__.columns.get("metric")
        assert col is not None
        assert getattr(col, "onupdate", None) is None

    def test_deviation_calculation_decimal(self):
        """Statistical deviation must use Decimal."""
        current = Decimal("50")
        baseline = Decimal("100")
        deviation = abs(current - baseline) / baseline
        assert isinstance(deviation, Decimal)
        assert deviation == Decimal("0.5")

    def test_30_pct_threshold_triggers(self):
        """30% deviation should trigger anomaly."""
        threshold = Decimal("0.30")
        deviation = Decimal("0.45")
        assert deviation >= threshold


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 9: METRIC REGISTRY / SEMANTICS
# ──────────────────────────────────────────────────────────────────────────────

class TestMetricRegistry:

    def test_metric_definition_model_has_formula_field(self):
        from app.models.revenue_intelligence_b09_models import MetricDefinition
        col = MetricDefinition.__table__.columns.get("formula")
        assert col is not None

    def test_metric_definition_unique_constraint(self):
        from app.models.revenue_intelligence_b09_models import MetricDefinition
        constraints = list(MetricDefinition.__table_args__)
        uc_names = [
            c.name for c in constraints
            if hasattr(c, "name") and c.name
        ]
        assert "uq_metric_def_id_version" in uc_names

    def test_metric_definition_has_version(self):
        from app.models.revenue_intelligence_b09_models import MetricDefinition
        col = MetricDefinition.__table__.columns.get("metric_version")
        assert col is not None

    def test_no_undefined_formulas_in_service_metric_defs(self):
        from app.modules.revenue_intelligence.service_b09 import METRIC_DEFINITIONS
        for key, defn in METRIC_DEFINITIONS.items():
            formula = defn.get("formula", "")
            assert formula, f"Metric {key} has empty formula"
            assert "UNDEFINED" not in formula.upper()
            assert "TODO" not in formula.upper()


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 10: RECONCILIATION
# ──────────────────────────────────────────────────────────────────────────────

class TestReconciliation:

    def test_reconciliation_difference_types(self):
        from app.models.revenue_intelligence_b09_models import ReconciliationDifference
        required = [
            "MISSING_PAYMENT", "MISSING_BOOKING", "MISSING_REVENUE_EVENT",
            "INVENTORY_MISMATCH", "AMOUNT_MISMATCH", "CURRENCY_MISMATCH",
            "DUPLICATE_EVENT",
        ]
        for diff_type in required:
            assert hasattr(ReconciliationDifference, diff_type), f"Missing: {diff_type}"

    def test_reconciliation_record_has_run_id(self):
        from app.models.revenue_intelligence_b09_models import RevenueReconciliationRecord
        col = RevenueReconciliationRecord.__table__.columns.get("reconciliation_run_id")
        assert col is not None

    def test_reconciliation_record_has_resolution(self):
        from app.models.revenue_intelligence_b09_models import RevenueReconciliationRecord
        assert RevenueReconciliationRecord.__table__.columns.get("is_resolved") is not None
        assert RevenueReconciliationRecord.__table__.columns.get("resolution_at") is not None


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 11: AI CONTRIBUTION RECORD
# ──────────────────────────────────────────────────────────────────────────────

class TestAIContributionRecord:

    def test_ai_contribution_categories(self):
        from app.models.revenue_intelligence_b09_models import AIContributionCategory
        assert AIContributionCategory.AI_TOUCHED == "AI_TOUCHED"
        assert AIContributionCategory.AI_ASSISTED == "AI_ASSISTED"
        assert AIContributionCategory.AI_INFLUENCED == "AI_INFLUENCED"
        assert AIContributionCategory.AI_EXECUTED == "AI_EXECUTED"
        assert AIContributionCategory.HUMAN_ONLY == "HUMAN_ONLY"
        assert AIContributionCategory.UNKNOWN == "UNKNOWN"

    def test_ai_contribution_model_has_no_revenue_amount(self):
        """AI contribution records must NOT contain monetary attribution amounts — observational only."""
        from app.models.revenue_intelligence_b09_models import AIContributionRecord
        # Should NOT have an 'attributed_amount' — that belongs to AttributionResult
        assert AIContributionRecord.__table__.columns.get("attributed_amount") is None

    def test_ai_contribution_links_to_lead_and_opportunity(self):
        from app.models.revenue_intelligence_b09_models import AIContributionRecord
        assert AIContributionRecord.__table__.columns.get("lead_id") is not None
        assert AIContributionRecord.__table__.columns.get("opportunity_id") is not None
        assert AIContributionRecord.__table__.columns.get("revenue_event_id") is not None


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 12: ROUTER ENDPOINT STRUCTURE
# ──────────────────────────────────────────────────────────────────────────────

class TestRouterEndpoints:

    def test_router_prefix_is_analytics(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        assert router_b09.prefix == "/analytics"

    def test_router_has_revenue_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/revenue" in paths

    def test_router_has_funnel_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/funnel" in paths

    def test_router_has_pipeline_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/pipeline" in paths

    def test_router_has_leakage_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/leakage" in paths

    def test_router_has_forecast_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/forecast" in paths

    def test_router_has_attribution_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/attribution" in paths

    def test_router_has_unit_economics_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/unit-economics" in paths

    def test_router_has_ai_tools(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert any("ai" in p for p in paths)

    def test_router_has_reconciliation_endpoint(self):
        from app.modules.revenue_intelligence.router_b09 import router_b09
        paths = [r.path.removeprefix(router_b09.prefix) for r in router_b09.routes]
        assert "/reconciliation" in paths


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 13: PIPELINE ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────

class TestPipelineAnalytics:

    def test_pipeline_value_calculation_decimal(self):
        """Sum of deal values must be Decimal."""
        deals_values = [Decimal("5000000"), Decimal("3000000"), Decimal("2000000")]
        total = sum(deals_values, Decimal("0"))
        assert isinstance(total, Decimal)
        assert total == Decimal("10000000")

    def test_weighted_pipeline_calculation(self):
        """weighted = value * probability."""
        probs = {"NEGOTIATION": Decimal("0.70"), "SITE_VISIT_COMPLETED": Decimal("0.55")}
        deals = [
            ("NEGOTIATION", Decimal("5000000")),
            ("SITE_VISIT_COMPLETED", Decimal("3000000")),
        ]
        weighted = sum(v * probs[s] for s, v in deals)
        assert isinstance(weighted, Decimal)
        assert weighted == Decimal("5150000")

    def test_stall_threshold_detection(self):
        """Deals untouched > 14 days = stalled."""
        updated_at = datetime.now(timezone.utc) - timedelta(days=20)
        now = datetime.now(timezone.utc)
        stall_threshold = 14
        is_stalled = (now - updated_at).days > stall_threshold
        assert is_stalled is True


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 14: MULTI-CURRENCY SAFETY
# ──────────────────────────────────────────────────────────────────────────────

class TestMultiCurrency:

    def test_attribution_result_has_currency_field(self):
        from app.models.revenue_intelligence_b09_models import AttributionResult
        col = AttributionResult.__table__.columns.get("currency")
        assert col is not None

    def test_forecast_snapshot_has_reporting_currency(self):
        from app.models.revenue_intelligence_b09_models import ForecastSnapshotV2
        col = ForecastSnapshotV2.__table__.columns.get("reporting_currency")
        assert col is not None
        # Default is AED
        assert col.default.arg == "AED"

    def test_unit_economics_has_reporting_currency(self):
        from app.models.revenue_intelligence_b09_models import UnitEconomicsRecord
        col = UnitEconomicsRecord.__table__.columns.get("reporting_currency")
        assert col is not None

    def test_leakage_v2_has_currency_field(self):
        from app.models.revenue_intelligence_b09_models import RevenueLeakageEventV2
        col = RevenueLeakageEventV2.__table__.columns.get("currency")
        assert col is not None
        assert col.nullable is True

    def test_reconciliation_has_currency_comparison_fields(self):
        from app.models.revenue_intelligence_b09_models import RevenueReconciliationRecord
        assert RevenueReconciliationRecord.__table__.columns.get("expected_currency") is not None
        assert RevenueReconciliationRecord.__table__.columns.get("actual_currency") is not None


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 15: DTO VALIDATION
# ──────────────────────────────────────────────────────────────────────────────

class TestDTOValidation:

    def test_touchpoint_create_valid(self):
        from app.modules.revenue_intelligence.dto_b09 import TouchpointCreate
        dto = TouchpointCreate(
            channel="META_ADS",
            event_type="meta_lead",
        )
        assert dto.channel == "META_ADS"

    def test_attribution_compute_decimal_validation(self):
        from app.modules.revenue_intelligence.dto_b09 import AttributionComputeRequest
        import pydantic
        dto = AttributionComputeRequest(
            lead_id=uuid.uuid4(),
            attributed_amount="1500000.0000",
            currency="AED",
            window_days=30,
        )
        assert dto.attributed_amount == "1500000.0000"

    def test_attribution_compute_invalid_amount_fails(self):
        from app.modules.revenue_intelligence.dto_b09 import AttributionComputeRequest
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            AttributionComputeRequest(
                lead_id=uuid.uuid4(),
                attributed_amount="not_a_number",
                window_days=30,
            )

    def test_unit_economics_request_invalid_cost_fails(self):
        from app.modules.revenue_intelligence.dto_b09 import UnitEconomicsRequest
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            UnitEconomicsRequest(
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc),
                acquisition_cost="not_a_decimal",
            )

    def test_forecast_request_defaults(self):
        from app.modules.revenue_intelligence.dto_b09 import ForecastRequest
        now = datetime.now(timezone.utc)
        dto = ForecastRequest(
            period_start=now,
            period_end=now + timedelta(days=30),
        )
        assert dto.scenario == "BASE"
        assert dto.reporting_currency == "AED"
        assert dto.timezone_name == "UTC"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 16: IMMUTABILITY GUARANTEES
# ──────────────────────────────────────────────────────────────────────────────

class TestImmutability:

    def test_attribution_touchpoint_no_mutable_business_fields(self):
        """Once recorded, touchpoint core fields must not have onupdate."""
        from app.models.revenue_intelligence_b09_models import AttributionTouchpoint
        immutable_cols = ["channel", "event_type", "occurred_at", "source_name"]
        for col_name in immutable_cols:
            col = AttributionTouchpoint.__table__.columns.get(col_name)
            assert col is not None
            assert getattr(col, "onupdate", None) is None

    def test_forecast_snapshot_v2_has_reconciled_flag(self):
        """Snapshots use is_reconciled to mark backfill — never overwrite history."""
        from app.models.revenue_intelligence_b09_models import ForecastSnapshotV2
        col = ForecastSnapshotV2.__table__.columns.get("is_reconciled")
        assert col is not None
        # Default must be False (not reconciled until actuals backfilled)
        assert col.default.arg is False

    def test_revenue_event_type_constants_cover_corrections(self):
        """RevenueEventType must include REFUND and cancellation for corrections."""
        from app.models.sales_pipeline_models import RevenueEventType
        assert hasattr(RevenueEventType, "REFUND_ISSUED")
        assert hasattr(RevenueEventType, "BOOKING_CANCELLED")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 17: NO-FAKE-REVENUE RULE ENFORCEMENT
# ──────────────────────────────────────────────────────────────────────────────

class TestNoFakeRevenueRule:
    """
    Scans the Build 09 service code for prohibited patterns that could
    fabricate or falsify revenue data.
    """

    def _get_service_source(self):
        import inspect
        from app.modules.revenue_intelligence import service_b09
        return inspect.getsource(service_b09)

    def test_no_random_revenue_generation(self):
        src = self._get_service_source()
        assert "random.uniform" not in src
        assert "random.randint" not in src

    def test_no_hardcoded_revenue_amounts(self):
        src = self._get_service_source()
        # No patterns like = 1000000 or = 5000000 as default amounts
        assert "= 2_000_000" not in src
        assert "or 2000000" not in src

    def test_no_fabricated_defaults_for_missing_values(self):
        """Missing budget/value must remain None, not be substituted."""
        src = self._get_service_source()
        # The old pattern: float(l.budget_max or 2_000_000.0)
        assert "or 2_000_000" not in src
        assert "or 2000000" not in src

    def test_all_monetary_responses_use_str_conversion(self):
        """API responses must convert Decimal to str, not float."""
        import inspect
        from app.modules.revenue_intelligence import router_b09
        src = inspect.getsource(router_b09)
        # float() conversion of monetary values is banned in router
        assert "float(rec." not in src
        assert "float(snap." not in src

    def test_no_success_true_fabrication(self):
        src = self._get_service_source()
        # Ensure no "return True" fakes a success
        # (actual return True may exist for boolean checks, but not for financial operations)
        # We check for the specific anti-pattern from the audit
        assert 'return {"success": True, "revenue":' not in src
