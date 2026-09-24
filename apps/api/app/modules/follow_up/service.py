"""
Follow-Up & Lead Nurturing Orchestrator Service
===============================================
Main workflow engine orchestrating lifecycle state verification, suppression checks,
smart timing, channel selection, grounded message generation, Next Best Action, and dispatch.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, and_

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.follow_up_models import (
    FollowUpPolicy, FollowUpSequence, FollowUpSequenceStep, FollowUpEnrollment,
    FollowUpExecution, FollowUpDecision, CommunicationConsent, ContactFatigue,
    NextBestAction, FollowUpRule, FollowUpAutomationEvent
)
from app.models.crm_models import Task, Notification, Activity, Meeting
from app.models.crm_intelligence_models import SlaInstance, SlaBreach
from app.modules.follow_up.lifecycle.lifecycle_manager import LeadLifecycleManager
from app.modules.follow_up.consent.consent_manager import ConsentManager
from app.modules.follow_up.suppression.suppression_engine import SuppressionEngine
from app.modules.follow_up.timing.timing_engine import TimingEngine
from app.modules.follow_up.channel_selection.channel_selector import ChannelSelector
from app.modules.follow_up.content_strategy.strategy_engine import ContentStrategyEngine
from app.modules.follow_up.message_generation.grounded_generator import GroundedMessageGenerator
from app.modules.follow_up.fatigue.fatigue_detector import FatigueDetector
from app.modules.follow_up.next_best_action.nba_calculator import NextBestActionEngine
from app.modules.follow_up.sequence.sequence_engine import SequenceEngine
from app.modules.follow_up.sla.sla_service import SlaService
from app.modules.follow_up.rules.rule_engine import RuleEngine
from app.modules.follow_up.escalation.escalation_service import EscalationService
from app.modules.follow_up.briefing.briefing_service import BriefingService
from app.modules.follow_up.ai_reengagement.reengagement_service import ReengagementService
from app.modules.follow_up.idempotency.idempotency_service import IdempotencyService
from app.modules.follow_up.dto.follow_up_schemas import (
    FollowUpPolicyDTO, UpdatePolicyDTO, NextBestActionDTO, FollowUpExecutionDTO,
    FollowUpEvaluationResponseDTO, LeadFollowUpStatusDTO
)

logger = logging.getLogger(__name__)

class FollowUpOrchestratorService:
    """
    Enterprise lead follow-up & autonomous lifecycle orchestrator.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.lifecycle_manager = LeadLifecycleManager(db)
        self.consent_manager = ConsentManager(db)
        self.suppression_engine = SuppressionEngine(db)
        self.timing_engine = TimingEngine()
        self.channel_selector = ChannelSelector()
        self.strategy_engine = ContentStrategyEngine(db)
        self.generator = GroundedMessageGenerator()
        self.fatigue_detector = FatigueDetector(db)
        self.nba_engine = NextBestActionEngine(db)
        self.sequence_engine = SequenceEngine(db)
        self.sla_service = SlaService(db)
        self.rule_engine = RuleEngine(db)
        self.escalation_service = EscalationService(db)
        self.briefing_service = BriefingService(db)
        self.reengagement_service = ReengagementService()

    async def get_or_create_policy(self, organization_id: str) -> FollowUpPolicy:
        """Loads organization follow-up policy or creates default."""
        stmt = select(FollowUpPolicy).where(FollowUpPolicy.organization_id == organization_id)
        res = await self.db.execute(stmt)
        policy = res.scalar_one_or_none()

        if not policy:
            policy = FollowUpPolicy(
                organization_id=organization_id,
                autonomy_level="LEVEL_3",
                allowed_channels=["WHATSAPP", "EMAIL"],
                quiet_hours_start="21:00",
                quiet_hours_end="08:00",
                working_days=[1, 2, 3, 4, 5, 6],
                max_messages_per_day=2,
                max_messages_per_week=5,
                max_consecutive_no_reply=3,
                min_hours_between_msgs=18,
                require_approval_high_value=True,
                high_value_threshold_aed=5000000.0
            )
            self.db.add(policy)
            await self.db.commit()
            await self.db.refresh(policy)

        return policy

    async def update_policy(self, organization_id: str, dto: UpdatePolicyDTO) -> FollowUpPolicy:
        """Updates organization policy settings."""
        policy = await self.get_or_create_policy(organization_id)
        for field, val in dto.model_dump(exclude_unset=True).items():
            if val is not None:
                setattr(policy, field, val)

        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    async def get_channel_status(self) -> Dict[str, Any]:
        """Return the truthful per-channel availability used by channel selection."""
        from app.modules.communication.channels import ChannelStatusService
        return await ChannelStatusService().get_public_summary()

    async def dispatch_execution(self, execution_id: str, organization_id: str) -> Dict[str, Any]:
        """Dispatch a scheduled follow-up execution through the Communication Hub.

        Part 12: the follow-up engine never calls providers directly. The Hub enforces
        channel availability, canonical channel vocabulary, idempotency and outbound
        queueing. Idempotent: an execution already dispatched or terminal is not re-sent.
        """
        from app.modules.communication.hub import CommunicationHub
        from app.modules.communication.channels import Channel, MessageActorType

        stmt = select(FollowUpExecution).where(
            FollowUpExecution.id == execution_id,
            FollowUpExecution.organization_id == organization_id,
        )
        execution = (await self.db.execute(stmt)).scalars().first()
        if not execution:
            raise ValueError(f"Follow-up execution '{execution_id}' not found.")

        if execution.status in ("CANCELLED", "SUPPRESSED", "FAILED"):
            raise ValueError(
                f"Follow-up execution '{execution_id}' is {execution.status} and cannot be dispatched."
            )
        if execution.status in ("DISPATCHED", "DELIVERED", "READ", "RESPONDED", "SENT"):
            return {
                "status": "already_dispatched",
                "execution_id": execution.id,
                "message_id": None,
                "channel": execution.channel,
                "delivery_status": execution.status,
            }

        try:
            lead_pk = uuid.UUID(str(execution.lead_id))
        except Exception:
            lead_pk = execution.lead_id
        lead = (await self.db.execute(select(Lead).where(Lead.id == lead_pk))).scalars().first()
        if not lead:
            raise ValueError(f"Lead '{execution.lead_id}' not found for execution '{execution_id}'.")

        if not execution.message_body:
            raise ValueError("Follow-up execution has no message body to dispatch.")

        canonical = Channel.normalize(execution.channel)
        recipient = self._recipient_identifier_for(canonical, lead)
        if not recipient:
            raise ValueError(f"No recipient identifier available for channel '{canonical.value}'.")

        hub = CommunicationHub()
        result = await hub.send_message(
            db=self.db,
            organization_id=organization_id,
            lead_id=str(lead.id),
            channel=canonical,
            content=execution.message_body,
            recipient_identifier=recipient,
            actor_type=MessageActorType.AUTOMATION,
            message_type="text",
            content_structured={"subject": execution.message_subject} if execution.message_subject else None,
            # Deterministic key: a retried dispatch (Celery retry, duplicate
            # scheduled trigger) reuses the existing message instead of re-sending.
            idempotency_key=f"followup:{execution.id}",
        )

        execution.status = "DISPATCHED"
        execution.executed_at = datetime.now(timezone.utc)
        facts = list(execution.grounded_facts or [])
        facts.append({
            "dispatch": "communication_hub",
            "message_id": result.message_id,
            "provider": result.provider_name,
        })
        execution.grounded_facts = facts
        await self.db.commit()

        logger.info(
            f"[FollowUpService] Dispatched execution {execution.id} via Communication Hub "
            f"channel={result.channel} message_id={result.message_id}"
        )
        return {
            "status": "dispatched",
            "execution_id": execution.id,
            "message_id": result.message_id,
            "conversation_id": result.conversation_id,
            "channel": result.channel,
            "delivery_status": result.delivery_status,
            "provider": result.provider_name,
        }

    @staticmethod
    def _recipient_identifier_for(channel, lead: Lead) -> Optional[str]:
        """Resolve the channel-appropriate recipient identifier for a lead."""
        from app.modules.communication.channels import Channel
        if channel is Channel.EMAIL:
            return lead.email
        if channel in (Channel.SMS, Channel.WHATSAPP):
            return lead.phone
        return lead.email or lead.phone or str(lead.id)

    async def evaluate_lead_followup(
        self,
        lead_id: str,
        organization_id: str,
        broker_id: str,
        trigger_event: Optional[str] = None,
        target_property_id: Optional[str] = None
    ) -> FollowUpEvaluationResponseDTO:
        """
        Main decision pipeline: Evaluates lead eligibility, suppression, timing, channel,
        calculates Next Best Action, and generates grounded message draft if eligible.
        """
        # 1. Fetch Lead
        try:
            lead_pk = uuid.UUID(str(lead_id))
        except Exception:
            lead_pk = lead_id

        stmt = select(Lead).where(Lead.id == lead_pk)
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead ID '{lead_id}' not found.")

        policy = await self.get_or_create_policy(organization_id)
        stage = (lead.pipeline_stage or "new").upper()

        # 2. Compute Next Best Action
        nba = await self.nba_engine.compute_next_best_action(lead, policy, target_property_id)

        # 3. Channel Selection (never returns a disabled/unavailable channel)
        reason_type = trigger_event or "UNANSWERED_INQUIRY"
        channel, channel_score = await self.channel_selector.select_channel(
            lead, policy, reason_type=reason_type, organization_id=organization_id
        )

        # 4. Suppression Evaluation
        if channel is None:
            # No permitted channel is currently enabled/deliverable — do not
            # queue an undeliverable follow-up.
            is_suppressed, supp_reason, rules = True, "NO_AVAILABLE_CHANNEL", []
            logger.info(
                f"[FollowUpService] No available channel for lead {lead_id}; "
                f"follow-up suppressed."
            )
        else:
            is_suppressed, supp_reason, rules = await self.suppression_engine.evaluate_suppression(
                lead=lead, channel=channel, policy=policy
            )

        # 5. Timing Calculation
        optimal_time_utc, tz_name = self.timing_engine.calculate_optimal_send_time(lead, policy)

        # 6. Draft Message if Eligible
        draft_exec_dto: Optional[FollowUpExecutionDTO] = None
        if not is_suppressed and policy.autonomy_level != "LEVEL_0":
            context = await self.strategy_engine.build_strategy_context(lead, reason_type, target_property_id)
            body, subject = self.generator.generate_message(context, language="en", channel=channel)

            # Check if high-value lead requires manual broker approval
            budget_val = float(lead.budget_max or 0.0)
            req_approval = policy.require_approval_high_value and (budget_val >= policy.high_value_threshold_aed)

            exec_status = "PENDING_APPROVAL" if (req_approval or policy.autonomy_level in ("LEVEL_1", "LEVEL_2")) else "SCHEDULED"

            execution = FollowUpExecution(
                lead_id=str(lead.id),
                organization_id=organization_id,
                broker_id=broker_id,
                channel=channel,
                reason_type=reason_type,
                status=exec_status,
                scheduled_for_utc=optimal_time_utc,
                recipient_identifier=lead.phone or "customer",
                message_subject=subject,
                message_body=body,
                grounded_facts=context.get("grounded_facts", [])
            )
            self.db.add(execution)
            await self.db.commit()
            await self.db.refresh(execution)

            # Audit Decision Record
            decision = FollowUpDecision(
                execution_id=execution.id,
                lead_id=str(lead.id),
                decision_outcome="ELIGIBLE" if not is_suppressed else "SUPPRESSED",
                fatigue_score=0.0,
                selected_channel_score=channel_score,
                rules_evaluated=rules
            )
            self.db.add(decision)
            await self.db.commit()

            draft_exec_dto = FollowUpExecutionDTO(
                id=execution.id,
                lead_id=str(lead.id),
                organization_id=organization_id,
                broker_id=broker_id,
                channel=channel,
                reason_type=reason_type,
                status=execution.status,
                scheduled_for_utc=execution.scheduled_for_utc,
                recipient_identifier=execution.recipient_identifier,
                message_subject=execution.message_subject,
                message_body=execution.message_body,
                grounded_facts=execution.grounded_facts,
                suppression_reason=execution.suppression_reason,
                response_detected=execution.response_detected
            )

        return FollowUpEvaluationResponseDTO(
            lead_id=str(lead.id),
            lifecycle_state=stage,
            is_eligible=not is_suppressed,
            is_suppressed=is_suppressed,
            suppression_reason=supp_reason,
            selected_channel=channel,
            optimal_time_utc=optimal_time_utc,
            next_best_action=NextBestActionDTO(
                recommended_action=nba.recommended_action,
                action_reason=nba.action_reason,
                priority_score=nba.priority_score,
                confidence=nba.confidence,
                expected_outcome=nba.expected_outcome,
                target_property_id=nba.target_property_id
            ),
            draft_message=draft_exec_dto
        )

    async def handle_inbound_reply(self, lead_id: str, organization_id: str) -> None:
        """
        HALT INVARIANT & FATIGUE RESET:
        When customer replies, immediately reset fatigue and halt active follow-up sequences.
        """
        # 1. Reset fatigue
        await self.fatigue_detector.record_inbound_response(lead_id, organization_id)

        # 2. Halt active sequences and cancel pending follow-up messages
        await self.sequence_engine.halt_active_enrollments(lead_id, reason="Customer Responded")

        # 3. Transition lead stage to engaging/qualifying if contacting
        try:
            lead_pk = uuid.UUID(str(lead_id))
        except Exception:
            lead_pk = lead_id

        stmt = select(Lead).where(Lead.id == lead_pk)
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if lead and (lead.pipeline_stage or "").lower() in ("new", "contacting"):
            await self.lifecycle_manager.transition_lead(lead, "ENGAGING", reason="Customer Inbound Reply")

    async def handle_opt_out(self, lead_id: str, organization_id: str) -> None:
        """
        PERMANENT STOP INVARIANT:
        When customer requests STOP / opt-out, record permanent opt-out and halt automation.
        """
        await self.consent_manager.record_opt_out(lead_id, organization_id)
        await self.sequence_engine.halt_active_enrollments(lead_id, reason="Customer Opted Out")

        try:
            lead_pk = uuid.UUID(str(lead_id))
        except Exception:
            lead_pk = lead_id

        stmt = select(Lead).where(Lead.id == lead_pk)
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if lead:
            await self.lifecycle_manager.transition_lead(lead, "DO_NOT_CONTACT", reason="Customer Opt-Out")

    # ── Rule Management ───────────────────────────────────────────────────────
    async def create_rule(
        self,
        organization_id: str,
        name: str,
        trigger: str,
        action: str,
        delay_minutes: int = 0,
        conditions: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        max_runs: int = 1,
        cooldown_hours: int = 24,
        action_config: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None
    ) -> FollowUpRule:
        """Creates a tenant-scoped follow-up automation rule."""
        rule = FollowUpRule(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            name=name,
            enabled=True,
            trigger=trigger,
            delay_minutes=delay_minutes,
            action=action,
            conditions=conditions or {},
            priority=priority,
            max_runs=max_runs,
            cooldown_hours=cooldown_hours,
            action_config=action_config or {},
            created_by=created_by
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        logger.info(f"[FollowUpService] Created rule '{name}' ({rule.id}) for Org {organization_id}.")
        return rule

    async def list_rules(self, organization_id: str) -> List[FollowUpRule]:
        """Lists all automation rules for an organization."""
        stmt = select(FollowUpRule).where(FollowUpRule.organization_id == organization_id).order_by(FollowUpRule.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_rule(self, organization_id: str, rule_id: str) -> Optional[FollowUpRule]:
        """Retrieves a single rule ensuring tenant isolation."""
        stmt = select(FollowUpRule).where(
            FollowUpRule.id == rule_id,
            FollowUpRule.organization_id == organization_id
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def update_rule(self, organization_id: str, rule_id: str, updates: Dict[str, Any]) -> Optional[FollowUpRule]:
        """Updates rule configuration attributes."""
        rule = await self.get_rule(organization_id, rule_id)
        if not rule:
            return None

        allowed_fields = {"name", "enabled", "trigger", "delay_minutes", "action", "action_config", "conditions", "priority", "max_runs", "cooldown_hours"}
        for k, v in updates.items():
            if k in allowed_fields and v is not None:
                setattr(rule, k, v)

        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, organization_id: str, rule_id: str) -> bool:
        """Deletes a rule ensuring tenant isolation."""
        rule = await self.get_rule(organization_id, rule_id)
        if not rule:
            return False
        await self.db.delete(rule)
        await self.db.commit()
        return True

    # ── Task Snooze & Reschedule (Human Override) ─────────────────────────────
    async def snooze_task(
        self,
        broker_id: uuid.UUID,
        task_id: str,
        snooze_until: datetime,
        reason: str = "Snoozed by Broker"
    ) -> Optional[Task]:
        """
        Snoozes a task to a later time. Preserves task history and records activity.
        Ensures automation does not overwrite manual agent adjustments.
        """
        stmt = select(Task).where(Task.id == task_id)
        res = await self.db.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            return None

        old_due = task.due_at
        task.due_at = snooze_until
        await self.db.commit()
        await self.db.refresh(task)

        # Record activity
        if task.lead_id:
            act = Activity(
                organization_id=task.organization_id,
                actor_id=broker_id,
                lead_id=task.lead_id,
                activity_type="task_snoozed",
                title="Task Snoozed",
                description=f"Task '{task.title}' snoozed to {snooze_until.isoformat()}. Reason: {reason}",
                activity_data={"task_id": task.id, "previous_due_at": old_due.isoformat() if old_due else None, "new_due_at": snooze_until.isoformat()}
            )
            self.db.add(act)
            await self.db.commit()

        logger.info(f"[FollowUpService] Snoozed task {task_id} to {snooze_until.isoformat()}.")
        return task

    async def reschedule_task(
        self,
        broker_id: uuid.UUID,
        task_id: str,
        new_due_at: datetime,
        reason: str = "Rescheduled by Broker"
    ) -> Optional[Task]:
        """Reschedules a task ensuring human override is respected."""
        return await self.snooze_task(broker_id, task_id, new_due_at, reason=reason)

    # ── Follow-Up Dashboard Summary ───────────────────────────────────────────
    async def get_dashboard_summary(
        self,
        broker_id: uuid.UUID,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Returns full CRM Follow-Up Dashboard metrics:
        - Today's tasks (due today, overdue, SLA breaches, high priority)
        - Upcoming tasks (tomorrow, next 7 days)
        - Pipeline counts (new leads awaiting contact, active follow-ups, re-engagement candidates)
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        tomorrow_end = today_end + timedelta(days=1)
        next_7_days_end = today_end + timedelta(days=7)

        # 1. Due Today Tasks
        stmt_due_today = select(Task).where(
            Task.broker_id == broker_id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at >= today_start,
            Task.due_at <= today_end
        ).order_by(Task.due_at.asc())
        res_dt = await self.db.execute(stmt_due_today)
        due_today_tasks = list(res_dt.scalars().all())

        # 2. Overdue Tasks
        stmt_overdue = select(Task).where(
            Task.broker_id == broker_id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at < now
        ).order_by(Task.due_at.asc())
        res_ov = await self.db.execute(stmt_overdue)
        overdue_tasks = list(res_ov.scalars().all())

        # 3. Upcoming Tasks (Tomorrow to next 7 days)
        stmt_upcoming = select(Task).where(
            Task.broker_id == broker_id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at > today_end,
            Task.due_at <= next_7_days_end
        ).order_by(Task.due_at.asc())
        res_up = await self.db.execute(stmt_upcoming)
        upcoming_tasks = list(res_up.scalars().all())

        # 4. Active SLA Breaches
        stmt_breaches = select(SlaBreach).where(
            SlaBreach.organization_id == organization_id
        ).order_by(SlaBreach.breached_at_utc.desc()).limit(20)
        res_br = await self.db.execute(stmt_breaches)
        sla_breaches = list(res_br.scalars().all())

        # 5. Pipeline Counts
        stmt_awaiting_contact = select(func.count(Lead.id)).where(
            Lead.broker_id == broker_id,
            Lead.pipeline_stage.in_(["new", "lead_captured"]),
            Lead.status.in_(["pending", "active"]),
            Lead.deleted_at.is_(None)
        )
        res_aw = await self.db.execute(stmt_awaiting_contact)
        awaiting_contact_count = res_aw.scalar() or 0

        # Helper serialize
        def _fmt_task(t: Task) -> Dict[str, Any]:
            return {
                "id": str(t.id),
                "title": t.title,
                "description": t.description,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "priority": t.priority,
                "status": t.status,
                "lead_id": str(t.lead_id) if t.lead_id else None
            }

        return {
            "counts": {
                "due_today": len(due_today_tasks),
                "overdue": len(overdue_tasks),
                "upcoming": len(upcoming_tasks),
                "sla_breaches": len(sla_breaches),
                "awaiting_first_contact": awaiting_contact_count
            },
            "tasks_due_today": [_fmt_task(t) for t in due_today_tasks],
            "tasks_overdue": [_fmt_task(t) for t in overdue_tasks],
            "tasks_upcoming": [_fmt_task(t) for t in upcoming_tasks],
            "sla_breaches": [
                {
                    "id": str(b.id),
                    "lead_id": b.lead_id,
                    "sla_type": b.sla_type,
                    "overdue_minutes": b.overdue_minutes,
                    "breached_at": b.breached_at_utc.isoformat() if b.breached_at_utc else None
                }
                for b in sla_breaches
            ]
        }

    # ── Performance Analytics ─────────────────────────────────────────────────
    async def get_performance_analytics(self, organization_id: str) -> Dict[str, Any]:
        """
        Calculates aggregate follow-up performance metrics:
        - Tasks created, completed, overdue, skipped
        - SLA compliance rate
        - Average time to first contact
        """
        # Tasks metrics
        stmt_total_tasks = select(func.count(Task.id)).where(Task.organization_id == organization_id)
        total_tasks = (await self.db.execute(stmt_total_tasks)).scalar() or 0

        stmt_completed = select(func.count(Task.id)).where(
            Task.organization_id == organization_id,
            Task.status == "completed"
        )
        completed_tasks = (await self.db.execute(stmt_completed)).scalar() or 0

        now = datetime.now(timezone.utc)
        stmt_overdue = select(func.count(Task.id)).where(
            Task.organization_id == organization_id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at < now
        )
        overdue_tasks = (await self.db.execute(stmt_overdue)).scalar() or 0

        # SLA metrics
        stmt_total_sla = select(func.count(SlaInstance.id)).where(SlaInstance.organization_id == organization_id)
        total_slas = (await self.db.execute(stmt_total_sla)).scalar() or 0

        stmt_met_sla = select(func.count(SlaInstance.id)).where(
            SlaInstance.organization_id == organization_id,
            SlaInstance.status == "MET"
        )
        met_slas = (await self.db.execute(stmt_met_sla)).scalar() or 0

        sla_compliance_rate = round((met_slas / total_slas * 100.0), 1) if total_slas > 0 else 100.0
        completion_rate = round((completed_tasks / total_tasks * 100.0), 1) if total_tasks > 0 else 100.0

        # Automation events count
        stmt_auto_events = select(func.count(FollowUpAutomationEvent.id)).where(
            FollowUpAutomationEvent.organization_id == organization_id,
            FollowUpAutomationEvent.status == "COMPLETED"
        )
        automated_actions = (await self.db.execute(stmt_auto_events)).scalar() or 0

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "completion_rate_pct": completion_rate,
            "total_slas": total_slas,
            "met_slas": met_slas,
            "sla_compliance_rate_pct": sla_compliance_rate,
            "automated_actions_executed": automated_actions,
            "generated_at": now.isoformat()
        }

    # ── Batch Lead Evaluation for Celery ───────────────────────────────────────
    async def process_active_leads_batch(self, batch_size: int = 250, offset: int = 0) -> int:
        """
        Batch-processes active leads for SLA timers, overdue follow-ups, and rule triggers.
        Bounded memory usage: operates in chunks without loading all leads at once.
        """
        stmt = (
            select(Lead)
            .where(
                Lead.status.in_(["pending", "active", "qualified"]),
                Lead.deleted_at.is_(None)
            )
            .order_by(Lead.created_at.desc())
            .offset(offset)
            .limit(batch_size)
        )
        res = await self.db.execute(stmt)
        leads = res.scalars().all()

        processed_count = 0
        now = datetime.now(timezone.utc)

        for lead in leads:
            org_id = str(lead.broker_id)
            policy = await self.get_or_create_policy(org_id)

            # 1. Check if first-contact SLA needs to be created
            lead_created = lead.created_at if lead.created_at.tzinfo else lead.created_at.replace(tzinfo=timezone.utc)
            lead_age_mins = (now - lead_created).total_seconds() / 60.0

            if lead_age_mins <= 60: # Fresh lead in first hour
                await self.sla_service.create_first_contact_sla(lead, policy)

            # 2. Check and evaluate organization rules matching lead state
            rules = await self.list_rules(org_id)
            for rule in rules:
                if not rule.enabled:
                    continue

                hours_since_contact = (now - lead_created).total_seconds() / 3600.0
                ctx = {
                    "hours_since_contact": hours_since_contact,
                    "no_response_count": 0
                }
                await self.rule_engine.execute_rule(rule, lead, trigger_event=rule.trigger, policy=policy, context=ctx)

            processed_count += 1

        return processed_count
