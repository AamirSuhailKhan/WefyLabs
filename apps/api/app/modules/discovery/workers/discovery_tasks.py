"""
Part 21.2 — Discovery Celery Async Tasks
==========================================
Background execution tasks for AI lead discovery pipelines.
Uses existing Celery + Redis infrastructure with synchronous graceful fallback in test mode.
"""
from __future__ import annotations
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

try:
    from app.celery_app import celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    celery_app = None


if CELERY_AVAILABLE and celery_app:
    @celery_app.task(
        name="discovery.execute_discovery_run_task",
        bind=True,
        max_retries=3,
        default_retry_delay=60,
        acks_late=True,
    )
    def execute_discovery_run_task(self, organization_id: str, run_id: str):
        """Execute full discovery run across configured sources in background."""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_async_execute_discovery_run(organization_id, run_id))
        except Exception as exc:
            logger.error(f"[DISCOVERY_TASK] Run {run_id} failed: {exc}")
            raise self.retry(exc=exc)
        finally:
            loop.close()

    @celery_app.task(
        name="discovery.process_candidate_task",
        bind=True,
        max_retries=2,
        default_retry_delay=30,
    )
    def process_candidate_task(self, organization_id: str, candidate_id: str):
        """Process candidate validation, relevance scoring, and duplicate check."""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_async_process_candidate(organization_id, candidate_id))
        except Exception as exc:
            logger.warning(f"[DISCOVERY_TASK] Candidate {candidate_id} processing error: {exc}")
        finally:
            loop.close()

else:
    def execute_discovery_run_task(organization_id: str, run_id: str):
        logger.debug(f"[DISCOVERY_TASK][STUB] execute_discovery_run_task {run_id}")

    def process_candidate_task(organization_id: str, candidate_id: str):
        logger.debug(f"[DISCOVERY_TASK][STUB] process_candidate_task {candidate_id}")


async def _async_execute_discovery_run(organization_id: str, run_id: str) -> None:
    from app.database import AsyncSessionLocal
    from app.models.discovery_models import DiscoveryRun, DiscoveryCampaign, DiscoverySource
    from app.modules.discovery.service.discovery_run_service import DiscoveryRunService
    from app.modules.discovery.service.discovery_source_service import DiscoverySourceService
    from app.modules.discovery.service.discovery_candidate_service import DiscoveryCandidateService
    from app.modules.discovery.connectors.provider_registry import get_discovery_provider
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as db:
        try:
            run_svc = DiscoveryRunService(db)
            source_svc = DiscoverySourceService(db)
            cand_svc = DiscoveryCandidateService(db)

            run = await run_svc.get_run(organization_id, run_id)
            if not run:
                return

            await run_svc.mark_running(run)

            # Load Campaign
            stmt_c = select(DiscoveryCampaign).where(
                and_(DiscoveryCampaign.id == run.campaign_id, DiscoveryCampaign.organization_id == organization_id)
            )
            campaign = (await db.execute(stmt_c)).scalars().first()
            if not campaign:
                await run_svc.fail_run(run, "Campaign not found")
                return

            # Target Sources
            sources = []
            if campaign.source_ids:
                stmt_s = select(DiscoverySource).where(
                    and_(
                        DiscoverySource.id.in_(campaign.source_ids),
                        DiscoverySource.organization_id == organization_id,
                        DiscoverySource.is_active.is_(True),
                    )
                )
                sources = list((await db.execute(stmt_s)).scalars().all())

            criteria = {
                "cities": campaign.cities,
                "property_types": campaign.property_types,
                "budget_min": float(campaign.budget_min) if campaign.budget_min else None,
                "budget_max": float(campaign.budget_max) if campaign.budget_max else None,
                "currency": campaign.currency,
                "country_code": campaign.country_code,
            }

            scanned = 0
            found = 0

            for src in sources:
                allowed, reason = await source_svc.check_quota_and_rate_limit(src)
                if not allowed:
                    continue

                provider = get_discovery_provider(src.provider)
                if not provider:
                    continue

                batch = await provider.discover(
                    criteria, src.configuration, cursor=run.cursor_position, limit=50
                )
                scanned += batch.records_scanned

                for rec in batch.records:
                    cand = await cand_svc.create_candidate_from_record(
                        organization_id=organization_id,
                        discovery_run_id=run.id,
                        source_id=src.id,
                        record=rec,
                    )
                    await cand_svc.process_candidate_pipeline(organization_id, cand, campaign=campaign)
                    found += 1

                await source_svc.increment_usage(src, count=len(batch.records))

            await run_svc.update_counters(run, scanned=scanned, found=found)
            await run_svc.complete_run(run)

        except Exception as exc:
            logger.error(f"[DISCOVERY_ASYNC] Run execution failed: {exc}")
            await db.rollback()


async def _async_process_candidate(organization_id: str, candidate_id: str) -> None:
    from app.database import AsyncSessionLocal
    from app.modules.discovery.service.discovery_candidate_service import DiscoveryCandidateService

    async with AsyncSessionLocal() as db:
        cand_svc = DiscoveryCandidateService(db)
        candidate = await cand_svc.get_candidate(organization_id, candidate_id)
        if candidate:
            await cand_svc.process_candidate_pipeline(organization_id, candidate)
            await db.commit()
