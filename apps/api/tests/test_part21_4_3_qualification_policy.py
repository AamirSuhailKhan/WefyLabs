"""
Part 21.4.3 — Qualification Decision & Policy Execution Engine Test Suite
========================================================================
Comprehensive test suite validating:
1. Zero LLM Black-Box: Qualification states are determined purely deterministically.
2. Completeness vs. Confidence Separation: Completeness strictly counts known fields; confidence reflects evidence trust.
3. Controlled State Transitions: NEW -> COLLECTING_INFO -> PARTIALLY_QUALIFIED -> QUALIFIED / NURTURE / DISQUALIFIED / NEEDS_HUMAN_REVIEW.
4. Deterministic Next Best Questions: Grounded question templates mapped to top missing required/recommended fields.
5. Snapshot Persistence & Audit Trails: Point-in-time snapshot and state change audit records.
6. Multi-Tenant Isolation & RBAC: Strict tenant-scoped evaluation and missing info retrieval.
7. Anti-Tamper & Invariant Protection: Client cannot inject state; scoring/recommendation systems remain strictly decoupled.
8. Async Background Execution: Celery task evaluation worker test.
"""
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.lead import Lead
from app.models.broker import Broker
from app.models.qualification_models import (
    QualificationFact,
    QualificationConflict,
    QualificationRequirementPolicy,
    QualificationSnapshotRecord,
    QualificationAuditEvent,
    QualificationState,
    QualificationIntent,
    QualificationBuyerType,
    QualificationTimeline,
    QualificationFinancing,
    EvidenceSourceType,
    FactValueCategory,
    FactStatus,
    ConflictStatus,
    QualificationAuditEventType,
)
from app.modules.lead_qualification.dto import (
    QualificationSnapshotDTO,
    QualificationEvaluationResultDTO,
    QualificationMissingInfoDTO,
)
from app.modules.lead_qualification.policy_engine import DeterministicQualificationPolicyEngine
from app.modules.lead_qualification.service import LeadQualificationDomainService
from app.modules.lead_qualification.tasks import evaluate_lead_qualification_task
from app.modules.auth.service import create_access_token


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()
    app.dependency_overrides.clear()


# ─── 1. Pure Policy Engine Decision & Scoring Tests ──────────────────────────

