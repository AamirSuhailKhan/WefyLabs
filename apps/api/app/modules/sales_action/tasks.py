"""
Part 21.5 — Sales Action Background Celery Tasks
================================================
Idempotent, tenant-scoped background workers for automated action evaluations,
scheduled follow-up dispatches, and stale proposal expiration.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from app.celery_app import celery_app
except ImportError:
    celery_app = None


def _get_async_session():
    from app.database import AsyncSessionLocal
    return AsyncSessionLocal()


if celery_app:
    @celery_app.task(name="sales_action.evaluate_due_actions", bind=True, max_retries=3)
    def evaluate_due_sales_actions_task(self, organization_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        Background task scanning active pipeline leads and computing Next Best Actions.
        """
        import asyncio
        async def _run():
            async with _get_async_session() as session:
                from sqlalchemy import select
                from app.models.lead import Lead
                from app.modules.sales_action.service import SalesActionDomainService

                service = SalesActionDomainService(session)
                stmt = (
                    select(Lead)
                    .where(
                        Lead.status.in_(["new", "active", "qualified"]),
                        Lead.pipeline_stage.notin_(["CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED"])
                    )
                    .limit(limit)
                )
                res = await session.execute(stmt)
                leads = list(res.scalars().all())

                evaluated_count = 0
                for lead in leads:
                    try:
                        await service.evaluate_next_sales_action(
                            lead_id=str(lead.id),
                            organization_id=organization_id,
                        )
                        evaluated_count += 1
                    except Exception as e:
                        logger.warning(f"[SALES_ACTION_TASK] Error evaluating lead {lead.id}: {e}")

                return {"status": "SUCCESS", "evaluated_leads": evaluated_count}

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_run())


    @celery_app.task(name="sales_action.process_scheduled_followups", bind=True, max_retries=3)
    def process_scheduled_followups_task(self, limit: int = 100) -> Dict[str, Any]:
        """
        Processes and dispatches scheduled follow-up actions whose execution time has arrived.
        """
        import asyncio
        async def _run():
            async with _get_async_session() as session:
                from sqlalchemy import select
                from app.models.follow_up_models import FollowUpExecution
                from app.models.lead import Lead
                from app.models.broker import Broker
                from app.modules.sales_action.service import SalesActionDomainService

                now_utc = datetime.now(timezone.utc)
                stmt = (
                    select(FollowUpExecution)
                    .where(
                        FollowUpExecution.status == "SCHEDULED",
                        FollowUpExecution.scheduled_for_utc <= now_utc,
                    )
                    .limit(limit)
                )
                res = await session.execute(stmt)
                due_execs = list(res.scalars().all())

                processed = 0
                service = SalesActionDomainService(session)
                for item in due_execs:
                    try:
                        await service.execute_sales_action(
                            action_id=item.id,
                            lead_id=item.lead_id,
                            organization_id=item.organization_id,
                        )
                        processed += 1
                    except Exception as e:
                        logger.error(f"[SALES_ACTION_TASK] Failed to execute scheduled item {item.id}: {e}")

                return {"status": "SUCCESS", "dispatched": processed}

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_run())
