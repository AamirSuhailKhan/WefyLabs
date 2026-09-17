"""
PART 24.1 — Self-Service Password Reset Unit & Integration Tests
================================================================
Validates:
- Generic responses to prevent account enumeration
- Secure token generation, hashing (SHA-256), and TTL enforcement (15 min)
- Password complexity validation (min 8 chars)
- Single-use token invalidation
- Celery email queue dispatch
- Direct login verification with updated password
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.main import app
from app.config import settings
from app.database import Base
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.invitation_models import PasswordResetToken
from app.modules.auth.service import hash_password, verify_password
from app.modules.auth.password_reset_service import PasswordResetService, GENERIC_RESET_RESPONSE

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
async def sample_broker(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email="realtor_reset@example.com",
        password_hash=hash_password("OldPassword123!"),
        name="Alex Realtor",
        phone="+919876543210",
        whatsapp_number="+919876543210",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@pytest.mark.asyncio
async def test_forgot_password_valid_user(client: AsyncClient, db_session: AsyncSession, sample_broker: Broker):
    with patch("app.tasks.queue_workers.process_email_dispatch.delay") as mock_email:
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "realtor_reset@example.com"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == GENERIC_RESET_RESPONSE

        # Verify token created in database
        stmt = select(PasswordResetToken).where(PasswordResetToken.broker_id == sample_broker.id)
        res = await db_session.execute(stmt)
        token_rec = res.scalars().first()
        assert token_rec is not None
        assert token_rec.token_hash is not None
        assert len(token_rec.token_hash) == 64  # SHA-256
        assert token_rec.used_at is None
        assert _ensure_utc(token_rec.expires_at) > datetime.now(timezone.utc)

        # Verify Celery email dispatch was attempted
        assert mock_email.called
        call_args = mock_email.call_args[0][0]
        assert call_args["recipient"] == "realtor_reset@example.com"
        assert "reset-password?token=" in call_args["html_content"]


@pytest.mark.asyncio
async def test_forgot_password_unknown_user_returns_generic_response(client: AsyncClient, db_session: AsyncSession):
    with patch("app.tasks.queue_workers.process_email_dispatch.delay") as mock_email:
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent_ghost@example.com"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == GENERIC_RESET_RESPONSE

        # Zero tokens created
        stmt = select(PasswordResetToken)
        res = await db_session.execute(stmt)
        assert len(res.scalars().all()) == 0

        # Zero emails sent
        assert not mock_email.called


@pytest.mark.asyncio
async def test_reset_password_full_lifecycle(client: AsyncClient, db_session: AsyncSession, sample_broker: Broker):
    # 1. Request reset
    with patch("app.tasks.queue_workers.process_email_dispatch.delay") as mock_email:
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": sample_broker.email}
        )
        # Extract raw token from reset link in dispatched email
        call_args = mock_email.call_args[0][0]
        reset_link = call_args["content"]
        raw_token = reset_link.split("token=")[1].split(".")[0].strip()

    # 2. Verify token is valid
    v_resp = await client.get(f"/api/v1/auth/verify-reset-token?token={raw_token}")
    assert v_resp.status_code == 200
    assert v_resp.json()["valid"] is True

    # 3. Submit reset with new password
    r_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewBrandNewPassword2026!"}
    )
    assert r_resp.status_code == 200
    assert "successfully reset" in r_resp.json()["message"]

    # 4. Verify broker password was updated in DB
    updated_broker = await db_session.get(Broker, sample_broker.id)
    assert verify_password("NewBrandNewPassword2026!", updated_broker.password_hash)
    assert not verify_password("OldPassword123!", updated_broker.password_hash)

    # 5. Token cannot be reused (Single-use enforcement)
    reused_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherPassword333!"}
    )
    assert reused_resp.status_code == 400
    assert "already been used" in reused_resp.json()["detail"]


@pytest.mark.asyncio
async def test_reset_password_rejects_weak_password(client: AsyncClient, db_session: AsyncSession, sample_broker: Broker):
    with patch("app.tasks.queue_workers.process_email_dispatch.delay") as mock_email:
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": sample_broker.email}
        )
        call_args = mock_email.call_args[0][0]
        raw_token = call_args["content"].split("token=")[1].split(".")[0].strip()

    # Attempt reset with 5 characters (too short)
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "short"}
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_reset_password_expired_token(client: AsyncClient, db_session: AsyncSession, sample_broker: Broker):
    now = datetime.now(timezone.utc)
    # Create manually expired token
    raw_token = "expired_secret_token_abcdef123456"
    token_hash = PasswordResetService._hash_token(raw_token)
    expired_record = PasswordResetToken(
        broker_id=sample_broker.id,
        token_hash=token_hash,
        expires_at=now - timedelta(minutes=5),  # Expired 5 minutes ago
        used_at=None
    )
    db_session.add(expired_record)
    await db_session.commit()

    # Verify endpoint returns 400
    v_resp = await client.get(f"/api/v1/auth/verify-reset-token?token={raw_token}")
    assert v_resp.status_code == 400
    assert "expired" in v_resp.json()["detail"]

    # Reset endpoint returns 400
    r_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "ValidNewPassword2026!"}
    )
    assert r_resp.status_code == 400
    assert "expired" in r_resp.json()["detail"]

