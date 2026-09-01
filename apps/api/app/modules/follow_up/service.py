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
    NextBestAction
)
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

        # 3. Channel Selection
        reason_type = trigger_event or "UNANSWERED_INQUIRY"
        channel, channel_score = self.channel_selector.select_channel(lead, policy, reason_type=reason_type)

        # 4. Suppression Evaluation
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
