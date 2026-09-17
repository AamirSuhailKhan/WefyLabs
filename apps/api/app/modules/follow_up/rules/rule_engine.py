"""
Follow-Up Rule & Automation Engine
====================================
Evaluates organization-configured follow-up rules against lead states,
enforces working hours and IANA timezone boundaries, and executes
deterministic CRM tasks, notifications, and re-engagements.
"""

import html
import logging
import uuid
from datetime import datetime, timezone, timedelta, time
from typing import Optional, List, Dict, Any, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.crm_models import Task, Notification, Activity
from app.models.follow_up_models import (
    FollowUpRule, FollowUpPolicy, FollowUpAutomationEvent, CommunicationConsent
)
from app.modules.follow_up.idempotency.idempotency_service import IdempotencyService
from app.modules.follow_up.timing.timing_engine import TimingEngine
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Evaluates and dispatches organization follow-up rules.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.timing_engine = TimingEngine()

    def evaluate_conditions(self, rule: FollowUpRule, lead: Lead, context: Dict[str, Any]) -> bool:
        """
        Evaluates rule conditions against actual lead fields and context.
        Conditions schema:
          - score_in: List[str] e.g. ["hot", "warm"]
          - min_budget: float
          - max_budget: float
          - pipeline_stages: List[str]
          - sources: List[str]
          - min_hours_since_contact: float
          - min_no_response_count: int
        """
        conds = rule.conditions or {}
        if not conds:
            return True

        # 1. Score check
        if "score_in" in conds:
            allowed_scores = [s.lower() for s in conds["score_in"]]
            lead_score = (lead.score or "pending").lower()
            if lead_score not in allowed_scores:
                return False

        # 2. Pipeline stage check
        if "pipeline_stages" in conds:
            allowed_stages = [st.lower() for st in conds["pipeline_stages"]]
            lead_stage = (lead.pipeline_stage or "new").lower()
            if lead_stage not in allowed_stages:
                return False

        # 3. Source check
        if "sources" in conds:
            allowed_sources = [src.lower() for src in conds["sources"]]
            lead_src = (lead.source or "manual").lower()
            if lead_src not in allowed_sources:
                return False

        # 4. Budget check
        if "min_budget" in conds:
            lead_budget = float(lead.budget_max or lead.budget_min or 0.0)
            if lead_budget < float(conds["min_budget"]):
                return False

        # 5. Inactivity hours check
        if "min_hours_since_contact" in conds:
            hours_passed = float(context.get("hours_since_contact", 0.0))
            if hours_passed < float(conds["min_hours_since_contact"]):
                return False

        # 6. Consecutive no response count check
        if "min_no_response_count" in conds:
            no_resp = int(context.get("no_response_count", 0))
            if no_resp < int(conds["min_no_response_count"]):
                return False

        return True

    def calculate_working_hours_due_date(
        self,
        target_utc: datetime,
        policy: Optional[FollowUpPolicy],
        lead: Lead
    ) -> datetime:
        """
        Ensures target time falls strictly within organization working hours and working days.
        If scheduled at 2 AM or on a weekend, shifts to next valid morning (09:30 AM local time).
        """
        tz_str = self.timing_engine.resolve_timezone(lead)
        if policy and getattr(policy, "timezone", None):
            tz_str = policy.timezone

        try:
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = ZoneInfo("UTC")

        working_start_str = getattr(policy, "working_hours_start", "09:00") if policy else "09:00"
        working_end_str = getattr(policy, "working_hours_end", "18:00") if policy else "18:00"
        working_days = getattr(policy, "working_days", [1, 2, 3, 4, 5]) if policy else [1, 2, 3, 4, 5]

        start_h, start_m = map(int, working_start_str.split(":"))
        end_h, end_m = map(int, working_end_str.split(":"))

        local_dt = target_utc.astimezone(tz)

        # Check if today is a valid working day and within hours
        # Python weekday: Monday is 0, Sunday is 6.
        # DB convention: 1 = Monday, 7 = Sunday.
        current_db_day = local_dt.weekday() + 1
        current_time = local_dt.time()
        start_t = time(start_h, start_m)
        end_t = time(end_h, end_m)

        if current_db_day in working_days and start_t <= current_time <= end_t:
            return target_utc

        # Advance day-by-day to find next working day at working_start + 30m (e.g. 09:30)
        curr = local_dt
        if current_time > end_t or current_db_day not in working_days:
            curr = curr + timedelta(days=1)

        for _ in range(14): # Max 2 weeks search
            day_num = curr.weekday() + 1
            if day_num in working_days:
                target_local = curr.replace(hour=start_h, minute=start_m + 30, second=0, microsecond=0)
                return target_local.astimezone(timezone.utc)
            curr = curr + timedelta(days=1)

        # Fallback
        return target_utc

    async def execute_rule(
        self,
        rule: FollowUpRule,
        lead: Lead,
        trigger_event: str,
        policy: Optional[FollowUpPolicy] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[FollowUpAutomationEvent]:
        """
        Executes an enabled rule for a lead if conditions, limits, and stop invariants are met.
        """
        if not rule.enabled:
            return None

        ctx = context or {}
        org_id = rule.organization_id

        # ── 1. Stop Invariant Checks ──────────────────────────────────────────
        # Lead converted, lost, deleted, or permanently opted out
        if (lead.status or "").lower() in ("converted", "lost") or (lead.pipeline_stage or "").lower() in ("closed_won", "closed_lost", "converted"):
            logger.info(f"[RuleEngine] Stop condition met: Lead {lead.id} is {lead.status}/{lead.pipeline_stage}.")
            return None

        if lead.deleted_at is not None:
            return None

        # Check consent opt-out
        stmt_consent = select(CommunicationConsent).where(
            CommunicationConsent.lead_id == str(lead.id),
            CommunicationConsent.status == "OPTED_OUT"
        )
        res_c = await self.db.execute(stmt_consent)
        if res_c.scalar_one_or_none() is not None:
            logger.info(f"[RuleEngine] Stop condition met: Lead {lead.id} has opted out.")
            return None

        # ── 2. Evaluate Rule Conditions ───────────────────────────────────────
        if not self.evaluate_conditions(rule, lead, ctx):
            return None

        # ── 3. Check Max Runs & Cooldown ──────────────────────────────────────
        stmt_history = select(FollowUpAutomationEvent).where(
            FollowUpAutomationEvent.rule_id == rule.id,
            FollowUpAutomationEvent.lead_id == str(lead.id),
            FollowUpAutomationEvent.status == "COMPLETED"
        ).order_by(desc(FollowUpAutomationEvent.created_at))
        res_h = await self.db.execute(stmt_history)
        past_events = res_h.scalars().all()

        if len(past_events) >= rule.max_runs:
            logger.info(f"[RuleEngine] Rule {rule.name} reached max_runs ({rule.max_runs}) for Lead {lead.id}.")
            return None

        now = datetime.now(timezone.utc)
        if past_events and rule.cooldown_hours > 0:
            last_run = past_events[0].created_at
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
            if (now - last_run).total_seconds() < (rule.cooldown_hours * 3600):
                logger.info(f"[RuleEngine] Rule {rule.name} in cooldown for Lead {lead.id}.")
                return None

        # ── 4. Target Window & Idempotency Key ─────────────────────────────────
        target_date_window = now.strftime("%Y-%m-%d")
        idempotency_key = IdempotencyService.build_key(
            organization_id=org_id,
            lead_id=str(lead.id),
            rule_identifier=str(rule.id),
            trigger_type=trigger_event,
            target_window=f"{target_date_window}:run{len(past_events)+1}"
        )

        acquired, event = await IdempotencyService.try_acquire_execution(
            db=self.db,
            idempotency_key=idempotency_key,
            organization_id=org_id,
            lead_id=str(lead.id),
            trigger_type=trigger_event,
            action_type=rule.action,
            rule_id=rule.id,
            details={"rule_name": rule.name, "priority": rule.priority}
        )
        if not acquired:
            return None

        # ── 5. Calculate Execution Timing ─────────────────────────────────────
        delay_mins = rule.delay_minutes or 0
        desired_dt = now + timedelta(minutes=delay_mins)
        scheduled_due = self.calculate_working_hours_due_date(desired_dt, policy, lead)

        # ── 6. Execute Configured Action ──────────────────────────────────────
        lead_name = html.escape(lead.name or "Lead")
        lead_phone = lead.phone or ""
        act_cfg = rule.action_config or {}

        created_task_id = None
        created_notif_id = None

        try:
            if rule.action in ("create_task", "create_reengagement_task"):
                title_tpl = act_cfg.get("task_title", "Follow up with {{lead_name}}")
                desc_tpl = act_cfg.get("task_description", "Scheduled automated follow-up for {{lead_name}} ({{phone}}).")
                title = title_tpl.replace("{{lead_name}}", lead_name).replace("{{phone}}", lead_phone)
                description = desc_tpl.replace("{{lead_name}}", lead_name).replace("{{phone}}", lead_phone)

                task = Task(
                    id=str(uuid.uuid4()),
                    broker_id=lead.broker_id,
                    lead_id=lead.id,
                    organization_id=org_id,
                    assigned_broker_id=lead.broker_id,
                    title=title,
                    description=description,
                    due_at=scheduled_due,
                    priority=rule.priority or "normal",
                    status="pending"
                )
                self.db.add(task)
                await self.db.commit()
                await self.db.refresh(task)
                created_task_id = task.id

                # Record activity
                act = Activity(
                    organization_id=org_id,
                    actor_id=lead.broker_id,
                    lead_id=lead.id,
                    activity_type="task_created",
                    title=f"Automation Task: {title}",
                    description=f"Rule '{rule.name}' generated task #{task.id}.",
                    activity_data={"rule_id": rule.id, "due_at": scheduled_due.isoformat()}
                )
                self.db.add(act)
                await self.db.commit()

            elif rule.action == "send_notification":
                notif_title_tpl = act_cfg.get("notification_title", "Follow-up Reminder for {{lead_name}}")
                notif_body_tpl = act_cfg.get("notification_body", "Follow-up due for {{lead_name}}.")
                n_title = notif_title_tpl.replace("{{lead_name}}", lead_name)
                n_body = notif_body_tpl.replace("{{lead_name}}", lead_name).replace("{{phone}}", lead_phone)

                if lead.broker_id:
                    notif = Notification(
                        id=str(uuid.uuid4()),
                        broker_id=lead.broker_id,
                        organization_id=org_id,
                        category="task",
                        title=n_title,
                        body=n_body,
                        action_url="/dashboard/tasks"
                    )
                    self.db.add(notif)
                    await self.db.commit()
                    await self.db.refresh(notif)
                    created_notif_id = notif.id

            elif rule.action == "escalate":
                # Manager escalation task + notification
                esc_title = f"Manager Escalation: Follow-up required for {lead_name}"
                esc_desc = f"Lead {lead_name} ({lead_phone}) requires manager review. Trigger: {trigger_event}."
                task = Task(
                    id=str(uuid.uuid4()),
                    broker_id=lead.broker_id,
                    lead_id=lead.id,
                    organization_id=org_id,
                    assigned_broker_id=lead.broker_id,
                    title=esc_title,
                    description=esc_desc,
                    due_at=scheduled_due,
                    priority="urgent",
                    status="pending"
                )
                self.db.add(task)
                await self.db.commit()
                await self.db.refresh(task)
                created_task_id = task.id

                if lead.broker_id:
                    notif = Notification(
                        id=str(uuid.uuid4()),
                        broker_id=lead.broker_id,
                        organization_id=org_id,
                        category="task",
                        title=esc_title,
                        body=esc_desc,
                        action_url="/dashboard/tasks"
                    )
                    self.db.add(notif)
                    await self.db.commit()
                    await self.db.refresh(notif)
                    created_notif_id = notif.id

            elif rule.action == "send_email":
                # If auto_send_email is enabled and email available, would dispatch. Otherwise creates draft task.
                if policy and getattr(policy, "auto_send_email", False) and hasattr(lead, "email") and lead.email:
                    logger.info(f"[RuleEngine] Email dispatch enabled for Lead {lead.id}.")
                else:
                    # Safe fallback: draft task
                    task = Task(
                        id=str(uuid.uuid4()),
                        broker_id=lead.broker_id,
                        lead_id=lead.id,
                        organization_id=org_id,
                        assigned_broker_id=lead.broker_id,
                        title=f"Send Email Follow-Up to {lead_name}",
                        description=f"Draft email follow-up for {lead_name}. Auto-send is disabled by org policy.",
                        due_at=scheduled_due,
                        priority="normal",
                        status="pending"
                    )
                    self.db.add(task)
                    await self.db.commit()
                    await self.db.refresh(task)
                    created_task_id = task.id

            await IdempotencyService.record_success(
                db=self.db,
                event_id=event.id,
                task_id=created_task_id,
                notification_id=created_notif_id,
                details={"scheduled_due": scheduled_due.isoformat()}
            )
            return event

        except Exception as exc:
            logger.exception(f"[RuleEngine] Error executing rule {rule.id}: {exc}")
            await IdempotencyService.record_failure(self.db, event.id, str(exc))
            return None
