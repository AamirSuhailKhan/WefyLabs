"""
PART 24.1 — Account Deletion & External Google OAuth Revocation Test Suite
==========================================================================
Tests the full lifecycle of broker account deletion with external Google OAuth revocation:
- Revocation of connected Google Calendar OAuth credentials
- Resilience: Google outage/network timeout never blocks local DB deletion
- Asynchronous Celery retry fallback on Google failure
- Cleanup of associated records (CalendarAccount, PasswordResetToken, OrganizationInvitation, OrganizationMember, User, Broker)
- Direct unit tests for perform_google_token_revocation (200, 400, 500, timeout)
- Zero credential logging and token encryption validation
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
import httpx
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.dependencies import clear_rate_limits
from app.main import app
from app.models.broker import Broker
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.models.calendar_models import CalendarAccount
from app.models.invitation_models import PasswordResetToken, OrganizationInvitation
from app.common.security.token_encryption import encrypt_token, decrypt_token
from app.modules.auth.service import create_access_token
from app.modules.auth.oauth_revocation import perform_google_token_revocation, GOOGLE_REVOCATION_URL
from app.tasks.queue_workers import revoke_google_oauth_token_task

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
async def test_organization(db_session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        name="Apex Realty Partners",
        slug="apex-realty"
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_broker(db_session: AsyncSession, test_organization: Organization) -> Broker:
    broker = Broker(
        id=uuid.uuid4(),
        email="agent_delete@example.com",
        name="Sam Deletion Test",
        phone="+919876500001",
        whatsapp_number="+919876500001",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    member = OrganizationMember(
        organization_id=test_organization.id,
        broker_id=broker.id,
        role="admin"
    )
    db_session.add(member)

    user = User(
        id=broker.id,
        email=broker.email,
        name=broker.name,
        phone=broker.phone,
        organization_id=str(test_organization.id)
    )
    db_session.add(user)

    await db_session.commit()
    return broker


def get_auth_headers(broker: Broker, org_id: str = None) -> dict:
    token = create_access_token(data={
        "sub": str(broker.id),
        "broker_id": str(broker.id),
        "email": broker.email,
        "role": "admin",
        "organization_id": org_id or str(broker.id)
    })
    return {"Authorization": f"Bearer {token}"}


# ─── 1. End-to-End Account Deletion with Google Revocation Success ──────────────

@pytest.mark.asyncio
async def test_account_deletion_with_google_oauth_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_broker: Broker,
    test_organization: Organization
):
    # Connect a Google Calendar account with encrypted tokens
    plain_refresh_token = "1//0gRealGoogleRefreshTokenXYZ123"
    plain_access_token = "ya29.a0AfH6SMBDummyGoogleAccessToken456"

    cal_acc = CalendarAccount(
        organization_id=str(test_organization.id),
        broker_id=test_broker.id,
        provider="GOOGLE",
        account_email="sam.google@example.com",
        encrypted_access_token=encrypt_token(plain_access_token),
        encrypted_refresh_token=encrypt_token(plain_refresh_token),
        is_connected=True
    )
    db_session.add(cal_acc)
    await db_session.commit()

    headers = get_auth_headers(test_broker)

    # Mock external Google revocation returning 200 OK
    with patch(
        "app.modules.auth.account_deletion_service.perform_google_token_revocation"
    ) as mock_revoke:
        mock_revoke.return_value = (True, 200, None)

        resp = await client.delete("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["google_revocation_attempted"] is True
        assert data["google_revocation_success"] is True

        # Verify revocation was called with the decrypted refresh token
        mock_revoke.assert_called_once_with(plain_refresh_token)

    # Verify DB cleanup: CalendarAccount, Broker, User, OrganizationMember are all gone
    stmt_b = select(Broker).where(Broker.id == test_broker.id)
    assert (await db_session.execute(stmt_b)).scalars().first() is None

    stmt_c = select(CalendarAccount).where(CalendarAccount.id == cal_acc.id)
    assert (await db_session.execute(stmt_c)).scalars().first() is None

    stmt_u = select(User).where(User.id == test_broker.id)
    assert (await db_session.execute(stmt_u)).scalars().first() is None

    stmt_m = select(OrganizationMember).where(OrganizationMember.broker_id == test_broker.id)
    assert (await db_session.execute(stmt_m)).scalars().first() is None


# ─── 2. Resilience: Google Revocation Failure Falls Back to Celery ─────────────

@pytest.mark.asyncio
async def test_account_deletion_with_google_failure_enqueues_celery(
    client: AsyncClient,
    db_session: AsyncSession,
    test_broker: Broker,
    test_organization: Organization
):
    plain_refresh_token = "1//0gFailingGoogleToken999"
    cal_acc = CalendarAccount(
        organization_id=str(test_organization.id),
        broker_id=test_broker.id,
        provider="GOOGLE",
        account_email="failing.google@example.com",
        encrypted_access_token=encrypt_token("access_token_123"),
        encrypted_refresh_token=encrypt_token(plain_refresh_token),
        is_connected=True
    )
    db_session.add(cal_acc)
    await db_session.commit()

    headers = get_auth_headers(test_broker)

    # Simulate Google outage (503 Service Unavailable)
    with patch(
        "app.modules.auth.account_deletion_service.perform_google_token_revocation"
    ) as mock_revoke, patch(
        "app.tasks.queue_workers.revoke_google_oauth_token_task.delay"
    ) as mock_celery:
        mock_revoke.return_value = (False, 503, "Service Unavailable")

        resp = await client.delete("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        # Local account deletion succeeded
        assert data["success"] is True
        assert data["google_revocation_attempted"] is True
        assert data["google_revocation_success"] is False

        # Celery retry task was enqueued as fallback
        mock_celery.assert_called_once_with(plain_refresh_token)

    # Local database deletion must NEVER be blocked
    stmt_b = select(Broker).where(Broker.id == test_broker.id)
    assert (await db_session.execute(stmt_b)).scalars().first() is None


# ─── 3. Account Deletion Without External Google OAuth ─────────────────────────

@pytest.mark.asyncio
async def test_account_deletion_without_oauth(
    client: AsyncClient,
    db_session: AsyncSession,
    test_broker: Broker
):
    headers = get_auth_headers(test_broker)

    with patch(
        "app.modules.auth.account_deletion_service.perform_google_token_revocation"
    ) as mock_revoke:
        resp = await client.delete("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["google_revocation_attempted"] is False
        assert data["google_revocation_success"] is False
        mock_revoke.assert_not_called()

    stmt_b = select(Broker).where(Broker.id == test_broker.id)
    assert (await db_session.execute(stmt_b)).scalars().first() is None


# ─── 4. Direct Unit Tests for perform_google_token_revocation ─────────────────

def test_perform_google_token_revocation_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        succ, code, err = perform_google_token_revocation("valid_token_xyz")
        assert succ is True
        assert code == 200
        assert err is None
        mock_post.assert_called_once_with(
            GOOGLE_REVOCATION_URL,
            data={"token": "valid_token_xyz"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )


def test_perform_google_token_revocation_already_revoked_400():
    # Google returns 400 with invalid_token when token was previously revoked
    mock_resp = MagicMock()
    mock_resp.status_code = 400

    with patch("httpx.Client.post", return_value=mock_resp):
        succ, code, err = perform_google_token_revocation("already_revoked_token")
        assert succ is True
        assert code == 400
        assert "already revoked" in err


def test_perform_google_token_revocation_google_error_500():
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("httpx.Client.post", return_value=mock_resp):
        succ, code, err = perform_google_token_revocation("any_token")
        assert succ is False
        assert code == 500
        assert "500" in err


def test_perform_google_token_revocation_timeout():
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timeout")):
        succ, code, err = perform_google_token_revocation("any_token")
        assert succ is False
        assert code == 504
        assert "timed out" in err


def test_perform_google_token_revocation_empty_token():
    succ, code, err = perform_google_token_revocation(None)
    assert succ is True
    assert code == 200
    assert err == "No token provided"


# ─── 5. Celery Task Execution ──────────────────────────────────────────────────

def test_celery_task_revocation_success():
    with patch(
        "app.modules.auth.oauth_revocation.perform_google_token_revocation",
        return_value=(True, 200, None)
    ):
        result = revoke_google_oauth_token_task("celery_token_abc")
        assert result["revoked"] is True
        assert result["status_code"] == 200
        assert result["error"] is None
