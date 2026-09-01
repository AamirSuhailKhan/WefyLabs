import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_super_admin_operations_platform(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Get Operations & Super Admin Control Overview
        res_ov = await ac.get("/api/v1/super-admin/overview", headers=headers)
        assert res_ov.status_code == 200
        data_ov = res_ov.json()
        assert data_ov["platform_status"] == "OPERATIONAL"
        assert "financials" in data_ov
        assert data_ov["financials"]["mrr_usd"] >= 0.0

        # 2. Get AI Observability & Cost Metrics
        res_ai = await ac.get("/api/v1/super-admin/ai-observability", headers=headers)
        assert res_ai.status_code == 200
        data_ai = res_ai.json()
        assert "total_prompt_tokens" in data_ai
        assert "avg_llm_latency_ms" in data_ai

        # 3. Get Active Incidents Dashboard
        res_inc = await ac.get("/api/v1/super-admin/incidents", headers=headers)
        assert res_inc.status_code == 200
        assert len(res_inc.json()) >= 1

        # 4. Impersonate Broker Session
        res_imp = await ac.post("/api/v1/super-admin/impersonate", json={"target_broker_id": str(test_broker.id)}, headers=headers)
        assert res_imp.status_code == 200
        assert res_imp.json()["impersonation_token"].startswith("imp_")

        # 5. Toggle Maintenance Mode
        res_maint = await ac.post("/api/v1/super-admin/maintenance-mode", json={"maintenance_enabled": True, "reason": "Security Patching"}, headers=headers)
        assert res_maint.status_code == 200
        assert res_maint.json()["maintenance_mode"] == "ENABLED"

    app.dependency_overrides.clear()
