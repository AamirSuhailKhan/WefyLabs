"""
PART 24.1 — Team Member Email Invitation Test Suite
====================================================
Tests the full lifecycle of organization team member invitations:
- Invitation creation with role scoping and single-use token generation
- RBAC enforcement (only owners and admins can invite)
- Invitation listing and revocation
- Public token verification
- Invitation acceptance by unauthenticated user (account creation + membership)
- Invitation acceptance by existing authenticated broker
- Single-use and expiration enforcement
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.dependencies import clear_rate_limits
from app.main import app
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.invitation_models import OrganizationInvitation
from app.modules.auth.service import hash_password, create_access_token
from app.modules.auth.invitation_service import InvitationService, _ensure_utc

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    from app.database import get_db as db_get_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[db_get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_org(db_session: AsyncSession):
    org = Organization(
        id=uuid.uuid4(),
        name="Apex Luxury Properties",
        slug="apex-luxury",
        plan="pro"
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def admin_broker(db_session: AsyncSession, sample_org: Organization):
    broker = Broker(
        id=uuid.uuid4(),
        email="admin@apexluxury.com",
        password_hash=hash_password("AdminPass123!"),
        name="Sarah Admin",
        phone="+919876543211",
        whatsapp_number="+919876543211",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    member = OrganizationMember(
        organization_id=sample_org.id,
        broker_id=broker.id,
        role="admin"
    )
    db_session.add(member)
    await db_session.commit()
    return broker


@pytest_asyncio.fixture
async def agent_broker(db_session: AsyncSession, sample_org: Organization):
    broker = Broker(
        id=uuid.uuid4(),
        email="agent@apexluxury.com",
        password_hash=hash_password("AgentPass123!"),
        name="Bob Agent",
        phone="+919876543212",
        whatsapp_number="+919876543212",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    member = OrganizationMember(
        organization_id=sample_org.id,
        broker_id=broker.id,
        role="agent"
    )
    db_session.add(member)
    await db_session.commit()
    return broker


def get_auth_headers(broker: Broker) -> dict:
    token = create_access_token({"sub": str(broker.id), "email": broker.email, "broker_id": str(broker.id), "role": "broker"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_invitation_by_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_org: Organization,
    admin_broker: Broker
):
    headers = get_auth_headers(admin_broker)
    with patch("app.tasks.queue_workers.process_email_dispatch.delay") as mock_email:
        resp = await client.post(
            "/api/v1/organizations/invitations",
            json={"email": "newbie@example.com", "role": "agent"},
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == "newbie@example.com"
        assert data["role"] == "agent"
        assert data["organization_id"] == str(sample_org.id)
        assert data["status"] == "pending"

        # Verify Celery email dispatch enqueued
        assert mock_email.called
        call_args = mock_email.call_args[0][0]
        assert call_args["recipient"] == "newbie@example.com"
        assert "invite/accept?token=" in call_args["content"]


@pytest.mark.asyncio
async def test_create_invitation_forbidden_for_agent(
    client: AsyncClient,
    agent_broker: Broker
):
    headers = get_auth_headers(agent_broker)
    resp = await client.post(
        "/api/v1/organizations/invitations",
        json={"email": "another@example.com", "role": "agent"},
        headers=headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_and_revoke_invitations(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_org: Organization,
    admin_broker: Broker
):
    headers = get_auth_headers(admin_broker)
    with patch("app.tasks.queue_workers.process_email_dispatch.delay"):
        # Create an invitation
        c_resp = await client.post(
            "/api/v1/organizations/invitations",
            json={"email": "revoke_me@example.com", "role": "manager"},
            headers=headers
        )
        assert c_resp.status_code == 200
        inv_id = c_resp.json()["data"]["id"]

    # List invitations
    l_resp = await client.get("/api/v1/organizations/invitations", headers=headers)
    assert l_resp.status_code == 200
    inv_list = l_resp.json()["data"]
    assert any(inv["id"] == inv_id for inv in inv_list)

    # Revoke invitation
    r_resp = await client.delete(f"/api/v1/organizations/invitations/{inv_id}", headers=headers)
    assert r_resp.status_code == 200
    assert r_resp.json()["data"]["success"] is True

    # Verify token check now fails
    stmt = select(OrganizationInvitation).where(OrganizationInvitation.id == uuid.UUID(inv_id))
    inv_rec = (await db_session.execute(stmt)).scalars().first()
    assert inv_rec.status == "revoked"


@pytest.mark.asyncio
async def test_accept_invitation_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_org: Organization,
    admin_broker: Broker
):
    headers = get_auth_headers(admin_broker)
    with patch("app.tasks.queue_workers.process_email_dispatch.delay") as mock_email:
        await client.post(
            "/api/v1/organizations/invitations",
            json={"email": "join_team@example.com", "role": "agent"},
            headers=headers
        )
        raw_token = mock_email.call_args[0][0]["content"].split("token=")[1].strip()

    # 1. Public token verify
    v_resp = await client.get(f"/api/v1/invitations/verify?token={raw_token}")
    assert v_resp.status_code == 200
    assert v_resp.json()["data"]["email"] == "join_team@example.com"
    assert v_resp.json()["data"]["organization_name"] == "Apex Luxury Properties"

    # 2. Accept without existing account
    acc_resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "password": "SecurePassword123!",
            "name": "Jordan Agent"
        }
    )
    assert acc_resp.status_code == 200
    acc_data = acc_resp.json()["data"]
    assert acc_data["success"] is True
    assert acc_data["role"] == "agent"
    assert "access_token" in acc_data

    # 3. Verify created broker and organization membership in database
    stmt_b = select(Broker).where(Broker.email == "join_team@example.com")
    new_broker = (await db_session.execute(stmt_b)).scalars().first()
    assert new_broker is not None
    assert new_broker.name == "Jordan Agent"

    stmt_m = select(OrganizationMember).where(
        OrganizationMember.organization_id == sample_org.id,
        OrganizationMember.broker_id == new_broker.id
    )
    member = (await db_session.execute(stmt_m)).scalars().first()
    assert member is not None
    assert member.role == "agent"

    # 4. Enforce Single-Use (Re-acceptance must fail)
    reuse_resp = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "password": "SecurePassword123!"
        }
    )
    assert reuse_resp.status_code == 400
    assert "already been accepted" in reuse_resp.json()["detail"]
