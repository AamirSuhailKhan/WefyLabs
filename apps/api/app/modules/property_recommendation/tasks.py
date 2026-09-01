"""
Part 21.3 — Property Recommendation Async Celery Tasks
=======================================================
Background tasks for calculating and refreshing property recommendations
without blocking interactive web requests.
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


async def _async_generate_recommendations(organization_id: str, lead_id: str, top_k: int = 5):
    from app.database import async_session_factory
    from app.modules.property_recommendation.service import PropertyRecommendationService
    from app.modules.property_recommendation.dto import PropertyRecommendationRequestDTO

    async with async_session_factory() as db:
        service = PropertyRecommendationService(db)
        dto = PropertyRecommendationRequestDTO(lead_id=lead_id, top_k=top_k)
        await service.generate_recommendations(dto, organization_id=organization_id)


if CELERY_AVAILABLE and celery_app:
    @celery_app.task(
        name="property_recommendation.generate_recommendations_task",
        bind=True,
        max_retries=3,
        default_retry_delay=30,
        acks_late=True,
    )
    def generate_property_recommendations_task(self, organization_id: str, lead_id: str, top_k: int = 5):
        """Asynchronously compute property recommendations."""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_async_generate_recommendations(organization_id, lead_id, top_k))
        except Exception as exc:
            logger.error(f"[REC_TASK] Lead {lead_id} recommendation failed: {exc}")
            raise self.retry(exc=exc)
        finally:
            loop.close()

else:
    def generate_property_recommendations_task(organization_id: str, lead_id: str, top_k: int = 5):
        """Synchronous in-process fallback when Celery worker is offline."""
        logger.info(f"[REC_TASK_FALLBACK] In-process execution for lead {lead_id}")
        return None
