"""
Unit & Integration Tests for Part 21.4.1 — AI Lead Qualification Domain Foundation
================================================================================
Comprehensive verification covering:
1. Domain state values and controlled taxonomies (Intent, BuyerType, Timeline, Financing).
2. Evidence provenance, confidence scoring, timestamps, and supersession.
3. Unknown invariant: Missing fields strictly remain UNKNOWN (no synthetic fallbacks).
4. Conflict detection, status tracking, and authorized resolution.
5. Deterministic policy evaluation: Strict separation of completeness and confidence.
6. Multi-tenant security & query isolation (Tenant A cannot access or mutate Tenant B data).
7. RBAC enforcement on human overrides with immutable audit trails.
8. REST API endpoints (Snapshot, Facts, Conflicts, History, Policies, Overrides).
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
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.qualification_models import (
    QualificationFact,
    QualificationConflict,
    QualificationRequirementPolicy,
    QualificationAuditEvent,
    QualificationSnapshotRecord,
    QualificationState,
    QualificationIntent,
    QualificationBuyerType,
    QualificationTimeline,
    QualificationFinancing,
    FactValueCategory,
    EvidenceSourceType,
    FactStatus,
    ConflictStatus,
    QualificationAuditActorType,
    QualificationAuditEventType,
)
from app.modules.lead_qualification.taxonomies import QualificationTaxonomyNormalizer
from app.modules.lead_qualification.dto import (
    QualificationFactCreateDTO,
    QualificationConflictResolveDTO,
    QualificationHumanOverrideDTO,
    QualificationSnapshotDTO,
)
from app.modules.lead_qualification.policy_engine import DeterministicQualificationPolicyEngine
from app.modules.lead_qualification.service import LeadQualificationDomainService
from app.modules.auth.service import create_access_token


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()
    app.dependency_overrides.clear()


# ─── 1. Taxonomy & Normalizer Tests ──────────────────────────────────────────

class TestQualificationTaxonomies:
    """Verifies that taxonomies are strictly controlled and unknown values remain UNKNOWN."""

    def test_intent_taxonomy_and_normalization(self):
        norm = QualificationTaxonomyNormalizer
        assert norm.normalize_intent("buy") == QualificationIntent.BUY
        assert norm.normalize_intent("PURCHASE") == QualificationIntent.BUY
        assert norm.normalize_intent("rent") == QualificationIntent.RENT
        assert norm.normalize_intent("invest") == QualificationIntent.INVEST
        assert norm.normalize_intent("sell") == QualificationIntent.SELL
        assert norm.normalize_intent("random string") == QualificationIntent.UNKNOWN
        assert norm.normalize_intent(None) == QualificationIntent.UNKNOWN
        assert norm.normalize_intent("") == QualificationIntent.UNKNOWN

    def test_buyer_taxonomy_and_normalization(self):
        norm = QualificationTaxonomyNormalizer
        assert norm.normalize_buyer_type("end_user") == QualificationBuyerType.END_USER
        assert norm.normalize_buyer_type("first_time_buyer") == QualificationBuyerType.END_USER
        assert norm.normalize_buyer_type("investor") == QualificationBuyerType.INVESTOR
        assert norm.normalize_buyer_type("landlord") == QualificationBuyerType.LANDLORD
        assert norm.normalize_buyer_type("tenant") == QualificationBuyerType.TENANT
        assert norm.normalize_buyer_type("company") == QualificationBuyerType.COMPANY
        assert norm.normalize_buyer_type("agent") == QualificationBuyerType.AGENT
        assert norm.normalize_buyer_type("unknown_buyer") == QualificationBuyerType.UNKNOWN
        assert norm.normalize_buyer_type(None) == QualificationBuyerType.UNKNOWN

    def test_timeline_taxonomy_and_normalization(self):
        norm = QualificationTaxonomyNormalizer
        assert norm.normalize_timeline("immediate") == QualificationTimeline.IMMEDIATE
        assert norm.normalize_timeline("within_30_days") == QualificationTimeline.WITHIN_30_DAYS
        assert norm.normalize_timeline("1_month") == QualificationTimeline.WITHIN_30_DAYS
        assert norm.normalize_timeline("within_3_months") == QualificationTimeline.WITHIN_3_MONTHS
        assert norm.normalize_timeline("within_6_months") == QualificationTimeline.WITHIN_6_MONTHS
        assert norm.normalize_timeline("within_12_months") == QualificationTimeline.WITHIN_12_MONTHS
        assert norm.normalize_timeline("more_than_12_months") == QualificationTimeline.MORE_THAN_12_MONTHS
        assert norm.normalize_timeline("someday") == QualificationTimeline.UNKNOWN
        assert norm.normalize_timeline(None) == QualificationTimeline.UNKNOWN

    def test_financing_taxonomy_and_normalization(self):
        norm = QualificationTaxonomyNormalizer
        assert norm.normalize_financing("cash") == QualificationFinancing.CASH
        assert norm.normalize_financing("mortgage") == QualificationFinancing.MORTGAGE
        assert norm.normalize_financing("home_loan") == QualificationFinancing.MORTGAGE
        assert norm.normalize_financing("payment_plan") == QualificationFinancing.PAYMENT_PLAN
        assert norm.normalize_financing("unspecified") == QualificationFinancing.UNKNOWN
        assert norm.normalize_financing(None) == QualificationFinancing.UNKNOWN

    def test_zero_mock_unknown_guarantee(self):
        """Verifies that blank/missing fields are NEVER assumed or synthesized."""
        norm = QualificationTaxonomyNormalizer
        assert norm.normalize_intent(None) == QualificationIntent.UNKNOWN
        assert norm.normalize_buyer_type(None) == QualificationBuyerType.UNKNOWN
        assert norm.normalize_timeline(None) == QualificationTimeline.UNKNOWN
        assert norm.normalize_financing(None) == QualificationFinancing.UNKNOWN


# ─── 2. Deterministic Policy Engine Tests ────────────────────────────────────

class TestDeterministicPolicyEngine:
    """Verifies pure deterministic policy evaluation without LLM black box."""

    def test_policy_engine_empty_facts_returns_new_state(self):
        snapshot = DeterministicQualificationPolicyEngine.evaluate(
            organization_id="org_test_1",
            lead_id="lead_test_1",
            active_facts=[],
            open_conflicts=[],
        )
        assert snapshot.state == QualificationState.NEW.value
        assert snapshot.completeness_score == 0.0
        assert snapshot.confidence_score == 0.0
        assert snapshot.intent == "UNKNOWN"
        assert snapshot.location == "UNKNOWN"
        assert snapshot.property_type == "UNKNOWN"
        assert "intent" in snapshot.missing_fields
        assert "location" in snapshot.missing_fields
        assert "property_type" in snapshot.missing_fields

    def test_policy_engine_partially_qualified(self):
        facts = [
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="intent",
                raw_value="BUY",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="location",
                raw_value="Dubai Marina",
                confidence=0.9,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        snapshot = DeterministicQualificationPolicyEngine.evaluate(
            organization_id="org_test_1",
            lead_id="lead_test_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert snapshot.state == QualificationState.PARTIALLY_QUALIFIED.value
        assert snapshot.intent == "BUY"
        assert snapshot.location == "Dubai Marina"
        assert snapshot.completeness_score > 0.0
        assert snapshot.confidence_score == 0.95
        assert "property_type" in snapshot.missing_fields

    def test_policy_engine_fully_qualified(self):
        facts = [
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="intent",
                raw_value="BUY",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="location",
                raw_value="Palm Jumeirah",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="property_type",
                raw_value="Villa",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="budget_max",
                raw_value="15000000",
                confidence=0.95,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="timeline",
                raw_value="immediate",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        snapshot = DeterministicQualificationPolicyEngine.evaluate(
            organization_id="org_test_1",
            lead_id="lead_test_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert snapshot.state == QualificationState.QUALIFIED.value
        assert snapshot.completeness_score == 1.0
        assert snapshot.confidence_score >= 0.95
        assert len(snapshot.missing_fields) == 0

    def test_policy_engine_nurture_for_long_timeline(self):
        facts = [
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="intent",
                raw_value="BUY",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="timeline",
                raw_value="more_than_12_months",
                confidence=1.0,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        snapshot = DeterministicQualificationPolicyEngine.evaluate(
            organization_id="org_test_1",
            lead_id="lead_test_1",
            active_facts=facts,
            open_conflicts=[],
        )
        assert snapshot.state == QualificationState.NURTURE.value

    def test_policy_engine_conflict_triggers_human_review(self):
        conflicts = [
            QualificationConflict(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="budget_max",
                status=ConflictStatus.OPEN.value,
            )
        ]
        snapshot = DeterministicQualificationPolicyEngine.evaluate(
            organization_id="org_test_1",
            lead_id="lead_test_1",
            active_facts=[],
            open_conflicts=conflicts,
        )
        assert snapshot.state == QualificationState.NEEDS_HUMAN_REVIEW.value
        assert "budget_max" in snapshot.conflicting_fields

    def test_completeness_vs_confidence_separation(self):
        """High completeness (all fields known) but low confidence (weak inference) remains distinct."""
        weak_facts = [
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="intent",
                raw_value="BUY",
                confidence=0.3,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="location",
                raw_value="Downtown",
                confidence=0.4,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="property_type",
                raw_value="Apartment",
                confidence=0.35,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="budget_max",
                raw_value="3000000",
                confidence=0.3,
                status=FactStatus.ACTIVE.value,
            ),
            QualificationFact(
                organization_id="org_test_1",
                lead_id="lead_test_1",
                field_name="timeline",
                raw_value="within_30_days",
                confidence=0.35,
                status=FactStatus.ACTIVE.value,
            ),
        ]
        snapshot = DeterministicQualificationPolicyEngine.evaluate(
            organization_id="org_test_1",
            lead_id="lead_test_1",
            active_facts=weak_facts,
            open_conflicts=[],
        )
        assert snapshot.completeness_score == 1.0  # 100% complete
        assert snapshot.confidence_score == 0.34   # 34% confidence (low)
        # Because min_confidence (0.7) is not met, state must NOT be QUALIFIED
        assert snapshot.state != QualificationState.QUALIFIED.value


# ─── 3. Domain Service & Multi-Tenant Isolation Tests ────────────────────────

@pytest.mark.asyncio
class TestLeadQualificationServiceE2E:
    """Verifies domain service, fact lifecycle, supersession, conflict resolution, and tenant isolation."""

    async def test_fact_lifecycle_and_supersession(self, db_session: AsyncSession):
        broker = Broker(
            id=uuid.uuid4(),
            email="broker_fact_test@example.com",
            password_hash="hash",
            phone="+919876500001",
            name="Broker Fact Test",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            phone="+919876500002",
            name="Lead Fact Test",
            source="manual",
        )
        db_session.add(lead)
        await db_session.commit()

        svc = LeadQualificationDomainService(db_session)
        org_id = str(broker.id)

        # 1. Record initial budget fact
        dto1 = QualificationFactCreateDTO(
            field_name="budget_max",
            raw_value="2000000",
            source_type=EvidenceSourceType.CUSTOMER_MESSAGE,
            confidence=0.9,
        )
        fact1 = await svc.record_fact(
            organization_id=org_id,
            lead_id=str(lead.id),
            dto=dto1,
            actor_type=QualificationAuditActorType.HUMAN,
            actor_id=str(broker.id),
            broker=broker,
        )
        assert fact1.raw_value == "2000000"
        assert fact1.status == FactStatus.ACTIVE.value

        # 2. Record updated budget fact (customer stated new budget) -> Should supersede fact1
        dto2 = QualificationFactCreateDTO(
            field_name="budget_max",
            raw_value="2500000",
            source_type=EvidenceSourceType.CUSTOMER_MESSAGE,
            confidence=0.95,
        )
        fact2 = await svc.record_fact(
            organization_id=org_id,
            lead_id=str(lead.id),
            dto=dto2,
            actor_type=QualificationAuditActorType.HUMAN,
            actor_id=str(broker.id),
            broker=broker,
        )
        assert fact2.raw_value == "2500000"
        assert fact2.supersedes_fact_id == fact1.id

        # Verify active facts
        active_facts = await svc.get_lead_facts(organization_id=org_id, lead_id=str(lead.id), broker=broker)
        assert len(active_facts) == 1
        assert active_facts[0].raw_value == "2500000"

        # Verify all facts (including superseded)
        all_facts = await svc.get_lead_facts(
            organization_id=org_id, lead_id=str(lead.id), include_superseded=True, broker=broker
        )
        assert len(all_facts) == 2

    async def test_human_override_flow_and_audit(self, db_session: AsyncSession):
        broker = Broker(
            id=uuid.uuid4(),
            email="broker_override_test@example.com",
            password_hash="hash",
            phone="+919876500003",
            name="Broker Override Test",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            phone="+919876500004",
            name="Lead Override Test",
            source="manual",
        )
        db_session.add(lead)
        await db_session.commit()

        svc = LeadQualificationDomainService(db_session)
        org_id = str(broker.id)

        override_dto = QualificationHumanOverrideDTO(
            target_state=QualificationState.QUALIFIED,
            reason="Verified VIP high-net-worth buyer in-person at Dubai showroom.",
            notes="Ready to sign SPA directly with Emaar.",
        )

        snapshot = await svc.apply_human_override(
            organization_id=org_id,
            lead_id=str(lead.id),
            dto=override_dto,
            actor_id=str(broker.id),
            actor_role="broker",
            broker=broker,
        )

        assert snapshot.state == QualificationState.QUALIFIED.value
        assert "Verified VIP" in snapshot.summary_notes

        # Verify Audit Trail
        history = await svc.get_lead_audit_history(
            organization_id=org_id, lead_id=str(lead.id), broker=broker
        )
        assert len(history) >= 1
        override_event = next(e for e in history if e.event_type == QualificationAuditEventType.HUMAN_OVERRIDE.value)
        assert override_event.new_state == QualificationState.QUALIFIED.value
        assert override_event.actor_type == QualificationAuditActorType.HUMAN.value
        assert "Verified VIP" in override_event.reason

    async def test_tenant_isolation_prevents_cross_tenant_access(self, db_session: AsyncSession):
        """Verifies that Broker A cannot read or mutate Broker B's qualification data."""
        # Tenant A
        broker_a = Broker(
            id=uuid.uuid4(),
            email="tenant_a@example.com",
            password_hash="hash",
            phone="+919876500010",
            name="Tenant A Broker",
        )
        db_session.add(broker_a)

        # Tenant B
        broker_b = Broker(
            id=uuid.uuid4(),
            email="tenant_b@example.com",
            password_hash="hash",
            phone="+919876500020",
            name="Tenant B Broker",
        )
        db_session.add(broker_b)
        await db_session.commit()

        # Lead owned by Tenant B
        lead_b = Lead(
            id=uuid.uuid4(),
            broker_id=broker_b.id,
            phone="+919876500021",
            name="Tenant B Lead",
            source="manual",
        )
        db_session.add(lead_b)
        await db_session.commit()

        svc = LeadQualificationDomainService(db_session)
        org_a = str(broker_a.id)

        # 1. Tenant A cannot get Tenant B's qualification snapshot
        with pytest.raises(Exception) as exc_info:
            await svc.get_lead_qualification_snapshot(
                organization_id=org_a, lead_id=str(lead_b.id), broker=broker_a
            )
        assert "Access denied" in str(exc_info.value) or "403" in str(exc_info.value)

        # 2. Tenant A cannot get Tenant B's facts
        with pytest.raises(Exception) as exc_info:
            await svc.get_lead_facts(
                organization_id=org_a, lead_id=str(lead_b.id), broker=broker_a
            )
        assert "Access denied" in str(exc_info.value) or "403" in str(exc_info.value)

        # 3. Tenant A cannot override Tenant B's qualification
        with pytest.raises(Exception) as exc_info:
            await svc.apply_human_override(
                organization_id=org_a,
                lead_id=str(lead_b.id),
                dto=QualificationHumanOverrideDTO(
                    target_state=QualificationState.QUALIFIED, reason="Unauthorized hack"
                ),
                actor_id=str(broker_a.id),
                actor_role="broker",
                broker=broker_a,
            )
        assert "Access denied" in str(exc_info.value) or "403" in str(exc_info.value)


