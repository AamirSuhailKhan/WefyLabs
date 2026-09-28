"""
Master Build 14 - Intelligence Graph & Outcome Model Tests
==========================================================
Tests covering:
1. Outcome events - taxonomy, tenant isolation, immutability
2. Learning events - signal taxonomy, provenance, immutability
3. Sales graph - edge creation, traversal queries
4. Recommendation feedback - AI action lifecycle
5. Lead learning - funnel transitions
6. Property learning - match outcomes
7. Objection intelligence - classification and resolution
8. Funnel intelligence - stage transitions
9. Experimentation - controlled safety, no auto-activation
10. Tenant isolation - strict boundary enforcement
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence_models import (
    OutcomeEvent, OutcomeEventType, OutcomeEntityType, OutcomeSource,
    LearningEvent, LearningSignalType,
    SalesOutcomeEdge, AIActionOutcome,
    RecommendationQualitySnapshot,
    ObjectionRecord, ObjectionType,
    FunnelTransitionRecord,
    Experiment, ExperimentStatus, ExperimentVariant,
    ExperimentAssignment, ExperimentConversion,
    BenchmarkDefinition, BenchmarkSnapshot, BenchmarkType,
    DataQualityIssue, DataQualityIssueType,
    PolicyRegistryEntry, RegistryEntityType, RegistryEntryStatus,
    DriftAlertRecord, DriftType,
    IntelligenceSnapshot,
    InsightRecord, InsightType,
    OrganizationLearningProfile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


def _org(n: int = 1) -> str:
    return f"org-{n:04d}-{uuid.uuid4().hex[:8]}"


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 1. Outcome Event Tests
# ---------------------------------------------------------------------------

class TestOutcomeEvents:

    def test_create_lead_qualified_event(self, db):
        org = _org()
        lead = _id()
        evt = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.LEAD_QUALIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=_id(),
            lead_id=lead,
            occurred_at=_now(),
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)
        assert evt.id is not None
        assert evt.organization_id == org
        assert evt.event_type == OutcomeEventType.LEAD_QUALIFIED
        assert evt.captured_at is not None

    def test_all_outcome_event_types_valid(self, db):
        """Verify all taxonomy members can be stored."""
        org = _org()
        for etype in OutcomeEventType:
            evt = OutcomeEvent(
                organization_id=org,
                event_type=etype,
                entity_type=OutcomeEntityType.LEAD,
                entity_id=_id(),
                source_system=OutcomeSource.SYSTEM,
                actor_type="SYSTEM",
                occurred_at=_now(),
            )
            db.add(evt)
        db.commit()

    def test_outcome_event_requires_organization_id(self, db):
        """Tenant isolation: organization_id is mandatory."""
        from sqlalchemy.exc import IntegrityError
        evt = OutcomeEvent(
            organization_id=None,
            event_type=OutcomeEventType.LEAD_QUALIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=_id(),
            source_system=OutcomeSource.SYSTEM,
            actor_type="SYSTEM",
            occurred_at=_now(),
        )
        db.add(evt)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_correction_chain_preserves_immutability(self, db):
        """Corrections create new records, not updates."""
        org = _org()
        original = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.LEAD_QUALIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=_id(),
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            occurred_at=_now(),
        )
        db.add(original)
        db.commit()
        db.refresh(original)

        correction = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.LEAD_DISQUALIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=original.entity_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            correction_of=original.id,
            occurred_at=_now(),
        )
        db.add(correction)
        db.commit()
        db.refresh(correction)

        assert correction.correction_of == original.id
        # Original still exists unchanged
        db.refresh(original)
        assert original.event_type == OutcomeEventType.LEAD_QUALIFIED

    def test_human_override_captured(self, db):
        org = _org()
        ai_rec_id = _id()
        evt = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.AI_ACTION_OVERRIDDEN,
            entity_type=OutcomeEntityType.AI_ACTION,
            entity_id=ai_rec_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=_id(),
            is_human_override=True,
            overrode_ai_recommendation_id=ai_rec_id,
            occurred_at=_now(),
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)
        assert evt.is_human_override is True
        assert evt.overrode_ai_recommendation_id == ai_rec_id

    def test_tenant_isolation_events(self, db):
        """Events from org1 must not be visible when filtering for org2."""
        org1, org2 = _org(1), _org(2)
        for org in [org1, org2]:
            db.add(OutcomeEvent(
                organization_id=org,
                event_type=OutcomeEventType.LEAD_QUALIFIED,
                entity_type=OutcomeEntityType.LEAD,
                entity_id=_id(),
                source_system=OutcomeSource.SYSTEM,
                actor_type="SYSTEM",
                occurred_at=_now(),
            ))
        db.commit()

        org1_events = db.query(OutcomeEvent).filter(
            OutcomeEvent.organization_id == org1
        ).all()
        org2_events = db.query(OutcomeEvent).filter(
            OutcomeEvent.organization_id == org2
        ).all()

        org1_ids = {e.organization_id for e in org1_events}
        org2_ids = {e.organization_id for e in org2_events}
        assert org1_ids == {org1}
        assert org2_ids == {org2}
        assert org1_ids.isdisjoint(org2_ids)


# ---------------------------------------------------------------------------
# 2. Learning Event Tests
# ---------------------------------------------------------------------------

class TestLearningEvents:

    def test_create_learning_event_with_provenance(self, db):
        org = _org()
        source_evt_id = _id()
        le = LearningEvent(
            organization_id=org,
            event_type="AI_FEEDBACK",
            signal_type=LearningSignalType.AI_RESPONSE_HELPFUL,
            signal_value="1",
            source_event_id=source_evt_id,
            source_table="outcome_events",
            entity_type="AI_ACTION",
            entity_id=_id(),
            actor_type="HUMAN",
            actor_id=_id(),
            model_version="gemini-2.5-flash-v1",
            prompt_version="lead-qualification-v3",
            confidence=Decimal("0.85"),
            occurred_at=_now(),
        )
        db.add(le)
        db.commit()
        db.refresh(le)
        assert le.id is not None
        assert le.source_event_id == source_evt_id
        assert le.model_version == "gemini-2.5-flash-v1"
        assert le.confidence == Decimal("0.85")

    def test_all_signal_types_valid(self, db):
        org = _org()
        for sig in LearningSignalType:
            le = LearningEvent(
                organization_id=org,
                event_type="SIGNAL_TEST",
                signal_type=sig,
                source_event_id=_id(),
                source_table="outcome_events",
                entity_type="LEAD",
                entity_id=_id(),
                actor_type="SYSTEM",
                occurred_at=_now(),
            )
            db.add(le)
        db.commit()

    def test_learning_event_confidence_range(self, db):
        """Confidence must be 0.0 - 1.0."""
        from sqlalchemy.exc import IntegrityError
        org = _org()
        le = LearningEvent(
            organization_id=org,
            event_type="AI_FEEDBACK",
            signal_type=LearningSignalType.AI_RESPONSE_HELPFUL,
            source_event_id=_id(),
            source_table="outcome_events",
            entity_type="LEAD",
            entity_id=_id(),
            actor_type="HUMAN",
            confidence=Decimal("1.5"),  # INVALID
            occurred_at=_now(),
        )
        db.add(le)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_learning_event_tenant_isolation(self, db):
        org1, org2 = _org(1), _org(2)
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

        org1_signals = db.query(LearningEvent).filter(
            LearningEvent.organization_id == org1
        ).all()
        assert all(e.organization_id == org1 for e in org1_signals)

    def test_feedback_does_not_auto_change_model(self):
        """
        PRINCIPLE: A user clicking helpful must not directly retrain a model.
        This test verifies the LearningEvent is just a signal record with no
        automatic model update mechanism.
        """
        # LearningEvent has no auto-promote fields.
        # It has is_verified and verified_by - explicit human approval required.
        assert hasattr(LearningEvent, "is_verified")
        assert hasattr(LearningEvent, "verified_by")
        assert hasattr(LearningEvent, "verified_at")
        # No field like auto_promoted or auto_applied
        assert not hasattr(LearningEvent, "auto_promoted")
        assert not hasattr(LearningEvent, "auto_applied")


# ---------------------------------------------------------------------------
# 3. Sales Outcome Graph Tests
# ---------------------------------------------------------------------------

class TestSalesOutcomeGraph:

    def test_create_graph_edge(self, db):
        org = _org()
        lead = _id()
        outcome_evt = _id()

        edge = SalesOutcomeEdge(
            organization_id=org,
            from_entity_type="LEAD",
            from_entity_id=lead,
            from_stage="QUALIFIED",
            to_entity_type="APPOINTMENT",
            to_entity_id=_id(),
            to_stage="APPOINTMENT_BOOKED",
            transition_type=OutcomeEventType.APPOINTMENT_BOOKED,
            lead_id=lead,
            outcome_event_id=outcome_evt,
            transition_at=_now(),
            duration_seconds=3600,
            was_successful=True,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
        assert edge.id is not None
        assert edge.lead_id == lead

    def test_graph_traversal_by_lead(self, db):
        """What happened after this lead was qualified?"""
        org = _org()
        lead = _id()
        stages = [
            ("LEAD", "QUALIFIED", "APPOINTMENT", "APPOINTMENT_BOOKED", OutcomeEventType.APPOINTMENT_BOOKED),
            ("APPOINTMENT", "APPOINTMENT_BOOKED", "SITE_VISIT", "SITE_VISIT_COMPLETED", OutcomeEventType.SITE_VISIT_COMPLETED),
        ]
        now = _now()
        for i, (fe, fs, te, ts, tt) in enumerate(stages):
            db.add(SalesOutcomeEdge(
                organization_id=org,
                from_entity_type=fe,
                from_entity_id=_id(),
                from_stage=fs,
                to_entity_type=te,
                to_entity_id=_id(),
                to_stage=ts,
                transition_type=tt,
                lead_id=lead,
                outcome_event_id=_id(),
                transition_at=now + timedelta(days=i),
            ))
        db.commit()

        lead_edges = db.query(SalesOutcomeEdge).filter(
            SalesOutcomeEdge.lead_id == lead,
            SalesOutcomeEdge.organization_id == org,
        ).order_by(SalesOutcomeEdge.transition_at).all()
        assert len(lead_edges) == 2
        assert lead_edges[0].to_entity_type == "APPOINTMENT"
        assert lead_edges[1].to_entity_type == "SITE_VISIT"


# ---------------------------------------------------------------------------
# 4. AI Action Outcome Loop Tests
# ---------------------------------------------------------------------------

class TestAIActionOutcomeLoop:

    def test_create_ai_action_outcome(self, db):
        org = _org()
        rec_id = _id()
        outcome = AIActionOutcome(
            organization_id=org,
            recommendation_id=rec_id,
            recommendation_type="PROPERTY_RECOMMENDATION",
            ai_model_version="gemini-2.5-flash-v1",
            prompt_version="property-rec-v3",
            policy_version="rec-policy-v1",
            confidence_score=Decimal("0.82"),
            lead_id=_id(),
            agent_id=_id(),
            recommended_at=_now(),
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)
        assert outcome.id is not None
        assert outcome.confidence_score == Decimal("0.82")

    def test_ai_action_lifecycle_accept_execute_outcome(self, db):
        org = _org()
        now = _now()
        outcome = AIActionOutcome(
            organization_id=org,
            recommendation_id=_id(),
            recommendation_type="NBA",
            ai_model_version="gemini-2.5-flash-v1",
            lead_id=_id(),
            recommended_at=now,
            accepted_at=now + timedelta(minutes=5),
            executed_at=now + timedelta(minutes=6),
            outcome_at=now + timedelta(hours=2),
            human_decision="accept",
            human_override=False,
            outcome_type=OutcomeEventType.APPOINTMENT_BOOKED,
            business_result="POSITIVE",
            outcome_event_id=_id(),
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)
        assert outcome.human_decision == "accept"
        assert outcome.business_result == "POSITIVE"

    def test_ai_action_human_override_captured(self, db):
        org = _org()
        now = _now()
        outcome = AIActionOutcome(
            organization_id=org,
            recommendation_id=_id(),
            recommendation_type="LEAD_SCORING",
            ai_model_version="gemini-2.5-flash-v1",
            lead_id=_id(),
            recommended_at=now,
            rejected_at=now + timedelta(minutes=1),
            human_decision="override",
            human_override=True,
            override_reason="Agent has additional context not in the system",
            business_result="NEUTRAL",
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)
        assert outcome.human_override is True
        assert outcome.override_reason is not None

    def test_ai_action_confidence_range_validated(self, db):
        from sqlalchemy.exc import IntegrityError
        org = _org()
        outcome = AIActionOutcome(
            organization_id=org,
            recommendation_id=_id(),
            recommendation_type="NBA",
            ai_model_version="v1",
            lead_id=_id(),
            recommended_at=_now(),
            confidence_score=Decimal("1.5"),  # INVALID
        )
        db.add(outcome)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 5. Funnel Intelligence Tests
# ---------------------------------------------------------------------------

class TestFunnelIntelligence:

    def test_create_funnel_transition(self, db):
        org = _org()
        lead = _id()
        now = _now()
        trans = FunnelTransitionRecord(
            organization_id=org,
            from_stage="LEAD",
            to_stage="QUALIFIED",
            lead_id=lead,
            source_event_id=_id(),
            from_stage_entered_at=now - timedelta(hours=2),
            transition_at=now,
            duration_seconds=7200,
            channel="WHATSAPP",
            lead_source="META_ADS",
        )
        db.add(trans)
        db.commit()
        db.refresh(trans)
        assert trans.duration_seconds == 7200
        assert trans.channel == "WHATSAPP"

    def test_funnel_stages_queryable(self, db):
        org = _org()
        funnel = [
            ("LEAD", "QUALIFIED"),
            ("QUALIFIED", "APPOINTMENT"),
            ("APPOINTMENT", "SITE_VISIT"),
            ("SITE_VISIT", "OPPORTUNITY"),
            ("OPPORTUNITY", "BOOKING"),
        ]
        now = _now()
        lead = _id()
        for i, (f, t) in enumerate(funnel):
            db.add(FunnelTransitionRecord(
                organization_id=org,
                from_stage=f, to_stage=t,
                lead_id=lead,
                source_event_id=_id(),
                from_stage_entered_at=now + timedelta(days=i),
                transition_at=now + timedelta(days=i, hours=1),
            ))
        db.commit()

        transitions = db.query(FunnelTransitionRecord).filter(
            FunnelTransitionRecord.organization_id == org,
            FunnelTransitionRecord.lead_id == lead,
        ).order_by(FunnelTransitionRecord.transition_at).all()
        assert len(transitions) == 5
        assert transitions[0].from_stage == "LEAD"
        assert transitions[-1].to_stage == "BOOKING"


# ---------------------------------------------------------------------------
# 6. Property Match Learning Tests
# ---------------------------------------------------------------------------

class TestPropertyMatchLearning:

    def test_property_match_positive_signal(self, db):
        org = _org()
        prop = _id()
        outcome = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.PROPERTY_MATCH_ACCEPTED,
            entity_type=OutcomeEntityType.PROPERTY,
            entity_id=prop,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            property_id=prop,
            lead_id=_id(),
            occurred_at=_now(),
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        signal = LearningEvent(
            organization_id=org,
            event_type="PROPERTY_FEEDBACK",
            signal_type=LearningSignalType.PROPERTY_MATCH_POSITIVE,
            source_event_id=outcome.id,
            source_table="outcome_events",
            entity_type="PROPERTY",
            entity_id=prop,
            actor_type="HUMAN",
            occurred_at=_now(),
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        assert signal.signal_type == LearningSignalType.PROPERTY_MATCH_POSITIVE
        assert signal.source_event_id == outcome.id

    def test_property_rejection_captured(self, db):
        org = _org()
        prop = _id()
        evt = OutcomeEvent(
            organization_id=org,
            event_type=OutcomeEventType.PROPERTY_MATCH_REJECTED,
            entity_type=OutcomeEntityType.PROPERTY,
            entity_id=prop,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            property_id=prop,
            occurred_at=_now(),
        )
        db.add(evt)
        db.commit()
        assert evt.event_type == OutcomeEventType.PROPERTY_MATCH_REJECTED


# ---------------------------------------------------------------------------
# 7. Objection Intelligence Tests
# ---------------------------------------------------------------------------

class TestObjectionIntelligence:

    def test_all_objection_types_valid(self, db):
        org = _org()
        lead = _id()
        for obj_type in ObjectionType:
            db.add(ObjectionRecord(
                organization_id=org,
                lead_id=lead,
                objection_type=obj_type,
                extracted_from="CONVERSATION",
                source_conversation_id=_id(),
                raised_at=_now(),
            ))
        db.commit()

    def test_objection_resolution_tracked(self, db):
        org = _org()
        obj = ObjectionRecord(
            organization_id=org,
            lead_id=_id(),
            objection_type=ObjectionType.PRICE,
            extracted_from="AGENT_NOTE",
            raised_at=_now(),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        assert obj.is_resolved is False

        obj.is_resolved = True
        obj.resolved_at = _now()
        obj.resolution_method = "HUMAN"
        obj.conversion_after_resolution = True
        db.commit()
        db.refresh(obj)
        assert obj.is_resolved is True
        assert obj.conversion_after_resolution is True

    def test_objection_confidence_range(self, db):
        from sqlalchemy.exc import IntegrityError
        org = _org()
        obj = ObjectionRecord(
            organization_id=org,
            lead_id=_id(),
            objection_type=ObjectionType.PRICE,
            extracted_from="CONVERSATION",
            extraction_confidence=Decimal("1.5"),  # INVALID
            raised_at=_now(),
        )
        db.add(obj)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 8. Experimentation Engine Tests
# ---------------------------------------------------------------------------

class TestExperimentationEngine:

    def test_experiment_starts_as_draft(self, db):
        exp = Experiment(
            name="Follow-up timing test",
            slug=f"followup-timing-{_id()[:8]}",
            description="Test shorter follow-up interval",
            hypothesis="6h follow-up increases appointment rate vs 24h",
            primary_metric="appointment_conversion_rate",
            secondary_metrics=["response_rate", "time_to_appointment"],
            population_definition={"segment": "new_leads"},
            expected_sample_size=500,
            owner_id=_id(),
            rollback_condition="appointment_rate drops > 10% vs control",
        )
        db.add(exp)
        db.commit()
        db.refresh(exp)
        assert exp.status == ExperimentStatus.DRAFT
        assert exp.approved_by is None
        assert exp.actual_start_at is None

    def test_experiment_approval_flow(self, db):
        """DRAFT -> REVIEW -> APPROVED -> RUNNING (no auto-activation)."""
        approver = _id()
        exp = Experiment(
            name="Approval flow test",
            slug=f"approval-{_id()[:8]}",
            description="Test approval flow",
            hypothesis="Hypothesis A",
            primary_metric="conversion",
            population_definition={},
            expected_sample_size=100,
            owner_id=_id(),
            rollback_condition="revert if metric drops",
        )
        db.add(exp)
        db.commit()
        assert exp.status == ExperimentStatus.DRAFT

        exp.status = ExperimentStatus.REVIEW
        db.commit()
        assert exp.status == ExperimentStatus.REVIEW

        exp.status = ExperimentStatus.APPROVED
        exp.approved_by = approver
        exp.approved_at = _now()
        db.commit()
        assert exp.status == ExperimentStatus.APPROVED
        assert exp.approved_by == approver

        # Not automatically RUNNING - requires explicit activation
        assert exp.actual_start_at is None

    def test_experiment_no_auto_activation(self, db):
        """SAFETY: Experiment must never automatically become RUNNING."""
        exp = Experiment(
            name="No auto test",
            slug=f"no-auto-{_id()[:8]}",
            description="Test auto prevention",
            hypothesis="Test hypothesis",
            primary_metric="conversion",
            population_definition={},
            expected_sample_size=100,
            owner_id=_id(),
            rollback_condition="revert",
        )
        db.add(exp)
        db.commit()
        # Status must be DRAFT, not RUNNING
        assert exp.status == ExperimentStatus.DRAFT
        assert exp.status != ExperimentStatus.RUNNING

    def test_experiment_requires_positive_sample_size(self, db):
        from sqlalchemy.exc import IntegrityError
        exp = Experiment(
            name="Invalid sample",
            slug=f"invalid-{_id()[:8]}",
            description="desc",
            hypothesis="h",
            primary_metric="m",
            population_definition={},
            expected_sample_size=0,  # INVALID
            owner_id=_id(),
            rollback_condition="r",
        )
        db.add(exp)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_experiment_assignment_is_unique(self, db):
        """INVARIANT: One assignment per experiment per subject."""
        from sqlalchemy.exc import IntegrityError
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

        db.add(ExperimentAssignment(
            experiment_id=exp_id, variant_id=variant_id,
            organization_id=org, subject_type="LEAD",
            subject_id=subject_id,  # DUPLICATE
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 9. Benchmarking Tests
# ---------------------------------------------------------------------------

class TestBenchmarking:

    def test_benchmark_definition_requires_methodology(self, db):
        bdef = BenchmarkDefinition(
            name="Lead Response Time",
            slug=f"lead-response-{_id()[:8]}",
            benchmark_type=BenchmarkType.ORGANIZATION,
            metric_name="lead_response_time_seconds",
            unit="seconds",
            description="Time from lead creation to first response",
            methodology="Median of time_to_first_response computed from outcome_events",
            minimum_cohort_size=10,
        )
        db.add(bdef)
        db.commit()
        db.refresh(bdef)
        assert bdef.methodology is not None

    def test_benchmark_minimum_cohort_enforced(self, db):
        """Cohort size < 5 must fail at DB level."""
        from sqlalchemy.exc import IntegrityError
        bdef = BenchmarkDefinition(
            name="Too small",
            slug=f"too-small-{_id()[:8]}",
            benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
            metric_name="conversion",
            description="desc",
            methodology="method",
            minimum_cohort_size=3,  # INVALID - must be >= 5
        )
        db.add(bdef)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_snapshot_privacy_enforcement(self, db):
        """Cohort snapshots with insufficient data are flagged not-safe."""
        bdef = BenchmarkDefinition(
            name="Conversion Rate",
            slug=f"conv-rate-{_id()[:8]}",
            benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
            metric_name="conversion_rate",
            description="desc",
            methodology="method",
            minimum_cohort_size=10,
        )
        db.add(bdef)
        db.commit()
        db.refresh(bdef)

        now = _now()
        snapshot = BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=None,  # anonymized
            period_start=now - timedelta(days=30),
            period_end=now,
            period_type="MONTHLY",
            value=Decimal("0.35"),
            actual_cohort_size=5,  # below minimum of 10
            is_privacy_safe=False,  # correctly flagged
            is_statistically_meaningful=False,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        assert snapshot.is_privacy_safe is False

    def test_no_customer_identity_in_cohort_benchmark(self, db):
        """Anonymized cohort snapshots must have organization_id=NULL."""
        bdef = BenchmarkDefinition(
            name="Anon Benchmark",
            slug=f"anon-{_id()[:8]}",
            benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
            metric_name="appt_rate",
            description="desc",
            methodology="method",
        )
        db.add(bdef)
        db.commit()
        db.refresh(bdef)

        now = _now()
        # Correct: anonymized snapshot has organization_id=None
        snapshot = BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=None,
            period_start=now - timedelta(days=7),
            period_end=now,
            period_type="WEEKLY",
            actual_cohort_size=25,
            is_privacy_safe=True,
            is_statistically_meaningful=True,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        # organization_id must be None for cohort benchmarks
        assert snapshot.organization_id is None

    def test_snapshot_is_immutable_conceptually(self, db):
        """Snapshot rows should not be updated after creation."""
        bdef = BenchmarkDefinition(
            name="Immutable Test",
            slug=f"immutable-{_id()[:8]}",
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
        snap = BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=org,
            period_start=now - timedelta(days=1),
            period_end=now,
            period_type="DAILY",
            value=Decimal("0.5"),
            actual_cohort_size=100,
            is_privacy_safe=True,
            is_statistically_meaningful=True,
        )
        db.add(snap)
        db.commit()
        initial_computed_at = snap.computed_at
        # A second snapshot should be a new row, not an update
        snap2 = BenchmarkSnapshot(
            definition_id=bdef.id,
            organization_id=org,
            period_start=now,
            period_end=now + timedelta(days=1),
            period_type="DAILY",
            value=Decimal("0.6"),
            actual_cohort_size=110,
            is_privacy_safe=True,
            is_statistically_meaningful=True,
        )
        db.add(snap2)
        db.commit()
        assert snap.computed_at == initial_computed_at  # unchanged


# ---------------------------------------------------------------------------
# 10. Data Quality Tests
# ---------------------------------------------------------------------------

class TestDataQuality:

    def test_create_data_quality_issue(self, db):
        org = _org()
        issue = DataQualityIssue(
            organization_id=org,
            issue_type=DataQualityIssueType.DUPLICATE_LEAD,
            severity="HIGH",
            entity_type="LEAD",
            entity_id=_id(),
            description="Duplicate lead detected via identity resolution",
            detection_method="identity_resolution_service",
            dimension="UNIQUENESS",
        )
        db.add(issue)
        db.commit()
        db.refresh(issue)
        assert issue.id is not None
        assert issue.is_resolved is False

    def test_data_quality_issue_resolution(self, db):
        org = _org()
        issue = DataQualityIssue(
            organization_id=org,
            issue_type=DataQualityIssueType.MISSING_SOURCE_ATTRIBUTION,
            severity="MEDIUM",
            entity_type="LEAD",
            entity_id=_id(),
            description="Lead source not attributed",
            detection_method="daily_scan",
            dimension="COMPLETENESS",
        )
        db.add(issue)
        db.commit()
        db.refresh(issue)

        issue.is_resolved = True
        issue.resolved_at = _now()
        issue.resolved_by = _id()
        issue.resolution_notes = "Manual attribution applied"
        db.commit()
        db.refresh(issue)
        assert issue.is_resolved is True
        assert issue.resolved_by is not None


# ---------------------------------------------------------------------------
# 11. Policy Registry Tests
# ---------------------------------------------------------------------------

class TestPolicyRegistry:

    def test_register_model_version(self, db):
        entry = PolicyRegistryEntry(
            entity_type=RegistryEntityType.MODEL,
            entity_key="lead_qualification_model",
            version="v3.1.0",
            description="Lead qualification model v3.1.0",
            content_hash="abc123def456",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        assert entry.status == RegistryEntryStatus.CANDIDATE

    def test_register_prompt_version(self, db):
        entry = PolicyRegistryEntry(
            entity_type=RegistryEntityType.PROMPT,
            entity_key="property_recommendation_prompt",
            version="v5.2",
            description="Property recommendation prompt v5.2",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        assert entry.entity_type == RegistryEntityType.PROMPT

    def test_version_uniqueness(self, db):
        from sqlalchemy.exc import IntegrityError
        key = f"model-{_id()[:8]}"
        for _ in range(2):
            db.add(PolicyRegistryEntry(
                entity_type=RegistryEntityType.MODEL,
                entity_key=key,
                version="v1.0.0",  # DUPLICATE
                description="desc",
            ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_rollback_chain(self, db):
        """Rollback creates a new entry pointing to the original."""
        key = f"policy-{_id()[:8]}"
        v1 = PolicyRegistryEntry(
            entity_type=RegistryEntityType.POLICY,
            entity_key=key,
            version="v1.0",
            description="Version 1",
            status=RegistryEntryStatus.ACTIVE,
        )
        db.add(v1)
        db.commit()
        db.refresh(v1)

        rollback = PolicyRegistryEntry(
            entity_type=RegistryEntityType.POLICY,
            entity_key=key,
            version="v1.0-rollback",
            description="Rollback to v1.0",
            status=RegistryEntryStatus.ROLLED_BACK,
            rollback_of_id=v1.id,
            previous_version_id=v1.id,
        )
        db.add(rollback)
        db.commit()
        db.refresh(rollback)
        assert rollback.rollback_of_id == v1.id

    def test_no_unversioned_model_change(self):
        """
        PRINCIPLE: No unversioned model change.
        Verify PolicyRegistryEntry requires entity_key and version.
        """
        # entity_key and version are both not nullable
        assert not PolicyRegistryEntry.__table__.c.entity_key.nullable
        assert not PolicyRegistryEntry.__table__.c.version.nullable


# ---------------------------------------------------------------------------
# 12. Drift Detection Tests
# ---------------------------------------------------------------------------

class TestDriftDetection:

    def test_create_drift_alert(self, db):
        now = _now()
        alert = DriftAlertRecord(
            drift_type=DriftType.MODEL_QUALITY,
            entity_key="lead_qualification_model",
            detection_method="PSI (Population Stability Index)",
            baseline_period_start=now - timedelta(days=30),
            baseline_period_end=now - timedelta(days=7),
            current_period_start=now - timedelta(days=7),
            current_period_end=now,
            drift_score=Decimal("0.25"),
            threshold=Decimal("0.20"),
            is_significant=True,
            baseline_sample_size=500,
            current_sample_size=120,
            severity="MEDIUM",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        assert alert.is_significant is True
        assert alert.acknowledged is False

    def test_drift_acknowledgement(self, db):
        now = _now()
        alert = DriftAlertRecord(
            drift_type=DriftType.CONVERSION,
            entity_key="booking_conversion_rate",
            detection_method="threshold",
            baseline_period_start=now - timedelta(days=14),
            baseline_period_end=now - timedelta(days=7),
            current_period_start=now - timedelta(days=7),
            current_period_end=now,
            drift_score=Decimal("0.15"),
            threshold=Decimal("0.10"),
            is_significant=True,
            baseline_sample_size=200,
            current_sample_size=80,
            severity="LOW",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        alert.acknowledged = True
        alert.acknowledged_by = _id()
        alert.acknowledged_at = _now()
        alert.action_taken = "Investigated - attributed to seasonal variation"
        db.commit()
        db.refresh(alert)
        assert alert.acknowledged is True


# ---------------------------------------------------------------------------
# 13. Intelligence Snapshot Tests
# ---------------------------------------------------------------------------

class TestIntelligenceSnapshots:

    def test_create_daily_snapshot(self, db):
        org = _org()
        now = _now()
        snap = IntelligenceSnapshot(
            organization_id=org,
            period_type="DAILY",
            period_start=now - timedelta(days=1),
            period_end=now,
            funnel_metrics={"lead_to_qualified": 0.35, "qualified_to_appointment": 0.28},
            channel_metrics={"whatsapp_response_rate": 0.72},
            ai_metrics={"acceptance_rate": 0.65, "override_rate": 0.12},
            revenue_metrics={"bookings_count": 3, "total_revenue_aed": "1500000"},
            data_quality_metrics={"completeness": 0.94},
            source_event_count=847,
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        assert snap.source_event_count == 847

    def test_snapshot_uniqueness_by_org_period(self, db):
        from sqlalchemy.exc import IntegrityError
        org = _org()
        now = _now()
        period_start = now - timedelta(days=1)
        for _ in range(2):
            db.add(IntelligenceSnapshot(
                organization_id=org,
                period_type="DAILY",
                period_start=period_start,
                period_end=now,
                funnel_metrics={},
                channel_metrics={},
                ai_metrics={},
                revenue_metrics={},
                data_quality_metrics={},
                source_event_count=0,
            ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 14. Insight Engine Tests
# ---------------------------------------------------------------------------

class TestInsightEngine:

    def test_create_insight_with_explicit_dimensions(self, db):
        org = _org()
        now = _now()
        insight = InsightRecord(
            organization_id=org,
            insight_type=InsightType.BOTTLENECK,
            title="Follow-up completion rate dropped 15%",
            description="Follow-up completion rate has dropped significantly in the last 7 days.",
            source_metric="followup_completion_rate",
            source_event_ids=["evt-001", "evt-002"],
            period_start=now - timedelta(days=7),
            period_end=now,
            impact_score=Decimal("8.5"),
            urgency_score=Decimal("7.0"),
            confidence_score=Decimal("6.5"),
            actionability_score=Decimal("9.0"),
            recommended_action="Review follow-up assignments for this week",
            expected_benefit="Expected to restore 15% completion rate",
            supporting_evidence=[{"metric": "completion_rate", "value": 0.52}],
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)
        assert insight.insight_type == InsightType.BOTTLENECK
        assert insight.impact_score == Decimal("8.5")

    def test_insight_score_range_enforced(self, db):
        from sqlalchemy.exc import IntegrityError
        org = _org()
        now = _now()
        insight = InsightRecord(
            organization_id=org,
            insight_type=InsightType.TREND,
            title="Test",
            description="Test",
            source_metric="test",
            period_start=now - timedelta(days=1),
            period_end=now,
            impact_score=Decimal("11"),  # INVALID > 10
            urgency_score=Decimal("5"),
            confidence_score=Decimal("5"),
            actionability_score=Decimal("5"),
        )
        db.add(insight)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# 15. Organization Learning Profile Tests
# ---------------------------------------------------------------------------

class TestOrganizationLearningProfile:

    def test_create_org_learning_profile(self, db):
        org = _org()
        profile = OrganizationLearningProfile(
            organization_id=org,
            preferred_channels={"WHATSAPP": 0.75, "EMAIL": 0.20},
            response_patterns={"avg_response_minutes": 45},
            property_preferences={"apartment": 0.60, "villa": 0.30},
            sales_cadence={"follow_up_interval_days": 3},
            conversion_patterns={"lead_to_booking_days_p50": 21},
            ai_usage_patterns={"ai_acceptance_rate": 0.65},
            workflow_patterns={"automation_rate": 0.45},
            objection_patterns={"PRICE": 0.40, "LOCATION": 0.25},
            learning_loop_maturity="BUILDING",
            total_outcomes_sampled=350,
            total_learning_events=1200,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        assert profile.organization_id == org
        assert profile.learning_loop_maturity == "BUILDING"

    def test_one_profile_per_org(self, db):
        from sqlalchemy.exc import IntegrityError
        org = _org()
        for _ in range(2):
            db.add(OrganizationLearningProfile(
                organization_id=org,  # DUPLICATE
                preferred_channels={},
                response_patterns={},
                property_preferences={},
                sales_cadence={},
                conversion_patterns={},
                ai_usage_patterns={},
                workflow_patterns={},
                objection_patterns={},
            ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_profile_tenant_isolation(self, db):
        """Each org's learning profile is isolated."""
        orgs = [_org() for _ in range(3)]
        for org in orgs:
            db.add(OrganizationLearningProfile(
                organization_id=org,
                preferred_channels={"WHATSAPP": 1.0},
                response_patterns={}, property_preferences={},
                sales_cadence={}, conversion_patterns={},
                ai_usage_patterns={}, workflow_patterns={},
                objection_patterns={},
            ))
        db.commit()

        for org in orgs:
            profiles = db.query(OrganizationLearningProfile).filter(
                OrganizationLearningProfile.organization_id == org
            ).all()
            assert len(profiles) == 1
            assert profiles[0].organization_id == org


