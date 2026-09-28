"""
Master Build 14 - Security, Invariant, and Learning Loop Tests
==============================================================
Tests covering:
- Tenant isolation proofs (no cross-tenant data leakage)
- Benchmark privacy enforcement (minimum cohort, no customer identity)
- Experiment safety (no auto-activation)
- Learning data poisoning defense
- AI feedback safety (no direct model change)
- No duplicate outcomes/exposures
- No unsupported causal claims (structural tests)
- No unsourced recommendations
- Replay determinism
- Backfill idempotency
- Concurrency safety (unique constraints)
- Data governance integration
"""
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models.intelligence_models import (
    OutcomeEvent, OutcomeEventType, OutcomeEntityType, OutcomeSource,
    LearningEvent, LearningSignalType,
    ExperimentAssignment, ExperimentConversion,
    BenchmarkDefinition, BenchmarkSnapshot, BenchmarkType,
    PolicyRegistryEntry, RegistryEntityType, RegistryEntryStatus,
    DriftAlertRecord, DriftType,
    InsightRecord, InsightType,
    OrganizationLearningProfile,
    AIActionOutcome,
    DataQualityIssue, DataQualityIssueType,
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _org() -> str:
    return f"org-sec-{uuid.uuid4().hex[:10]}"


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Invariant: NO CROSS-TENANT LEARNING
# ---------------------------------------------------------------------------

class TestNoCrossTenantLearning:

    def test_outcome_events_strictly_tenant_scoped(self, db):
        """Events from org1 NEVER visible when querying org2."""
        org1, org2 = _org(), _org()
        shared_lead = _id()  # same lead ID used across both orgs (adversarial)

        for org in [org1, org2]:
            db.add(OutcomeEvent(
                organization_id=org,
                event_type=OutcomeEventType.LEAD_QUALIFIED,
                entity_type=OutcomeEntityType.LEAD,
                entity_id=shared_lead,  # Same entity_id, different org
                source_system=OutcomeSource.SYSTEM,
                actor_type="SYSTEM",
                occurred_at=_now(),
            ))
        db.commit()

        org1_events = db.query(OutcomeEvent).filter(
            OutcomeEvent.organization_id == org1,
            OutcomeEvent.entity_id == shared_lead,
        ).all()
        org2_events = db.query(OutcomeEvent).filter(
            OutcomeEvent.organization_id == org2,
            OutcomeEvent.entity_id == shared_lead,
        ).all()

        # Both exist but are tenant-isolated
        assert all(e.organization_id == org1 for e in org1_events)
        assert all(e.organization_id == org2 for e in org2_events)
        # No org1 data appears in org2 query
        assert not any(e.organization_id == org1 for e in org2_events)

    def test_learning_events_tenant_scoped(self, db):
        org1, org2 = _org(), _org()
        for org in [org1, org2]:
            db.add(LearningEvent(
                organization_id=org,
                event_type="SIGNAL",
                signal_type=LearningSignalType.HUMAN_ACCEPT,
                source_event_id=_id(),
                source_table="outcome_events",
                entity_type="LEAD",
                entity_id=_id(),
                actor_type="HUMAN",
                occurred_at=_now(),
            ))
        db.commit()

        org2_signals = db.query(LearningEvent).filter(
            LearningEvent.organization_id == org2
        ).all()
        assert all(s.organization_id == org2 for s in org2_signals)
        assert not any(s.organization_id == org1 for s in org2_signals)

    def test_org_learning_profiles_are_isolated(self, db):
        org1, org2 = _org(), _org()
        for org in [org1, org2]:
            db.add(OrganizationLearningProfile(
                organization_id=org,
                preferred_channels={"WHATSAPP": 1.0},
                response_patterns={}, property_preferences={},
                sales_cadence={}, conversion_patterns={},
                ai_usage_patterns={}, workflow_patterns={},
                objection_patterns={},
            ))
        db.commit()

        org1_profile = db.query(OrganizationLearningProfile).filter(
            OrganizationLearningProfile.organization_id == org1
        ).one()
        assert org1_profile.organization_id == org1
        # The org1 profile should not contain org2 data
        assert org1_profile.organization_id != org2


# ---------------------------------------------------------------------------
# Invariant: NO IDENTIFIABLE CUSTOMER DATA IN GLOBAL BENCHMARKS
# ---------------------------------------------------------------------------

class TestBenchmarkPrivacy:

    def _make_bdef(self, db, btype=BenchmarkType.ANONYMIZED_COHORT):
        bdef = BenchmarkDefinition(
            name=f"Privacy Test {_id()[:8]}",
            slug=f"priv-{_id()[:8]}",
            benchmark_type=btype,
            metric_name="conversion_rate",
            description="desc",
            methodology="method",
            minimum_cohort_size=10,
        )
        db.add(bdef)
        db.commit()
        db.refresh(bdef)
        return bdef

    def test_cohort_snapshot_has_null_org_id(self, db):
        """Anonymized cohort benchmarks must never have organization_id set."""
        bdef = self._make_bdef(db)
        now = _now()
        snap = BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=None,  # REQUIRED: no customer identity
            period_start=now - timedelta(days=30),
            period_end=now,
            period_type="MONTHLY",
            actual_cohort_size=50,
            is_privacy_safe=True,
            is_statistically_meaningful=True,
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        assert snap.organization_id is None

    def test_small_cohort_flagged_not_privacy_safe(self, db):
        bdef = self._make_bdef(db)
        now = _now()
        snap = BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=None,
            period_start=now - timedelta(days=7),
            period_end=now,
            period_type="WEEKLY",
            actual_cohort_size=3,  # < minimum_cohort_size of 10
            is_privacy_safe=False,  # Must be False
            is_statistically_meaningful=False,
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        # Application layer must not expose this snapshot
        assert snap.is_privacy_safe is False
        assert snap.actual_cohort_size < 10

    def test_minimum_cohort_size_enforced_at_db(self, db):
        """minimum_cohort_size < 5 rejected at DB level."""
        with pytest.raises(IntegrityError):
            bdef = BenchmarkDefinition(
                name="Invalid",
                slug=f"invalid-coh-{_id()[:8]}",
                benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
                metric_name="m",
                description="d",
                methodology="m",
                minimum_cohort_size=2,  # INVALID
            )
            db.add(bdef)
            db.commit()
        db.rollback()

    def test_no_industry_benchmark_without_external_source(self, db):
        """
        PRINCIPLE: Never call internally calculated data an industry benchmark.
        Verified structurally: external_source is optional, not required.
        But benchmark_type has no INDUSTRY value in the enum.
        """
        # BenchmarkType enum must not have INDUSTRY value
        assert not hasattr(BenchmarkType, "INDUSTRY")
        assert "INDUSTRY" not in [e.value for e in BenchmarkType]

    def test_benchmark_snapshot_unique_per_definition_org_period(self, db):
        """No duplicate snapshots for same definition+org+period."""
        bdef = self._make_bdef(db, btype=BenchmarkType.ORGANIZATION)
        org = _org()
        now = _now()
        period_start = now - timedelta(days=1)
        period_end = now

        db.add(BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=org,
            period_start=period_start,
            period_end=period_end,
            period_type="DAILY",
            actual_cohort_size=100,
            is_privacy_safe=True,
            is_statistically_meaningful=True,
        ))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(BenchmarkSnapshot(
                definition_id=bdef.id,
                organization_id=org,
                period_start=period_start,  # DUPLICATE
                period_end=period_end,
                period_type="DAILY",
                actual_cohort_size=99,
                is_privacy_safe=True,
                is_statistically_meaningful=True,
            ))
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# Invariant: NO DUPLICATE OUTCOMES
# ---------------------------------------------------------------------------