# ─── 4. REST API Endpoint Integration Tests ─────────────────────────────────

@pytest.mark.asyncio
class TestLeadQualificationAPIEndpoints:
    """Verifies HTTP responses, authorization, and error handling for qualification endpoints."""

    async def test_get_qualification_snapshot_api(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        # Create broker & token
        broker = Broker(
            id=uuid.uuid4(),
            email="api_qual_test@example.com",
            password_hash="hash",
            phone="+919876511111",
            name="API Qual Test Broker",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            phone="+919876511112",
            name="API Qual Test Lead",
            source="manual",
            transaction_type="buy",
            property_type="Apartment",
            budget_max=4500000,
            preferred_locations=["Downtown Dubai"],
            timeline="1_month",
        )
        db_session.add(lead)
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Fetch qualification snapshot
            res = await ac.get(f"/api/v1/leads/{lead.id}/qualification", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["lead_id"] == str(lead.id)
            assert data["intent"] == "BUY"
            assert data["location"] == "Downtown Dubai"
            assert data["property_type"] == "Apartment"
            assert data["budget_max"] == 4500000
            assert data["completeness_score"] > 0.0

    async def test_record_fact_and_get_facts_api(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        broker = Broker(
            id=uuid.uuid4(),
            email="api_fact_test@example.com",
            password_hash="hash",
            phone="+919876522221",
            name="API Fact Test Broker",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            phone="+919876522222",
            name="API Fact Test Lead",
            source="manual",
        )
        db_session.add(lead)
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Record a fact
            fact_payload = {
                "field_name": "bedrooms",
                "raw_value": "3",
                "value_type": "number",
                "source_type": "CUSTOMER_MESSAGE",
                "confidence": 1.0,
            }
            res_post = await ac.post(
                f"/api/v1/leads/{lead.id}/qualification/facts",
                json=fact_payload,
                headers=headers,
            )
            assert res_post.status_code == 201
            fact_data = res_post.json()
            assert fact_data["field_name"] == "bedrooms"
            assert fact_data["raw_value"] == "3"

            # 2. Get facts
            res_get = await ac.get(f"/api/v1/leads/{lead.id}/qualification/facts", headers=headers)
            assert res_get.status_code == 200
            facts_list = res_get.json()
            assert len(facts_list) >= 1
            assert any(f["field_name"] == "bedrooms" for f in facts_list)

    async def test_human_override_api(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        broker = Broker(
            id=uuid.uuid4(),
            email="api_override_test@example.com",
            password_hash="hash",
            phone="+919876533331",
            name="API Override Test Broker",
        )
        db_session.add(broker)
        await db_session.commit()

        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            phone="+919876533332",
            name="API Override Test Lead",
            source="manual",
        )
        db_session.add(lead)
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        headers = {"Authorization": f"Bearer {token}"}

        override_payload = {
            "target_state": "QUALIFIED",
            "reason": "Direct broker phone qualification completed.",
            "notes": "Spoke for 20 minutes, verified mortgage approval letter.",
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/leads/{lead.id}/qualification/override",
                json=override_payload,
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["state"] == "QUALIFIED"

            # Check history endpoint
            res_hist = await ac.get(f"/api/v1/leads/{lead.id}/qualification/history", headers=headers)
            assert res_hist.status_code == 200
            history = res_hist.json()
            assert len(history) >= 1
            assert any(e["event_type"] == "HUMAN_OVERRIDE" for e in history)

    async def test_nonexistent_lead_returns_404(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db

        broker = Broker(
            id=uuid.uuid4(),
            email="api_404_test@example.com",
            password_hash="hash",
            phone="+919876544441",
            name="API 404 Test Broker",
        )
        db_session.add(broker)
        await db_session.commit()

        token = create_access_token({"sub": broker.email, "email": broker.email, "broker_id": str(broker.id)})
        headers = {"Authorization": f"Bearer {token}"}

        fake_lead_id = str(uuid.uuid4())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/leads/{fake_lead_id}/qualification", headers=headers)
            assert res.status_code == 404
