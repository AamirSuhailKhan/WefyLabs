import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.broker import Broker
from app.modules.auth.service import create_access_token
from app.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_integration_provider_abstraction(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. List active integration providers
        res_providers = await ac.get("/api/v1/integrations/providers")
        assert res_providers.status_code == 200
        providers = res_providers.json()
        assert len(providers) >= 5
        ids = [p["provider_id"] for p in providers]
        assert "google_calendar" in ids
        assert "stripe" in ids
        assert "docusign" in ids
        assert "property_finder" in ids

        # 2. Test Calendar Provider (Google Calendar)
        cal_payload = {
            "provider_id": "google_calendar",
            "title": "Property Viewing with Client",
            "start_time": "2026-08-10T10:00:00Z",
            "end_time": "2026-08-10T11:00:00Z",
            "attendees": ["client@example.com"]
        }
        res_cal = await ac.post("/api/v1/integrations/calendar/events", json=cal_payload, headers=headers)
        assert res_cal.status_code == 200
        assert res_cal.json()["status"] == "success"
        assert res_cal.json()["provider"] == "google_calendar"

        # 3. Test E-Signature Provider (DocuSign)
        sig_payload = {
            "provider_id": "docusign",
            "document_name": "Tenancy_Agreement.pdf",
            "signer_email": "tenant@example.com"
        }
        res_sig = await ac.post("/api/v1/integrations/signature/request", json=sig_payload, headers=headers)
        assert res_sig.status_code == 200
        assert res_sig.json()["status"] == "sent"
        assert res_sig.json()["provider"] == "docusign"

        # 4. Test Portal Syndication Provider (Property Finder)
        portal_payload = {
            "provider_id": "property_finder",
            "property_id": "PROP_101",
            "title": "Marina Gate Penthouse",
            "price": 2850000.0,
            "location": "Dubai Marina"
        }
        res_portal = await ac.post("/api/v1/integrations/portal/publish", json=portal_payload, headers=headers)
        assert res_portal.status_code == 200
        assert res_portal.json()["status"] == "published"
        assert res_portal.json()["provider"] == "property_finder"

    app.dependency_overrides.clear()
