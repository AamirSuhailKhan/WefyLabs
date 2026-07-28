import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()

@pytest.mark.asyncio
async def test_lead_crud_and_pipeline_flow(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create Lead (POST /api/v1/leads)
        create_payload = {
            "phone": "+919876543210",
            "name": "Karan Johar",
            "source": "manual",
            "budget_min": 6000000,
            "budget_max": 8500000,
            "property_type": "3bhk",
            "transaction_type": "buy",
            "preferred_locations": ["Indiranagar", "Koramangala"],
            "timeline": "1_month",
            "loan_status": "in_process",
            "notes": "Client requested high-rise apartment with balcony."
        }
        res_create = await ac.post("/api/v1/leads", json=create_payload, headers=headers)
        assert res_create.status_code == 201
        lead_data = res_create.json()
        lead_id = lead_data["id"]

        assert lead_data["name"] == "Karan Johar"
        assert lead_data["phone"] == "+919876543210"
        assert lead_data["source"] == "manual"
        assert lead_data["status"] == "pending"
        assert lead_data["pipeline_stage"] == "new"
        assert len(lead_data["notes"]) == 1
        assert lead_data["notes"][0]["content"] == "Client requested high-rise apartment with balcony."

        # 2. Get Single Lead Detail (GET /api/v1/leads/{lead_id})
        res_detail = await ac.get(f"/api/v1/leads/{lead_id}", headers=headers)
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["id"] == lead_id
        assert detail["conversation_count"] == 0

        # 3. Patch Lead Status (PATCH /api/v1/leads/{lead_id}/status)
        res_status = await ac.patch(
            f"/api/v1/leads/{lead_id}/status",
            json={"status": "qualified"},
            headers=headers
        )
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "qualified"
        assert res_status.json()["qualified_at"] is not None

        # 4. Patch Lead Stage (PATCH /api/v1/leads/{lead_id}/stage) - Move to closed_won
        res_stage = await ac.patch(
            f"/api/v1/leads/{lead_id}/stage",
            json={"stage": "closed_won"},
            headers=headers
        )
        assert res_stage.status_code == 200
        assert res_stage.json()["pipeline_stage"] == "closed_won"
        assert res_stage.json()["status"] == "converted"  # Auto-transitioned

        # 5. Add Note to Lead (POST /api/v1/leads/{lead_id}/notes)
        res_note = await ac.post(
            f"/api/v1/leads/{lead_id}/notes",
            json={"content": "Token advance received ₹1,00,000", "color_tag": "green"},
            headers=headers
        )
        assert res_note.status_code == 200
        assert len(res_note.json()["notes"]) == 2
        assert res_note.json()["notes"][1]["color_tag"] == "green"

        # 6. List Leads with filtering and search (GET /api/v1/leads)
        res_list = await ac.get(
            "/api/v1/leads",
            params={"search": "Karan", "stage": "closed_won", "page": 1, "limit": 10},
            headers=headers
        )
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["total"] == 1
        assert list_data["data"][0]["name"] == "Karan Johar"

        # 7. Soft Delete Lead (DELETE /api/v1/leads/{lead_id})
        res_del = await ac.delete(f"/api/v1/leads/{lead_id}", headers=headers)
        assert res_del.status_code == 204

        # Verify excluded after deletion
        res_get_after_del = await ac.get(f"/api/v1/leads/{lead_id}", headers=headers)
        assert res_get_after_del.status_code == 404

        res_list_after_del = await ac.get("/api/v1/leads", headers=headers)
        assert res_list_after_del.json()["total"] == 0

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_lead_multi_tenant_isolation(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Create Broker B
    broker_b = Broker(
        email="brokerb@example.com",
        phone="+919876549999",
        name="Broker B",
        whatsapp_number="+919876549999"
    )
    db_session.add(broker_b)
    await db_session.commit()
    await db_session.refresh(broker_b)

    # Lead belonging to Broker A
    lead_a = Lead(
        broker_id=test_broker.id,
        phone="+919111122222",
        name="Broker A Lead",
        source="manual"
    )
    db_session.add(lead_a)
    await db_session.commit()
    await db_session.refresh(lead_a)

    token_b = create_access_token({"sub": broker_b.email, "email": broker_b.email})
    headers_b = {"Authorization": f"Bearer {token_b}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Broker B attempts to access Broker A's lead -> 404 Not Found
        res_get = await ac.get(f"/api/v1/leads/{lead_a.id}", headers=headers_b)
        assert res_get.status_code == 404

        # Broker B attempts to delete Broker A's lead -> 404 Not Found
        res_del = await ac.delete(f"/api/v1/leads/{lead_a.id}", headers=headers_b)
        assert res_del.status_code == 404

    app.dependency_overrides.clear()
