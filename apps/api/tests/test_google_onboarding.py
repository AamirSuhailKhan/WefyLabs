"""
Google OAuth Broker Onboarding Flow Test Suite
=============================================
Tests:
- Unauthenticated access returns 401.
- Google OAuth callback creates AUTHENTICATED_NOT_ONBOARDED broker with null profile.
- Onboarding submission updates profile, transitions status to ONBOARDED.
- Onboarding transactionally creates Organization, OrganizationMember, and User.
- Idempotency checks (resubmitting does not duplicate orgs/users).
- Suspended accounts receive 403 Forbidden.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db, check_auth_rate_limit
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.user import User

@pytest.fixture(autouse=True)
def override_rate_limit():
    app.dependency_overrides[check_auth_rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(check_auth_rate_limit, None)


@pytest.mark.asyncio
async def test_unauthenticated_access_denied(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Accessing /auth/me without token
        res_me = await ac.get("/api/v1/auth/me")
        assert res_me.status_code == 401

        # 2. Accessing /auth/onboard without token
        res_onboard = await ac.post("/api/v1/auth/onboard", json={
            "name": "Test Name",
            "phone": "+919876543210",
            "whatsapp_number": "+919876543210",
            "agency_name": "Test Agency",
            "city": "Bengaluru"
        })
        assert res_onboard.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_google_oauth_callback_creates_incomplete_broker(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cb_payload = {
            "email": "newgoogleuser@example.com",
            "name": "Google Broker"
        }
        res = await ac.post("/api/v1/auth/callback", json=cb_payload)
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["broker"]["email"] == "newgoogleuser@example.com"
        assert data["broker"]["onboarding_status"] == "AUTHENTICATED_NOT_ONBOARDED"
        assert data["broker"]["phone"] is None
        assert data["broker"]["whatsapp_number"] is None

        # Verify DB has broker but NO organization/user yet
        stmt_broker = select(Broker).where(Broker.email == "newgoogleuser@example.com")
        broker = (await db_session.execute(stmt_broker)).scalars().first()
        assert broker is not None

        stmt_org = select(OrganizationMember).where(OrganizationMember.broker_id == broker.id)
        member = (await db_session.execute(stmt_org)).scalars().first()
        assert member is None

        stmt_user = select(User).where(User.id == broker.id)
        user = (await db_session.execute(stmt_user)).scalars().first()
        assert user is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_google_onboarding_submission_workflow(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Step 1: Trigger Google callback
        cb_res = await ac.post("/api/v1/auth/callback", json={
            "email": "onboardgoogle@example.com",
            "name": "Onboard Google"
        })
        token = cb_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Submit onboarding payload
        onboard_payload = {
            "name": "Onboard Google Name Edited",
            "phone": "+919988776655",
            "whatsapp_number": "+919988776655",
            "agency_name": "Horizon Real Estate",
            "city": "Bengaluru"
        }
        res = await ac.post("/api/v1/auth/onboard", json=onboard_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["onboarding_status"] == "ONBOARDED"
        assert data["phone"] == "+919988776655"
        assert data["agency_name"] == "Horizon Real Estate"

        # Step 3: Verify DB state has org, member and synced User
        stmt_broker = select(Broker).where(Broker.email == "onboardgoogle@example.com")
        broker = (await db_session.execute(stmt_broker)).scalars().first()
        assert broker.onboarding_status == "ONBOARDED"

        stmt_org = select(OrganizationMember).where(OrganizationMember.broker_id == broker.id)
        member = (await db_session.execute(stmt_org)).scalars().first()
        assert member is not None
        assert member.role == "owner"

        stmt_user = select(User).where(User.id == broker.id)
        user = (await db_session.execute(stmt_user)).scalars().first()
        assert user is not None
        assert user.name == "Onboard Google Name Edited"
        assert user.phone == "+919988776655"

        # Step 4: Verify idempotency - duplicate onboarding should succeed and not create duplicate orgs
        res_dup = await ac.post("/api/v1/auth/onboard", json=onboard_payload, headers=headers)
        assert res_dup.status_code == 200

        # Query all members for this broker
        members = (await db_session.execute(
            select(OrganizationMember).where(OrganizationMember.broker_id == broker.id)
        )).scalars().all()
        assert len(members) == 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_suspended_broker_denied(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Manually create suspended broker in DB
    suspended_broker = Broker(
        email="suspended@example.com",
        name="Suspended Broker",
        subscription_status="trial",
        onboarding_status="SUSPENDED"
    )
    db_session.add(suspended_broker)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Generate login / callback token
        res_cb = await ac.post("/api/v1/auth/callback", json={
            "email": "suspended@example.com",
            "name": "Suspended Broker"
        })
        token = res_cb.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Attempt to access dashboard API (e.g. GET /auth/me) -> should return 403
        res_me = await ac.get("/api/v1/auth/me", headers=headers)
        assert res_me.status_code == 403
        assert "suspended" in res_me.json()["detail"].lower()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_onboarding_invalid_phone_rejection_and_422_structure(db_session: AsyncSession):
    """Tests that invalid phone text (e.g. 'rdsy...') is rejected with structured 422."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cb_res = await ac.post("/api/v1/auth/callback", json={
            "email": "invalidphonebroker@example.com",
            "name": "Invalid Phone Broker"
        })
        token = cb_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Invalid text phone 'rdsy...'
        invalid_payload = {
            "name": "Aamir",
            "phone": "rdsy...",
            "whatsapp_number": "rdsy...",
            "agency_name": "test text",
            "city": "Bengaluru"
        }
        res_invalid = await ac.post("/api/v1/auth/onboard", json=invalid_payload, headers=headers)
        assert res_invalid.status_code == 422
        body = res_invalid.json()
        assert "error" in body or "details" in body or "detail" in body
        error_str = str(body).lower()
        assert "phone" in error_str

        # 2. Valid spaced/delimited phone '+91 98765 43210' -> successfully normalized
        valid_payload = {
            "name": "Aamir",
            "phone": "+91 98765 43210",
            "whatsapp_number": "+91 98765 43210",
            "agency_name": "Beetle Realty",
            "city": "Bengaluru"
        }
        res_valid = await ac.post("/api/v1/auth/onboard", json=valid_payload, headers=headers)
        assert res_valid.status_code == 200
        valid_data = res_valid.json()
        assert valid_data["phone"] == "+919876543210"
        assert valid_data["whatsapp_number"] == "+919876543210"
        assert valid_data["onboarding_status"] == "ONBOARDED"

    app.dependency_overrides.clear()

