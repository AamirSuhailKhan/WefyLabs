from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, require_active_subscription, clear_rate_limits
from app.models.broker import Broker
from app.modules.auth.service import create_access_token
from fastapi import Depends

@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_registration_and_validation(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Successful Registration
        reg_payload = {
            "email": "newbroker@example.com",
            "password": "securepassword123",
            "phone": "+919876500001",
            "name": "New Broker",
            "agency_name": "New Realty",
            "city": "Bengaluru",
            "whatsapp_number": "9876500001"  # Normalized to +919876500001
        }
        res = await ac.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["broker"]["email"] == "newbroker@example.com"
        assert data["broker"]["phone"] == "+919876500001"
        assert data["broker"]["whatsapp_number"] == "+919876500001"
        assert data["broker"]["trial_days_remaining"] >= 6

        # 2. Duplicate Registration (409 Conflict)
        res_dup = await ac.post("/api/v1/auth/register", json=reg_payload)
        assert res_dup.status_code == 409

        # 3. Invalid Indian Phone Number (422 Unprocessable Entity)
        invalid_payload = reg_payload.copy()
        invalid_payload["email"] = "invalidphone@example.com"
        invalid_payload["phone"] = "12345"
        res_inv = await ac.post("/api/v1/auth/register", json=invalid_payload)
        assert res_inv.status_code == 422

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_login_and_auth_me(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register broker first
        reg_payload = {
            "email": "loginbroker@example.com",
            "password": "mypassword123",
            "phone": "+919876500002",
            "name": "Login Broker",
            "agency_name": "Apex Realty",
            "whatsapp_number": "+919876500002"
        }
        reg_res = await ac.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201

        # Successful Login
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "loginbroker@example.com",
            "password": "mypassword123"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]

        # Failed Login (Wrong Password -> 401)
        bad_login = await ac.post("/api/v1/auth/login", json={
            "email": "loginbroker@example.com",
            "password": "wrongpassword"
        })
        assert bad_login.status_code == 401

        # Test GET /api/v1/auth/me
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "loginbroker@example.com"
        assert me_res.json()["trial_days_remaining"] >= 6

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_oauth_callback(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cb_payload = {
            "email": "googleuser@example.com",
            "name": "Google Broker",
            "agency_name": "Google Realty",
            "city": "Mumbai"
        }
        res = await ac.post("/api/v1/auth/callback", json=cb_payload)
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["broker"]["email"] == "googleuser@example.com"
        assert data["broker"]["city"] == "Mumbai"

        # Subsequent callback sync updates profile
        cb_payload["agency_name"] = "Updated Google Realty"
        res_sync = await ac.post("/api/v1/auth/callback", json=cb_payload)
        assert res_sync.status_code == 200
        assert res_sync.json()["broker"]["agency_name"] == "Updated Google Realty"

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_broker_me_and_patch(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register broker
        reg_payload = {
            "email": "patchbroker@example.com",
            "password": "password123",
            "phone": "+919876500003",
            "name": "Original Name",
            "agency_name": "Old Agency",
            "whatsapp_number": "+919876500003"
        }
        reg_res = await ac.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # GET /api/v1/brokers/me
        get_res = await ac.get("/api/v1/brokers/me", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Original Name"

        # PATCH /api/v1/brokers/me
        patch_payload = {
            "name": "Updated Broker Name",
            "agency_name": "New Agency Name",
            "city": "Delhi"
        }
        patch_res = await ac.patch("/api/v1/brokers/me", json=patch_payload, headers=headers)
        assert patch_res.status_code == 200
        updated_data = patch_res.json()
        assert updated_data["name"] == "Updated Broker Name"
        assert updated_data["agency_name"] == "New Agency Name"
        assert updated_data["city"] == "Delhi"

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_trial_expiry_enforcement(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Manually expire trial
    test_broker.subscription_status = "trial"
    test_broker.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    # Protected endpoint requiring active subscription
    @app.get("/api/v1/test-paid-feature")
    async def paid_feature(b: Broker = Depends(require_active_subscription)):
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/test-paid-feature", headers=headers)
        assert res.status_code == 403
        data = res.json()
        assert data["detail"]["code"] == "TRIAL_EXPIRED"

    app.dependency_overrides.clear()
