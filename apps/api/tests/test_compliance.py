import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_compliance_and_security_endpoints(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Get Enterprise Security & Disaster Recovery Status
        res_sec = await ac.get("/api/v1/compliance/security-status", headers=headers)
        assert res_sec.status_code == 200
        data_sec = res_sec.json()
        assert data_sec["soc2_readiness"] == "compliant"
        assert data_sec["encryption_at_rest"] == "AES-256-GCM"

        # 2. Get Immutable Audit Logs
        res_audit = await ac.get("/api/v1/compliance/audit-logs", headers=headers)
        assert res_audit.status_code == 200
        logs = res_audit.json()
        assert len(logs) >= 1

        # 3. GDPR Data Export (Article 15)
        res_export = await ac.post("/api/v1/compliance/gdpr/export", json={"lead_id": str(test_lead.id)}, headers=headers)
        assert res_export.status_code == 200
        data_exp = res_export.json()
        assert data_exp["lead_id"] == str(test_lead.id)
        assert data_exp["phone"] == test_lead.phone

        # 4. GDPR Right to Be Forgotten (Article 17)
        res_forget = await ac.post("/api/v1/compliance/gdpr/forget", json={"lead_id": str(test_lead.id)}, headers=headers)
        assert res_forget.status_code == 200
        assert res_forget.json()["status"] == "success"

    app.dependency_overrides.clear()
