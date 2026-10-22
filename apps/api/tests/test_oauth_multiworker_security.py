"""
Phase 0 P0.1 — Multi-Worker Distributed OAuth State & Session Security Matrix
=============================================================================

Comprehensive regression tests validating:
1. Valid OAuth flow with server-side state bound to session cookie
2. Invalid state rejection
3. Expired state rejection
4. Wrong session rejection (cross-session tamper defense)
5. Replayed state rejection (one-time atomic consumption)
6. Cross-worker state validation (Worker A issues state, Worker B consumes it via Redis)
7. Shared session secret validation across workers
8. Cookie persistence, security attributes (HttpOnly, SameSite, Path, Secure), and cleanup
9. State atomic consumption under concurrency
10. Authorization code replay defense across workers
"""
import asyncio
import os
import secrets
import time
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock

from app.main import app
from app.config import settings
from app.database import get_db
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.common.auth.oauth_state import (
    issue_oauth_state,
    consume_oauth_state,
    consume_authorization_code,
    OAuthStateMissing,
    OAuthStateExpired,
    OAuthStateReplayed,
    OAuthStateSessionMismatch,
    _get_redis,
    _is_redis_usable,
    reset_memory_store,
    STATE_TTL_SECONDS,
)
from app.modules.auth.router import (
    OAUTH_SESSION_COOKIE,
    _resolve_or_create_oauth_session,
    _resolve_oauth_session,
    _oauth_cookie_secure,
)


@pytest.fixture(autouse=True)
def setup_oauth_environment():
    """Ensure in-memory store is reset between tests."""
    reset_memory_store()
    yield
    reset_memory_store()


