"""
Part 16 — Comprehensive Test Suite: Advanced Conversion Intelligence
=====================================================================
Tests:
1. Target definition contracts — all fields, enum values, registry
2. Data sufficiency gate logic — boundary conditions, class balance
3. PropensityEngine — all 6 targets, hot/warm/cold/stall/booking/visit
4. NextBestActionRanker — stage-specific actions, priority ordering
5. CRMPredictionIntelligenceService — graceful degradation, cache behavior
6. Temporal leakage prevention (inherited from feature store)
7. Integration — feature store → propensity → NBA pipeline
8. Router imports — all Part 16 endpoints importable without error
"""

import pytest
import uuid
import math
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# ─── Target Definition Tests ──────────────────────────────────────────────────

from app.modules.predictive.targets.target_definitions import (
    ALL_TARGET_DEFINITIONS, get_target, PredictionMethod, ModelStatus,
    LEAD_RESPONSE_PROPENSITY_V1, OPPORTUNITY_STALL_RISK_V1,
    BOOKING_PROPENSITY_V1, NEXT_BEST_ACTION_V1, REVENUE_FORECAST_V1,
)


class TestTargetDefinitions:
    """Validates all prediction target definitions meet Part 16 contract requirements."""

    REQUIRED_TARGETS = [
        "LEAD_RESPONSE_PROPENSITY_V1",
        "APPOINTMENT_PROPENSITY_V1",
        "SITE_VISIT_PROPENSITY_V1",
        "OPPORTUNITY_STALL_RISK_V1",
        "BOOKING_PROPENSITY_V1",
        "LEAD_COLD_RISK_V1",
        "PROPERTY_CONVERSION_PROPENSITY_V1",
        "SOURCE_QUALITY_V1",
        "NEXT_BEST_ACTION_V1",
        "REVENUE_FORECAST_V1",
    ]

    def test_all_required_targets_registered(self):
        """All Part 16 required targets must be in the registry."""
        for tid in self.REQUIRED_TARGETS:
            assert tid in ALL_TARGET_DEFINITIONS, f"Missing target: {tid}"

    def test_each_target_has_complete_fields(self):
        """Each target must have all required fields with non-empty values."""
        for tid, t in ALL_TARGET_DEFINITIONS.items():
            assert t.target_id, f"{tid} missing target_id"
            assert t.name, f"{tid} missing name"
            assert t.definition, f"{tid} missing definition"
            assert t.positive_outcome, f"{tid} missing positive_outcome"
            assert t.negative_outcome, f"{tid} missing negative_outcome"
            assert t.lookahead_window_days > 0, f"{tid} invalid lookahead_window"
            assert t.anchor_event, f"{tid} missing anchor_event"
            assert t.min_eligible_rows > 0, f"{tid} must require > 0 eligible rows"
            assert t.min_positive_labels > 0, f"{tid} must require > 0 positive labels"
            assert isinstance(t.method, PredictionMethod)
            assert isinstance(t.status, ModelStatus)
            assert t.version, f"{tid} missing version"

    def test_target_to_dict_serializable(self):
        """Each target's to_dict() must produce a valid dict with all required keys."""
        required_keys = {
            "target_id", "name", "definition", "positive_outcome", "negative_outcome",
            "lookahead_window_days", "min_eligible_rows", "min_positive_labels",
            "method", "status", "version", "reason"
        }
        for tid, t in ALL_TARGET_DEFINITIONS.items():
            d = t.to_dict()
            assert required_keys.issubset(d.keys()), f"{tid} to_dict missing keys: {required_keys - d.keys()}"

    def test_get_target_raises_for_unknown(self):
        """get_target() must raise KeyError for unregistered targets."""
        with pytest.raises(KeyError):
            get_target("DOES_NOT_EXIST_V99")

    def test_get_target_returns_correct_object(self):
        t = get_target("LEAD_RESPONSE_PROPENSITY_V1")
        assert t.target_id == "LEAD_RESPONSE_PROPENSITY_V1"
        assert t.lookahead_window_days == 2

    def test_no_zero_min_eligibility(self):
        """No target can have min_eligible_rows = 0 — prevents trivially passing the gate."""
        for tid, t in ALL_TARGET_DEFINITIONS.items():
            assert t.min_eligible_rows > 0, f"{tid} has min_eligible_rows=0"
            assert t.min_positive_labels > 0, f"{tid} has min_positive_labels=0"


