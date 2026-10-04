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
from typing import Any, Dict, List, Optional

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

        # Worker-level Kill Switch reality check (Section 32, 45, 80)
        tenant_id = event_payload.get("tenant_id")
        from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
        is_g_paused, g_reason = EmergencyAutomationPauseService.is_global_paused()
        if is_g_paused:
            logger.warning(f"[LOOP_WORKER] Event processing suppressed by global kill switch: {g_reason}")
            return {"status": "PAUSED_BY_KILL_SWITCH", "reason": g_reason}
        if tenant_id:
            is_t_paused, t_reason = EmergencyAutomationPauseService.is_tenant_paused(tenant_id)
            if is_t_paused:
                logger.warning(f"[LOOP_WORKER] Event processing suppressed by tenant kill switch: {t_reason}")
                return {"status": "PAUSED_BY_KILL_SWITCH", "reason": t_reason}

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

                # Phase 2C Event Bridge hook — Additive shadow observation pipeline
                pilot_obs_result = None
                try:
                    from app.modules.autonomous_loop.phase2c_event_bridge import Phase2CEventBridge
                    bridge = Phase2CEventBridge(session)
                    raw_event_type = (
                        event_dto.event_type.value
                        if hasattr(event_dto.event_type, "value")
                        else str(event_dto.event_type)
                    )
                    pilot_obs_result = await bridge.route_event(
                        event_type=raw_event_type,
                        organization_id=str(event_dto.tenant_id),
                        lead_id=str(event_dto.lead_id) if event_dto.lead_id else None,
                        event_id=result.event_id or getattr(event_dto, "event_id", None),
                        correlation_id=str(getattr(event_dto, "correlation_id", "") or ""),
                        payload=event_dto.payload or {},
                    )
                    if pilot_obs_result:
                        await session.commit()
                except Exception as bridge_exc:
                    logger.warning(
                        f"[LOOP_WORKER] Phase 2C event bridge hook non-fatal error: {bridge_exc}",
                        exc_info=True,
                    )

                ret_val = {
                    "status": result.processing_state.value,
                    "event_id": result.event_id,
                    "lead_id": result.lead_id,
                    "action_type": result.action_type,
                    "provider_status": result.provider_status,
                    "decision_reason": result.decision_reason,
                }
                if pilot_obs_result:
                    ret_val["pilot_observation"] = pilot_obs_result
                return ret_val

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
                            # Phase 2C.3A canonical identity: tenant_id references organization_id
                            # Lead.organization_id is the correct canonical tenant field (post migration 0015)
                            Lead.organization_id == tenant_id,
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

    @celery_app.task(
        name="autonomous_loop.generate_daily_pilot_snapshots",
        bind=True,
        max_retries=2,
    )
    def generate_daily_pilot_snapshots_task(self, target_date_iso: Optional[str] = None) -> Dict[str, Any]:
        """
        Computes and persists daily PilotMetricSnapshot records for all active pilot tenants.
        Derives metrics strictly from persisted DB observations (never in-memory counters).
        """
        logger.info("[LOOP_WORKER] Generating daily pilot metric snapshots...")

        async def _run():
            async with _get_async_session() as session:
                from sqlalchemy import select
                from app.modules.autonomous_loop.phase2c_durable_models import (
                    PilotTenant, PilotMetricSnapshot
                )
                from app.modules.autonomous_loop.phase2c_pilot_repository import (
                    PilotRepository, MINIMUM_SHADOW_SAMPLE
                )

                if target_date_iso:
                    target_date = datetime.fromisoformat(target_date_iso).date()
                else:
                    target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

                day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
                day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

                stmt = select(PilotTenant).where(PilotTenant.pilot_status == "ACTIVE")
                res = await session.execute(stmt)
                pilots = list(res.scalars().all())

                snapshots_created = 0
                repo = PilotRepository(session)

                for pilot in pilots:
                    try:
                        metrics = await repo.compute_shadow_accuracy(
                            pilot_id=pilot.id,
                            period_start=day_start,
                            period_end=day_end,
                        )

                        snapshot = PilotMetricSnapshot(
                            pilot_id=pilot.id,
                            organization_id=pilot.organization_id,
                            stage=pilot.current_stage,
                            period_start=day_start,
                            period_end=day_end,
                            metric_name="shadow_accuracy",
                            metric_value=metrics.get("observed_value", 0.0),
                            sample_size=metrics.get("sample_size", 0),
                            minimum_sample=metrics.get("minimum_sample", MINIMUM_SHADOW_SAMPLE),
                            numerator=metrics.get("numerator", 0),
                            denominator=metrics.get("denominator", 0),
                            source="pilot_observations",
                            calculation_version="v2c.1.0",
                            is_synthetic=False,
                            computed_at=datetime.now(timezone.utc),
                        )
                        session.add(snapshot)
                        snapshots_created += 1
                    except Exception as snap_err:
                        logger.warning(f"[LOOP_WORKER] Failed to create snapshot for pilot {pilot.id}: {snap_err}")

                await session.commit()
                return {
                    "status": "SUCCESS",
                    "target_date": target_date.isoformat(),
                    "snapshots_created": snapshots_created,
                }

        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_run(), loop)
            return future.result()
        else:
            return asyncio.run(_run())
