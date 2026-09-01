"""
Identity Resolution Celery Worker — async background task for queue processing.
Subscribes to LeadNormalized events and triggers identity resolution pipeline.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def process_identity_resolution_queue(lead_data: Dict[str, Any], organization_id: str):
    """
    Celery task: process a lead through the identity resolution pipeline.
    Triggered by LeadNormalized event from the ingestion engine.

    Note: This is a synchronous Celery task wrapper.
    The actual async pipeline runs inside an asyncio event loop.
    """
    import asyncio
    from app.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            from app.modules.identity_resolution.service import IdentityResolutionService
            service = IdentityResolutionService(db=db, redis_client=None)
            return await service.resolve_lead(lead_data, organization_id)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        loop.close()
        logger.info(
            f"[IDENTITY_WORKER] Resolved lead {lead_data.get('id')}: "
            f"decision={result.get('decision')} identity={result.get('identity_id')}"
        )
        return result
    except Exception as e:
        logger.error(f"[IDENTITY_WORKER] Resolution failed for lead {lead_data.get('id')}: {e}")
        raise
