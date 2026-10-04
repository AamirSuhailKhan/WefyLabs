"""
Master Build 14 — Asynchronous Intelligence Background Tasks
==============================================================
Celery tasks for:
- Periodic data quality scanning
- Intelligence snapshot generation
- Actionable insight detection
- Async outcome event recording
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.modules.intelligence.service import IntelligenceService

logger = logging.getLogger(__name__)


def _run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()
    else:
        return asyncio.run(coro)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def scan_data_quality_task(self, organization_id: str) -> Dict[str, Any]:
    """Runs data quality verification scan for an organization in the background."""
    logger.info(f"[CELERY_INTELLIGENCE] Starting data quality scan for org={organization_id}")

    async def _run():
        async with AsyncSessionLocal() as session:
            service = IntelligenceService()
            report = await service.scan_data_quality(session, organization_id)
            await session.commit()
            return {
                "status": "success",
                "organization_id": organization_id,
                "overall_quality_score": report.overall_quality_score,
                "total_issues": report.total_issues,
                "unresolved_issues": report.unresolved_issues,
            }

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY_INTELLIGENCE] Data quality scan failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def generate_intelligence_snapshot_task(
    self, organization_id: str, period_type: str = "DAILY"
) -> Dict[str, Any]:
    """Computes and persists an immutable intelligence snapshot."""
    logger.info(
        f"[CELERY_INTELLIGENCE] Generating snapshot ({period_type}) for org={organization_id}"
    )

    async def _run():
        async with AsyncSessionLocal() as session:
            service = IntelligenceService()
            snapshot = await service.generate_intelligence_snapshot(
                session, organization_id, period_type
            )
            await session.commit()
            return {
                "status": "success",
                "snapshot_id": snapshot.id,
                "organization_id": organization_id,
                "period_type": period_type,
                "computed_at": snapshot.computed_at.isoformat(),
            }

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY_INTELLIGENCE] Snapshot generation failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def generate_actionable_insights_task(self, organization_id: str) -> Dict[str, Any]:
    """Evaluates telemetry and creates actionable insight records."""
    logger.info(f"[CELERY_INTELLIGENCE] Generating insights for org={organization_id}")

    async def _run():
        async with AsyncSessionLocal() as session:
            service = IntelligenceService()
            insights = await service.generate_actionable_insights(session, organization_id)
            await session.commit()
            return {
                "status": "success",
                "organization_id": organization_id,
                "insights_generated_count": len(insights),
            }

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY_INTELLIGENCE] Insight generation failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    retry_backoff=True,
    name="intelligence.advance_policy_rollouts",
)
def advance_policy_rollouts_task(self) -> Dict[str, Any]:
    """
    Sprint 1F — Progressive Rollout Controller.

    Scans all active AdaptivePolicyRollout records and advances traffic_pct
    by increment_pct for each rollout that:
      - is not emergency_paused
      - is not is_rolled_back
      - has waited at least increment_interval_hours since last_increment_at
      - passes guardrail checks (sample size)

    Scheduled: every 1 hour at minute 30.

    Sprint 1F Gate: G-02
    """
    logger.info("[CELERY_INTELLIGENCE] [Sprint 1F] Starting policy rollout advancement scan.")

    async def _run():
        from sqlalchemy import select
        from app.models.intelligence_models import AdaptivePolicyRollout, PolicyRegistryEntry, RegistryEntryStatus
        from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

        adaptive_service = AdaptivePolicyService()
        advanced_count = 0
        skipped_count = 0
        error_count = 0

        async with AsyncSessionLocal() as session:
            # Find all active, non-paused, non-rolled-back rollouts
            q = select(AdaptivePolicyRollout).where(
                AdaptivePolicyRollout.is_rolled_back.is_(False)
            )
            rollouts = list((await session.execute(q)).scalars().all())

            for rollout in rollouts:
                if rollout.emergency_pause:
                    skipped_count += 1
                    continue
                if rollout.fully_deployed_at is not None:
                    skipped_count += 1
                    continue

                try:
                    updated = await adaptive_service.advance_rollout(
                        session=session,
                        policy_entry_id=rollout.policy_entry_id,
                        org_id=rollout.organization_id,
                    )
                    if updated and updated.traffic_pct != rollout.traffic_pct:
                        advanced_count += 1
                    else:
                        skipped_count += 1
                except Exception as exc:
                    logger.error(
                        f"[CELERY_INTELLIGENCE] Rollout advance failed for "
                        f"policy={rollout.policy_entry_id}: {exc}"
                    )
                    error_count += 1

            await session.commit()

        logger.info(
            f"[CELERY_INTELLIGENCE] Rollout advancement complete: "
            f"advanced={advanced_count} skipped={skipped_count} errors={error_count}"
        )
        return {
            "status": "success",
            "advanced_count": advanced_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
        }

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY_INTELLIGENCE] Policy rollout advancement failed: {exc}")
        raise self.retry(exc=exc)
