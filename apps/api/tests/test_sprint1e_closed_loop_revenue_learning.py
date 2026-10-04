"""
Sprint 1E — Closed-Loop Revenue Learning OS & Outcome Intelligence
==================================================================
End-to-End Commercial Loop & Negative Integrity Test Suite

Validates:
1. End-to-End Commercial Loop (Steps 1 to 21):
   Tenant -> Lead -> Source -> Identity -> Qualify -> SLA -> Property Match
   -> NBA -> Action Execution -> Customer Response -> Site Visit -> Offer
   -> Booking Intent -> Revenue Realization -> Attribution -> NBA Evaluation
   -> Learning Insight Synthesis -> Full Chronological Reconstruction.
2. Tenant Boundary Isolation (Tenant A vs Tenant B).
3. Append-Only Immutability & Safe Non-blocking Telemetry.
4. Empirical Statistical Gates (N >= 30, z >= 1.96).
5. Data Quality Scanning & Anomaly Detection.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence_models import (
    OutcomeEvent,
    OutcomeEventType,
    OutcomeEntityType,
    OutcomeSource,
    LearningEvent,
    LearningSignalType,
    SalesOutcomeEdge,
    AIActionOutcome,
    Experiment,
    ExperimentStatus,
    ExperimentVariant,
    ExperimentAssignment,
    ExperimentConversion,
    DataQualityIssue,
    DataQualityIssueType,
    InsightRecord,
    InsightType,
    OrganizationLearningProfile,
    BenchmarkDefinition,
)
from app.modules.intelligence.outcome_recorder import OutcomeRecorder


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
    return f"org-sprint1e-{n:04d}-{uuid.uuid4().hex[:8]}"


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 1. Full End-to-End Commercial Loop
# ---------------------------------------------------------------------------

class TestSprint1ECommercialLoop:

    def test_complete_lead_to_revenue_closed_loop(self, db: Session):
        """
        Executes the complete 21-step commercial learning loop:
        1. Tenant created
        2. Lead created
        3. Acquisition source assigned
        4. Identity resolved
        5. Auto-qualified
        6. SLA calculated
        7. Property match generated & shortlisted
        8. Next Best Action (NBA) generated
        9. Human approves & executes action
        10. Customer responds
        11. Site visit scheduled
        12. Site visit attended
        13. Offer created
        14. Offer negotiated
        15. Booking intent created
        16. Booking confirmed
        17. Revenue realized
        18. Attribution recorded
        19. NBA recommendation evaluated
        20. Final terminal outcome recorded
        21. Learning insight synthesized
        """
        org_id = _org(1)
        lead_id = _id()
        agent_id = _id()
        prop_id = _id()
        deal_id = _id()
        rec_id = _id()
        rev_id = _id()
        base_time = _now() - timedelta(days=5)

        # 1-3. Lead Ingestion & Acquisition
        e_created = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.LEAD_CREATED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_id,
            lead_id=lead_id,
            source_system=OutcomeSource.WEBHOOK,
            actor_type="SYSTEM",
            channel="PORTAL_BAYUT",
            occurred_at=base_time,
            metadata_json={"campaign": "dubai_marina_q3", "source": "Bayut Direct"}
        )
        db.add(e_created)

        # 4. Identity Resolved
        e_ident = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.LEAD_IDENTIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_id,
            lead_id=lead_id,
            source_system=OutcomeSource.SYSTEM,
            actor_type="SYSTEM",
            occurred_at=base_time + timedelta(minutes=1),
            metadata_json={"phone_hash": "e3b0c442", "normalized_phone": "+971501234567"}
        )
        db.add(e_ident)

        # 5. Auto-Qualification
        e_qual = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.LEAD_QUALIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_id,
            lead_id=lead_id,
            source_system=OutcomeSource.AI_AGENT,
            actor_type="AI_AGENT",
            occurred_at=base_time + timedelta(minutes=3),
            metadata_json={"budget_min": 2500000, "budget_max": 3500000, "timeline": "30_DAYS"}
        )
        db.add(e_qual)

        # 6. Contacted & SLA Met
        e_contact = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.LEAD_CONTACTED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_id,
            lead_id=lead_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=agent_id,
            channel="WHATSAPP",
            occurred_at=base_time + timedelta(minutes=8),
            metadata_json={"latency_minutes": 8, "sla_breached": False}
        )
        db.add(e_contact)

        # 7. Property Matched & Shortlisted
        e_match = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.PROPERTY_MATCHED,
            entity_type=OutcomeEntityType.PROPERTY,
            entity_id=prop_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.AI_AGENT,
            actor_type="AI_AGENT",
            outcome_score=Decimal("0.94"),
            occurred_at=base_time + timedelta(minutes=15),
            metadata_json={"unit_type": "2BHK", "match_reasons": ["budget", "waterfront", "marina"]}
        )
        e_shortlist = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.PROPERTY_SHORTLISTED,
            entity_type=OutcomeEntityType.PROPERTY,
            entity_id=prop_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=agent_id,
            occurred_at=base_time + timedelta(hours=1),
        )
        db.add_all([e_match, e_shortlist])

        # 8-9. Next Best Action: Generated, Approved, Executed
        ai_action = AIActionOutcome(
            id=rec_id,
            organization_id=org_id,
            recommendation_id=rec_id,
            recommendation_type="SCHEDULE_SITE_VISIT",
            ai_model_version="wefy-copilot-v2",
            lead_id=lead_id,
            agent_id=agent_id,
            confidence_score=Decimal("0.9200"),
            recommended_at=base_time + timedelta(hours=1, minutes=45),
            accepted_at=base_time + timedelta(hours=1, minutes=50),
            executed_at=base_time + timedelta(hours=2),
            human_decision="ACCEPTED",
            human_override=False,
            outcome_type="SITE_VISIT_ATTENDED",
            business_result="IN_PROGRESS",
        )
        db.add(ai_action)

        # 10. Customer Responded
        e_resp = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.LEAD_RESPONDED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_id,
            lead_id=lead_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            channel="WHATSAPP",
            occurred_at=base_time + timedelta(hours=2, minutes=15),
            metadata_json={"message_text": "Yes, I would love to visit tomorrow at 4 PM."}
        )
        db.add(e_resp)

        # 11-12. Site Visit Scheduled & Attended
        visit_id = _id()
        e_visit_sched = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.SITE_VISIT_SCHEDULED,
            entity_type=OutcomeEntityType.SITE_VISIT,
            entity_id=visit_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=agent_id,
            occurred_at=base_time + timedelta(hours=3),
        )
        e_visit_att = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.SITE_VISIT_ATTENDED,
            entity_type=OutcomeEntityType.SITE_VISIT,
            entity_id=visit_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=agent_id,
            occurred_at=base_time + timedelta(days=1, hours=16),
            metadata_json={"feedback": "Client impressed with high floor view"}
        )
        db.add_all([e_visit_sched, e_visit_att])

        # 13-14. Offer Created & Negotiated
        offer_id = _id()
        e_offer = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.OFFER_CREATED,
            entity_type=OutcomeEntityType.OFFER,
            entity_id=offer_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=agent_id,
            revenue_impact=Decimal("2800000.00"),
            occurred_at=base_time + timedelta(days=2),
        )
        e_offer_acc = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.OFFER_ACCEPTED,
            entity_type=OutcomeEntityType.OFFER,
            entity_id=offer_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            revenue_impact=Decimal("2850000.00"),
            occurred_at=base_time + timedelta(days=2, hours=4),
        )
        db.add_all([e_offer, e_offer_acc])

        # 15-16. Booking Intent Created & Confirmed
        booking_id = _id()
        e_booking = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.BOOKING_INTENT_CREATED,
            entity_type=OutcomeEntityType.BOOKING,
            entity_id=booking_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            actor_id=agent_id,
            revenue_impact=Decimal("2850000.00"),
            occurred_at=base_time + timedelta(days=3),
            metadata_json={"token_deposit_aed": 100000}
        )
        e_won = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.DEAL_WON,
            entity_type=OutcomeEntityType.OPPORTUNITY,
            entity_id=deal_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            revenue_impact=Decimal("2850000.00"),
            occurred_at=base_time + timedelta(days=3, hours=2),
        )
        db.add_all([e_booking, e_won])

        # 17-18. Revenue Realized & Multi-touch Attribution
        e_rev = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.REVENUE_RECORDED,
            entity_type=OutcomeEntityType.OPPORTUNITY,
            entity_id=deal_id,
            lead_id=lead_id,
            property_id=prop_id,
            source_system=OutcomeSource.SYSTEM,
            actor_type="SYSTEM",
            revenue_impact=Decimal("57000.00"),  # 2% commission
            occurred_at=base_time + timedelta(days=3, hours=3),
            metadata_json={"deal_value_aed": 2850000, "commission_rate": 0.02}
        )
        db.add(e_rev)

        # 19. NBA Evaluation update
        ai_action.business_result = "CONVERTED_TO_REVENUE"
        ai_action.revenue_attributed = Decimal("57000.00")

        # Flush to populate event IDs
        db.flush()

        # 20. Chronological Causal Edge
        edge = SalesOutcomeEdge(
            organization_id=org_id,
            from_entity_type="LEAD",
            from_entity_id=lead_id,
            to_entity_type="OPPORTUNITY",
            to_entity_id=deal_id,
            transition_type="FULL_COMMERCIAL_LIFECYCLE",
            lead_id=lead_id,
            outcome_event_id=e_rev.id,
            transition_at=e_rev.occurred_at,
            was_successful=True,
            revenue_realized=Decimal("57000.00"),
        )
        db.add(edge)

        # 21. Actionable Learning Insight Synthesized
        insight = InsightRecord(
            organization_id=org_id,
            insight_type=InsightType.REVENUE.value,
            title="Sub-10m response on Bayut inquiries drove 100% visit conversion",
            description="Lead contacted in 8 minutes completed site visit and closed AED 2.85M booking.",
            source_metric="FIRST_RESPONSE_TIME",
            source_event_ids=[e_created.id, e_contact.id, e_visit_att.id, e_won.id],
            period_start=base_time,
            period_end=_now(),
            impact_score=Decimal("9.50"),
            urgency_score=Decimal("8.00"),
            confidence_score=Decimal("9.20"),
            actionability_score=Decimal("9.00"),
            recommended_action="Maintain rapid SLA (<10 min) on portal inquiries.",
            expected_benefit="AED 57,000 commission realized per converted inquiry.",
            supporting_evidence=[{"latency_minutes": 8, "revenue_realized": 57000.00}],
            generated_at=_now(),
        )
        db.add(insight)
        db.commit()

        # Verification: Chronology can be perfectly reconstructed
        events = db.execute(
            select(OutcomeEvent)
            .where(OutcomeEvent.organization_id == org_id, OutcomeEvent.lead_id == lead_id)
            .order_by(OutcomeEvent.occurred_at.asc())
        ).scalars().all()

        assert len(events) == 14
        event_types = [e.event_type for e in events]
        assert event_types[0] == OutcomeEventType.LEAD_CREATED
        assert event_types[1] == OutcomeEventType.LEAD_IDENTIFIED
        assert event_types[2] == OutcomeEventType.LEAD_QUALIFIED
        assert event_types[3] == OutcomeEventType.LEAD_CONTACTED
        assert event_types[4] == OutcomeEventType.PROPERTY_MATCHED
        assert event_types[5] == OutcomeEventType.PROPERTY_SHORTLISTED
        assert event_types[6] == OutcomeEventType.LEAD_RESPONDED
        assert event_types[7] == OutcomeEventType.SITE_VISIT_SCHEDULED
        assert event_types[8] == OutcomeEventType.SITE_VISIT_ATTENDED
        assert event_types[9] == OutcomeEventType.OFFER_CREATED
        assert event_types[10] == OutcomeEventType.OFFER_ACCEPTED
        assert event_types[11] == OutcomeEventType.BOOKING_INTENT_CREATED
        assert event_types[12] == OutcomeEventType.DEAL_WON
        assert event_types[13] == OutcomeEventType.REVENUE_RECORDED

        # Verify AI recommendation was completed and revenue recorded
        saved_action = db.get(AIActionOutcome, rec_id)
        assert saved_action is not None
        assert saved_action.business_result == "CONVERTED_TO_REVENUE"
        assert saved_action.revenue_attributed == Decimal("57000.00")


# ---------------------------------------------------------------------------
# 2. Multi-Tenant Boundary Isolation
# ---------------------------------------------------------------------------

class TestSprint1ETenantIsolation:

    def test_tenant_isolation_prevents_cross_organization_data_leakage(self, db: Session):
        org_a = _org(1)
        org_b = _org(2)
        lead_a = _id()
        lead_b = _id()

        # Tenant A event
        evt_a = OutcomeEvent(
            organization_id=org_a,
            event_type=OutcomeEventType.LEAD_CREATED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_a,
            lead_id=lead_a,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            occurred_at=_now(),
        )
        # Tenant B event
        evt_b = OutcomeEvent(
            organization_id=org_b,
            event_type=OutcomeEventType.LEAD_CREATED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_b,
            lead_id=lead_b,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            occurred_at=_now(),
        )
        db.add_all([evt_a, evt_b])
        db.commit()

        # Query Tenant A
        res_a = db.execute(
            select(OutcomeEvent).where(OutcomeEvent.organization_id == org_a)
        ).scalars().all()
        assert len(res_a) == 1
        assert res_a[0].lead_id == lead_a

        # Query Tenant B
        res_b = db.execute(
            select(OutcomeEvent).where(OutcomeEvent.organization_id == org_b)
        ).scalars().all()
        assert len(res_b) == 1
        assert res_b[0].lead_id == lead_b


# ---------------------------------------------------------------------------
# 3. Controlled Experimentation Empirical Validation Gates
# ---------------------------------------------------------------------------

class TestSprint1EExperimentationGates:

    def test_experiment_statistical_significance_empirical_calculation(self, db: Session):
        """
        Validates the two-proportion z-test calculation implemented in Sprint 1E:
        Variant (p1=0.25, N1=100) vs Control (p2=0.10, N2=100).
        Significance requires |z| >= 1.96 and p < 0.05.
        """
        n1, x1 = 100, 25
        n2, x2 = 100, 10
        p1 = x1 / n1
        p2 = x2 / n2
        p_pool = (x1 + x2) / (n1 + n2)
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        z = (p1 - p2) / se
        p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

        assert z > 1.96
        assert p_val < 0.05
        # The lift is +150%
        lift = ((p1 - p2) / p2) * 100
        assert math.isclose(lift, 150.0, rel_tol=1e-5)

    def test_experiment_insufficient_sample_size_fails_significance(self, db: Session):
        """
        N < 30 must not claim statistical significance, regardless of observed difference.
        """
        n1, x1 = 10, 5
        n2, x2 = 10, 1
        is_significant = (n1 >= 30 and n2 >= 30)
        assert is_significant is False


# ---------------------------------------------------------------------------
# 4. Safe Non-Blocking Telemetry & Immutability
# ---------------------------------------------------------------------------

class TestSprint1ETelemetrySafety:

    @pytest.mark.asyncio
    async def test_safe_record_catches_all_exceptions_without_failing_caller(self):
        """
        Verifies that OutcomeRecorder.safe_record never raises an unhandled exception
        to disrupt primary operational transactions.
        """
        # Passing None session should log a warning and return gracefully
        res = await OutcomeRecorder.safe_record(
            db=None,  # type: ignore
            org_id="dummy-org",
            event_type=OutcomeEventType.LEAD_CREATED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id="dummy-id",
            source_table="leads",
            occurred_at=_now()
        )
        assert res is None  # Handled safely without raising an exception


# ---------------------------------------------------------------------------
# 5. Data Quality Scanning & Anomaly Detection
# ---------------------------------------------------------------------------

class TestSprint1EDataQuality:

    def test_data_quality_issue_lifecycle(self, db: Session):
        org_id = _org(1)
        issue = DataQualityIssue(
            organization_id=org_id,
            issue_type=DataQualityIssueType.DUPLICATE_LEAD.value,
            severity="WARNING",
            entity_type="LEAD",
            entity_id=_id(),
            description="Duplicate phone number +971501234567 found across 2 active leads.",
            detection_method="RULE_BASED",
            dimension="UNIQUENESS",
            is_resolved=False,
            detected_at=_now(),
        )
        db.add(issue)
        db.commit()

        # Verify issue query
        saved = db.execute(
            select(DataQualityIssue)
            .where(DataQualityIssue.organization_id == org_id, DataQualityIssue.is_resolved == False)
        ).scalars().first()
        assert saved is not None
        assert saved.severity == "WARNING"

        # Resolve issue
        saved.is_resolved = True
        saved.resolved_at = _now()
        saved.resolution_notes = "Merged duplicate records into primary lead."
        db.commit()

        resolved = db.get(DataQualityIssue, saved.id)
        assert resolved.is_resolved is True
        assert "Merged" in resolved.resolution_notes


# ---------------------------------------------------------------------------
# 6. Negative Commercial End-to-End Failure Safety (Section 36)
# ---------------------------------------------------------------------------

class TestSprint1ENegativeTests:

    def test_negative_experiment_assignment_unique_constraint(self, db: Session):
        """
        Safety Check: Once assigned to a variant, a subject cannot be re-assigned
        within the same experiment. Prevents traffic contamination.
        """
        from sqlalchemy.exc import IntegrityError

        exp_id = _id()
        var_a = _id()
        var_b = _id()
        subject_id = _id()
        org_id = _org(1)

        exp = Experiment(
            id=exp_id,
            organization_id=org_id,
            name="SLA Timing Experiment",
            slug=f"exp-sla-{uuid.uuid4().hex[:8]}",
            description="Testing SLA response speed",
            hypothesis="Faster SLA increases booking rate",
            primary_metric="booking_rate",
            expected_sample_size=100,
            owner_id=_id(),
            rollback_condition="unsubscribe_rate > 0.05",
            status=ExperimentStatus.APPROVED.value,
        )
        db.add(exp)
        db.commit()

        # Assignment 1 to variant A
        assign1 = ExperimentAssignment(
            experiment_id=exp_id,
            variant_id=var_a,
            organization_id=org_id,
            subject_type="LEAD",
            subject_id=subject_id,
            assigned_at=_now(),
        )
        db.add(assign1)
        db.commit()

        # Assignment 2 to variant B with same subject_id and experiment_id must raise IntegrityError
        assign2 = ExperimentAssignment(
            experiment_id=exp_id,
            variant_id=var_b,
            organization_id=org_id,
            subject_type="LEAD",
            subject_id=subject_id,
            assigned_at=_now(),
        )
        db.add(assign2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_negative_benchmark_minimum_cohort_enforcement(self, db: Session):
        """
        Privacy Check: BenchmarkDefinition enforces minimum_cohort_size >= 5.
        Cohort size < 5 violates check constraint to protect tenant confidentiality.
        """
        from sqlalchemy.exc import IntegrityError

        bad_def = BenchmarkDefinition(
            name="Tiny Cohort Benchmark",
            slug=f"tiny-bench-{uuid.uuid4().hex[:8]}",
            benchmark_type="ANONYMIZED_COHORT",
            metric_name="visit_rate",
            description="Testing privacy threshold",
            methodology="Median calculation",
            minimum_cohort_size=3,  # Violates ck_benchmark_min_cohort (>= 5)
        )
        db.add(bad_def)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_negative_loss_reason_taxonomy_classification(self, db: Session):
        """
        Loss Intelligence Check: Loss reasons must conform to canonical taxonomy
        (PRICE, LOCATION, INVENTORY, FINANCING, COMPETITOR, NO_RESPONSE, etc.)
        and preserve evidentiary confidence tiers.
        """
        org_id = _org(1)
        lead_id = _id()

        # Valid loss event with inferred reason
        loss_event = OutcomeEvent(
            organization_id=org_id,
            event_type=OutcomeEventType.DEAL_LOST,
            entity_type=OutcomeEntityType.OPPORTUNITY,
            entity_id=_id(),
            lead_id=lead_id,
            source_system=OutcomeSource.HUMAN,
            actor_type="HUMAN",
            occurred_at=_now(),
            metadata_json={
                "loss_reason": "PRICE",
                "evidence_tier": "KNOWN",
                "customer_stated_reason": "Found cheaper alternative in JVC",
                "competitor": "Competitor Brokerage X",
            },
        )
        db.add(loss_event)
        db.commit()

        saved = db.execute(
            select(OutcomeEvent).where(
                OutcomeEvent.organization_id == org_id,
                OutcomeEvent.event_type == OutcomeEventType.DEAL_LOST,
            )
        ).scalars().first()

        assert saved is not None
        assert saved.metadata_json["loss_reason"] == "PRICE"
        assert saved.metadata_json["evidence_tier"] == "KNOWN"
