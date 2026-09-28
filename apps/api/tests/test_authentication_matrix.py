import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.main import app
from app.dependencies import get_db, check_auth_rate_limit
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
import os

from app.modules.auth.service import hash_password, create_access_token
from app.common.auth.oauth_state import (
    issue_oauth_state,
    consume_oauth_state,
    consume_authorization_code,
    reset_memory_store,
    OAuthStateReplayed,
)

# Phase 0 P0.1: pin testing environment BEFORE app modules load so the OAuth
# state store deterministically uses its bounded in-memory backend.
os.environ.setdefault("ENV", "testing")

@pytest.fixture(autouse=True)
def override_test_dependencies(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None
    reset_memory_store()
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(check_auth_rate_limit, None)
    reset_memory_store()

@pytest.mark.asyncio
async def test_1_direct_email_login_correct_password(db_session: AsyncSession):
    """TEST 1: Email + correct password -> authenticated."""
    email = f"direct_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "SecurePassword123!"
    broker = Broker(
        email=email,
        password_hash=hash_password(pwd),
        name="Direct Broker",
        phone="+919876543210",
        whatsapp_number="+919876543210",
        agency_name="Direct Agency",
        city="Bengaluru",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["broker"]["email"] == email
        assert data["broker"]["onboarding_status"] == "ONBOARDED"

@pytest.mark.asyncio
async def test_2_direct_email_login_wrong_password(db_session: AsyncSession):
    """TEST 2: Email + wrong password -> rejected (401)."""
    email = f"wrong_{uuid.uuid4().hex[:6]}@example.com"
    broker = Broker(
        email=email,
        password_hash=hash_password("CorrectPassword123!"),
        name="Broker Two",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword!"})
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_3_direct_email_login_nonexistent_account():
    """TEST 3: Email + nonexistent account -> rejected (401)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/login", json={"email": "nonexistent@example.com", "password": "AnyPassword123!"})
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_4_google_existing_onboarded_user(db_session: AsyncSession):
    """TEST 4: Google exchange with an invalid state is rejected (mock identity removed).

    Phase 0 P0.1: caller-supplied email/name and 'test_code_' mock identities are
    no longer accepted. The old mock path returned the broker profile; now the
    request is rejected (400) because state and real provider verification are
    mandatory.
    """
    email = f"google_onboarded_{uuid.uuid4().hex[:6]}@example.com"
    broker = Broker(
        email=email,
        name="Existing Google Broker",
        phone="+919876543211",
        whatsapp_number="+919876543211",
        agency_name="Google Realty",
        city="Mumbai",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"test_code_{uuid.uuid4().hex}", "state": "stale-state-value-1234"}
        )
        assert res.status_code == 400

@pytest.mark.asyncio
async def test_5_google_new_user_rejects_missing_state(db_session: AsyncSession):
    """TEST 5: Google exchange without server-issued state -> rejected (400).

    Phase 0 P0.1: state is mandatory; the pre-hardening endpoint created brokers
    from caller identity. Now there is no identity path without verified state.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"real_looking_code_{uuid.uuid4().hex}"}
        )
        # 422: schema rejects the request outright — state is mandatory
        assert res.status_code in (400, 422)

@pytest.mark.asyncio
async def test_6_google_incomplete_user_redirect_state(db_session: AsyncSession):
    """TEST 6: Google incomplete user -> /auth/me returns AUTHENTICATED_NOT_ONBOARDED."""
    email = f"incomplete_{uuid.uuid4().hex[:6]}@example.com"
    broker = Broker(
        email=email,
        name="Incomplete User",
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()

    token = create_access_token({"sub": email, "email": email, "broker_id": str(broker.id)})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["onboarding_status"] == "AUTHENTICATED_NOT_ONBOARDED"

@pytest.mark.asyncio
async def test_7_google_auth_url_generation():
    """TEST 7: Google OAuth URL generation returns valid Google authorization endpoint & state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/google/url")
        assert res.status_code == 200
        data = res.json()
        assert "auth_url" in data
        assert "state" in data
        assert "accounts.google.com/o/oauth2/v2/auth" in data["auth_url"]
        assert "state=" in data["auth_url"]

@pytest.mark.asyncio
async def test_8_google_oauth_failure_empty_code():
    """TEST 8: Google OAuth failure on empty or blank code -> rejected (422/400)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/google/exchange", json={"code": ""})
        # Empty code fails state validation (422 schema / 400 service) before
        # any provider interaction.
        assert res.status_code in (400, 422)

@pytest.mark.asyncio
async def test_9_google_callback_replay_rejected(db_session: AsyncSession):
    """TEST 9: Replaying an authorization code -> rejected (400).

    Phase 0 P0.1: replay protection is distributed (Redis SET-NX with TTL,
    backed by the bounded in-memory store in tests) and is enforced BEFORE any
    provider interaction, so both replays are rejected identically.
    """
    code = f"unique_replay_code_{uuid.uuid4().hex}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First use consumes the code and then fails at the provider boundary
        # (no mock identity in testing) — the exact failure code is irrelevant.
        res1 = await ac.post("/api/v1/auth/google/exchange", json={"code": code, "state": "state-value-12345678"})
        assert res1.status_code in (400, 401, 422, 502)

        # Second exchange with the same code is rejected as a REPLAY before any
        # provider interaction — this is the distributed one-time guarantee.
        res2 = await ac.post("/api/v1/auth/google/exchange", json={"code": code, "state": "state-value-12345678"})
        assert res2.status_code == 400
        assert "consumed" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_9b_caller_supplied_identity_rejected(db_session: AsyncSession):
    """TEST 9b: Caller-supplied email/name (former mock identity) is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"code_{uuid.uuid4().hex}", "state": "state-value-12345678",
                  "email": f"attacker_{uuid.uuid4().hex[:6]}@example.com", "name": "Attacker"},
        )
        # 400 (identity fields rejected) or 422 (extra-forbidden schema)
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_9c_oauth_state_full_security_matrix(db_session: AsyncSession):
    """TEST 9c: OAuth state security matrix — valid, wrong-session, replay,
    expired, missing. Distributed store semantics proven at the unit level.
    """
    sid_a = "session-a-aaaaaaaaaaaaaaaaaaaa"
    sid_b = "session-b-bbbbbbbbbbbbbbbbbbbb"

    # Valid state + correct session -> PASS
    state = issue_oauth_state(sid_a)
    consume_oauth_state(state, sid_a)  # must not raise

    # Wrong session -> FAIL
    state = issue_oauth_state(sid_a)
    from app.common.auth.oauth_state import OAuthStateSessionMismatch
    with pytest.raises(OAuthStateSessionMismatch):
        consume_oauth_state(state, sid_b)

    # Missing state -> FAIL
    from app.common.auth.oauth_state import OAuthStateMissing
    with pytest.raises(OAuthStateMissing):
        consume_oauth_state("nonexistent-state-value", sid_a)
    with pytest.raises(OAuthStateMissing):
        consume_oauth_state(None, sid_a)

    # Reused state -> FAIL (one-time consumption)
    with pytest.raises(OAuthStateReplayed):
        consume_oauth_state(state, sid_a)  # already consumed above

    # Reused authorization code -> FAIL
    code = f"authz-code-{uuid.uuid4().hex}"
    consume_authorization_code(code)
    with pytest.raises(OAuthStateReplayed):
        consume_authorization_code(code)


@pytest.mark.asyncio
async def test_9d_test_identity_endpoint_isolated_and_functional(db_session: AsyncSession):
    """TEST 9d: The isolated test-identity endpoint works in testing env and
    differs from the production OAuth flow.
    """
    from app.config import settings as _settings
    if _settings.ENV.lower() in ("production", "prod"):
        pytest.skip("test identity endpoint is compiled out in production")

    email = f"fixture_{uuid.uuid4().hex[:6]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/test/identity", json={"email": email, "name": "Fixture User"})
        assert res.status_code == 200
        data = res.json()
        assert data["broker"]["email"] == email
        assert data["broker"]["onboarding_status"] == "AUTHENTICATED_NOT_ONBOARDED"

        # Second call is idempotent — no duplicate broker
        res2 = await ac.post("/api/v1/auth/test/identity", json={"email": email})
        assert res2.status_code == 200

@pytest.mark.asyncio
async def test_10_existing_email_signs_in_with_google_no_duplicate(db_session: AsyncSession):
    """TEST 10: Existing email account signs in with Google -> links identity without duplicate broker/org."""
    email = f"link_account_{uuid.uuid4().hex[:6]}@example.com"
    
    # 1. Broker registers via email
    broker = Broker(
        email=email,
        password_hash=hash_password("Password123!"),
        name="Original Broker",
        phone="+919876543212",
        whatsapp_number="+919876543212",
        agency_name="Original Agency",
        city="Bengaluru",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)
    await db_session.flush()

    org = Organization(
        id=uuid.uuid4(),
        name="Original Agency",
        slug=f"org-{uuid.uuid4().hex[:6]}",
        plan="pro",
        country_code="IN"
    )
    db_session.add(org)
    await db_session.flush()

    member = OrganizationMember(
        organization_id=org.id,
        broker_id=broker.id,
        role="owner"
    )
    db_session.add(member)

    user = User(
        id=broker.id,
        email=email,
        name="Original Broker",
        phone=broker.phone,
        whatsapp_number=broker.whatsapp_number,
        organization_id=str(org.id),
        auth_provider="email",
        subscription_status="active"
    )
    db_session.add(user)
    await db_session.commit()

    # 2. Broker signs in with Google OAuth using same email
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Phase 0 P0.1: identity linking through caller-controlled exchange is
        # gone; mock identity requests are now rejected outright.
        res = await ac.post(
            "/api/v1/auth/google/exchange",
            json={"code": f"test_code_{uuid.uuid4().hex}", "state": "stale-state-value-1234"}
        )
        assert res.status_code == 400

    # Verify no duplicate broker, user, or organization exists
    brokers_count = (await db_session.execute(select(Broker).where(Broker.email == email))).scalars().all()
    assert len(brokers_count) == 1

    users_count = (await db_session.execute(select(User).where(User.email == email))).scalars().all()
    assert len(users_count) == 1

    members_count = (await db_session.execute(select(OrganizationMember).where(OrganizationMember.broker_id == broker.id))).scalars().all()
    assert len(members_count) == 1

@pytest.mark.asyncio
async def test_11_unauthenticated_request_rejected():
    """TEST 11: Unauthenticated request to protected endpoint -> 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me")
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_12_direct_access_suspended_broker_rejected(db_session: AsyncSession):
    """TEST 12: Suspended broker accessing protected API -> 403 Forbidden."""
    email = f"suspended_{uuid.uuid4().hex[:6]}@example.com"
    broker = Broker(
        email=email,
        name="Suspended Broker",
        onboarding_status="SUSPENDED"
    )
    db_session.add(broker)
    await db_session.commit()

    token = create_access_token({"sub": email, "email": email, "broker_id": str(broker.id)})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

@pytest.mark.asyncio
async def test_13_onboarding_submission_transitions_to_onboarded(db_session: AsyncSession):
    """TEST 13: Onboarding submission transitions broker to ONBOARDED and creates org."""
    email = f"onboard_test_{uuid.uuid4().hex[:6]}@example.com"
    broker = Broker(
        email=email,
        name="Pending Broker",
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()

    token = create_access_token({"sub": email, "email": email, "broker_id": str(broker.id)})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/auth/onboard",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Fully Onboarded Broker",
                "phone": "+919876543213",
                "whatsapp_number": "+919876543213",
                "agency_name": "Premium Realty",
                "city": "Bengaluru"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["onboarding_status"] == "ONBOARDED"
        assert data["agency_name"] == "Premium Realty"

@pytest.mark.asyncio
async def test_14_google_auth_url_sanitizes_redirect():
    """TEST 14: Custom redirect_uri is embedded cleanly in the generated Google OAuth URL."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/google/url?redirect_uri=http://localhost:3000/auth/callback")
        assert res.status_code == 200
        data = res.json()
        assert "http%3A%2F%2Flocalhost%3A3000%2Fauth%2Fcallback" in data["auth_url"]

@pytest.mark.asyncio
async def test_15_duplicate_onboarding_submission_idempotent(db_session: AsyncSession):
    """TEST 15: Submitting onboarding twice is idempotent and does not create duplicate organizations."""
    email = f"idempotent_{uuid.uuid4().hex[:6]}@example.com"
    broker = Broker(
        email=email,
        name="Idempotent Broker",
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(broker)
    await db_session.commit()

    token = create_access_token({"sub": email, "email": email, "broker_id": str(broker.id)})
    payload = {
        "name": "Idempotent Broker",
        "phone": "+919876543214",
        "whatsapp_number": "+919876543214",
        "agency_name": "Idempotent Agency",
        "city": "Bengaluru"
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First submission
        res1 = await ac.post("/api/v1/auth/onboard", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert res1.status_code == 200

        # Second submission
        res2 = await ac.post("/api/v1/auth/onboard", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert res2.status_code == 200

    # Ensure only 1 member association exists
    members = (await db_session.execute(select(OrganizationMember).where(OrganizationMember.broker_id == broker.id))).scalars().all()
    assert len(members) == 1