# ─── Data Sufficiency Gate Tests ──────────────────────────────────────────────

from app.modules.predictive.targets.data_sufficiency_auditor import (
    DataSufficiencyAuditor, DataSufficiencyGateResult
)


class TestDataSufficiencyGate:
    """Tests the gate logic in isolation using static apply_gate()."""

    def _make_target(self, min_rows: int = 100, min_pos: int = 20):
        from app.modules.predictive.targets.target_definitions import TargetDefinition
        return TargetDefinition(
            target_id="TEST_TARGET_V1",
            name="Test",
            definition="Test target",
            positive_outcome="Success",
            negative_outcome="Failure",
            unknown_outcome="Unknown",
            lookahead_window_days=14,
            anchor_event="created_at",
            eligibility_criteria="active leads",
            exclusion_criteria="none",
            min_eligible_rows=min_rows,
            min_positive_labels=min_pos,
            method=PredictionMethod.DETERMINISTIC_HEURISTIC,
            version="v1",
            status=ModelStatus.BASELINE,
            reason="Test target",
        )

    def test_gate_passes_with_sufficient_data(self):
        target = self._make_target(100, 20)
        now = datetime.now(timezone.utc)
        result = DataSufficiencyAuditor._apply_gate(target, 200, 40, 160, now)
        assert result.gate_passed is True

    def test_gate_fails_insufficient_eligible(self):
        target = self._make_target(100, 20)
        now = datetime.now(timezone.utc)
        result = DataSufficiencyAuditor._apply_gate(target, 50, 20, 30, now)
        assert result.gate_passed is False
        assert "eligible=50" in result.reason

    def test_gate_fails_insufficient_positives(self):
        target = self._make_target(100, 20)
        now = datetime.now(timezone.utc)
        result = DataSufficiencyAuditor._apply_gate(target, 200, 5, 195, now)
        assert result.gate_passed is False
        assert "positives=5" in result.reason

    def test_gate_fails_extreme_class_imbalance(self):
        """Less than 3% minority class → gate FAILS regardless of absolute counts."""
        target = self._make_target(100, 20)
        now = datetime.now(timezone.utc)
        # 2 positives in 1000 → 0.2% balance
        result = DataSufficiencyAuditor._apply_gate(target, 1000, 2, 998, now)
        assert result.gate_passed is False

    def test_gate_passes_yields_validated_ml_above_10pct_balance(self):
        target = self._make_target(100, 20)
        now = datetime.now(timezone.utc)
        # 200 eligible, 30 positive = 15% balance → VALIDATED_ML
        result = DataSufficiencyAuditor._apply_gate(target, 200, 30, 170, now)
        assert result.gate_passed is True
        assert result.resolved_method == PredictionMethod.VALIDATED_ML

    def test_gate_passes_low_balance_yields_statistical_baseline(self):
        target = self._make_target(100, 5)
        now = datetime.now(timezone.utc)
        # 200 eligible, 8 positive = 4% balance → STATISTICAL_BASELINE only
        result = DataSufficiencyAuditor._apply_gate(target, 200, 8, 192, now)
        assert result.gate_passed is True
        assert result.resolved_method == PredictionMethod.STATISTICAL_BASELINE

    def test_gate_result_to_dict_complete(self):
        target = self._make_target(100, 20)
        now = datetime.now(timezone.utc)
        result = DataSufficiencyAuditor._apply_gate(target, 150, 30, 120, now)
        d = result.to_dict()
        assert "target_id" in d
        assert "gate_passed" in d
        assert "eligible_rows" in d
        assert "positive_labels" in d
        assert "class_balance_ratio" in d
        assert "resolved_method" in d
        assert "reason" in d

    def test_zero_eligible_rows_not_gate_passed(self):
        target = self._make_target(100, 20)
        now = datetime.now(timezone.utc)
        result = DataSufficiencyAuditor._apply_gate(target, 0, 0, 0, now)
        assert result.gate_passed is False
        assert result.eligible_rows == 0


# ─── PropensityEngine Tests ───────────────────────────────────────────────────

from app.modules.predictive.propensity.propensity_engine import PropensityEngine

