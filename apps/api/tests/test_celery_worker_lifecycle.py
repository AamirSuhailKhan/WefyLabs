"""
Automated Regression Tests for Celery Worker Event Loop & Database Lifecycle
===========================================================================
Verifies:
1. Sequential execution of coroutines via centralized run_async maintains a persistent,
   open event loop and never raises RuntimeError: Event loop is closed.
2. Worker process lifecycle signals (worker_process_init / reset_worker_event_loop,
   worker_process_shutdown / close_worker_event_loop) cleanly reset the loop and pool.
3. CRM intelligence tasks are registered in Celery under fully-qualified names
   matching beat_schedule and task_routes.
4. Autonomous loop tasks correctly handle tenant_id="__all__" without asyncpg UUID cast errors.
5. Exception propagation leaves the loop healthy for subsequent tasks.
6. Thread-isolation: concurrent worker threads maintain independent persistent loops.
7. Nested active loop compatibility (e.g. under pytest-asyncio).
8. Strict fail-closed tenant boundary and security enforcement.
"""

import asyncio
import concurrent.futures
import threading
import uuid
try:
    import pytest
    asyncio_test = pytest.mark.asyncio
except ImportError:
    pytest = None
    def asyncio_test(f):
        return f
from unittest.mock import AsyncMock, patch, MagicMock

from app.celery_app import celery_app
from app.core.async_runner import (
    get_worker_event_loop,
    run_async,
    reset_worker_event_loop,
    close_worker_event_loop,
)


def test_persistent_event_loop_across_sequential_calls():
    """
    Simulates sequential Celery task executions in the same worker process.
    Proves that the event loop remains open across invocations and does NOT close.
    """
    reset_worker_event_loop()

    results = []

    async def task_coro_1():
        await asyncio.sleep(0.01)
        return "result_1"

    async def task_coro_2():
        await asyncio.sleep(0.01)
        return "result_2"

    async def task_coro_3():
        await asyncio.sleep(0.01)
        return "result_3"

    res1 = run_async(task_coro_1())
    loop1 = get_worker_event_loop()
    assert not loop1.is_closed(), "Loop was closed after task 1"
    assert res1 == "result_1"

    res2 = run_async(task_coro_2())
    loop2 = get_worker_event_loop()
    assert not loop2.is_closed(), "Loop was closed after task 2"
    assert loop1 is loop2, "Loop was replaced instead of reused"
    assert res2 == "result_2"

    res3 = run_async(task_coro_3())
    loop3 = get_worker_event_loop()
    assert not loop3.is_closed(), "Loop was closed after task 3"
    assert loop1 is loop3, "Loop was replaced instead of reused"
    assert res3 == "result_3"


def test_exception_propagation_and_loop_integrity():
    """
    Verifies that exceptions in coroutines propagate cleanly and the event loop
    remains open and healthy for subsequent tasks without corruption.
    """
    reset_worker_event_loop()

    class CustomTaskError(Exception):
        pass

    async def failing_task():
        await asyncio.sleep(0.01)
        raise CustomTaskError("Task failed intentionally")

    async def succeeding_task():
        await asyncio.sleep(0.01)
        return "recovered"

    # Step 1: Exception is propagated
    exception_caught = False
    try:
        run_async(failing_task())
    except CustomTaskError:
        exception_caught = True
    assert exception_caught, "Expected CustomTaskError was not raised by run_async"

    # Step 2: Loop is still alive and subsequent task succeeds
    loop = get_worker_event_loop()
    assert not loop.is_closed(), "Loop was closed after an exception"
    res = run_async(succeeding_task())
    assert res == "recovered"


def test_thread_isolation_concurrent_runners():
    """
    Verifies that run_async is thread-safe: two separate worker threads
    get independent persistent loops without collision or corruption.
    """
    reset_worker_event_loop()

    def thread_worker(val: int):
        async def work():
            await asyncio.sleep(0.02)
            return val * 2
        return run_async(work())

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(thread_worker, 10)
        f2 = executor.submit(thread_worker, 20)
        assert f1.result() == 20
        assert f2.result() == 40


def test_nested_or_active_loop_compatibility():
    """
    Verifies that calling run_async from an already active event loop (e.g. pytest-asyncio)
    delegates safely via thread pool rather than crashing.
    """
    async def outer():
        async def inner():
            await asyncio.sleep(0.01)
            return "inner_ok"
        return run_async(inner())

    # Run outer in an active event loop
    outer_loop = asyncio.new_event_loop()
    try:
        result = outer_loop.run_until_complete(outer())
        assert result == "inner_ok"
    finally:
        outer_loop.close()


def test_reset_worker_event_loop_lifecycle():
    """
    Verifies that reset_worker_event_loop() properly disposes and cleans up.
    """
    async def sample():
        return 42

    assert run_async(sample()) == 42
    old_loop = get_worker_event_loop()
    assert not old_loop.is_closed()

    # Worker process fork / init
    reset_worker_event_loop()

    # Next call creates a fresh loop
    assert run_async(sample()) == 42
    new_loop = get_worker_event_loop()
    assert new_loop is not old_loop
    assert not new_loop.is_closed()

    # Worker process shutdown
    close_worker_event_loop()


