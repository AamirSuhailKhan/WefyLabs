"""
Automated Guard Tests for Database Isolation & Safety (Master Prompts 6 & 7)
=============================================================================
Tests verify that:
1. Harness refuses to connect to 'leadscore'.
2. Missing test-database configuration causes an immediate failure.
3. Invalid database configuration prevents any write.
4. Cleanup cannot delete a pre-existing organization.
5. Cleanup cannot delete a pre-existing broker.
6. Cleanup cannot delete a pre-existing lead.
7. Cleanup uses captured test-owned IDs only.
8. Duplicate test execution does not clean up another test's data.
9. Failure halfway through setup leaves either a safely recoverable test state or a properly isolated database.
10. The application environment cannot accidentally be mistaken for the test environment.
11. POSITIVE ALLOWLIST: Unfamiliar database names are rejected fail-closed.
12. ENGINE-SESSION VERIFICATION: Session factory target mismatch raises EngineSessionMismatchError.
13. CLEANUP IDEMPOTENCY: Calling cleanup multiple times is safe and returns cached summary.
14. HOST ISOLATION: Unapproved remote host targets are rejected.
"""
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.pool import NullPool

from app.core.database_safety import (
    validate_test_database_target,
    is_live_or_shared_database,
    verify_session_target,
    UnsafeDatabaseTargetError,
    AmbiguousEnvironmentError,
    EngineSessionMismatchError,
    UnregisteredEntityCleanupError,
    TestEntityTracker,
    EXPLICIT_TEST_DATABASE_ALLOWLIST,
)
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.organization import Organization, OrganizationMember