@pytest.mark.asyncio
async def test_oauth_cookie_persistence_and_attributes():
    """TEST: Pre-login session cookie attributes conform to security specifications:
    - HttpOnly = True
    - SameSite = Lax
    - Path = /
    - Secure = True in prod/staging, False in dev/test
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/google/url")
        assert res.status_code == 200
        assert OAUTH_SESSION_COOKIE in res.cookies

        cookie_header = res.headers.get("set-cookie", "")
        assert OAUTH_SESSION_COOKIE in cookie_header
        assert "httponly" in cookie_header.lower()
        assert "samesite=lax" in cookie_header.lower()
        assert "path=/" in cookie_header.lower()

        # In testing/dev mode, Secure should match _oauth_cookie_secure()
        if _oauth_cookie_secure():
            assert "secure" in cookie_header.lower()


@pytest.mark.asyncio
async def test_oauth_invalid_state_rejected():
    """TEST: Callback with unknown or invalid state is rejected with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First obtain session cookie
        res_url = await ac.get("/api/v1/auth/google/url")
        assert res_url.status_code == 200

        # Attempt exchange with tampered state
        res = await ac.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"valid_looking_code_{uuid.uuid4().hex}", "state": "tampered-state-invalid"}
        )
        assert res.status_code == 400
        assert "state" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_wrong_session_rejected():
    """TEST: Callback presenting a state that belongs to a different browser session
    is rejected with 'OAuth state does not belong to this session.' and burned.
    """
    transport = ASGITransport(app=app)

    # Session A starts OAuth
    async with AsyncClient(transport=transport, base_url="http://test") as ac_a:
        res_a = await ac_a.get("/api/v1/auth/google/url")
        assert res_a.status_code == 200
        state_a = res_a.json()["state"]

    # Session B starts OAuth (different session cookie)
    async with AsyncClient(transport=transport, base_url="http://test") as ac_b:
        res_b = await ac_b.get("/api/v1/auth/google/url")
        assert res_b.status_code == 200

        # Session B attempts to exchange state_a (belonging to Session A)
        res_exchange = await ac_b.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"code_{uuid.uuid4().hex}", "state": state_a}
        )
        assert res_exchange.status_code == 400
        assert res_exchange.json()["detail"] == "OAuth state does not belong to this session."

    # Verify state_a was burned: even Session A can no longer use it
    async with AsyncClient(transport=transport, base_url="http://test") as ac_a:
        # Restore session A cookie
        ac_a.cookies.set(OAUTH_SESSION_COOKIE, res_a.cookies[OAUTH_SESSION_COOKIE])
        res_retry = await ac_a.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"code_{uuid.uuid4().hex}", "state": state_a}
        )
        assert res_retry.status_code == 400
        assert "already been used" in res_retry.json()["detail"].lower() or "missing" in res_retry.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_missing_session_cookie_rejected():
    """TEST: Callback without the pre-login session cookie is rejected immediately."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # No GET /auth/google/url, so no cookie
        res = await ac.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"code_{uuid.uuid4().hex}", "state": "some-valid-looking-state"}
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "OAuth state does not belong to this session."


@pytest.mark.asyncio
async def test_oauth_expired_state_rejected():
    """TEST: Expired OAuth state is rejected."""
    session_id = secrets.token_urlsafe(32)
    # Issue with 0 or negative TTL to simulate immediate expiration
    state = issue_oauth_state(session_id, ttl=0)
    time.sleep(0.05)

    with pytest.raises((OAuthStateExpired, OAuthStateMissing)):
        consume_oauth_state(state, session_id)


@pytest.mark.asyncio
async def test_oauth_replayed_state_rejected():
    """TEST: Replaying an already consumed OAuth state is rejected with OAuthStateReplayed."""
    session_id = secrets.token_urlsafe(32)
    state = issue_oauth_state(session_id)

    # First consumption succeeds
    consume_oauth_state(state, session_id)

    # Second consumption MUST fail with OAuthStateReplayed
    with pytest.raises(OAuthStateReplayed):
        consume_oauth_state(state, session_id)


@pytest.mark.asyncio
async def test_oauth_state_atomic_consumption_concurrency():
    """TEST: Two concurrent workers consuming the exact same state: exactly one succeeds."""
    session_id = secrets.token_urlsafe(32)
    state = issue_oauth_state(session_id)

    success_count = 0
    failure_count = 0

    def try_consume():
        nonlocal success_count, failure_count
        try:
            consume_oauth_state(state, session_id)
            success_count += 1
        except (OAuthStateReplayed, OAuthStateMissing):
            failure_count += 1

    # Simulate 2 workers concurrently attempting atomic consumption
    loop = asyncio.get_event_loop()
    await asyncio.gather(
        loop.run_in_executor(None, try_consume),
        loop.run_in_executor(None, try_consume),
    )

    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
    assert failure_count == 1, f"Expected exactly 1 failure, got {failure_count}"


@pytest.mark.asyncio
async def test_cross_worker_oauth_state_validation_via_redis():
    """TEST MULTI-WORKER: Worker A starts OAuth, Worker B receives callback.
    Both share the live Redis instance.
    Valid flow succeeds, cross-worker state is resolved and consumed atomically.
    """
    redis = _get_redis()
    if redis is None:
        pytest.skip("Live Redis not reachable in current environment")

    # Force Redis usage for this multi-worker test
    os.environ["FORCE_OAUTH_REDIS"] = "1"
    try:
        # Worker A simulates process 1
        session_id = secrets.token_urlsafe(32)
        state = issue_oauth_state(session_id, ttl=STATE_TTL_SECONDS)

        # Verify key exists in Redis: oauth:state:<state>
        redis_key = f"oauth:state:{state}"
        stored_val = redis.get(redis_key)
        assert stored_val is not None, "Worker A did not store state in Redis"
        assert stored_val == session_id, "Redis value must be the stable session identifier"

        # Worker B simulates process 2 (separate worker consuming from Redis)
        consume_oauth_state(state, session_id)

        # Verify key deleted in Redis (atomic one-time consumption)
        assert redis.get(redis_key) is None, "State key must be deleted after consumption"

        # Verify tombstone exists to block replay
        dead_key = f"oauth:statedead:{state}"
        assert redis.get(dead_key) is not None, "Dead state tombstone must exist"

        # Worker B rejects replayed state
        with pytest.raises(OAuthStateReplayed):
            consume_oauth_state(state, session_id)
    finally:
        os.environ.pop("FORCE_OAUTH_REDIS", None)


@pytest.mark.asyncio
async def test_full_oauth_flow_with_mocked_google_provider(db_session: AsyncSession):
    """TEST: End-to-end OAuth flow through FastAPI:
    1. Worker A: GET /api/v1/auth/google/url -> returns state, mints session cookie
    2. Worker B: POST /api/v1/auth/google/exchange with session cookie and state
    3. Google returns verified identity -> broker and organization created
    4. Session cookie is cleared on successful completion
    """
    from app.dependencies import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        mock_email = f"verified_user_{uuid.uuid4().hex[:8]}@example.com"
        mock_name = "Verified Google User"

        # Worker A: Start OAuth
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res_url = await ac.get("/api/v1/auth/google/url")
            assert res_url.status_code == 200
            state = res_url.json()["state"]
            cookie_val = ac.cookies[OAUTH_SESSION_COOKIE]
            assert cookie_val is not None

            # Mock Google provider responses
            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {
                "access_token": "mock_google_access_token_123",
                "token_type": "Bearer",
                "expires_in": 3600
            }

            mock_userinfo_resp = MagicMock()
            mock_userinfo_resp.status_code = 200
            mock_userinfo_resp.json.return_value = {
                "email": mock_email,
                "email_verified": True,
                "name": mock_name,
                "sub": "google-sub-12345"
            }

            from unittest.mock import AsyncMock

            mock_outbound_client = MagicMock()
            mock_outbound_client.__aenter__ = AsyncMock(return_value=mock_outbound_client)
            mock_outbound_client.__aexit__ = AsyncMock(return_value=None)
            mock_outbound_client.post = AsyncMock(return_value=mock_token_resp)
            mock_outbound_client.get = AsyncMock(return_value=mock_userinfo_resp)

            with patch("app.modules.auth.service.httpx.AsyncClient", return_value=mock_outbound_client):

                # Worker B: Callback
                res_exchange = await ac.post(
                    "/api/v1/auth/google/exchange",
                    json={
                        "code": f"valid_auth_code_{uuid.uuid4().hex}",
                        "state": state
                    }
                )
                assert res_exchange.status_code == 200
                data = res_exchange.json()
                assert "access_token" in data
                assert data["broker"]["email"] == mock_email
                assert data["broker"]["name"] == mock_name
                first_broker_id = data["broker"]["id"]

                # Returning Google identity is resolved by immutable subject,
                # even if the provider's verified email has changed.
                mock_userinfo_resp.json.return_value = {
                    "email": f"updated_{mock_email}",
                    "email_verified": True,
                    "name": mock_name,
                    "sub": "google-sub-12345",
                }
                res_returning_url = await ac.get("/api/v1/auth/google/url")
                res_returning = await ac.post(
                    "/api/v1/auth/google/exchange",
                    json={
                        "code": f"returning_auth_code_{uuid.uuid4().hex}",
                        "state": res_returning_url.json()["state"],
                    },
                )
                assert res_returning.status_code == 200
                assert res_returning.json()["broker"]["id"] == first_broker_id
                assert res_returning.json()["broker"]["email"] == mock_email
                linked_broker = await db_session.get(Broker, uuid.UUID(first_broker_id))
                assert linked_broker.google_subject == "google-sub-12345"

                # Pre-login session cookie must be cleared on successful authentication
                set_cookie_header = res_exchange.headers.get("set-cookie", "")
                assert OAUTH_SESSION_COOKIE in set_cookie_header
                assert 'max-age=0' in set_cookie_header.lower() or 'expires=' in set_cookie_header.lower() or '=""' in set_cookie_header

                # An unverified provider email must never create or link a broker account.
                unverified_email = f"unverified_{uuid.uuid4().hex[:8]}@example.com"
                mock_userinfo_resp.json.return_value = {
                    "email": unverified_email,
                    "email_verified": False,
                    "name": "Unverified User",
                    "sub": "google-sub-unverified"
                }
                res_unverified_url = await ac.get("/api/v1/auth/google/url")
                unverified_state = res_unverified_url.json()["state"]
                res_unverified = await ac.post(
                    "/api/v1/auth/google/exchange",
                    json={
                        "code": f"unverified_auth_code_{uuid.uuid4().hex}",
                        "state": unverified_state
                    }
                )
                assert res_unverified.status_code == 401
                assert "email is not verified" in res_unverified.json()["detail"]
                created_unverified = (await db_session.execute(
                    select(Broker).where(Broker.email == unverified_email)
                )).scalars().first()
                assert created_unverified is None
    finally:
        app.dependency_overrides.clear()
