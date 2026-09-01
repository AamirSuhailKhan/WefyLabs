"""
Part 21.8 — Autonomous Sales Loop Celery Workers
=================================================
Idempotent, tenant-scoped background tasks for the autonomous sales loop.

Workers:
  1. process_sales_loop_event_task — Process a single inbound domain event
  2. retry_failed_events_task      — Retry RETRYABLE events (cron)
  3. evaluate_inactive_leads_task  — Trigger NEW_LEAD events for neglected leads (cron)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    from app.celery_app import celery_app
except ImportError:
    celery_app = None


def _get_async_session():
    from app.database import AsyncSessionLocal
    return AsyncSessionLocal()


if celery_app:
    @celery_app.task(
        name="autonomous_loop.process_sales_loop_event",
        bind=True,
        max_retries=3,
        default_retry_delay=30,
    )
    def process_sales_loop_event_task(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a single sales loop event through the AutonomousSalesLoopService.
        Idempotent: duplicate events are suppressed by idempotency_key.
        """
        logger.info(
            f"[LOOP_WORKER] Processing event: "
            f"type={event_payload.get('event_type')} "
            f"lead={event_payload.get('lead_id')} "
            f"idem_key={event_payload.get('idempotency_key', 'unset')}"
        )

        async def _run():
            async with _get_async_session() as session:
                from app.modules.autonomous_loop.orchestrator import AutonomousSalesLoopService
                from app.modules.autonomous_loop.dto import SalesLoopEventDTO
                from app.modules.autonomous_loop.taxonomies import (
                    SalesLoopEventType, ActorType
                )

                try:
                    event_dto = SalesLoopEventDTO(**event_payload)
                except Exception as e:
                    logger.error(f"[LOOP_WORKER] Invalid event payload: {e}")
                    return {"status": "INVALID_PAYLOAD", "error": str(e)}

                service = AutonomousSalesLoopService(session)
                result = await service.process_event(event_dto)
                await session.commit()

                return {
                    "status": result.processing_state.value,
                    "event_id": result.event_id,
                    "lead_id": result.lead_id,
                    "action_type": result.action_type,
                    "provider_status": result.provider_status,
                    "decision_reason": result.decision_reason,
                }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_run(), loop)
                return future.result()
            else:
                return asyncio.run(_run())
        except Exception as exc:
            logger.error(f"[LOOP_WORKER] Event processing error: {exc}", exc_info=True)
            raise self.retry(exc=exc)

    @celery_app.task(
        name="autonomous_loop.retry_failed_events",
        bind=True,
        max_retries=1,
    )
    def retry_failed_events_task(self, tenant_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        Retries RETRYABLE events that have not yet exhausted their max_retries.
        Designed to run on a cron schedule.
        """
        logger.info(f"[LOOP_WORKER] Retrying failed events for tenant: {tenant_id}")

        async def _run():
            async with _get_async_session() as session:
                from sqlalchemy import select, and_
                from app.modules.autonomous_loop.models import SalesLoopEvent
                from app.modules.autonomous_loop.orchestrator import AutonomousSalesLoopService
                from app.modules.autonomous_loop.dto import SalesLoopEventDTO
                from app.modules.autonomous_loop.taxonomies import (
                    SalesLoopEventType, ActorType, EventProcessingState
                )

                stmt = (
                    select(SalesLoopEvent)
                    .where(
                        and_(
                            SalesLoopEvent.tenant_id == tenant_id,
                            SalesLoopEvent.processing_state == EventProcessingState.RETRYABLE.value,
                            SalesLoopEvent.retry_count < SalesLoopEvent.max_retries,
                        )
                    )
                    .limit(limit)
                )
                res = await session.execute(stmt)
                retryable_events = list(res.scalars().all())

                service = AutonomousSalesLoopService(session)
                retried = 0

                for evt in retryable_events:
                    try:
                        event_dto = SalesLoopEventDTO(
                            event_id=evt.id,
                            event_type=SalesLoopEventType(evt.event_type),
                            tenant_id=evt.tenant_id,
                            lead_id=evt.lead_id,
                            broker_id=evt.broker_id,
                            correlation_id=evt.correlation_id,
                            causation_id=evt.causation_id,
                            actor_type=ActorType(evt.actor_type) if evt.actor_type else ActorType.SYSTEM,
                            actor_id=evt.actor_id,
                            payload=evt.payload or {},
                            source=evt.source,
                            idempotency_key=f"retry_{evt.id}_{evt.retry_count + 1}",
                            occurred_at=evt.occurred_at,
                        )
                        await service.process_event(event_dto)
                        retried += 1
                    except Exception as ex:
                        logger.warning(f"[LOOP_WORKER] Retry failed for event {evt.id}: {ex}")

                await session.commit()
                return {"status": "SUCCESS", "retried": retried}

        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_run(), loop)
            return future.result()
        else:
            return asyncio.run(_run())

    @celery_app.task(
        name="autonomous_loop.evaluate_inactive_leads",
        bind=True,
        max_retries=1,
    )
    def evaluate_inactive_leads_task(
        self,
        tenant_id: str,
        inactive_days: int = 3,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Scans active leads that haven't received attention in `inactive_days` days
        and emits NEW_LEAD events to kick off the autonomous loop.
        Idempotency keys prevent double-processing within the same day.
        """
        logger.info(f"[LOOP_WORKER] Evaluating inactive leads for tenant: {tenant_id}")

        async def _run():
            async with _get_async_session() as session:
                from sqlalchemy import select, and_
                from app.models.lead import Lead
                from app.modules.autonomous_loop.orchestrator import AutonomousSalesLoopService
                from app.modules.autonomous_loop.dto import SalesLoopEventDTO
                from app.modules.autonomous_loop.taxonomies import SalesLoopEventType, ActorType

                cutoff = datetime.now(timezone.utc) - timedelta(days=inactive_days)
                stmt = (
                    select(Lead)
                    .where(
                        and_(
                            Lead.broker_id == tenant_id,
                            Lead.status.in_(["active", "new", "pending"]),
                            Lead.pipeline_stage.notin_([
                                "CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED"
                            ]),
                            Lead.updated_at <= cutoff,
                        )
                    )
                    .limit(limit)
                )
                res = await session.execute(stmt)
                leads = list(res.scalars().all())

                service = AutonomousSalesLoopService(session)
                processed = 0

                today_str = datetime.now(timezone.utc).date().isoformat()
                for lead in leads:
                    try:
                        event_dto = SalesLoopEventDTO(
                            event_type=SalesLoopEventType.NEW_LEAD,
                            tenant_id=tenant_id,
                            lead_id=str(lead.id),
                            actor_type=ActorType.SCHEDULER,
                            payload={"trigger": "inactive_lead_scan"},
                            source="inactive_lead_scanner",
                            # Idempotency: one check per lead per day
                            idempotency_key=f"inactive_scan_{lead.id}_{today_str}",
                        )
                        await service.process_event(event_dto)
                        processed += 1
                    except Exception as ex:
                        logger.warning(f"[LOOP_WORKER] Inactive lead scan error for {lead.id}: {ex}")

                await session.commit()
                return {"status": "SUCCESS", "leads_scanned": len(leads), "processed": processed}

        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_run(), loop)
            return future.result()
        else:
            return asyncio.run(_run())