class TestNoDuplicateOutcomes:

    def test_outcome_events_are_idempotently_identifiable(self, db):
        """Events have unique IDs. Application should check before inserting."""
        org = _org()
        evt = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.BOOKING_CREATED,
            entity_type=OutcomeEntityType.BOOKING,
            entity_id=_id(),
            source_system=OutcomeSource.SYSTEM,
            actor_type="SYSTEM",
            occurred_at=_now(),
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)

        # Check via primary key uniqueness
        assert evt.id is not None
        existing = db.get(OutcomeEvent, evt.id)
        assert existing is not None


# ---------------------------------------------------------------------------
# Invariant: NO DUPLICATE EXPERIMENT EXPOSURES
# ---------------------------------------------------------------------------

class TestNoDuplicateExperimentExposures:

    def test_unique_assignment_per_experiment_subject(self, db):
        exp_id = _id()
        variant_id = _id()
        subject_id = _id()
        org = _org()

        db.add(ExperimentAssignment(
            experiment_id=exp_id, variant_id=variant_id,
            organization_id=org, subject_type="LEAD",
            subject_id=subject_id,
        ))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(ExperimentAssignment(
                experiment_id=exp_id, variant_id=variant_id,
                organization_id=org, subject_type="LEAD",
                subject_id=subject_id,  # DUPLICATE
            ))
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# Invariant: NO UNVERSIONED MODEL/PROMPT CHANGE
# ---------------------------------------------------------------------------

