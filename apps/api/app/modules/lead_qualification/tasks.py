"""
Part 21.4.2 — Asynchronous Qualification Background Tasks
=========================================================
Celery tasks for async message qualification fact extraction.
Guarantees:
- Idempotency via deterministic deduplication.
- Strict tenant-scoping (no cross-tenant access).
- Safe retry handling with exponential backoff.
"""
import logging
from typing import Dict, Any, Optional

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.modules.lead_qualification.service import LeadQualificationDomainService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def extract_qualification_facts_for_message_task(
    self, organization_id: str, lead_id: str, message_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Background worker task to extract qualification facts from newly arrived messages.
    Idempotent and retry-safe.
    """
    logger.info(
        f"[CELERY_QUALIFICATION] Processing async fact extraction for org={organization_id}, lead={lead_id}, message={message_id}"
    )

    import asyncio

    async def _async_extract():
        async with AsyncSessionLocal() as session:
            service = LeadQualificationDomainService(session)
            summary = await service.extract_and_ingest_from_lead_conversations(
                organization_id=organization_id,
                lead_id=lead_id,
                message_id=message_id,
                actor_id="celery_worker",
            )
            return {
                "status": "success",
                "lead_id": lead_id,
                "facts_extracted": summary.facts_extracted_count,
                "facts_persisted": summary.facts_persisted_count,
                "conflicts_detected": summary.conflicts_detected_count,
                "new_state": summary.snapshot.state,
            }

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(_async_extract())).result()
        else:
            return asyncio.run(_async_extract())
    except Exception as exc:
        logger.error(f"[CELERY_QUALIFICATION] Async fact extraction failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def evaluate_lead_qualification_task(
    self, organization_id: str, lead_id: str
) -> Dict[str, Any]:
    """
    Background worker task to deterministically evaluate lead qualification policy.
    Idempotent and retry-safe.
    """
    logger.info(
        f"[CELERY_QUALIFICATION] Processing async policy evaluation for org={organization_id}, lead={lead_id}"
    )

    import asyncio

    async def _async_evaluate():
        async with AsyncSessionLocal() as session:
            service = LeadQualificationDomainService(session)
            result = await service.evaluate_lead_qualification(
                organization_id=organization_id,
                lead_id=lead_id,
                actor_id="celery_evaluator",
            )
            return {
                "status": "success",
                "lead_id": lead_id,
                "qualification_state": result.qualification_state,
                "completeness_score": result.completeness_score,
                "confidence_score": result.confidence_score,
                "policy_version": result.policy_version,
                "missing_required": result.missing_required_information,
            }

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(_async_evaluate())).result()
        else:
            return asyncio.run(_async_evaluate())
    except Exception as exc:
        logger.error(f"[CELERY_QUALIFICATION] Async policy evaluation failed: {exc}")
        raise self.retry(exc=exc)


