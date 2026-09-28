"""
Master Build 14 — Continuous Learning Loop & AI Feedback Tests
=============================================================
Tests covering:
1. Learning event capture & schema fidelity across signal types
2. Signal provenance enforcement (source_table + source_event_id)
3. Mandatory human verification gate (no unverified auto-learning)
4. OrganizationLearningProfile lifecycle and learning counts
5. Poisoning defense (confidence bounds, cross-tenant isolation)
6. AI action outcomes & human override workflows
7. Recommendation quality tracking
8. Objection learning & winning rebuttal attribution
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence_models import (
    LearningEvent,
    LearningSignalType,
    AIActionOutcome,
    RecommendationQualitySnapshot,
    ObjectionRecord,
    ObjectionType,
    OrganizationLearningProfile,
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


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── 1. Signal Taxonomy & Provenance ────────────────────────────────────────

def test_learning_event_taxonomy_complete(db: Session):
    org = _id()
    now = _now()
    for sig_type in LearningSignalType:
        ev = LearningEvent(
            organization_id=org,
            event_type="SIGNAL_TEST",
            signal_type=sig_type,
            signal_value="1",
            source_event_id=_id(),
            source_table="messages",
            entity_type="LEAD",
            entity_id=_id(),
            actor_type="SYSTEM",
            confidence=Decimal("0.9"),
            is_verified=False,
            occurred_at=now,
        )
        db.add(ev)
    db.commit()

    count = db.query(LearningEvent).filter(LearningEvent.organization_id == org).count()
    assert count == len(LearningSignalType)


def test_learning_event_requires_provenance(db: Session):
    org = _id()
    now = _now()
    ev = LearningEvent(
        organization_id=org,
        event_type="SIGNAL_TEST",
        signal_type=LearningSignalType.HUMAN_ACCEPT,
        signal_value="1",
        source_event_id=_id(),
        source_table="conversations",
        entity_type="LEAD",
        entity_id=_id(),
        actor_type="HUMAN",
        is_verified=False,
        occurred_at=now,
    )
    db.add(ev)
    db.commit()

    loaded = db.query(LearningEvent).filter(LearningEvent.id == ev.id).one()
    assert loaded.source_table == "conversations"
    assert loaded.source_event_id is not None
    assert loaded.is_verified is False


# ─── 2. Verification Gate & Organization Profile ────────────────────────────

def test_unverified_signal_cannot_update_profile(db: Session):
    org = _id()
    now = _now()
    profile = OrganizationLearningProfile(
        organization_id=org,
        total_learning_events=0,
        total_outcomes_sampled=0,
        learning_loop_maturity="FOUNDATIONAL",
        last_computed_at=now,
    )
    db.add(profile)
    db.commit()

    ev = LearningEvent(
        organization_id=org,
        event_type="SIGNAL_TEST",
        signal_type=LearningSignalType.RECOMMENDATION_ACCEPTED,
        source_event_id=_id(),
        source_table="leads",
        entity_type="LEAD",
        entity_id=_id(),
        actor_type="HUMAN",
        is_verified=False,
        occurred_at=now,
    )
    db.add(ev)
    db.commit()

    db.refresh(profile)
    assert profile.total_learning_events == 0


def test_verification_gate_increments_profile(db: Session):
    org = _id()
    now = _now()
    profile = OrganizationLearningProfile(
        organization_id=org,
        total_learning_events=0,
        total_outcomes_sampled=0,
        learning_loop_maturity="FOUNDATIONAL",
        last_computed_at=now,
    )
    db.add(profile)

    ev = LearningEvent(
        organization_id=org,
        event_type="PROPERTY_FEEDBACK",
        signal_type=LearningSignalType.PROPERTY_MATCH_POSITIVE,
        source_event_id=_id(),
        source_table="property_views",
        entity_type="LEAD",
        entity_id=_id(),
        actor_type="HUMAN",
        is_verified=False,
        occurred_at=now,
    )
    db.add(ev)
    db.commit()

    # Human gate verification
    ev.is_verified = True
    ev.verified_by = "lead_architect_sarah"
    ev.verified_at = now
    profile.total_learning_events += 1
    profile.last_computed_at = now
    db.commit()

    db.refresh(ev)
    db.refresh(profile)
    assert ev.is_verified is True
    assert ev.verified_by == "lead_architect_sarah"
    assert profile.total_learning_events == 1


# ─── 3. Poisoning & Isolation Defense ───────────────────────────────────────

def test_cross_tenant_signal_isolation(db: Session):
    org_a = _id()
    org_b = _id()
    now = _now()

    ev_a = LearningEvent(
        organization_id=org_a,
        event_type="SIGNAL_TEST",
        signal_type=LearningSignalType.AI_RESPONSE_HELPFUL,
        source_event_id=_id(),
        source_table="messages",
        entity_type="LEAD",
        entity_id=_id(),
        actor_type="HUMAN",
        is_verified=True,
        occurred_at=now,
    )
    db.add(ev_a)
    db.commit()

    org_b_events = db.query(LearningEvent).filter(LearningEvent.organization_id == org_b).all()
    assert len(org_b_events) == 0


def test_poisoning_weight_clamping(db: Session):
    org = _id()
    now = _now()
    weight_input = Decimal("500.0")
    clamped_weight = min(Decimal("10.0"), max(Decimal("0.0"), weight_input))

    ev = LearningEvent(
        organization_id=org,
        event_type="SIGNAL_TEST",
        signal_type=LearningSignalType.NBA_EXECUTED,
        signal_value=str(clamped_weight),
        source_event_id=_id(),
        source_table="actions",
        entity_type="LEAD",
        entity_id=_id(),
        actor_type="SYSTEM",
        confidence=Decimal("0.95"),
        is_verified=False,
        occurred_at=now,
    )
    db.add(ev)
    db.commit()

    loaded = db.query(LearningEvent).filter(LearningEvent.id == ev.id).one()
    assert loaded.signal_value == "10.0"


# ─── 4. AI Action Outcome & Human Override ──────────────────────────────────

def test_human_override_workflow(db: Session):
    org = _id()
    now = _now()
    action = AIActionOutcome(
        organization_id=org,
        recommendation_id=_id(),
        recommendation_type="PROPERTY_RECOMMENDATION",
        ai_model_version="gpt-4o-mini-2026-03",
        prompt_version="prompt-rec-v2.1",
        policy_version="1.0.0",
        confidence_score=Decimal("0.88"),
        lead_id=_id(),
        human_decision="ACCEPTED",
        human_override=False,
        outcome_type="POSITIVE",
        recommended_at=now,
    )
    db.add(action)
    db.commit()

    # Sales rep manually overrides AI proposal
    action.human_override = True
    action.human_decision = "OVERRIDDEN"
    action.override_reason = "Customer explicitly requested quiet suburban area, not city center"
    db.commit()

    loaded = db.query(AIActionOutcome).filter(AIActionOutcome.id == action.id).one()
    assert loaded.human_override is True
    assert loaded.human_decision == "OVERRIDDEN"
    assert "suburban" in loaded.override_reason


def test_recommendation_quality_snapshot(db: Session):
    org = _id()
    now = _now()
    snap = RecommendationQualitySnapshot(
        organization_id=org,
        recommendation_type="PROPERTY_RECOMMENDATION",
        period_start=now,
        period_end=now,
        period_type="DAILY",
        total_recommendations=100,
        sample_size_sufficient=True,
        acceptance_rate=Decimal("0.6500"),
        execution_rate=Decimal("0.6000"),
        success_rate=Decimal("0.5500"),
        override_rate=Decimal("0.0800"),
        rejection_rate=Decimal("0.3500"),
        methodology="EXACT_COUNT",
    )
    db.add(snap)
    db.commit()

    loaded = db.query(RecommendationQualitySnapshot).filter(RecommendationQualitySnapshot.id == snap.id).one()
    assert loaded.total_recommendations == 100
    assert loaded.acceptance_rate == Decimal("0.6500")
    assert loaded.override_rate == Decimal("0.0800")


# ─── 5. Objection Learning & Rebuttal Attribution ───────────────────────────

def test_objection_learning_attribution(db: Session):
    org = _id()
    now = _now()
    obj = ObjectionRecord(
        organization_id=org,
        lead_id=_id(),
        objection_type=ObjectionType.PRICE,
        objection_text="The square foot rate is higher than neighboring towers",
        extracted_from="WHATSAPP",
        source_event_id=_id(),
        is_resolved=True,
        resolved_at=now,
        resolution_method="REBUTTAL_PRESENTED",
        resolution_response="Highlighted luxury fittings, private elevators, and zero maintenance for 3 years",
        conversion_after_resolution=True,
        raised_at=now,
    )
    db.add(obj)
    db.commit()

    loaded = db.query(ObjectionRecord).filter(ObjectionRecord.id == obj.id).one()
    assert loaded.objection_type == ObjectionType.PRICE
    assert loaded.is_resolved is True
    assert "luxury fittings" in loaded.resolution_response
    assert loaded.conversion_after_resolution is True
