"""
PART 31 — Celery Background Tasks for Customer Onboarding & Demo Lifecycle
==========================================================================
Scheduled & asynchronous Celery tasks:
1. cleanup_expired_demo_sessions_task: Safely purges expired demo tenants (TTL expiry).
2. send_onboarding_reminder_task: Sends idempotent setup reminders to incomplete tenants.
3. calculate_activation_snapshot_task: Evaluates live activation milestones in background.
"""
import asyncio
import logging
from typing import Dict, Any
from app.tasks.celery_worker import celery_app
from app.database import AsyncSessionLocal

logger = logging.getLogger("beetlelabs.tasks.onboarding")


def _run_async(coro):
    """Safely runs an async coroutine inside a synchronous Celery task thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def cleanup_expired_demo_sessions_task(self) -> Dict[str, Any]:
    """
    Scheduled task that purges expired demo workspaces.
    Strictly isolated to organizations with is_demo=True.
    """
    async def _execute():
        async with AsyncSessionLocal() as db:
            from app.modules.onboarding.demo_service import DemoModeService
            demo_svc = DemoModeService(db)
            purged = await demo_svc.cleanup_expired_demo_sessions()
            await db.commit()
            return {"status": "success", "purged_sessions_count": purged}

    try:
        return _run_async(_execute())
    except Exception as exc:
        logger.error(f"[CELERY_ONBOARDING] cleanup_expired_demo_sessions_task failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def calculate_activation_snapshot_task(self, broker_id: str, organization_id: str) -> Dict[str, Any]:
    """
    Asynchronous milestone calculation snapshot for a tenant organization.
    """
    import uuid
    async def _execute():
        async with AsyncSessionLocal() as db:
            from app.models.broker import Broker
            from app.modules.onboarding.activation_service import TenantActivationService
            b_uuid = uuid.UUID(broker_id)
            org_uuid = uuid.UUID(organization_id)
            broker = await db.get(Broker, b_uuid)
            if not broker:
                return {"status": "skipped", "reason": "Broker not found"}

            svc = TenantActivationService(db)
            res = await svc.get_or_calculate_activation(broker, org_uuid, force_refresh=True)
            await db.commit()
            return {
                "status": "success",
                "is_activated": res.is_activated,
                "activation_score": res.activation_score
            }

    try:
        return _run_async(_execute())
    except Exception as exc:
        logger.error(f"[CELERY_ONBOARDING] calculate_activation_snapshot_task failed: {exc}")
        raise self.retry(exc=exc)