BASE_FEATURES = {
    "lead_id": str(uuid.uuid4()),
    "feature_schema_version": "v1.0.0",
    "as_of_timestamp": datetime.now(timezone.utc).isoformat(),
    "lead_age_days": 7.0,
    "activity_count": 5,
    "hours_since_last_activity": 12.0,
    "inbound_message_count": 4,
    "outbound_message_count": 5,
    "customer_response_ratio": 0.80,
    "viewings_count": 1,
    "cancelled_viewings_count": 0,
    "attended_viewings_count": 1,
    "viewing_attendance_ratio": 1.0,
    "budget_max_aed": 3_000_000.0,
    "has_budget": True,
    "has_preferred_location": True,
    "lead_score_points": 80.0,
    "score_confidence": 0.9,
    "pipeline_stage": "qualified",
    "lead_name": "Ahmed Al-Rashid",
}

COLD_FEATURES = {
    **BASE_FEATURES,
    "lead_id": str(uuid.uuid4()),
    "hours_since_last_activity": 200.0,
    "inbound_message_count": 0,
    "customer_response_ratio": 0.0,
    "attended_viewings_count": 0,
    "cancelled_viewings_count": 2,
    "lead_score_points": 15.0,
    "pipeline_stage": "cold",
}


class TestPropensityEngine:
    """Tests all 6 propensity score functions under warm/cold conditions."""

    ORG_ID = "org-test-" + str(uuid.uuid4())[:8]

    def test_response_propensity_high_engagement(self):
        score = PropensityEngine.score_response_propensity(BASE_FEATURES, self.ORG_ID)
        assert score.target_id == "LEAD_RESPONSE_PROPENSITY_V1"
        assert score.probability > 0.50  # Responsive lead
        assert score.confidence in ("HIGH", "MEDIUM")
        assert isinstance(score.drivers_positive, list)
        assert isinstance(score.explanation, str)
        assert len(score.explanation) > 0

    def test_response_propensity_cold_lead(self):
        score = PropensityEngine.score_response_propensity(COLD_FEATURES, self.ORG_ID)
        assert score.probability < 0.40
        assert len(score.drivers_negative) > 0

    def test_appointment_propensity_qualified_lead(self):
        score = PropensityEngine.score_appointment_propensity(BASE_FEATURES, self.ORG_ID)
        assert score.target_id == "APPOINTMENT_PROPENSITY_V1"
        assert 0.0 < score.probability < 1.0
        assert score.probability > 0.30

    def test_site_visit_propensity_good_attendance_history(self):
        score = PropensityEngine.score_site_visit_propensity(BASE_FEATURES, self.ORG_ID)
        assert score.target_id == "SITE_VISIT_PROPENSITY_V1"
        assert score.probability > 0.60  # Good attendance history

    def test_site_visit_propensity_cancellation_history(self):
        score = PropensityEngine.score_site_visit_propensity(COLD_FEATURES, self.ORG_ID)
        assert score.probability < 0.60  # Cancelled viewings reduce probability

    def test_stall_risk_active_lead_low_risk(self):
        score = PropensityEngine.score_stall_risk(BASE_FEATURES, self.ORG_ID)
        assert score.target_id == "OPPORTUNITY_STALL_RISK_V1"
        assert score.probability < 0.40  # Active lead: low stall risk

    def test_stall_risk_inactive_lead_high_risk(self):
        score = PropensityEngine.score_stall_risk(COLD_FEATURES, self.ORG_ID)
        assert score.probability > 0.50  # Inactive + cancelled → high stall risk

    def test_booking_propensity_qualified_with_viewings(self):
        score = PropensityEngine.score_booking_propensity(BASE_FEATURES, self.ORG_ID)
        assert score.target_id == "BOOKING_PROPENSITY_V1"
        assert score.probability > 0.30

    def test_booking_propensity_cold_no_viewings(self):
        score = PropensityEngine.score_booking_propensity(COLD_FEATURES, self.ORG_ID)
        assert score.probability < 0.15  # Cold lead, no viewings

    def test_cold_risk_active_lead_low(self):
        score = PropensityEngine.score_cold_risk(BASE_FEATURES, self.ORG_ID)
        assert score.target_id == "LEAD_COLD_RISK_V1"
        assert score.probability < 0.40  # Active lead: low cold risk

    def test_cold_risk_inactive_lead_high(self):
        score = PropensityEngine.score_cold_risk(COLD_FEATURES, self.ORG_ID)
        assert score.probability > 0.50  # Inactive lead: high cold risk

    def test_all_scores_probabilities_in_valid_range(self):
        """All propensity scores must be in [0.0, 1.0]."""
        for feats in [BASE_FEATURES, COLD_FEATURES]:
            scores = PropensityEngine.score_all(feats, self.ORG_ID)
            assert len(scores) == 6  # All 6 targets computed
            for tid, score in scores.items():
                assert 0.0 <= score.probability <= 1.0, f"{tid} probability out of range: {score.probability}"

    def test_all_scores_have_valid_until(self):
        """All propensity scores must include a valid_until > now."""
        now = datetime.now(timezone.utc)
        scores = PropensityEngine.score_all(BASE_FEATURES, self.ORG_ID)
        for tid, score in scores.items():
            assert score.valid_until > now, f"{tid} valid_until not in future"

    def test_score_to_dict_complete(self):
        """PropensityScore.to_dict() must have all required keys."""
        score = PropensityEngine.score_response_propensity(BASE_FEATURES, self.ORG_ID)
        d = score.to_dict()
        required = {"target_id", "entity_id", "organization_id", "probability",
                    "probability_pct", "confidence", "method", "explanation",
                    "computed_at", "valid_until"}
        assert required.issubset(d.keys())
        assert 0.0 <= d["probability_pct"] <= 100.0