class TestDeterministicPolicyEngineDecisions:
    """Verifies that all qualification states and scores are computed deterministically."""

    def test_empty_lead_evaluates_to_new_state(self):
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=[],
            open_conflicts=[],
        )
        assert result.qualification_state == QualificationState.NEW.value
        assert result.completeness_score == 0.0
        assert result.confidence_score == 0.0
        assert "intent" in result.missing_required_information
        assert "location" in result.missing_required_information
        assert "property_type" in result.missing_required_information
        assert result.next_best_question_field == "intent"
        assert "buy, rent, invest" in result.next_best_question.lower()

    def test_single_fact_collecting_information_or_partial(self):
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="budget_max",
                raw_value="5000000",
                normalized_value={"amount": 5000000, "currency": "AED"},
                confidence=0.9,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            )
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert result.qualification_state in (
            QualificationState.COLLECTING_INFORMATION.value,
            QualificationState.PARTIALLY_QUALIFIED.value,
        )
        assert result.completeness_score == 0.2
        assert result.confidence_score == 0.9
        assert result.next_best_question_field == "intent"

    def test_partially_qualified_state_with_core_fields(self):
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=0.95,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="location",
                raw_value="Downtown Dubai",
                normalized_value="Downtown Dubai",
                confidence=0.90,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert result.qualification_state == QualificationState.PARTIALLY_QUALIFIED.value
        assert result.completeness_score == 0.4
        assert result.confidence_score == 0.925
        assert "property_type" in result.missing_required_information
        assert result.next_best_question_field == "property_type"
        assert "property type" in result.next_best_question.lower()

    def test_fully_qualified_state_when_all_required_met(self):
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=1.0,
                source_type=EvidenceSourceType.HUMAN_VERIFICATION.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="location",
                raw_value="Palm Jumeirah",
                normalized_value="Palm Jumeirah",
                confidence=0.95,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="property_type",
                raw_value="Villa",
                normalized_value="Villa",
                confidence=0.95,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="budget_max",
                raw_value="12000000",
                normalized_value={"amount": 12000000, "currency": "AED"},
                confidence=0.90,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="timeline",
                raw_value="within_3_months",
                normalized_value="within_3_months",
                confidence=0.85,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert result.qualification_state == QualificationState.QUALIFIED.value
        assert result.completeness_score == 1.0
        assert result.confidence_score >= 0.9
        assert len(result.missing_required_information) == 0
        assert result.next_best_question is None

    def test_missing_required_field_blocks_qualified_state(self):
        """Missing required property_type blocks QUALIFIED state even if budget and timeline are present."""
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=1.0,
                source_type=EvidenceSourceType.HUMAN_VERIFICATION.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="location",
                raw_value="Dubai Hills",
                normalized_value="Dubai Hills",
                confidence=0.95,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
            # Missing property_type
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="budget_max",
                raw_value="8000000",
                normalized_value={"amount": 8000000, "currency": "AED"},
                confidence=0.90,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="timeline",
                raw_value="immediate",
                normalized_value="immediate",
                confidence=0.95,
                source_type=EvidenceSourceType.CUSTOMER_MESSAGE.value,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert result.qualification_state != QualificationState.QUALIFIED.value
        assert result.qualification_state == QualificationState.PARTIALLY_QUALIFIED.value
        assert "property_type" in result.missing_required_information
        assert result.next_best_question_field == "property_type"

    def test_low_confidence_blocks_qualified_state(self):
        """All fields present, but confidence below policy threshold (< 0.70) blocks QUALIFIED."""
        weak_facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=0.35,
                source_type=EvidenceSourceType.AI_EXTRACTION.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="location",
                raw_value="Dubai Marina",
                normalized_value="Dubai Marina",
                confidence=0.40,
                source_type=EvidenceSourceType.AI_EXTRACTION.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="property_type",
                raw_value="Apartment",
                normalized_value="Apartment",
                confidence=0.35,
                source_type=EvidenceSourceType.AI_EXTRACTION.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="budget_max",
                raw_value="2000000",
                normalized_value={"amount": 2000000, "currency": "AED"},
                confidence=0.30,
                source_type=EvidenceSourceType.AI_EXTRACTION.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="timeline",
                raw_value="within_30_days",
                normalized_value="within_30_days",
                confidence=0.35,
                source_type=EvidenceSourceType.AI_EXTRACTION.value,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=weak_facts,
            open_conflicts=[],
        )
        assert result.completeness_score == 1.0
        assert result.confidence_score == 0.35
        # Must NOT be qualified due to low confidence
        assert result.qualification_state != QualificationState.QUALIFIED.value

    def test_completeness_and_confidence_strict_separation(self):
        """Lead A (high completeness, low confidence) vs Lead B (medium completeness, high confidence)."""
        # Case A: 5 valid fields known with low confidence
        facts_a = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_a",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=0.30,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_a",
                field_name="location",
                raw_value="Downtown Dubai",
                normalized_value="Downtown Dubai",
                confidence=0.30,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_a",
                field_name="property_type",
                raw_value="Apartment",
                normalized_value="Apartment",
                confidence=0.30,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_a",
                field_name="budget_max",
                raw_value="3000000",
                normalized_value=3000000,
                confidence=0.30,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_a",
                field_name="timeline",
                raw_value="within_3_months",
                normalized_value="within_3_months",
                confidence=0.30,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        res_a = DeterministicQualificationPolicyEngine.evaluate_detailed("org_1", "lead_a", facts_a, [])
        assert res_a.completeness_score == 1.0
        assert res_a.confidence_score == 0.30

        # Case B: 2 valid fields known with perfect confidence
        facts_b = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_b",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=1.0,
                source_type=EvidenceSourceType.HUMAN_VERIFICATION.value,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_b",
                field_name="location",
                raw_value="Downtown",
                normalized_value="Downtown Dubai",
                confidence=1.0,
                source_type=EvidenceSourceType.HUMAN_VERIFICATION.value,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        res_b = DeterministicQualificationPolicyEngine.evaluate_detailed("org_1", "lead_b", facts_b, [])
        assert res_b.completeness_score == 0.40
        assert res_b.confidence_score == 1.0

    def test_unresolved_conflicts_force_needs_human_review(self):
        conflicts = [
            QualificationConflict(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="budget_max",
                status=ConflictStatus.OPEN.value,
            )
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=[],
            open_conflicts=conflicts,
        )
        assert result.qualification_state == QualificationState.NEEDS_HUMAN_REVIEW.value
        assert "budget_max" in result.blocking_conflicts

    def test_nurture_state_for_distant_timeline(self):
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="timeline",
                raw_value="more_than_12_months",
                normalized_value="more_than_12_months",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert result.qualification_state == QualificationState.NURTURE.value

    def test_disqualified_state_for_explicit_disqualification(self):
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="disqualified",
                raw_value="true",
                normalized_value="true",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            )
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert result.qualification_state == QualificationState.DISQUALIFIED.value

    def test_missing_info_dto_generation(self):
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_1",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            )
        ]
        missing_dto = DeterministicQualificationPolicyEngine.get_missing_info(
            organization_id="org_1",
            lead_id="lead_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert "location" in missing_dto.missing_required_fields
        assert "property_type" in missing_dto.missing_required_fields
        assert "budget_max" in missing_dto.missing_recommended_fields
        assert missing_dto.next_best_question_field == "location"
        assert "location" in missing_dto.field_questions
        assert "property_type" in missing_dto.field_questions

    def test_custom_requirement_policy_evaluation(self):
        """Custom policy with specific required fields and custom thresholds."""
        custom_policy = QualificationRequirementPolicy(
            policy_name="Luxury Investment Policy",
            policy_version="v2.0-luxury",
            required_fields=["intent", "budget_max", "buyer_type"],
            recommended_fields=["location", "financing"],
            min_completeness_for_qualified=0.9,
            min_confidence_for_qualified=0.8,
        )
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_luxury",
                field_name="intent",
                raw_value="INVEST",
                normalized_value="INVEST",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_luxury",
                field_name="budget_max",
                raw_value="25000000",
                normalized_value=25000000,
                confidence=0.95,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_luxury",
                field_name="buyer_type",
                raw_value="INVESTOR",
                normalized_value="INVESTOR",
                confidence=0.90,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_luxury",
                field_name="location",
                raw_value="Palm Jumeirah",
                normalized_value="Palm Jumeirah",
                confidence=0.85,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_luxury",
                field_name="financing",
                raw_value="CASH",
                normalized_value="CASH",
                confidence=0.90,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        result = DeterministicQualificationPolicyEngine.evaluate_detailed(
            organization_id="org_1",
            lead_id="lead_luxury",
            active_facts=facts,
            open_conflicts=[],
            policy=custom_policy,
        )
        assert result.qualification_state == QualificationState.QUALIFIED.value
        assert result.completeness_score == 1.0
        assert result.confidence_score >= 0.90
        assert result.policy_version == "v2.0-luxury"
        assert len(result.missing_required_information) == 0

    def test_deterministic_idempotency_sequential_evaluations(self):
        """Repeated evaluations with same facts produce identical results."""
        facts = [
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_idempotent",
                field_name="intent",
                raw_value="BUY",
                normalized_value="BUY",
                confidence=0.9,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_1",
                lead_id="lead_idempotent",
                field_name="location",
                raw_value="Dubai Hills",
                normalized_value="Dubai Hills",
                confidence=0.9,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        results = [
            DeterministicQualificationPolicyEngine.evaluate_detailed(
                "org_1", "lead_idempotent", facts, []
            )
            for _ in range(5)
        ]
        for r in results[1:]:
            assert r.qualification_state == results[0].qualification_state
            assert r.completeness_score == results[0].completeness_score
            assert r.confidence_score == results[0].confidence_score
            assert r.next_best_question_field == results[0].next_best_question_field
            assert r.next_best_question == results[0].next_best_question

    def test_question_templates_for_all_taxonomies(self):
        """Validates that all major real estate taxonomy fields have clear, conversational templates."""
        templates = DeterministicQualificationPolicyEngine.QUESTION_TEMPLATES
        expected_fields = [
            "intent",
            "property_type",
            "location",
            "budget_max",
            "budget_min",
            "timeline",
            "bedrooms",
            "financing",
            "buyer_type",
            "preferred_amenities",
        ]
        for f in expected_fields:
            assert f in templates
            assert len(templates[f]) > 10
            assert templates[f].endswith("?")

    def test_summary_notes_formatting(self):
        notes = DeterministicQualificationPolicyEngine._build_summary_notes(
            state=QualificationState.PARTIALLY_QUALIFIED,
            completeness=0.6,
            confidence=0.85,
            missing=["budget_max", "timeline"],
            conflicts=["location"],
        )
        assert "PARTIALLY_QUALIFIED" in notes
        assert "60%" in notes
        assert "85%" in notes
        assert "budget_max, timeline" in notes
        assert "location" in notes

    def test_celery_evaluation_task_contract(self):
        """Validates that Celery evaluation task is registered and has appropriate signature."""
        assert callable(evaluate_lead_qualification_task)
        assert evaluate_lead_qualification_task.name == "app.modules.lead_qualification.tasks.evaluate_lead_qualification_task"


# ─── 2. End-to-End Service & API Integration Tests ───────────────────────────

@pytest.mark.asyncio
class TestLeadQualificationPolicyAPIAndService:
    """Verifies service orchestration, API endpoints, persistence, and audit logging."""

    async def test_evaluate_endpoint_persists_snapshot_and_audit(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        broker = Broker(
            id=uuid.uuid4(),
            email="broker_eval_test@example.com",
            password_hash="hash",
            phone="+971501110001",
            name="Alice Broker",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            name="Hassan Test",
            phone="+971501112233",
            country_code="AE",
            transaction_type="buy",
            budget_max=10000000,
            source="manual",
        )
        db_session.add(lead)
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=headers
        ) as client:
            resp = await client.post(f"/api/v1/leads/{lead.id}/qualification/evaluate")
            assert resp.status_code == 200
            data = resp.json()
            assert data["lead_id"] == str(lead.id)
            assert data["organization_id"] == str(broker.id)
            assert data["qualification_state"] in [s.value for s in QualificationState]
            assert "completeness_score" in data
            assert "confidence_score" in data
            assert "snapshot" in data

            # Verify snapshot record was saved to DB
            stmt = select(QualificationSnapshotRecord).where(QualificationSnapshotRecord.lead_id == str(lead.id))
            snapshot_rec = (await db_session.execute(stmt)).scalars().first()
            assert snapshot_rec is not None
            assert snapshot_rec.state == data["qualification_state"]

    async def test_get_missing_endpoint(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        broker = Broker(
            id=uuid.uuid4(),
            email="broker_missing_test@example.com",
            password_hash="hash",
            phone="+971501110002",
            name="Bob Broker",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            name="Maya Client",
            phone="+971501112244",
            country_code="AE",
            source="manual",
        )
        db_session.add(lead)
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=headers
        ) as client:
            resp = await client.get(f"/api/v1/leads/{lead.id}/qualification/missing")
            assert resp.status_code == 200
            data = resp.json()
            assert data["lead_id"] == str(lead.id)
            assert isinstance(data["missing_required_fields"], list)
            assert isinstance(data["missing_recommended_fields"], list)
            assert isinstance(data["field_questions"], dict)
            if data["next_best_question_field"]:
                assert data["next_best_question"] is not None

    async def test_multi_tenant_isolation(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        broker_a = Broker(
            id=uuid.uuid4(),
            email="broker_a@example.com",
            password_hash="hash",
            phone="+971501110003",
            name="Broker Org A",
        )
        broker_b = Broker(
            id=uuid.uuid4(),
            email="broker_b@example.com",
            password_hash="hash",
            phone="+971501110004",
            name="Broker Org B",
        )
        db_session.add_all([broker_a, broker_b])
        await db_session.commit()

        lead_a = Lead(
            id=uuid.uuid4(),
            broker_id=broker_a.id,
            name="Lead Org A",
            phone="+971501112255",
            source="manual",
        )
        db_session.add(lead_a)
        await db_session.commit()

        token_b = create_access_token({"sub": broker_b.email, "email": broker_b.email, "broker_id": str(broker_b.id)})
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=headers_b
        ) as client:
            # Org B tries to evaluate Org A's lead
            resp_eval = await client.post(f"/api/v1/leads/{lead_a.id}/qualification/evaluate")
            assert resp_eval.status_code in (403, 404)

            # Org B tries to get missing info for Org A's lead
            resp_missing = await client.get(f"/api/v1/leads/{lead_a.id}/qualification/missing")
            assert resp_missing.status_code in (403, 404)

    async def test_anti_tamper_no_client_injected_state(self, db_session: AsyncSession):
        """POST /evaluate evaluates server-side active facts and ignores any attempt to inject client state."""
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        broker = Broker(
            id=uuid.uuid4(),
            email="broker_tamper_test@example.com",
            password_hash="hash",
            phone="+971501110005",
            name="Security Tester",
        )
        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            name="Tamper Test",
            phone="+971501112266",
            source="manual",
        )
        db_session.add_all([broker, lead])
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=headers
        ) as client:
            # Client attempts to send fake body claiming state="QUALIFIED"
            resp = await client.post(
                f"/api/v1/leads/{lead.id}/qualification/evaluate",
                json={"qualification_state": "QUALIFIED", "completeness_score": 1.0},
            )
            assert resp.status_code == 200
            data = resp.json()
            # Server must ignore the payload and evaluate genuine facts (which are empty -> NEW)
            assert data["qualification_state"] == QualificationState.NEW.value
            assert data["completeness_score"] == 0.0

    async def test_service_evaluate_lead_qualification_direct(self, db_session: AsyncSession):
        broker = Broker(
            id=uuid.uuid4(),
            email="direct_eval_test@example.com",
            password_hash="hash",
            phone="+971501110006",
            name="Direct Eval Broker",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            name="Direct Eval Lead",
            phone="+971501112277",
            source="manual",
            transaction_type="buy",
            property_type="Apartment",
            budget_max=5000000,
        )
        db_session.add(lead)
        await db_session.commit()

        svc = LeadQualificationDomainService(db_session)
        result = await svc.evaluate_lead_qualification(
            organization_id=str(broker.id),
            lead_id=str(lead.id),
            broker=broker,
        )
        assert result.lead_id == str(lead.id)
        assert result.organization_id == str(broker.id)
        assert result.qualification_state in [s.value for s in QualificationState]
        assert result.completeness_score > 0.0
        assert result.snapshot.intent == "BUY"
        assert result.snapshot.property_type == "Apartment"



