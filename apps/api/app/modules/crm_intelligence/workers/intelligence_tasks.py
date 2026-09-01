"""
CRM Intelligence Celery Background Workers & Periodic Tasks
============================================================
Background tasks for:
1. evaluate_lead_health_and_decay_task  — Scans active leads and detects decay/neglect
2. monitor_sla_breaches_task            — Checks running SLA timers every 2 mins
3. evaluate_pipeline_stagnation_task    — Evaluates stage dwell times and pipeline risk
4. calculate_agent_workload_task        — Evaluates broker capacity and overload warnings
5. detect_crm_anomalies_task            — Runs statistical anomaly detection
6. generate_daily_briefs_task           — Daily manager & broker briefing generation
"""

import asyncio
import logging
from typing import Dict, Any, List

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.modules.crm_intelligence.service import CRMIntelligenceService

logger = logging.getLogger(__name__)

def _run_async(coro):
    """Utility to run an async coroutine inside a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="evaluate_lead_health_and_decay_task", bind=True, max_retries=3, default_retry_delay=60)
def evaluate_lead_health_and_decay_task(self, organization_id: str = "org_default"):
    """Periodic task: Evaluates lead health, decay, and neglect detection."""
    async def _run():
        async with AsyncSessionLocal() as db:
            service = CRMIntelligenceService(db)
            # Scan active risks & insights
            insights = await service.generate_insights(organization_id)
            logger.info(f"[CELERY] Lead health and insights pass completed. {len(insights)} insight(s) generated.")
            return {"status": "success", "insights_generated": len(insights)}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY] evaluate_lead_health_and_decay_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(name="monitor_sla_breaches_task", bind=True, max_retries=3, default_retry_delay=30)
def monitor_sla_breaches_task(self, organization_id: str = "org_default"):
    """Periodic task (every 2 min): Checks active SLA timers and records breaches."""
    async def _run():
        async with AsyncSessionLocal() as db:
            service = CRMIntelligenceService(db)
            breaches = await service.check_sla_breaches(organization_id)
            logger.info(f"[CELERY] SLA monitoring pass completed. {len(breaches)} breach(es) detected.")
            return {"status": "success", "breaches_recorded": len(breaches)}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY] monitor_sla_breaches_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(name="evaluate_pipeline_stagnation_task", bind=True, max_retries=3, default_retry_delay=120)
def evaluate_pipeline_stagnation_task(self, organization_id: str = "org_default"):
    """Periodic task (every 30 min): Evaluates pipeline stage velocity and stagnation."""
    async def _run():
        async with AsyncSessionLocal() as db:
            service = CRMIntelligenceService(db)
            snapshots = await service.get_pipeline_health(organization_id)
            logger.info(f"[CELERY] Pipeline stagnation check completed for {len(snapshots)} stage(s).")
            return {"status": "success", "stages_evaluated": len(snapshots)}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY] evaluate_pipeline_stagnation_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(name="calculate_agent_workload_task", bind=True, max_retries=3, default_retry_delay=60)
def calculate_agent_workload_task(self, organization_id: str = "org_default"):
    """Periodic task (every 15 min): Evaluates agent capacity and overload warnings."""
    async def _run():
        async with AsyncSessionLocal() as db:
            service = CRMIntelligenceService(db)
            snapshots = await service.evaluate_all_agents(organization_id)
            logger.info(f"[CELERY] Agent workload evaluation completed for {len(snapshots)} broker(s).")
            return {"status": "success", "agents_evaluated": len(snapshots)}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY] calculate_agent_workload_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(name="detect_crm_anomalies_task", bind=True, max_retries=3, default_retry_delay=180)
def detect_crm_anomalies_task(self, organization_id: str = "org_default"):
    """Periodic task (hourly): Runs statistical anomaly detection across volume and conversions."""
    async def _run():
        async with AsyncSessionLocal() as db:
            service = CRMIntelligenceService(db)
            anomalies = await service.detect_anomalies(organization_id)
            logger.info(f"[CELERY] Anomaly detection completed. {len(anomalies)} anomaly(ies) detected.")
            return {"status": "success", "anomalies_detected": len(anomalies)}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY] detect_crm_anomalies_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(name="generate_daily_briefs_task", bind=True, max_retries=3, default_retry_delay=300)
def generate_daily_briefs_task(self, organization_id: str = "org_default"):
    """Periodic task (Daily at 07:00 AM UTC): Pre-generates daily operational briefs."""
    async def _run():
        async with AsyncSessionLocal() as db:
            service = CRMIntelligenceService(db)
            manager_brief = await service.get_manager_brief(organization_id)
            logger.info(f"[CELERY] Generated manager daily brief {manager_brief.id}.")
            return {"status": "success", "manager_brief_id": manager_brief.id}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[CELERY] generate_daily_briefs_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)
