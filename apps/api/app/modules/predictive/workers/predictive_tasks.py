"""
Celery Background Tasks for Predictive Analytics & MLOps Engine
===============================================================
Executes periodic asynchronous jobs:
- Refreshing active lead predictions
- Recalculating multi-horizon pipeline forecasts
- Monitoring feature & prediction drift (PSI)
- Reconciling ground truth outcomes
"""

import asyncio
import logging
from typing import List, Dict, Any

from app.celery_app import celery_app
from app.database import async_session_factory
from app.modules.predictive.service import PredictiveEngineService

logger = logging.getLogger(__name__)

def _run_async(coro):
    """Helper to run async coroutines synchronously in Celery worker thread."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.modules.predictive.workers.predictive_tasks.refresh_active_lead_predictions", queue="prediction")
def refresh_active_lead_predictions():
    """Refreshes conversion predictions for active pipeline leads (runs every 15 mins)."""
    async def _runner():
        async with async_session_factory() as session:
            logger.info("[PREDICTIVE_TASK] Refreshing active lead conversion predictions...")
            from sqlalchemy import select
            from app.models.lead import Lead
            from app.dependencies import TenantContext
            stmt = select(Lead.id, Lead.organization_id, Lead.broker_id).where(Lead.deleted_at == None).limit(50)
            res = await session.execute(stmt)
            leads = res.all()

            service = PredictiveEngineService(session)
            count = 0
            for lid, org_id, broker_id in leads:
                effective_org = str(org_id or broker_id or "system")
                TenantContext.for_background_task(organization_id=effective_org)
                try:
                    await service.predict_lead_conversion(str(lid), effective_org, force_refresh=True)
                    count += 1
                except Exception as e:
                    logger.error(f"[PREDICTIVE_TASK] Failed to predict lead {lid}: {e}")
            logger.info(f"[PREDICTIVE_TASK] Refreshed {count} lead predictions.")
            return {"status": "SUCCESS", "refreshed_count": count}

    return _run_async(_runner())


@celery_app.task(name="app.modules.predictive.workers.predictive_tasks.recalculate_pipeline_revenue_forecasts", queue="forecast")
def recalculate_pipeline_revenue_forecasts():
    """Recalculates multi-horizon revenue forecasts for active organizations (runs every 30 mins)."""
    async def _runner():
        async with async_session_factory() as session:
            logger.info("[PREDICTIVE_TASK] Recalculating multi-horizon pipeline forecasts...")
            from sqlalchemy import select
            from app.models.organization import Organization
            from app.dependencies import TenantContext
            service = PredictiveEngineService(session)
            org_res = await session.execute(select(Organization.id))
            org_ids = [str(o) for o in org_res.scalars().all()]
            if not org_ids:
                org_ids = ["org_default"]

            results = {}
            for org_id in org_ids:
                TenantContext.for_background_task(organization_id=org_id)
                try:
                    f30 = await service.forecast_revenue(org_id, "30_DAYS")
                    fq = await service.forecast_revenue(org_id, "QUARTER")
                    results[org_id] = {"forecast_30d": f30.expected_revenue, "forecast_quarter": fq.expected_revenue}
                except Exception as e:
                    logger.error(f"[PREDICTIVE_TASK] Forecast failed for org {org_id}: {e}")
            return {"status": "SUCCESS", "results": results}

    return _run_async(_runner())


@celery_app.task(name="app.modules.predictive.workers.predictive_tasks.monitor_prediction_drift", queue="drift-monitoring")
def monitor_prediction_drift():
    """Evaluates Population Stability Index (PSI) drift across models (hourly)."""
    async def _runner():
        async with async_session_factory() as session:
            logger.info("[PREDICTIVE_TASK] Running hourly PSI drift evaluation...")
            service = PredictiveEngineService(session)
            drift = await service.monitor_model_drift("v1.0.0")
            logger.info(f"[PREDICTIVE_TASK] Drift Evaluation: PSI={drift.psi_score:.4f}, Alert={drift.alert_triggered}.")
            return {"status": "SUCCESS", "psi_score": drift.psi_score, "alert_triggered": drift.alert_triggered}

    return _run_async(_runner())
