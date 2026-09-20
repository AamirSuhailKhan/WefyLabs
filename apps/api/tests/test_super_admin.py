import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_super_admin_operations_reject_a_regular_authenticated_broker(
    db_session: AsyncSession, test_broker: Broker, test_lead: Lead
):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_ov = await ac.get("/api/v1/super-admin/overview", headers=headers)
        assert res_ov.status_code == 403
        assert res_ov.json()["detail"] == "Super-admin access is required."

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_explicitly_allowlisted_operator_can_reach_super_admin_router(
    db_session: AsyncSession, test_broker: Broker, test_lead: Lead, monkeypatch
):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "SUPER_ADMIN_EMAILS", [test_broker.email.upper()])

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/super-admin/overview", headers=headers)
    assert response.status_code == 200

    app.dependency_overrides.clear()
