"""
WefyLabs Part 17 — Enterprise Reliability & Chaos Test Suite
============================================================
Verifies system resilience under operational faults and recovery lifecycles:
- Outbox event lifecycle: PENDING -> PROCESSING -> PROCESSED
- Outbox error backoff & DLQ transition on max retries
- Outbox retention hygiene & purge of processed events
- Deep health check multi-dependency reporting
- Non-destructive data integrity audit execution
- AI cost governance & PII-free accounting
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.database import Base
from app.infrastructure.outbox.outbox_service import OutboxService
from app.models.outbox_models import OutboxEvent, OutboxStatus
from app.presentation.api.health import deep_health_check, liveness_check, readiness_check
from app.modules.diagnostics.integrity_checker import DataIntegrityChecker
from app.modules.ai_agent.safety.runtime_governor import ai_governor


@pytest.fixture
async def async_test_session():
    """Isolated SQLite in-memory async engine."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    async with session_factory() as session:
        yield session

    await test_engine.dispose()


class TestOutboxLifecycleReliability:
    """Verifies transactional outbox state machine, retries, and DLQ."""

    @pytest.mark.asyncio
    async def test_outbox_successful_dispatch_lifecycle(self, async_test_session):
        tenant_id = str(uuid.uuid4())
        event = await OutboxService.record_event(
            async_test_session,
            tenant_id=tenant_id,
            event_type="appointment.confirmed",
            aggregate_type="appointment",
            aggregate_id="appt-555",
            payload={"customer_id": "cust-999", "time": "14:00"}
        )
        assert event.status == OutboxStatus.PENDING

        # Mock handler that succeeds
        async def mock_success_handler(ev: OutboxEvent) -> bool:
            return True

        success = await OutboxService.dispatch_event(
            async_test_session,
            event,
            mock_success_handler
        )

        assert success is True
        assert event.status == OutboxStatus.PROCESSED
        assert event.processed_at is not None
        assert event.retry_count == 0

    @pytest.mark.asyncio
    async def test_outbox_retry_and_dlq_escalation(self, async_test_session):
        tenant_id = str(uuid.uuid4())
        event = await OutboxService.record_event(
            async_test_session,
            tenant_id=tenant_id,
            event_type="notification.dispatch",
            aggregate_type="notification",
            aggregate_id="notif-123",
            payload={"message": "Your booking is confirmed"},
            max_retries=2  # Low max_retries to test DLQ quickly
        )

        # Mock handler that raises an exception
        async def mock_failing_handler(ev: OutboxEvent) -> bool:
            raise ConnectionError("Downstream gateway timeout")

        # Attempt 1: Fails, retry_count=1 -> FAILED
        await OutboxService.dispatch_event(async_test_session, event, mock_failing_handler)
        assert event.status == OutboxStatus.FAILED
        assert event.retry_count == 1
        assert "ConnectionError" in event.last_error
        assert event.next_retry_at is not None

        # Attempt 2: Fails again, reaches max_retries (2) -> DEAD_LETTER
        await OutboxService.dispatch_event(async_test_session, event, mock_failing_handler)
        assert event.status == OutboxStatus.DEAD_LETTER
        assert event.retry_count == 2
        assert event.next_retry_at is None

    @pytest.mark.asyncio
    async def test_outbox_purge_processed_hygiene(self, async_test_session):
        tenant_id = str(uuid.uuid4())
        # Event 1: Old processed event (15 days old)
        ev1 = await OutboxService.record_event(
            async_test_session,
            tenant_id=tenant_id,
            event_type="test.old",
            aggregate_type="test",
            aggregate_id="1",
            payload={}
        )
        ev1.mark_processed()
        ev1.processed_at = datetime.now(timezone.utc) - timedelta(days=15)

        # Event 2: Fresh pending event
        ev2 = await OutboxService.record_event(
            async_test_session,
            tenant_id=tenant_id,
            event_type="test.new",
            aggregate_type="test",
            aggregate_id="2",
            payload={}
        )
        await async_test_session.flush()

        # Purge older than 14 days
        purged_count = await OutboxService.purge_processed_events(
            async_test_session,
            retention_days=14,
            tenant_id=tenant_id
        )
        assert purged_count == 1

        # Verify ev2 still exists
        remaining = await OutboxService.fetch_due_events(async_test_session, tenant_id=tenant_id)
        assert len(remaining) == 1
        assert remaining[0].id == ev2.id


class TestHealthEndpointsReliability:
    """Verifies operational health check responses and contracts."""

    @pytest.mark.asyncio
    async def test_liveness_probe_returns_alive(self):
        resp = await liveness_check()
        assert resp["status"] == "alive"
        assert "version" in resp

    @pytest.mark.asyncio
    async def test_readiness_probe_contract(self):
        resp = await readiness_check()
        # Status code is 200 or 503 depending on local redis
        assert resp.status_code in (200, 503)
        body = resp.body.decode()
        assert "checks" in body

    @pytest.mark.asyncio
    async def test_deep_health_probe_reports_all_subsystems(self):
        resp = await deep_health_check()
        assert resp.status_code in (200, 207)
        import json
        data = json.loads(resp.body.decode())
        assert "status" in data
        assert "dependencies" in data
        assert "outbox_queue" in data
        assert "security_metrics" in data
        assert "database" in data["dependencies"]
        assert "redis" in data["dependencies"]


class TestDataIntegrityDiagnosticsReliability:
    """Verifies non-destructive data integrity checks."""

    @pytest.mark.asyncio
    async def test_full_diagnostic_runs_cleanly(self, async_test_session):
        audit = await DataIntegrityChecker.run_full_diagnostic(async_test_session)
        assert "timestamp" in audit
        assert "overall_integrity_status" in audit
        assert "diagnostics" in audit
        assert audit["diagnostics"]["orphans"]["status"] == "PASS"


class TestAICostGovernanceReliability:
    """Verifies that token and spend accounting works without logging prompt texts."""

    def test_record_usage_omits_raw_prompts(self):
        tenant_id = f"test-tenant-{uuid.uuid4().hex[:6]}"
        rec = ai_governor.record_usage(
            tenant_id=tenant_id,
            model="gemini-3.5-flash",
            input_tokens=1500,
            output_tokens=300,
            latency_ms=245.5,
            feature="lead_qualification",
            success=True
        )

        assert rec["tenant_id"] == tenant_id
        assert rec["total_tokens"] == 1800
        assert rec["estimated_cost_cents"] > 0
        assert "prompt" not in rec
        assert "system_instruction" not in rec

        # Verify tenant accumulated spend
        spend = ai_governor.get_tenant_spend(tenant_id)
        assert spend == rec["estimated_cost_cents"]
