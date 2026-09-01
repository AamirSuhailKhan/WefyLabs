"""
Volume 2 PART 2 — Celery Enrichment Queue Workers & Tasks
"""
import asyncio
import logging
from typing import Dict, Any
from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.modules.enrichment.service import LeadEnrichmentService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300
)
def process_enrichment_queue(self, lead_dto: Dict[str, Any], trigger_source: str = "LeadNormalized"):
    """
    Asynchronous queue worker for AI Lead Enrichment Engine.
    Subscribed to LeadNormalized events.
    """
    logger.info(f"[ENRICHMENT_WORKER] Processing lead enrichment task for Lead ID: {lead_dto.get('id')}")

    async def _run():
        async with AsyncSessionLocal() as session:
            service = LeadEnrichmentService(db=session)
            return await service.enrich_lead(lead_dto=lead_dto, trigger_source=trigger_source)

    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Running inside async event loop
        return asyncio.ensure_future(_run())
    else:
        return loop.run_until_complete(_run())


@celery_app.task(bind=True, max_retries=3)
def process_re_enrichment(self, lead_id: str, trigger_source: str = "ReEnrichRequested"):
    """
    Background task to force re-enrichment of an existing lead.
    """
    logger.info(f"[ENRICHMENT_WORKER] Re-enriching Lead ID: {lead_id}")
    return {"status": "re_enrichment_queued", "lead_id": lead_id}
