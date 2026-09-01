"""
Volume 2 PART 2 — AI Lead Enrichment Engine Comprehensive Test Suite
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.database import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.enrichment_models import LeadEnrichment, ConfidenceScore, EnrichmentHistory
from app.modules.enrichment.normalizers import (
    PhoneNormalizer, CurrencyNormalizer, LocationNormalizer, PropertyNormalizer
)
from app.modules.enrichment.extractors import (
    RegexExtractor, DictionaryExtractor, RuleExtractor
)
from app.modules.enrichment.classifiers import (
    IntentClassifier, BudgetClassifier, QualityClassifier
)
from app.modules.enrichment.confidence import ScoringEngine, ProvenanceManager
from app.modules.enrichment.service import LeadEnrichmentService


# ─── 1. Unit Tests: Normalizers ───────────────────────────────────────────────

def test_phone_normalizer():
    res1 = PhoneNormalizer.normalize("+971 50 123 4567")
    assert res1["e164"] == "+971501234567"
    assert res1["country"] == "United Arab Emirates"
    assert res1["iso2"] == "AE"
    assert res1["is_valid"] is True
    assert res1["confidence"] >= 0.9

    res2 = PhoneNormalizer.normalize("1-555-234-5678")
    assert res2["e164"] == "+15552345678"
    assert res2["iso2"] == "US"

    res3 = PhoneNormalizer.normalize("123")
    assert res3["is_valid"] is False


def test_currency_normalizer():
    res1 = CurrencyNormalizer.normalize("1.5M AED")
    assert res1["amount"] == 1500000.0
    assert res1["currency"] == "AED"
    assert res1["amount_aed"] == 1500000.0
    assert res1["amount_usd"] > 400000.0

    res2 = CurrencyNormalizer.normalize("$500k")
    assert res2["amount"] == 500000.0
    assert res2["currency"] == "USD"
    assert res2["amount_aed"] == round(500000.0 * 3.6725, 2)


def test_location_normalizer():
    res = LocationNormalizer.normalize(city="Dubai", raw_location="Looking for 2bhk in Dubai Marina or Downtown")
    assert res["city"] == "Dubai"
    assert res["country"] == "United Arab Emirates"
    assert "Dubai Marina" in res["preferred_areas"]
    assert "Downtown" in res["preferred_areas"]


def test_property_normalizer():
    res = PropertyNormalizer.normalize(property_type_raw="2bhk", notes="Need 2 bed 2 bath apartment")
    assert res["property_type"] == "2bhk"
    assert res["bedrooms"] == 2
    assert res["bathrooms"] == 2


# ─── 2. Unit Tests: Extractors & Classifiers ─────────────────────────────

def test_regex_and_rule_extractors():
    regex_ext = RegexExtractor()
    rule_ext = RuleExtractor()

    notes = "Budget is 2.5 million AED. Looking for investment property within 30 days."
    extracted = regex_ext.extract(notes, {})
    
    assert "2.5" in str(extracted.get("budget_raw", ""))
    assert extracted.get("purpose") == "investment"
    assert extracted.get("timeline") == "1_month"

    rule_res = rule_ext.extract("", {"phone": "+971501234567"})
    assert rule_res.get("country") == "United Arab Emirates"
    assert rule_res.get("default_currency") == "AED"


def test_quality_and_budget_classifiers():
    q_res = QualityClassifier.evaluate(
        has_phone=True,
        has_email=True,
        budget_aed=3000000.0,
        timeline="immediate",
        urgency="high",
        property_type="2bhk"
    )
    assert q_res["quality_tier"] == "hot"
    assert q_res["overall_quality_score"] >= 75.0

    b_res = BudgetClassifier.classify(budget_aed=3000000.0, property_type="2bhk")
    assert b_res["budget_tier"] == "luxury"
    assert b_res["is_realistic"] is True


# ─── 3. Unit Tests: Data Provenance Guard ────────────────────────────────────

def test_provenance_manager():
    upd, reason = ProvenanceManager.should_update_field(
        existing_source_type="observed",
        existing_confidence=0.9,
        new_source_type="inferred",
        new_confidence=0.95
    )
    assert upd is False
    assert "Cannot overwrite higher precedence" in reason

    upd2, _ = ProvenanceManager.should_update_field(
        existing_source_type="inferred",
        existing_confidence=0.8,
        new_source_type="inferred",
        new_confidence=0.6
    )
    assert upd2 is False

    upd3, _ = ProvenanceManager.should_update_field(
        existing_source_type="inferred",
        existing_confidence=0.8,
        new_source_type="observed",
        new_confidence=0.9
    )
    assert upd3 is True


# ─── 4. Integration Tests: Service & DB Persistence ──────────────────────────

@pytest.mark.asyncio
async def test_enrichment_service_full_pipeline(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        name="Enrichment Test Broker",
        email=f"enrich_broker_{uuid.uuid4().hex[:6]}@example.com",
        phone="+971501112233",
        agency_name="Beetle Real Estate"
    )
    db_session.add(broker)
    await db_session.commit()

    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        phone="+971509998877",
        name="Aamir Khan",
        source="facebook",
        budget_max=2000000,
        property_type="2bhk",
        notes=[{"content": "Looking for 2bhk in Dubai Marina. Urgent investment within 1 month. Cash buyer."}]
    )
    db_session.add(lead)
    await db_session.commit()

    service = LeadEnrichmentService(db=db_session)
    lead_dto = {
        "id": str(lead.id),
        "organization_id": str(broker.id),
        "phone": lead.phone,
        "name": lead.name,
        "source": lead.source,
        "budget_max": lead.budget_max,
        "property_type": lead.property_type,
        "notes": lead.notes
    }
    result = await service.enrich_lead(lead_dto=lead_dto, trigger_source="UnitTest")

    assert result["status"] == "completed"
    assert result["quality_tier"] in ["hot", "warm"]
    assert result["financial_profile"]["amount_canonical_aed"] == 2000000.0
    assert result["location_profile"]["city"] == "Dubai"
    assert "Dubai Marina" in result["location_profile"]["preferred_locations"]

    # Verify DB persistence
    await db_session.flush()
    stmt = select(LeadEnrichment).where(LeadEnrichment.lead_id == str(lead.id))
    res = await db_session.execute(stmt)
    enrichment_record = res.scalar_one_or_none()
    assert enrichment_record is not None, "LeadEnrichment record should be saved in DB"
    assert enrichment_record.overall_quality_score > 0.0

    # Verify ConfidenceScore records
    c_stmt = select(ConfidenceScore).where(ConfidenceScore.lead_id == str(lead.id))
    c_res = await db_session.execute(c_stmt)
    scores = c_res.scalars().all()
    assert len(scores) > 0, "ConfidenceScore records should be saved in DB"


# ─── 5. Integration Tests: API Endpoints ──────────────────────────────────────

@pytest.mark.asyncio
async def test_enrichment_api_endpoints(db_session: AsyncSession):
    # Override get_db dependency to use the active SQLite test session
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db

    broker = Broker(
        id=uuid.uuid4(),
        name="API Test Broker",
        email=f"api_broker_{uuid.uuid4().hex[:6]}@example.com",
        phone="+971504445566",
        agency_name="Beetle Real Estate"
    )
    db_session.add(broker)
    await db_session.commit()

    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        phone="+971551112233",
        name="Sarah Jenkins",
        source="google",
        budget_max=3500000,
        property_type="villa",
        notes=[{"content": "Looking for villa in Palm Jumeirah. High budget."}]
    )
    db_session.add(lead)
    await db_session.commit()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Trigger Enrich Endpoint
            enrich_res = await ac.post(f"/api/v1/enrichment/enrich/{lead.id}")
            assert enrich_res.status_code == 200
            data = enrich_res.json()
            assert data["status"] == "completed"
            assert data["quality_tier"] in ["hot", "warm"]

            # 2. Get Profile Endpoint
            profile_res = await ac.get(f"/api/v1/enrichment/profile/{lead.id}")
            assert profile_res.status_code == 200
            p_data = profile_res.json()
            assert p_data["lead_id"] == str(lead.id)
            assert len(p_data["confidence_scores"]) > 0

            # 3. Metrics Endpoint
            metrics_res = await ac.get("/api/v1/enrichment/metrics")
            assert metrics_res.status_code == 200
            m_data = metrics_res.json()
            assert m_data["total_enrichments"] >= 1
    finally:
        app.dependency_overrides.clear()
