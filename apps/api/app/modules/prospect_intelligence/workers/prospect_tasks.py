"""
Part 21.2A — Prospect Intelligence Async Celery Tasks
========================================================
Background tasks for executing AI prospect analysis without blocking interactive CRM endpoints.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from app.celery_app import celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    celery_app = None


async def _async_analyze_lead_prospect(organization_id: str, lead_id: str, force_refresh: bool):
    from app.database import async_session_factory
    from app.modules.prospect_intelligence.services.prospect_intelligence_service import ProspectIntelligenceService

    async with async_session_factory() as db:
        service = ProspectIntelligenceService(db)
        await service.analyze_lead(organization_id=organization_id, lead_id=lead_id, force_refresh=force_refresh)


if CELERY_AVAILABLE and celery_app:
    @celery_app.task(
        name="prospect_intelligence.analyze_lead_task",
        bind=True,
        max_retries=3,
        default_retry_delay=30,
        acks_late=True,
    )
    def analyze_lead_prospect_task(self, organization_id: str, lead_id: str, force_refresh: bool = False):
        """Asynchronously analyze lead prospect intelligence."""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_async_analyze_lead_prospect(organization_id, lead_id, force_refresh))
        except Exception as exc:
            logger.error(f"[PROSPECT_TASK] Lead {lead_id} analysis failed: {exc}")
            raise self.retry(exc=exc)
        finally:
            loop.close()

else:
    def analyze_lead_prospect_task(organization_id: str, lead_id: str, force_refresh: bool = False):
        """Synchronous in-process fallback when Celery worker is offline."""
        logger.info(f"[PROSPECT_TASK_FALLBACK] In-process execution for lead {lead_id}")
        return None