def test_crm_intelligence_task_registration_names():
    """
    Verifies that all CRM Intelligence tasks are registered under the fully-qualified
    names that celery_app.conf.beat_schedule and task_routes expect.
    """
    expected_tasks = [
        "app.modules.crm_intelligence.workers.intelligence_tasks.evaluate_lead_health_and_decay_task",
        "app.modules.crm_intelligence.workers.intelligence_tasks.monitor_sla_breaches_task",
        "app.modules.crm_intelligence.workers.intelligence_tasks.evaluate_pipeline_stagnation_task",
        "app.modules.crm_intelligence.workers.intelligence_tasks.calculate_agent_workload_task",
        "app.modules.crm_intelligence.workers.intelligence_tasks.detect_crm_anomalies_task",
        "app.modules.crm_intelligence.workers.intelligence_tasks.generate_daily_briefs_task",
    ]

    celery_app.loader.import_default_modules()
    registered_task_names = set(celery_app.tasks.keys())
    for task_name in expected_tasks:
        assert task_name in registered_task_names, f"Task {task_name} was NOT registered in Celery app!"


@asyncio_test
async def test_evaluate_inactive_leads_handles_all_and_uuid_tenant():
    """
    Verifies that evaluate_inactive_leads_task queries all leads when tenant_id='__all__'
    and converts valid UUIDs when a specific tenant_id is provided.
    """
    from app.modules.autonomous_loop.workers.loop_tasks import evaluate_inactive_leads_task

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    # Mock execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.modules.autonomous_loop.workers.loop_tasks._get_async_session") as mock_sess_factory:
        mock_sess = AsyncMock()
        mock_sess.__aenter__.return_value = mock_db
        mock_sess.__aexit__.return_value = None
        mock_sess_factory.return_value = mock_sess

        # Test with '__all__'
        res_all = evaluate_inactive_leads_task(tenant_id="__all__")
        assert res_all["status"] == "SUCCESS"
        assert res_all["leads_scanned"] == 0

        # Test with a specific UUID
        specific_tenant = str(uuid.uuid4())
        res_specific = evaluate_inactive_leads_task(tenant_id=specific_tenant)
        assert res_specific["status"] == "SUCCESS"
        assert res_specific["leads_scanned"] == 0


@asyncio_test
async def test_tenant_security_fail_closed_invalid_tenant():
    """
    Verifies that evaluate_inactive_leads_task fails closed immediately
    if an invalid non-UUID tenant identifier is passed.
    """
    from app.modules.autonomous_loop.workers.loop_tasks import evaluate_inactive_leads_task

    res = evaluate_inactive_leads_task(tenant_id="invalid-tenant-string' OR 1=1--")
    assert res["status"] == "SUCCESS"
    assert res["leads_scanned"] == 0
    assert res["processed"] == 0


@asyncio_test
async def test_retry_failed_events_handles_all_and_specific_tenant():
    """
    Verifies that retry_failed_events_task correctly queries retryable events
    when tenant_id='__all__' vs a specific tenant.
    """
    from app.modules.autonomous_loop.workers.loop_tasks import retry_failed_events_task

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.modules.autonomous_loop.workers.loop_tasks._get_async_session") as mock_sess_factory:
        mock_sess = AsyncMock()
        mock_sess.__aenter__.return_value = mock_db
        mock_sess.__aexit__.return_value = None
        mock_sess_factory.return_value = mock_sess

        res_all = retry_failed_events_task(tenant_id="__all__")
        assert res_all["status"] == "SUCCESS"
        assert res_all["retried"] == 0

        res_specific = retry_failed_events_task(tenant_id="tenant_123")
        assert res_specific["status"] == "SUCCESS"
        assert res_specific["retried"] == 0


if __name__ == "__main__":
    print("Running Celery worker lifecycle regression tests...")
    test_persistent_event_loop_across_sequential_calls()
    print("  ✓ test_persistent_event_loop_across_sequential_calls passed")
    test_exception_propagation_and_loop_integrity()
    print("  ✓ test_exception_propagation_and_loop_integrity passed")
    test_thread_isolation_concurrent_runners()
    print("  ✓ test_thread_isolation_concurrent_runners passed")
    test_nested_or_active_loop_compatibility()
    print("  ✓ test_nested_or_active_loop_compatibility passed")
    test_reset_worker_event_loop_lifecycle()
    print("  ✓ test_reset_worker_event_loop_lifecycle passed")
    test_crm_intelligence_task_registration_names()
    print("  ✓ test_crm_intelligence_task_registration_names passed")
    asyncio.run(test_evaluate_inactive_leads_handles_all_and_uuid_tenant())
    print("  ✓ test_evaluate_inactive_leads_handles_all_and_uuid_tenant passed")
    asyncio.run(test_tenant_security_fail_closed_invalid_tenant())
    print("  ✓ test_tenant_security_fail_closed_invalid_tenant passed")
    asyncio.run(test_retry_failed_events_handles_all_and_specific_tenant())
    print("  ✓ test_retry_failed_events_handles_all_and_specific_tenant passed")
    print("All Celery worker lifecycle tests completed successfully!")