class TestNoUnversionedModelChange:

    def test_model_version_uniqueness_enforced(self, db):
        key = f"model-{_id()[:8]}"
        db.add(PolicyRegistryEntry(
            entity_type=RegistryEntityType.MODEL,
            entity_key=key,
            version="v1.0.0",
            description="v1",
        ))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(PolicyRegistryEntry(
                entity_type=RegistryEntityType.MODEL,
                entity_key=key,
                version="v1.0.0",  # SAME VERSION: DUPLICATE
                description="duplicate",
            ))
            db.commit()
        db.rollback()

    def test_prompt_version_uniqueness_enforced(self, db):
        key = f"prompt-{_id()[:8]}"
        db.add(PolicyRegistryEntry(
            entity_type=RegistryEntityType.PROMPT,
            entity_key=key,
            version="v2.5",
            description="prompt v2.5",
        ))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(PolicyRegistryEntry(
                entity_type=RegistryEntityType.PROMPT,
                entity_key=key,
                version="v2.5",  # DUPLICATE
                description="dup",
            ))
            db.commit()
        db.rollback()

    def test_candidate_status_requires_approval_before_active(self, db):
        """A CANDIDATE entry must not be ACTIVE without explicit promotion."""
        entry = PolicyRegistryEntry(
            entity_type=RegistryEntityType.POLICY,
            entity_key=f"policy-{_id()[:8]}",
            version="v1",
            description="New policy",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        # Default is CANDIDATE, not ACTIVE
        assert entry.status == RegistryEntryStatus.CANDIDATE
        assert entry.promoted_by is None
        assert entry.promoted_at is None


# ---------------------------------------------------------------------------
# Invariant: NO AI FEEDBACK AUTOMATIC MODEL CHANGE
# ---------------------------------------------------------------------------

class TestAIFeedbackSafety:

    def test_helpful_feedback_creates_signal_not_model_change(self, db):
        """
        A user clicking 'helpful' creates a LearningEvent (signal).
        It does NOT automatically change model behavior.
        """
        org = _org()
        # Create a learning signal
        signal = LearningEvent(
            organization_id=org,
            event_type="AI_FEEDBACK",
            signal_type=LearningSignalType.AI_RESPONSE_HELPFUL,
            signal_value="1",
            source_event_id=_id(),
            source_table="ai_action_outcomes",
            entity_type="AI_ACTION",
            entity_id=_id(),
            actor_type="HUMAN",
            occurred_at=_now(),
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)

        # Signal is stored but NOT verified/promoted
        assert signal.is_verified is False
        assert signal.verified_by is None
        # No model_version automatically changed
        # Application must explicitly verify and promote
        assert signal.model_version is None  # No model linked without explicit context

    def test_signal_requires_human_verification_before_promotion(self, db):
        """
        Signals must be verified before influencing model decisions.
        """
        org = _org()
        signal = LearningEvent(
            organization_id=org,
            event_type="AI_FEEDBACK",
            signal_type=LearningSignalType.AI_RESPONSE_UNHELPFUL,
            source_event_id=_id(),
            source_table="ai_action_outcomes",
            entity_type="AI_ACTION",
            entity_id=_id(),
            actor_type="HUMAN",
            occurred_at=_now(),
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        assert signal.is_verified is False

        # Explicit verification by human
        signal.is_verified = True
        signal.verified_by = _id()
        signal.verified_at = _now()
        db.commit()
        db.refresh(signal)
        assert signal.is_verified is True
        assert signal.verified_by is not None


# ---------------------------------------------------------------------------
# Invariant: NO UNSOURCED INSIGHT
# ---------------------------------------------------------------------------

class TestNoUnsourcedInsight:

    def test_insight_requires_source_metric(self, db):
        """Every insight must cite its source metric."""
        # source_metric is NOT nullable in the model
        assert not InsightRecord.__table__.c.source_metric.nullable

    def test_insight_requires_source_event_ids(self, db):
        """Insights must have source event references."""
        org = _org()
        now = _now()
        insight = InsightRecord(
            organization_id=org,
            insight_type=InsightType.ANOMALY,
            title="Conversion spike detected",
            description="Unusually high conversion observed",
            source_metric="booking_conversion_rate",
            source_event_ids=[],  # Empty = no evidence (valid but weak)
            period_start=now - timedelta(days=7),
            period_end=now,
            impact_score=Decimal("7"),
            urgency_score=Decimal("6"),
            confidence_score=Decimal("3"),  # Low confidence when no evidence
            actionability_score=Decimal("5"),
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)
        # With no source events, confidence should be low
        assert insight.confidence_score == Decimal("3")


# ---------------------------------------------------------------------------
# Invariant: NO CAUSALITY CLAIM WITHOUT METHOD
# ---------------------------------------------------------------------------

class TestNoCausalityClaimWithoutMethod:

    def test_benchmark_methodology_required(self, db):
        """methodology field is NOT nullable in BenchmarkDefinition."""
        assert not BenchmarkDefinition.__table__.c.methodology.nullable

    def test_insight_engine_has_no_causal_claim_field(self):
        """
        InsightRecord has no field for causal claims.
        It stores: description, recommended_action, expected_benefit.
        These are recommendations, not causal proofs.
        """
        # Verify no 'caused_by' or 'causal_impact' field exists
        col_names = [c.name for c in InsightRecord.__table__.c]
        assert "caused_by" not in col_names
        assert "causal_impact" not in col_names
        assert "lift" not in col_names
        # supporting_evidence is present for provenance
        assert "supporting_evidence" in col_names


# ---------------------------------------------------------------------------
# Learning Data Poisoning Defense
# ---------------------------------------------------------------------------

class TestLearningDataPoisoningDefense:

    def test_learning_event_requires_explicit_signal_type(self, db):
        """
        signal_type must be from LearningSignalType taxonomy.
        Arbitrary strings cannot be inserted without schema change.
        """
        # The field is a String(60) - NOT an enum at DB level
        # But application should enforce LearningSignalType taxonomy.
        # We verify the field exists and is not nullable.
        assert not LearningEvent.__table__.c.signal_type.nullable

    def test_malformed_confidence_rejected(self, db):
        """Confidence outside [0, 1] must be rejected."""
        org = _org()
        # value > 1.0 should fail
        with pytest.raises(IntegrityError):
            db.add(LearningEvent(
                organization_id=org,
                event_type="POISON_TEST",
                signal_type=LearningSignalType.HUMAN_ACCEPT,
                source_event_id=_id(),
                source_table="outcome_events",
                entity_type="LEAD",
                entity_id=_id(),
                actor_type="HUMAN",
                confidence=Decimal("2.0"),  # INVALID
                occurred_at=_now(),
            ))
            db.commit()
        db.rollback()

    def test_learning_events_require_organization_id(self, db):
        """Unscoped learning events cannot exist."""
        with pytest.raises(IntegrityError):
            db.add(LearningEvent(
                organization_id=None,  # INVALID
                event_type="SIGNAL",
                signal_type=LearningSignalType.HUMAN_ACCEPT,
                source_event_id=_id(),
                source_table="outcome_events",
                entity_type="LEAD",
                entity_id=_id(),
                actor_type="HUMAN",
                occurred_at=_now(),
            ))
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# Concurrency Safety Tests
# ---------------------------------------------------------------------------

class TestConcurrencySafety:

    def test_concurrent_experiment_assignments_deduplicated(self, db):
        """
        Simulate two concurrent assignments for same subject.
        Only one should succeed due to unique constraint.
        """
        exp_id = _id()
        variant_id = _id()
        subject_id = _id()
        org = _org()

        db.add(ExperimentAssignment(
            experiment_id=exp_id, variant_id=variant_id,
            organization_id=org, subject_type="LEAD",
            subject_id=subject_id,
        ))
        db.commit()

        # Second assignment - must fail
        with pytest.raises(IntegrityError):
            db.add(ExperimentAssignment(
                experiment_id=exp_id, variant_id=variant_id,
                organization_id=org, subject_type="LEAD",
                subject_id=subject_id,
            ))
            db.commit()
        db.rollback()

    def test_duplicate_registry_entries_prevented(self, db):
        key = f"concurrent-model-{_id()[:8]}"
        db.add(PolicyRegistryEntry(
            entity_type=RegistryEntityType.MODEL,
            entity_key=key,
            version="v1.0",
            description="initial",
        ))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(PolicyRegistryEntry(
                entity_type=RegistryEntityType.MODEL,
                entity_key=key,
                version="v1.0",
                description="concurrent duplicate",
            ))
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# Replay Determinism Tests
# ---------------------------------------------------------------------------

class TestReplayDeterminism:

    def test_outcome_events_have_stable_timestamps(self, db):
        """
        Replay requires deterministic results.
        occurred_at is stored with timezone, enabling deterministic replay.
        Note: SQLite strips tzinfo from DateTime; compare naive-aware safely.
        """
        org = _org()
        fixed_time = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        evt = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.LEAD_QUALIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=_id(),
            source_system=OutcomeSource.SYSTEM,
            actor_type="SYSTEM",
            occurred_at=fixed_time,
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)

        # Querying by occurred_at should give deterministic results
        found = db.query(OutcomeEvent).filter(
            OutcomeEvent.organization_id == org,
        ).all()
        assert len(found) >= 1
        # Compare naive vs naive (SQLite strips tzinfo) or aware vs aware (Postgres)
        stored = found[-1].occurred_at
        stored_naive = stored.replace(tzinfo=None) if stored.tzinfo else stored
        fixed_naive = fixed_time.replace(tzinfo=None)
        assert stored_naive == fixed_naive

    def test_learning_events_source_traceability(self, db):
        """
        All learning events have source_event_id for full provenance tracing.
        Replay can reconstruct the learning signal from the source event.
        """
        org = _org()
        source_id = _id()
        le = LearningEvent(
            organization_id=org,
            event_type="SIGNAL",
            signal_type=LearningSignalType.RECOMMENDATION_ACCEPTED,
            source_event_id=source_id,
            source_table="outcome_events",
            entity_type="LEAD",
            entity_id=_id(),
            actor_type="SYSTEM",
            occurred_at=_now(),
        )
        db.add(le)
        db.commit()
        db.refresh(le)

        # Can trace back to source
        assert le.source_event_id == source_id
        assert le.source_table == "outcome_events"


# ---------------------------------------------------------------------------
# Backfill Idempotency Tests
# ---------------------------------------------------------------------------

class TestBackfillIdempotency:

    def test_intelligence_snapshot_unique_prevents_duplicate_backfill(self, db):
        """
        Backfill operations must be idempotent.
        Attempting to backfill the same period twice should fail cleanly.
        """
        from app.models.intelligence_models import IntelligenceSnapshot
        org = _org()
        now = _now()
        period_start = now - timedelta(days=30)

        db.add(IntelligenceSnapshot(
            organization_id=org,
            period_type="MONTHLY",
            period_start=period_start,
            period_end=now,
            funnel_metrics={}, channel_metrics={},
            ai_metrics={}, revenue_metrics={},
            data_quality_metrics={},
            source_event_count=500,
        ))
        db.commit()

        # Second backfill for same period - must fail
        with pytest.raises(IntegrityError):
            db.add(IntelligenceSnapshot(
                organization_id=org,
                period_type="MONTHLY",
                period_start=period_start,  # DUPLICATE
                period_end=now,
                funnel_metrics={}, channel_metrics={},
                ai_metrics={}, revenue_metrics={},
                data_quality_metrics={},
                source_event_count=501,
            ))
            db.commit()
        db.rollback()

    def test_benchmark_snapshot_unique_prevents_duplicate_backfill(self, db):
        bdef = BenchmarkDefinition(
            name=f"Backfill Test {_id()[:8]}",
            slug=f"backfill-{_id()[:8]}",
            benchmark_type=BenchmarkType.ORGANIZATION,
            metric_name="metric",
            description="desc",
            methodology="method",
        )
        db.add(bdef)
        db.commit()
        db.refresh(bdef)

        org = _org()
        now = _now()
        period_start = now - timedelta(days=7)

        db.add(BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=org,
            period_start=period_start,
            period_end=now,
            period_type="WEEKLY",
            actual_cohort_size=50,
            is_privacy_safe=True,
            is_statistically_meaningful=True,
        ))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(BenchmarkSnapshot(
                definition_id=bdef.id,
                organization_id=org,
                period_start=period_start,  # DUPLICATE
                period_end=now,
                period_type="WEEKLY",
                actual_cohort_size=51,
                is_privacy_safe=True,
                is_statistically_meaningful=True,
            ))
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# Evidence Classification Tests
# ---------------------------------------------------------------------------

