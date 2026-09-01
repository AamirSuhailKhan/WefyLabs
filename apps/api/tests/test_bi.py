import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_executive_analytics_bi_endpoints(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Get Executive BI Summary & Anomaly Alerts
        res_summary = await ac.get("/api/v1/bi/executive-summary", headers=headers)
        assert res_summary.status_code == 200
        data_summary = res_summary.json()
        assert "revenue_ytd" in data_summary
        assert "pipeline_total_value" in data_summary
        assert "anomalies" in data_summary
        assert len(data_summary["anomalies"]) >= 1

        # 2. Ask Natural Language Analytics Query
        nl_payload = {"query": "Why did conversion rate change this month?"}
        res_nl = await ac.post("/api/v1/bi/ask-nl-query", json=nl_payload, headers=headers)
        assert res_nl.status_code == 200
        data_nl = res_nl.json()
        assert data_nl["query"] == "Why did conversion rate change this month?"
        assert "explanation_markdown" in data_nl
        assert len(data_nl["data_points"]) >= 1

    app.dependency_overrides.clear()
