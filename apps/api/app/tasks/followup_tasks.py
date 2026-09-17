"""
Enterprise Follow-Up Automation Celery Tasks
=============================================
Bounded, idempotent, retry-safe background tasks for evaluating follow-up rules,
first-contact SLAs, manager escalations, and AI re-engagement.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.follow_up import FollowUp
from app.models.follow_up_models import FollowUpRule
from app.models.lead import Lead
from app.models.broker import Broker
from app.modules.follow_up.service import FollowUpOrchestratorService

logger = logging.getLogger(__name__)


def run_async(coro):
    """Utility helper to run async coroutine inside Celery synchronous task."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Backward Compatible Legacy Helpers ─────────────────────────────────────────

async def async_send_follow_up(follow_up_id_str: str, session: Optional[AsyncSession] = None) -> bool:
    """Legacy helper preserving backward compatibility."""
    try:
        follow_up_uuid = uuid.UUID(follow_up_id_str)
    except Exception:
        return False

    async def _execute(sess: AsyncSession) -> bool:
        stmt = select(FollowUp).where(FollowUp.id == follow_up_uuid).options(selectinload(FollowUp.lead))
        result = await sess.execute(stmt)
        follow_up = result.scalars().first()

        if not follow_up or follow_up.status != "scheduled":
            return False

        lead = follow_up.lead
        if not lead or lead.deleted_at or (lead.status or "").lower() in ("converted", "lost"):
            follow_up.status = "cancelled"
            await sess.commit()
            return False

        # WhatsApp is DISABLED in Part 27 — mark completed/logged
        follow_up.sent_at = datetime.now(timezone.utc)
        follow_up.status = "sent"
        await sess.commit()
        return True

    if session:
        return await _execute(session)
    else:
        async with AsyncSessionLocal() as sess:
            return await _execute(sess)


async def async_check_and_schedule_followups(session: Optional[AsyncSession] = None) -> int:
    """Legacy helper."""
    now = datetime.now(timezone.utc)

    async def _execute(sess: AsyncSession) -> int:
        stmt = select(FollowUp).where(FollowUp.scheduled_at <= now, FollowUp.status == "scheduled")
        result = await sess.execute(stmt)
        due_followups = result.scalars().all()

        dispatched_count = 0
        for f in due_followups:
            send_follow_up.delay(str(f.id))
            dispatched_count += 1

        return dispatched_count

    if session:
        return await _execute(session)
    else:
        async with AsyncSessionLocal() as sess:
            return await _execute(sess)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=7200)
def send_follow_up(self, follow_up_id: str):
    """Legacy Celery task to send a single scheduled follow-up message."""
    try:
        run_async(async_send_follow_up(follow_up_id))
    except Exception as exc:
        logger.error(f"[Celery Task Error] send_follow_up {follow_up_id}: {exc}")


@celery_app.task
def check_and_schedule_followups():
    """Legacy Celery beat periodic task."""
    return run_async(async_check_and_schedule_followups())


# ── Part 27 Enterprise Bounded Automation Tasks ────────────────────────────────

async def async_evaluate_followups(batch_size: int = 250) -> Dict[str, Any]:
    """
    Periodic evaluator:
    - Checks active response SLA breaches
    - Evaluates organization follow-up rules for active leads in bounded batches
    """
    async with AsyncSessionLocal() as session:
        service = FollowUpOrchestratorService(session)

        # 1. Evaluate SLA breaches across organizations
        breaches = await service.sla_service.evaluate_sla_breaches()

        # 2. Process active leads batch
        processed_leads = await service.process_active_leads_batch(batch_size=batch_size, offset=0)

        logger.info(f"[Celery FollowUp] Evaluated {processed_leads} active leads, recorded {len(breaches)} SLA breaches.")
        return {
            "processed_leads": processed_leads,
            "recorded_breaches": len(breaches)
        }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def evaluate_followups(self, batch_size: int = 250):
    """
    Bounded Celery task running periodically to evaluate SLAs and lead follow-up rules.
    """
    try:
        return run_async(async_evaluate_followups(batch_size=batch_size))
    except Exception as exc:
        logger.error(f"[Celery Task Error] evaluate_followups: {exc}")
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("[Celery Task Max Retries Exceeded] evaluate_followups")


async def async_escalate_stale_lead(organization_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Detects uncontacted hot leads and stale leads, escalating directly to managers.
    """
    async with AsyncSessionLocal() as session:
        service = FollowUpOrchestratorService(session)
        escalated_hot = await service.escalation_service.scan_and_escalate_hot_leads(organization_id)
        reengaged_stale = await service.escalation_service.scan_and_reengage_stale_leads(organization_id)

        logger.info(f"[Celery Escalation] Escalated {len(escalated_hot)} hot leads, re-engaged {len(reengaged_stale)} stale leads.")
        return {
            "escalated_hot_leads": len(escalated_hot),
            "reengaged_stale_leads": len(reengaged_stale)
        }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def escalate_stale_lead(self, organization_id: Optional[str] = None):
    """
    Celery task to escalate uncontacted hot leads and re-engage stale leads.
    """
    try:
        return run_async(async_escalate_stale_lead(organization_id=organization_id))
    except Exception as exc:
        logger.error(f"[Celery Task Error] escalate_stale_lead: {exc}")


async def async_process_followup_rule(rule_id: str, lead_id: str, trigger_event: str) -> bool:
    """Executes a single rule against a lead with idempotency protection."""
    async with AsyncSessionLocal() as session:
        service = FollowUpOrchestratorService(session)

        stmt_r = select(FollowUpRule).where(FollowUpRule.id == rule_id)
        res_r = await session.execute(stmt_r)
        rule = res_r.scalar_one_or_none()

        try:
            lead_pk = uuid.UUID(str(lead_id))
        except Exception:
            lead_pk = lead_id

        stmt_l = select(Lead).where(Lead.id == lead_pk)
        res_l = await session.execute(stmt_l)
        lead = res_l.scalar_one_or_none()

        if not rule or not lead:
            return False

        policy = await service.get_or_create_policy(rule.organization_id)
        event = await service.rule_engine.execute_rule(
            rule=rule,
            lead=lead,
            trigger_event=trigger_event,
            policy=policy
        )
        return event is not None


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_followup_rule(self, rule_id: str, lead_id: str, trigger_event: str):
    """Celery task to execute a specific follow-up rule for a lead."""
    try:
        return run_async(async_process_followup_rule(rule_id, lead_id, trigger_event))
    except Exception as exc:
        logger.error(f"[Celery Task Error] process_followup_rule: {exc}")
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            pass


async def async_send_daily_briefing() -> int:
    """Generates daily CRM briefing for all active brokers."""
    async with AsyncSessionLocal() as session:
        stmt = select(Broker).where(Broker.subscription_status.in_(["active", "trial"]))
        res = await session.execute(stmt)
        brokers = res.scalars().all()

        service = FollowUpOrchestratorService(session)
        count = 0
        for b in brokers:
            await service.briefing_service.get_daily_briefing_data(b.id, str(b.id))
            count += 1
        return count


@celery_app.task
def send_daily_briefing():
    """Celery beat task running daily to prepare agent briefings."""
    return run_async(async_send_daily_briefing())
