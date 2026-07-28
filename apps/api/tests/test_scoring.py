import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.score import Score
from app.services.lead_scorer import ExtractedData, calculate_score
from app.modules.auth.service import create_access_token

@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()

def test_hot_lead_scoring_logic():
    data = ExtractedData(
        budget_min=5000000,
        budget_max=7500000,
        preferred_locations=["Indiranagar", "Koramangala"],
        property_type="2bhk",
        transaction_type="buy",
        timeline="immediate",
        loan_status="pre_approved"
    )
    score, confidence, reasoning = calculate_score(data)
    assert score == "hot"
    assert confidence >= 0.70
    assert "Clear budget stated" in reasoning
    assert "Immediate timeline" in reasoning
    assert "Pre-approved loan" in reasoning

def test_warm_lead_scoring_logic():
    data = ExtractedData(
        budget_min=4000000,
        preferred_locations=["HSR Layout"],
        property_type="2bhk",
        timeline="3_months"
    )
    score, confidence, reasoning = calculate_score(data)
    assert score == "warm"
    assert 0.50 <= confidence <= 0.75

def test_cold_lead_scoring_logic():
    data = ExtractedData(
        timeline="6_months",
        preferred_locations=[]
    )
    score, confidence, reasoning = calculate_score(data)
    assert score == "cold"
    assert confidence <= 0.40

@pytest.mark.asyncio
async def test_qualify_endpoint_and_idempotency(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Trigger qualification (POST /api/v1/scoring/qualify)
        payload = {"lead_id": str(test_lead.id), "force": False}
        res = await ac.post("/api/v1/scoring/qualify", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["lead_id"] == str(test_lead.id)
        assert data["score"] in ("hot", "warm", "cold")
        assert "confidence" in data
        assert "reasoning" in data

        # 2. Check Lead updated in DB
        await db_session.refresh(test_lead)
        assert test_lead.status == "qualified"
        assert test_lead.qualified_at is not None

        # 3. Check Score audit trail created in DB
        score_stmt = select(Score).where(Score.lead_id == test_lead.id)
        score_obj = (await db_session.execute(score_stmt)).scalars().first()
        assert score_obj is not None
        assert score_obj.score == data["score"]

        # 4. Idempotent check (force=False returns cached score)
        res_idempotent = await ac.post("/api/v1/scoring/qualify", json={"lead_id": str(test_lead.id), "force": False}, headers=headers)
        assert res_idempotent.status_code == 200
        assert res_idempotent.json()["score"] == data["score"]

    app.dependency_overrides.clear()