# ---------------------------------------------------------------------------
# 16. Recommendation Quality Tests
# ---------------------------------------------------------------------------

class TestRecommendationQuality:

    def test_create_quality_snapshot(self, db):
        org = _org()
        now = _now()
        snap = RecommendationQualitySnapshot(
            organization_id=org,
            recommendation_type="PROPERTY_RECOMMENDATION",
            period_start=now - timedelta(days=7),
            period_end=now,
            period_type="WEEKLY",
            total_recommendations=120,
            sample_size_sufficient=True,
            acceptance_rate=Decimal("0.65"),
            execution_rate=Decimal("0.58"),
            success_rate=Decimal("0.42"),
            override_rate=Decimal("0.12"),
            rejection_rate=Decimal("0.23"),
            ignore_rate=Decimal("0.12"),
            methodology="Count from AIActionOutcome records in period",
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        assert snap.acceptance_rate == Decimal("0.65")
        assert snap.sample_size_sufficient is True

    def test_quality_rates_null_when_insufficient_sample(self, db):
        """Rates must be NULL when sample is insufficient."""
        org = _org()
        now = _now()
        snap = RecommendationQualitySnapshot(
            organization_id=org,
            recommendation_type="NBA",
            period_start=now - timedelta(days=1),
            period_end=now,
            period_type="DAILY",
            total_recommendations=3,  # Below minimum
            sample_size_sufficient=False,
            acceptance_rate=None,  # Correctly NULL
            methodology="Count from AIActionOutcome records",
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        assert snap.sample_size_sufficient is False
        assert snap.acceptance_rate is None


# ---------------------------------------------------------------------------
# 17. Extended Master Build 14 Intelligence Suites
# ---------------------------------------------------------------------------

class TestExtendedIntelligence:

    @staticmethod
    def _make_mock_session():
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        res = MagicMock()
        res.scalar.return_value = 10
        res.all.return_value = []
        session.execute.return_value = res
        return session

    @pytest.mark.asyncio
    async def test_executive_intelligence_service(self):
        from app.modules.intelligence.service import IntelligenceService
        from app.modules.intelligence.dto import ExecutiveIntelligenceResponse
        service = IntelligenceService()
        org = _org()
        mock_session = self._make_mock_session()

        exec_data = await service.get_executive_intelligence(mock_session, org, "MONTHLY")
        assert isinstance(exec_data, ExecutiveIntelligenceResponse)
        assert exec_data.organization_id == org
        assert exec_data.gross_margin_pct >= Decimal("0")
        assert len(exec_data.channel_summary) > 0

    @pytest.mark.asyncio
    async def test_manager_intelligence_service(self):
        from app.modules.intelligence.service import IntelligenceService
        from app.modules.intelligence.dto import ManagerIntelligenceResponse
        service = IntelligenceService()
        org = _org()
        mock_session = self._make_mock_session()

        mgr_data = await service.get_manager_intelligence(mock_session, org)
        assert isinstance(mgr_data, ManagerIntelligenceResponse)
        assert mgr_data.organization_id == org
        assert len(mgr_data.conversion_stages) > 0
        assert len(mgr_data.coaching_insights) > 0

    @pytest.mark.asyncio
    async def test_sales_user_intelligence_service(self):
        from app.modules.intelligence.service import IntelligenceService
        from app.modules.intelligence.dto import SalesUserIntelligenceResponse
        service = IntelligenceService()
        org = _org()
        agent = _id()
        mock_session = self._make_mock_session()

        sales_data = await service.get_sales_user_intelligence(mock_session, org, agent)
        assert isinstance(sales_data, SalesUserIntelligenceResponse)
        assert sales_data.agent_id == agent
        assert len(sales_data.priority_actions) > 0
        assert len(sales_data.property_opportunities) > 0

    @pytest.mark.asyncio
    async def test_moat_metrics_indicators(self):
        from app.modules.intelligence.service import IntelligenceService
        from app.modules.intelligence.dto import MoatMetricsResponse
        service = IntelligenceService()
        org = _org()
        mock_session = self._make_mock_session()

        moat = await service.get_moat_metrics(mock_session, org)
        assert isinstance(moat, MoatMetricsResponse)
        assert moat.organization_id == org
        assert moat.data_coverage_score > Decimal("0")
        assert moat.outcome_density > Decimal("0")
        assert moat.evidence_grade == "VERIFIED_IN_CODE_AND_TESTS"

    @pytest.mark.asyncio
    async def test_competitive_capability_matrix_no_synthetic_benchmarks(self):
        from app.modules.intelligence.service import IntelligenceService
        from app.modules.intelligence.dto import CompetitiveCapabilityMatrixResponse
        service = IntelligenceService()

        matrix = await service.get_competitive_matrix()
        assert isinstance(matrix, CompetitiveCapabilityMatrixResponse)
        assert len(matrix.dimensions) >= 12
        assert len(matrix.evidence_records) >= 5
        assert all(rec["verified_passing"] is True for rec in matrix.evidence_records)

    @pytest.mark.asyncio
    async def test_channel_intelligence_rates_and_margins(self):
        from app.modules.intelligence.service import IntelligenceService
        from app.modules.intelligence.dto import ChannelIntelligenceResponse
        service = IntelligenceService()
        org = _org()
        mock_session = self._make_mock_session()

        ch_data = await service.get_channel_intelligence(mock_session, org)
        assert isinstance(ch_data, ChannelIntelligenceResponse)
        assert len(ch_data.channels) >= 5
        assert ch_data.top_performing_channel == "WHATSAPP"
        for ch in ch_data.channels:
            assert ch.volume > 0
            assert ch.gross_margin_pct > Decimal("0")

    @pytest.mark.asyncio
    async def test_coaching_signals_cite_underlying_events(self):
        from app.modules.intelligence.service import IntelligenceService
        from app.modules.intelligence.dto import AgentCoachingResponse
        service = IntelligenceService()
        org = _org()
        mock_session = self._make_mock_session()

        coaching = await service.get_coaching_signals(mock_session, org)
        assert isinstance(coaching, AgentCoachingResponse)
        assert coaching.total_signals > 0
        for sig in coaching.signals:
            assert len(sig.underlying_event_ids) > 0  # Signals must cite underlying events!
            assert len(sig.recommended_action) > 0


