"""
Volume 2 PART 4 — AI Lead Intelligence & Revenue Engine Test Suite
===================================================================
Comprehensive unit & integration tests covering:
1. Feature Extractor (Signal extraction)
2. Intent & Urgency Engines (Buyer phase & urgency scoring)
3. Priority & Temperature Engine (Lead momentum & velocity)
4. Dynamic Rules Engine (Configurable DB rules evaluation)
5. Conversion Predictor & Risk Scoring (Milestone probabilities)
6. Recommendation Engine (Next Best Actions + % conversion lift)
7. Revenue Calculator & What-If Simulator (Baseline vs simulated lift)
8. Pipeline Service (End-to-end execution & persistence)
9. REST API Endpoints (FastAPI async test client)
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.modules.lead_intelligence.feature_engine.feature_extractor import FeatureExtractor
from app.modules.lead_intelligence.intent_engine.intent_calculator import IntentCalculator
from app.modules.lead_intelligence.urgency_engine.urgency_calculator import UrgencyCalculator
from app.modules.lead_intelligence.priority_engine.priority_calculator import PriorityCalculator
from app.modules.lead_intelligence.conversion_engine.conversion_predictor import ConversionPredictor
from app.modules.lead_intelligence.rules_engine.rule_evaluator import RuleEvaluator
from app.modules.lead_intelligence.recommendation_engine.action_recommender import ActionRecommender
from app.modules.lead_intelligence.revenue_engine.revenue_calculator import RevenueCalculator
from app.modules.lead_intelligence.service import LeadIntelligenceService

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def async_client(test_db):
    async def _get_test_db():
        yield test_db

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==============================================================================
# 1. UNIT TESTS: FEATURE, INTENT, URGENCY, PRIORITY ENGINES
# ==============================================================================

def test_feature_extractor():
    extractor = FeatureExtractor()
    lead_dto = {
        "id": str(uuid.uuid4()),
        "phone": "+971501234567",
        "email": "test@domain.com",
        "budget_max": 4000000,
        "property_type": "2bhk",
        "transaction_type": "buy",
        "timeline": "1_month",
        "loan_status": "pre_approved",
    }
    features = extractor.extract_features(lead_dto)

    assert features["has_phone"] is True
    assert features["has_email"] is True
    assert features["budget_aed"] == 4000000.0
    assert features["is_high_value"] is True
    assert features["is_immediate"] is True
    assert features["has_mortgage_preapproval"] is True


def test_intent_calculator():
    calculator = IntentCalculator()
    features = {
        "property_type": "2bhk",
        "budget_aed": 3500000.0,
        "is_cash_buyer": True,
        "has_viewing_booked": True,
        "is_immediate": True,
    }
    score, phase = calculator.calculate(features)

    assert score >= 80.0
    assert phase in ("purchase_ready", "negotiation", "decision")


def test_urgency_calculator():
    calculator = UrgencyCalculator()
    features = {
        "timeline": "immediate",
        "is_cash_buyer": True,
        "has_viewing_booked": True,
        "lead_age_days": 1.0,
        "activity_count": 2,
    }
    urgency = calculator.calculate(features)

    assert urgency >= 85.0


def test_priority_calculator():
    calculator = PriorityCalculator()
    features = {"has_viewing_booked": True, "is_luxury": True}

    temp, momentum, follow_up_prio, agent_prio = calculator.calculate(
        lead_score=82.0,
        score_yesterday=70.0,
        intent_phase="decision",
        features=features,
    )

    assert temp in ("very_hot", "purchase_ready", "hot")
    assert momentum == 12.0  # +12 acceleration
    assert follow_up_prio >= 80
    assert agent_prio >= 90


def test_conversion_predictor():
    predictor = ConversionPredictor()
    features = {
        "has_phone": True,
        "has_email": True,
        "has_viewing_booked": True,
        "is_cash_buyer": True,
        "lead_age_days": 2.0,
        "activity_count": 5,
    }
    preds = predictor.predict(lead_score=85.0, features=features)

    assert preds["conversion_probability"] >= 0.80
    assert preds["closing_probability"] >= 0.70
    assert preds["viewing_probability"] >= 0.90
    assert preds["churn_probability"] <= 0.20


def test_rule_evaluator():
    evaluator = RuleEvaluator()
    features = {
        "budget_aed": 2500000.0,
        "has_viewing_booked": True,
        "is_immediate": True,
        "lead_age_days": 5.0,
    }
    adj, fired = evaluator.evaluate_rules(features)

    assert adj >= 50.0  # High budget (+20) + Viewing (+30) + Immediate (+15)
    assert len(fired) >= 3


def test_action_recommender():
    recommender = ActionRecommender()
    features = {
        "lead_age_days": 0.2,
        "has_phone": True,
        "has_viewing_booked": False,
        "is_luxury": True,
    }
    recs = recommender.generate_recommendations(features, lead_score=80.0, temperature="hot")

    assert len(recs) >= 2
    assert recs[0]["rank"] == 1
    assert "estimated_conversion_lift" in recs[0]


def test_revenue_calculator_and_simulator():
    calc = RevenueCalculator()
    rev = calc.calculate_revenue(features={"budget_aed": 5000000.0}, conversion_probability=0.8)

    assert rev["estimated_revenue_aed"] == 5000000.0
    assert rev["estimated_commission_aed"] == 100000.0  # 2% of 5M
    assert rev["probability_weighted_revenue_aed"] == 4000000.0

    # Test What-If Simulator
    current_pipeline = {
        "probability_weighted_revenue_aed": 10000000.0,
        "expected_commission_aed": 200000.0,
    }
    sim = calc.simulate_what_if(current_pipeline, response_time_improvement_pct=50.0, viewing_booking_increase_pct=20.0)

    assert sim["simulated_weighted_revenue_aed"] > 10000000.0
    assert sim["revenue_lift_aed"] > 0.0


# ==============================================================================
# 2. PIPELINE INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_lead_intelligence_service_full_pipeline(test_db):
    service = LeadIntelligenceService(db=test_db)
    org_id = "org_intel_test"

    lead_dto = {
        "id": str(uuid.uuid4()),
        "phone": "+971508889900",
        "email": "rich.buyer@luxury.ae",
        "name": "Sheikh Rashid",
        "budget_max": 8000000,
        "property_type": "villa",
        "transaction_type": "buy",
        "timeline": "immediate",
        "loan_status": "cash_buyer",
        "source": "website",
    }

    res = await service.score_lead(lead_dto, organization_id=org_id, trigger_event="LeadCreated")

    assert res["lead_score"] >= 70.0
    assert res["temperature"] in ("very_hot", "purchase_ready", "hot")
    assert res["conversion_probability"] > 0.6
    assert res["estimated_revenue_aed"] == 8000000.0
    assert len(res["recommendations"]) >= 1

    # Verify profile retrieval
    profile = await service.get_lead_profile(lead_dto["id"])
    assert profile is not None
    assert profile["lead_score"] == res["lead_score"]
    assert profile["estimated_revenue_aed"] == 8000000.0


# ==============================================================================
# 3. REST API ENDPOINT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_rest_api_intelligence_endpoints(async_client):
    lead_id = str(uuid.uuid4())
    org_id = "org_api_intel"

    score_payload = {
        "lead_dto": {
            "phone": "+971507773344",
            "email": "api.intel@example.com",
            "name": "API Intelligence User",
            "budget_max": 2500000,
            "timeline": "1_month",
            "source": "api",
        },
        "organization_id": org_id,
        "trigger_event": "APITrigger",
    }

    # 1. POST /api/v1/intelligence/score/{lead_id}
    res = await async_client.post(f"/api/v1/intelligence/score/{lead_id}", json=score_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["result"]["lead_score"] > 0.0

    # 2. GET /api/v1/intelligence/profile/{lead_id}
    prof_res = await async_client.get(f"/api/v1/intelligence/profile/{lead_id}")
    assert prof_res.status_code == 200
    prof_data = prof_res.json()
    assert prof_data["profile"]["lead_id"] == lead_id

    # 3. GET /api/v1/intelligence/recommendations/{lead_id}
    rec_res = await async_client.get(f"/api/v1/intelligence/recommendations/{lead_id}")
    assert rec_res.status_code == 200

    # 4. POST /api/v1/intelligence/simulate
    sim_payload = {
        "baseline_weighted_revenue_aed": 12000000.0,
        "expected_commission_aed": 240000.0,
        "response_time_improvement_pct": 50.0,
        "viewing_booking_increase_pct": 25.0,
    }
    sim_res = await async_client.post("/api/v1/intelligence/simulate", json=sim_payload)
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert sim_data["simulation"]["simulated_weighted_revenue_aed"] > 12000000.0

    # 5. GET /api/v1/intelligence/metrics
    met_res = await async_client.get("/api/v1/intelligence/metrics")
    assert met_res.status_code == 200