class TestDatabaseIsolationGuards:
    """Proves the fail-closed database isolation gates."""

    # 1. The harness refuses to connect to 'leadscore'
    def test_guard_01_refuses_live_database_leadscore(self):
        live_urls = [
            "postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore",
            "postgresql+asyncpg://postgres:postgres@postgres:5432/leadscore",
            "postgresql://user:pass@prod.supabase.co:5432/leadscore",
            "postgresql+asyncpg://user:pass@internal.host:5432/leadscore_prod",
        ]
        for url in live_urls:
            with pytest.raises(UnsafeDatabaseTargetError) as exc_info:
                validate_test_database_target(url, env="testing")
            assert "CRITICAL SAFETY LOCKOUT" in str(exc_info.value) or "REFUSED" in str(exc_info.value)

    # 2. Missing test-database configuration causes an immediate failure
    def test_guard_02_missing_database_configuration_fails_immediately(self):
        for bad_url in [None, "", "   "]:
            with pytest.raises(UnsafeDatabaseTargetError) as exc_info:
                validate_test_database_target(bad_url, env="testing")
            assert "missing or empty" in str(exc_info.value)

    # 3. Invalid database configuration prevents any write
    def test_guard_03_invalid_database_configuration_prevents_write(self):
        unapproved_urls = [
            "postgresql+asyncpg://localhost:5432/arbitrary_dev_db",
            "postgresql+asyncpg://localhost:5432/customer_sandbox",
            "postgresql+asyncpg://localhost:5432/leadscore_replica",
        ]
        for url in unapproved_urls:
            with pytest.raises(UnsafeDatabaseTargetError) as exc_info:
                validate_test_database_target(url, env="testing")
            assert "not in the positive test database allowlist" in str(exc_info.value)

    # 4. Cleanup cannot delete a pre-existing organization
    @pytest.mark.asyncio
    async def test_guard_04_cleanup_cannot_delete_preexisting_organization(self, db_session: AsyncSession):
        pre_existing_org_id = uuid.uuid4()
        pre_existing_org = Organization(
            id=pre_existing_org_id,
            name="Pre-existing Production Org",
            slug="preexisting-prod-org",
            plan="enterprise",
        )
        db_session.add(pre_existing_org)
        await db_session.commit()

        # Tracker is aware of pre-existing records
        tracker = TestEntityTracker(
            pre_existing_ids={"organizations": {str(pre_existing_org_id)}}
        )

        # Attempting to register pre-existing record raises immediately
        with pytest.raises(UnregisteredEntityCleanupError):
            tracker.register("organizations", pre_existing_org_id)

        # Cleanup does not touch it
        await tracker.safe_cleanup(db_session)
        rem = await db_session.get(Organization, pre_existing_org_id)
        assert rem is not None
        assert rem.id == pre_existing_org_id

    # 5. Cleanup cannot delete a pre-existing broker
    @pytest.mark.asyncio
    async def test_guard_05_cleanup_cannot_delete_preexisting_broker(self, db_session: AsyncSession):
        pre_existing_broker_id = uuid.uuid4()
        pre_broker = Broker(
            id=pre_existing_broker_id,
            email="existing_broker@pilot.test",
            name="Existing Broker Admin",
            phone="+919999999999",
        )
        db_session.add(pre_broker)
        await db_session.commit()

        tracker = TestEntityTracker(
            pre_existing_ids={"brokers": {str(pre_existing_broker_id)}}
        )

        with pytest.raises(UnregisteredEntityCleanupError):
            tracker.register("brokers", pre_existing_broker_id)

        await tracker.safe_cleanup(db_session)
        rem = await db_session.get(Broker, pre_existing_broker_id)
        assert rem is not None

    # 6. Cleanup cannot delete a pre-existing lead
    @pytest.mark.asyncio
    async def test_guard_06_cleanup_cannot_delete_preexisting_lead(self, db_session: AsyncSession, test_broker: Broker):
        pre_lead_id = uuid.uuid4()
        pre_lead = Lead(
            id=pre_lead_id,
            broker_id=test_broker.id,
            name="Existing Production Lead",
            phone="+919111111111",
            status="active"
        )
        db_session.add(pre_lead)
        await db_session.commit()

        tracker = TestEntityTracker(
            pre_existing_ids={"leads": {str(pre_lead_id)}}
        )

        with pytest.raises(UnregisteredEntityCleanupError):
            tracker.register("leads", pre_lead_id)

        await tracker.safe_cleanup(db_session)
        rem = await db_session.get(Lead, pre_lead_id)
        assert rem is not None

    # 7. Cleanup uses captured test-owned IDs only
    @pytest.mark.asyncio
    async def test_guard_07_cleanup_uses_captured_test_owned_ids_only(self, db_session: AsyncSession, test_broker: Broker):
        untracked_lead = Lead(
            id=uuid.uuid4(),
            broker_id=test_broker.id,
            name="Untracked Lead",
            phone="+919222222222",
            status="active"
        )
        db_session.add(untracked_lead)

        tracked_lead_id = uuid.uuid4()
        tracked_lead = Lead(
            id=tracked_lead_id,
            broker_id=test_broker.id,
            name="Tracked Test Lead",
            phone="+919333333333",
            status="active"
        )
        db_session.add(tracked_lead)
        await db_session.commit()

        tracker = TestEntityTracker()
        tracker.register("leads", tracked_lead_id)

        summary = await tracker.safe_cleanup(db_session)
        assert summary["records_purged"].get("leads") == 1

        assert await db_session.get(Lead, tracked_lead_id) is None
        assert await db_session.get(Lead, untracked_lead.id) is not None

    # 8. Duplicate test execution does not clean up another test's data
    @pytest.mark.asyncio
    async def test_guard_08_duplicate_test_does_not_clean_other_test_data(self, db_session: AsyncSession, test_broker: Broker):
        lead_test_1 = Lead(
            id=uuid.uuid4(),
            broker_id=test_broker.id,
            name="Test Run 1 Lead",
            phone="+919444444441",
            status="active"
        )
        lead_test_2 = Lead(
            id=uuid.uuid4(),
            broker_id=test_broker.id,
            name="Test Run 2 Lead",
            phone="+919444444442",
            status="active"
        )
        db_session.add_all([lead_test_1, lead_test_2])
        await db_session.commit()

        tracker1 = TestEntityTracker(test_run_id="run-001")
        tracker1.register("leads", lead_test_1.id)

        tracker2 = TestEntityTracker(test_run_id="run-002")
        tracker2.register("leads", lead_test_2.id)

        await tracker1.safe_cleanup(db_session)
        assert await db_session.get(Lead, lead_test_1.id) is None
        assert await db_session.get(Lead, lead_test_2.id) is not None

        await tracker2.safe_cleanup(db_session)
        assert await db_session.get(Lead, lead_test_2.id) is None

    # 9. Failure halfway through setup leaves recoverable test state
    @pytest.mark.asyncio
    async def test_guard_09_failure_halfway_leaves_recoverable_state(self, db_session: AsyncSession, test_broker: Broker):
        tracker = TestEntityTracker()
        lead1_id = uuid.uuid4()
        lead1 = Lead(
            id=lead1_id,
            broker_id=test_broker.id,
            name="Halfway Lead 1",
            phone="+919555555551",
            status="active"
        )
        db_session.add(lead1)
        await db_session.commit()
        tracker.register("leads", lead1_id)

        try:
            raise RuntimeError("Setup failed halfway!")
        except RuntimeError:
            pass

        await tracker.safe_cleanup(db_session)
        assert await db_session.get(Lead, lead1_id) is None

    # 10. The application environment cannot accidentally be mistaken for the test environment
    def test_guard_10_app_env_cannot_be_mistaken_for_test(self):
        ambiguous_or_prod_envs = [
            "production",
            "prod",
            "staging",
            "",
            None,
        ]
        safe_url = "postgresql+asyncpg://localhost:5432/leadscore_test_acceptance"
        for bad_env in ambiguous_or_prod_envs:
            with pytest.raises(AmbiguousEnvironmentError):
                validate_test_database_target(safe_url, env=bad_env)

    # 11. Positive allowlist rejects unfamiliar database names
    def test_guard_11_positive_allowlist_rejects_unfamiliar_names(self):
        unfamiliar_dbs = [
            "postgresql+asyncpg://localhost:5432/customer_crm_staging",
            "postgresql+asyncpg://localhost:5432/some_broker_db",
            "postgresql+asyncpg://localhost:5432/unknown_test_sandbox",
        ]
        for url in unfamiliar_dbs:
            with pytest.raises(UnsafeDatabaseTargetError) as exc_info:
                validate_test_database_target(url, env="testing")
            assert "positive test database allowlist" in str(exc_info.value)

    # 12. Engine-Session target mismatch detection
    @pytest.mark.asyncio
    async def test_guard_12_engine_session_target_mismatch(self, db_session: AsyncSession):
        # db_session is in-memory SQLite (":memory:")
        # Attempting to assert it is 'leadscore_test_acceptance' must fail immediately
        with pytest.raises(EngineSessionMismatchError) as exc_info:
            verify_session_target(db_session, expected_db="leadscore_test_acceptance")
        assert "ENGINE-SESSION MISMATCH DETECTED" in str(exc_info.value)

    # 13. Cleanup idempotency (calling cleanup twice is safe)
    @pytest.mark.asyncio
    async def test_guard_13_cleanup_idempotency(self, db_session: AsyncSession, test_broker: Broker):
        tracker = TestEntityTracker()
        lead_id = uuid.uuid4()
        lead = Lead(id=lead_id, broker_id=test_broker.id, name="Idempotent Test", phone="+919000000000")
        db_session.add(lead)
        await db_session.commit()
        tracker.register("leads", lead_id)

        # First cleanup call
        summary1 = await tracker.safe_cleanup(db_session)
        assert summary1["records_purged"].get("leads") == 1

        # Second cleanup call: must return cached summary without error
        summary2 = await tracker.safe_cleanup(db_session)
        assert summary2 == summary1

    # 14. Host isolation: Remote or unapproved hosts are rejected
    def test_guard_14_rejects_unapproved_remote_hosts(self):
        remote_urls = [
            "postgresql+asyncpg://user:pass@remote.production.aws.com:5432/leadscore_test",
            "postgresql+asyncpg://user:pass@192.168.1.100:5432/leadscore_test",
        ]
        for url in remote_urls:
            with pytest.raises(UnsafeDatabaseTargetError) as exc_info:
                validate_test_database_target(url, env="testing")
            assert "not an approved test host" in str(exc_info.value)
