"""
Scoring Tasks — Celery Async Worker Tasks for Lead Intelligence Engine
=======================================================================
Executes background scoring, prediction processing, and batch revenue forecasting.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def process_lead_scoring_queue(lead_dto: Dict[str, Any], organization_id: str):
    """
    Celery task: process a lead through the AI Lead Intelligence pipeline.
    Triggered by LeadCreated, LeadEnriched, or IdentityResolved events.
    """
    import asyncio
    from app.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            from app.modules.lead_intelligence.service import LeadIntelligenceService
            service = LeadIntelligenceService(db=db)
            return await service.score_lead(lead_dto, organization_id)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        loop.close()
        logger.info(
            f"[SCORING_WORKER] Processed lead {lead_dto.get('id')}: "
            f"score={result.get('lead_score')} temp={result.get('temperature')}"
        )
        return result
    except Exception as e:
        logger.error(f"[SCORING_WORKER] Scoring failed for lead {lead_dto.get('id')}: {e}")
        raise