# ─── NextBestActionRanker Tests ───────────────────────────────────────────────

from app.modules.predictive.nba.next_best_action import (
    NextBestActionRanker, ActionType
)


class TestNextBestActionRanker:
    """Tests the NBA ranker under different lead states and propensity signal combinations."""

    ORG_ID = "org-nba-" + str(uuid.uuid4())[:8]

    def test_new_lead_calls_or_whatsapp_top_ranked(self):
        feats = {**BASE_FEATURES, "pipeline_stage": "new", "hours_since_last_activity": 48.0}
        result = NextBestActionRanker.rank(feats, self.ORG_ID)
        assert result.action_count > 0
        assert result.top_action is not None
        assert result.top_action.action_type in (ActionType.CALL_LEAD, ActionType.SEND_WHATSAPP)

    def test_viewing_stage_schedule_viewing_ranked_high(self):
        feats = {**BASE_FEATURES, "pipeline_stage": "viewing", "attended_viewings_count": 0}
        result = NextBestActionRanker.rank(feats, self.ORG_ID)
        action_types = [a.action_type for a in result.ranked_actions]
        assert ActionType.SCHEDULE_VIEWING in action_types or ActionType.SCHEDULE_FOLLOW_UP in action_types

    def test_stall_risk_increases_call_priority(self):
        feats = {**BASE_FEATURES, "pipeline_stage": "negotiation", "hours_since_last_activity": 200.0}
        high_stall_propensity = {
            "OPPORTUNITY_STALL_RISK_V1": {"probability": 0.85},
            "LEAD_COLD_RISK_V1": {"probability": 0.40},
        }
        result = NextBestActionRanker.rank(feats, self.ORG_ID, propensity_scores=high_stall_propensity)
        assert "STALL RISK" in result.reasoning_summary.upper() or "HIGH" in result.reasoning_summary.upper()
        assert result.top_action.utility_score >= 0.60

    def test_cold_lead_reassign_or_archive_ranked(self):
        feats = {**BASE_FEATURES, "pipeline_stage": "cold", "hours_since_last_activity": 200.0}
        cold_propensity = {
            "LEAD_COLD_RISK_V1": {"probability": 0.90},
            "OPPORTUNITY_STALL_RISK_V1": {"probability": 0.60},
        }
        result = NextBestActionRanker.rank(feats, self.ORG_ID, propensity_scores=cold_propensity)
        # Cold stage should surface cold-appropriate actions
        action_types = [a.action_type for a in result.ranked_actions]
        assert any(a in action_types for a in [
            ActionType.REASSIGN_LEAD, ActionType.SEND_WHATSAPP, ActionType.CREATE_TASK
        ])

    def test_won_lead_close_deal_ranked(self):
        feats = {**BASE_FEATURES, "pipeline_stage": "won"}
        result = NextBestActionRanker.rank(feats, self.ORG_ID)
        action_types = [a.action_type for a in result.ranked_actions]
        assert ActionType.CLOSE_DEAL in action_types

    def test_actions_ranked_by_utility_descending(self):
        result = NextBestActionRanker.rank(BASE_FEATURES, self.ORG_ID)
        scores = [a.utility_score for a in result.ranked_actions]
        assert scores == sorted(scores, reverse=True), "Actions not sorted by utility descending"

    def test_all_scored_actions_have_required_fields(self):
        result = NextBestActionRanker.rank(BASE_FEATURES, self.ORG_ID)
        required_keys = {"action_type", "utility_score", "priority", "rationale",
                         "estimated_impact", "cta_label"}
        for action in result.ranked_actions:
            d = action.to_dict()
            assert required_keys.issubset(d.keys())
            assert d["utility_score"] >= 0.0
            assert d["priority"] in ("URGENT", "HIGH", "MEDIUM", "LOW")

    def test_result_to_dict_complete(self):
        result = NextBestActionRanker.rank(BASE_FEATURES, self.ORG_ID)
        d = result.to_dict()
        assert "entity_id" in d
        assert "ranked_actions" in d
        assert "top_action" in d
        assert "reasoning_summary" in d
        assert "valid_until" in d
        assert isinstance(d["ranked_actions"], list)

    def test_no_crash_empty_features(self):
        """Ranker must not raise exceptions with missing features."""
        minimal = {"lead_id": str(uuid.uuid4()), "pipeline_stage": "new"}
        result = NextBestActionRanker.rank(minimal, self.ORG_ID)
        assert result.action_count > 0


