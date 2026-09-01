import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_crm_enterprise_deduplicate_and_commission(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Test Deduplication Check (Duplicate found by phone)
        dedup_payload = {
            "phone": test_lead.phone,
            "email": "lead@example.com"
        }
        res_dedup = await ac.post("/api/v1/crm/enterprise/deduplicate/check", json=dedup_payload, headers=headers)
        assert res_dedup.status_code == 200
        data_dedup = res_dedup.json()
        assert data_dedup["is_duplicate"] is True
        assert data_dedup["matching_lead_id"] == str(test_lead.id)

        # 2. Test Commission Calculator
        comm_payload = {
            "property_sale_price": 10000000, # 1 Crore INR
            "gross_commission_rate_pct": 2.0,
            "agent_split_pct": 70.0
        }
        res_comm = await ac.post("/api/v1/crm/enterprise/commission/calculate", json=comm_payload, headers=headers)
        assert res_comm.status_code == 200
        data_comm = res_comm.json()
        assert data_comm["total_gci"] == 200000.0
        assert data_comm["agent_net_commission"] == 140000.0
        assert data_comm["brokerage_commission"] == 60000.0

        # 3. Test Activity Timeline
        res_timeline = await ac.get(f"/api/v1/crm/enterprise/leads/{test_lead.id}/timeline", headers=headers)
        assert res_timeline.status_code == 200
        data_tl = res_timeline.json()
        assert data_tl["lead_id"] == str(test_lead.id)
        assert len(data_tl["activities"]) >= 1

    app.dependency_overrides.clear()