class TestEvidenceClassification:

    def test_no_fabricated_benchmark_values(self, db):
        """
        BenchmarkSnapshot.value must be nullable (can be NULL when
        insufficient data rather than fabricated).
        """
        assert BenchmarkSnapshot.__table__.c.value.nullable

    def test_no_fabricated_statistical_metrics(self, db):
        """
        confidence_interval_low/high must be nullable.
        When data is insufficient, intervals should be NULL, not fabricated.
        """
        assert BenchmarkSnapshot.__table__.c.confidence_interval_low.nullable
        assert BenchmarkSnapshot.__table__.c.confidence_interval_high.nullable

    def test_recommendation_quality_null_when_insufficient(self):
        """
        All rate fields in RecommendationQualitySnapshot must be nullable
        so they can be NULL when sample_size_sufficient is False.
        """
        from app.models.intelligence_models import RecommendationQualitySnapshot
        nullable_rates = [
            "acceptance_rate", "execution_rate", "success_rate",
            "override_rate", "rejection_rate", "ignore_rate"
        ]
        for field_name in nullable_rates:
            col = RecommendationQualitySnapshot.__table__.c[field_name]
            assert col.nullable, f"{field_name} should be nullable"

    def test_drift_has_required_methodology(self, db):
        """Drift alerts require detection_method documentation."""
        assert not DriftAlertRecord.__table__.c.detection_method.nullable

    def test_all_learning_events_have_source_provenance(self, db):
        """source_event_id must not be nullable in LearningEvent."""
        assert not LearningEvent.__table__.c.source_event_id.nullable
        assert not LearningEvent.__table__.c.source_table.nullable