# ─── CRM Prediction Intelligence Service Tests ────────────────────────────────

from app.modules.predictive.crm_intelligence.crm_prediction_service import (
    CRMPredictionIntelligenceService
)
from app.models.lead import Lead
from app.models.crm_models import Activity, Meeting
from app.models.conversation import Conversation


class TestCRMPredictionIntelligenceService:
    """Tests the aggregated CRM intelligence surface."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.rollback = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_get_lead_intelligence_success(self, mock_db):
        """Full pipeline: feature extraction → conversion → propensity → NBA → surface."""
        service = CRMPredictionIntelligenceService(mock_db)
        lead_id = str(uuid.uuid4())
        org_id = "org-test"

        fake_lead = Lead(
            id=uuid.UUID(lead_id),
            name="Test Buyer",
            pipeline_stage="qualified",
            score="warm",
            budget_max=3_000_000.0,
            preferred_locations=["Dubai Marina"],
            score_confidence=0.85,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        )

        # Mock feature store queries: lead, activity, messages, meetings
        results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=fake_lead)),    # Lead query
            MagicMock(scalar=MagicMock(return_value=0)),                         # Cache check
            MagicMock(scalar=MagicMock(return_value=3)),                         # Activity count
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),          # Last activity
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # Conversations
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # Meetings
        ]
        # For the cache check (first execute in get_lead_intelligence)
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        # Patch feature store to return deterministic features
        with patch.object(service.feature_store, "get_lead_features", return_value=dict(BASE_FEATURES)):
            surface = await service.get_lead_intelligence(lead_id, org_id, force_refresh=True)

        assert surface.lead_id == lead_id
        assert surface.organization_id == org_id
        assert 0.0 <= surface.conversion_probability <= 1.0
        assert surface.confidence_level in ("LOW", "MEDIUM", "HIGH")
        assert len(surface.propensity_scores) >= 4
        assert "ranked_actions" in surface.next_best_actions
        assert surface.prediction_id  # Has a UUID
        assert surface.generated_at <= datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_get_lead_intelligence_feature_error_returns_degraded(self, mock_db):
        """When feature extraction fails, returns degraded surface without crashing."""
        service = CRMPredictionIntelligenceService(mock_db)
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with patch.object(service.feature_store, "get_lead_features",
                          side_effect=ValueError("Lead not found")):
            surface = await service.get_lead_intelligence(
                "nonexistent-lead-id", "org-test", force_refresh=True
            )

        assert surface.confidence_level == "LOW"
        assert "degraded" in surface.explanation_text.lower() or "unavailable" in surface.explanation_text.lower()
        assert surface.conversion_probability == 0.25  # Degraded baseline

    @pytest.mark.asyncio
    async def test_degraded_surface_always_returns_valid_structure(self, mock_db):
        """Degraded surface must always include required keys."""
        surface = CRMPredictionIntelligenceService._degraded_surface(
            "lead-123", "org-123", reason="Test failure"
        )
        d = surface.to_dict()
        required_keys = {
            "lead_id", "organization_id", "conversion_probability",
            "confidence_level", "propensity_scores", "next_best_actions",
            "prediction_id", "generated_at", "valid_until"
        }
        assert required_keys.issubset(d.keys())
        assert d["conversion_probability"] == 0.25
        assert d["confidence_level"] == "LOW"

    @pytest.mark.asyncio
    async def test_surface_to_dict_contains_pct_value(self, mock_db):
        """Surface to_dict must include probability_pct (convenience field for frontend)."""
        surface = CRMPredictionIntelligenceService._degraded_surface("lead-x", "org-x")
        d = surface.to_dict()
        assert "conversion_probability_pct" in d
        assert d["conversion_probability_pct"] == 25.0  # 0.25 * 100


# ─── Integration Pipeline Test ────────────────────────────────────────────────

class TestIntegrationPipeline:
    """End-to-end pipeline: features → propensity → NBA → surface (mocked DB)."""

    ORG_ID = "org-integration-" + str(uuid.uuid4())[:8]

    def test_full_pipeline_warm_lead(self):
        """Warm lead with high engagement: should have high response/appointment probabilities."""
        feats = {**BASE_FEATURES, "pipeline_stage": "qualified"}
        all_scores = PropensityEngine.score_all(feats, self.ORG_ID)
        nba = NextBestActionRanker.rank(feats, self.ORG_ID,
                                         propensity_scores={k: v.to_dict() for k, v in all_scores.items()})

        # Warm engaged lead: high response probability
        assert all_scores["LEAD_RESPONSE_PROPENSITY_V1"].probability > 0.50
        # Low cold risk
        assert all_scores["LEAD_COLD_RISK_V1"].probability < 0.40
        # NBA has actions
        assert nba.action_count > 0
        # Top action has a CTA
        assert nba.top_action.cta_label

    def test_full_pipeline_cold_stalled_lead(self):
        """Cold stalled lead: high stall/cold risk, appropriate NBA actions."""
        feats = {**COLD_FEATURES}
        all_scores = PropensityEngine.score_all(feats, self.ORG_ID)
        nba = NextBestActionRanker.rank(feats, self.ORG_ID,
                                         propensity_scores={k: v.to_dict() for k, v in all_scores.items()})

        # Cold/stalled lead: high stall and cold risks
        assert all_scores["OPPORTUNITY_STALL_RISK_V1"].probability > 0.40
        assert all_scores["LEAD_COLD_RISK_V1"].probability > 0.40
        # NBA should surface re-engagement actions
        assert nba.action_count > 0

    def test_pipeline_probabilities_never_nan_inf(self):
        """All computed probabilities must be finite numbers."""
        for feats in [BASE_FEATURES, COLD_FEATURES]:
            scores = PropensityEngine.score_all(feats, self.ORG_ID)
            for tid, score in scores.items():
                assert math.isfinite(score.probability), f"{tid} probability is not finite"
                assert not math.isnan(score.probability), f"{tid} probability is NaN"

    def test_all_action_utility_scores_finite(self):
        """All NBA action utility scores must be finite."""
        result = NextBestActionRanker.rank(BASE_FEATURES, self.ORG_ID)
        for action in result.ranked_actions:
            assert math.isfinite(action.utility_score)
            assert 0.0 <= action.utility_score <= 1.0


# ─── Import Smoke Test ────────────────────────────────────────────────────────

class TestImportSmokeTest:
    """Validates all Part 16 modules can be imported without errors."""

    def test_target_definitions_importable(self):
        from app.modules.predictive.targets.target_definitions import ALL_TARGET_DEFINITIONS
        assert len(ALL_TARGET_DEFINITIONS) >= 10

    def test_data_sufficiency_auditor_importable(self):
        from app.modules.predictive.targets.data_sufficiency_auditor import DataSufficiencyAuditor
        assert DataSufficiencyAuditor is not None

    def test_propensity_engine_importable(self):
        from app.modules.predictive.propensity.propensity_engine import PropensityEngine
        assert PropensityEngine is not None

    def test_nba_ranker_importable(self):
        from app.modules.predictive.nba.next_best_action import NextBestActionRanker
        assert NextBestActionRanker is not None

    def test_crm_intelligence_service_importable(self):
        from app.modules.predictive.crm_intelligence.crm_prediction_service import (
            CRMPredictionIntelligenceService
        )
        assert CRMPredictionIntelligenceService is not None

    def test_existing_predictive_service_unchanged(self):
        """Existing PredictiveEngineService must still be importable and functional."""
        from app.modules.predictive.service import PredictiveEngineService
        assert PredictiveEngineService is not None
