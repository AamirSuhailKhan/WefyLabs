import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import clear_rate_limits
from app.main import app
from app.models.broker import Broker
from app.modules.auth.service import create_access_token


@pytest.mark.asyncio
async def test_logout_revokes_current_access_token(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    clear_rate_limits()
    broker = Broker(
        id=uuid.uuid4(),
        email=f"logout-{uuid.uuid4().hex[:8]}@example.com",
        name="Logout Test",
        onboarding_status="ONBOARDED",
    )
    db_session.add(broker)
    await db_session.commit()
    token = create_access_token({"sub": broker.email, "email": broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            me_before = await client.get("/api/v1/auth/me", headers=headers)
            assert me_before.status_code == 200

            logout_response = await client.post("/api/v1/auth/logout", headers=headers)
            assert logout_response.status_code == 200
            assert logout_response.json()["success"] is True

            me_after = await client.get("/api/v1/auth/me", headers=headers)
            assert me_after.status_code == 401
            assert "revoked" in me_after.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
        clear_rate_limits()
