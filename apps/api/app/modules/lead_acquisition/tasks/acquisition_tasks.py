"""
Part 21.1 — Acquisition Celery Tasks
======================================
Async processing tasks for lead acquisition pipeline.

Uses existing Celery + Redis infrastructure.

Long-running operations are never executed in the initial webhook request:
  Initial API → acknowledge (fast) → queue task → async normalize/dedupe/enrich

Tasks:
  process_acquisition_event   — full async pipeline for a recorded event
  async_normalize_prospect    — normalize contact fields
  async_deduplicate_prospect  — run identity resolution / dedup
  async_score_prospect        — compute acquisition quality score
  async_ai_extract_fields     — AI-based field extraction
  retry_failed_acquisition    — retry failed events from DLQ
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
    logger.debug("[TASKS] Celery not available — tasks will run synchronously")


def _get_celery_task(name: str):
    """Decorator factory that degrades gracefully if Celery unavailable."""
    def decorator(func):
        if CELERY_AVAILABLE and celery_app:
            return celery_app.task(
                name=name,
                bind=True,
                max_retries=3,
                default_retry_delay=30,
            )(func)
        return func
    return decorator


if CELERY_AVAILABLE and celery_app:
    @celery_app.task(
        name="lead_acquisition.process_acquisition_event",
        bind=True,
        max_retries=3,
        default_retry_delay=60,
        acks_late=True,
    )
    def process_acquisition_event(
        self,
        organization_id: str,
        prospect_id: str,
        source_id: Optional[str] = None,
    ):
        """
        Full async acquisition processing pipeline.

        Runs: normalize → deduplicate → quality score → AI extraction
        """
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                _async_process_acquisition_event(organization_id, prospect_id, source_id)
            )
        except Exception as exc:
            logger.error(f"[ACQ_TASK] process_acquisition_event failed: {exc}")
            raise self.retry(exc=exc)
        finally:
            loop.close()

    @celery_app.task(
        name="lead_acquisition.async_ai_extract_fields",
        bind=True,
        max_retries=2,
        default_retry_delay=30,
    )
    def async_ai_extract_fields(self, organization_id: str, prospect_id: str):
        """Async AI field extraction for a prospect."""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                _async_ai_extract(organization_id, prospect_id)
            )
        except Exception as exc:
            logger.warning(f"[ACQ_TASK] AI extraction failed for prospect {prospect_id}: {exc}")
            # AI extraction failure is non-fatal — log and continue
        finally:
            loop.close()

    @celery_app.task(
        name="lead_acquisition.retry_failed_acquisition",
        bind=True,
        max_retries=5,
        default_retry_delay=120,
    )
    def retry_failed_acquisition(self, organization_id: str, prospect_id: str):
        """Retry a previously failed acquisition event."""
        logger.info(f"[ACQ_TASK] Retrying failed acquisition: prospect={prospect_id}")
        return process_acquisition_event.apply_async(
            args=[organization_id, prospect_id],
        )

else:
    # No-op stubs when Celery unavailable (test environments)
    def process_acquisition_event(*args, **kwargs):
        logger.debug("[ACQ_TASK][STUB] process_acquisition_event (Celery unavailable)")

    def async_ai_extract_fields(*args, **kwargs):
        logger.debug("[ACQ_TASK][STUB] async_ai_extract_fields (Celery unavailable)")

    def retry_failed_acquisition(*args, **kwargs):
        logger.debug("[ACQ_TASK][STUB] retry_failed_acquisition (Celery unavailable)")


async def _async_process_acquisition_event(
    organization_id: str, prospect_id: str, source_id: Optional[str]
) -> None:
    """Internal async handler for the acquisition pipeline."""
    from app.database import AsyncSessionLocal
    from app.models.acquisition_models import LeadProspect
    from app.modules.lead_acquisition.services.prospect_service import ProspectService
    from app.modules.lead_acquisition.services.acquisition_quality_service import score_and_save
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as db:
        try:
            # Load prospect
            stmt = select(LeadProspect).where(
                and_(LeadProspect.id == prospect_id, LeadProspect.organization_id == organization_id)
            )
            prospect = (await db.execute(stmt)).scalars().first()
            if not prospect:
                logger.warning(f"[ACQ_TASK] Prospect not found: {prospect_id}")
                return

            svc = ProspectService(db)

            # Normalize
            prospect = await svc.run_normalization(prospect)

            # Deduplicate
            prospect, match_status = await svc.run_duplicate_check(organization_id, prospect)

            # Quality score
            await score_and_save(prospect, db)

            # Convert to canonical Lead / update duplicate attribution
            if not prospect.canonical_lead_id:
                await svc.import_as_lead(organization_id, prospect)

            await db.commit()
            logger.info(f"[ACQ_TASK] Processed and imported prospect {prospect_id}: status={prospect.status}")
        except Exception as exc:
            logger.error(f"[ACQ_TASK] Pipeline failed for prospect {prospect_id}: {exc}")
            await db.rollback()
            raise


async def _async_ai_extract(organization_id: str, prospect_id: str) -> None:
    """Run AI extraction on a prospect's message."""
    from app.database import AsyncSessionLocal
    from app.models.acquisition_models import LeadProspect
    from app.modules.lead_acquisition.services.ai_extraction_service import extract_from_message
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as db:
        stmt = select(LeadProspect).where(
            and_(LeadProspect.id == prospect_id, LeadProspect.organization_id == organization_id)
        )
        prospect = (await db.execute(stmt)).scalars().first()
        if not prospect or not prospect.message:
            return

        extracted = await extract_from_message(prospect.message, language_hint=prospect.language)
        non_null = {k: v for k, v in extracted.items() if v is not None}

        if non_null:
            prospect.ai_extracted_fields = non_null
            # Apply non-null extractions only if prospect field is currently None
            if not prospect.lead_intent and extracted.get("intent"):
                prospect.lead_intent = extracted["intent"]
            if not prospect.property_type and extracted.get("property_type"):
                prospect.property_type = extracted["property_type"]
            if not prospect.transaction_type and extracted.get("transaction_type"):
                prospect.transaction_type = extracted["transaction_type"]

        await db.commit()
        logger.info(f"[ACQ_TASK] AI extraction complete for prospect {prospect_id}")
