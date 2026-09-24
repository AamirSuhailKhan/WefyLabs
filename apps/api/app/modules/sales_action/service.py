"""
Part 21.5 — AI Sales Action & Follow-Up Domain Service
======================================================
Unified domain orchestrator coordinating:
- Next Best Action evaluation & policy priority
- Consent, quiet hours, and fatigue compliance guards
- Grounded multilingual message generation (EN, HI, AR)
- Part 21.3 Verified Property Recommendations
- Part 21.4.3 Qualification Snapshots & Conflict Detection
- Calendar Viewings & Scheduling Actions
- Multi-Tenant Isolation & Audit Trail
"""
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, update
from fastapi import HTTPException, status

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.follow_up_models import (
    FollowUpPolicy,
    FollowUpExecution,
    FollowUpDecision,
    ContactFatigue,
    NextBestAction,
)
from app.models.calendar_models import SchedulingMeeting as Meeting
from app.models.conversation import Conversation
from app.modules.sales_action.taxonomies import (
    SalesActionType,
    SalesActionStatus,
    CommunicationChannel,
    ConsentStatus,
)
from app.modules.sales_action.dto import (
    SalesActionDecisionDTO,
    SalesBriefDTO,
    SalesActionExecutionResultDTO,
    FollowUpStateDTO,
)
from app.modules.sales_action.guards.consent_guard import ConsentGuard
from app.modules.sales_action.guards.quiet_hours_guard import QuietHoursGuard
from app.modules.sales_action.guards.fatigue_guard import FatigueGuard
from app.modules.sales_action.policy_engine import SalesActionPolicyEngine
from app.modules.sales_action.message_generator import SalesActionMessageGenerator
from app.modules.sales_action.action_executor import SalesActionExecutor
from app.modules.sales_action.metrics import (
    SALES_ACTIONS_PROPOSED_TOTAL,
    SALES_ACTIONS_APPROVED_TOTAL,
    SALES_ACTIONS_BLOCKED_TOTAL,
    SALES_ACTION_EVALUATION_LATENCY,
    mask_org_id,
)

logger = logging.getLogger(__name__)


class SalesActionDomainService:
    """
    Core service orchestrating the AI Sales Action & Follow-Up Engine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.consent_guard = ConsentGuard(db)
        self.fatigue_guard = FatigueGuard(db)
        self.executor = SalesActionExecutor(db)

    async def _validate_and_get_lead(
        self,
        lead_id: str,
        organization_id: str,
        broker: Optional[Broker] = None,
    ) -> Lead:
        """Enforces strict multi-tenant authorization boundaries."""
        try:
            lead_uuid = uuid.UUID(str(lead_id))
        except Exception:
            lead_uuid = lead_id

        stmt = select(Lead).where(Lead.id == lead_uuid)
        res = await self.db.execute(stmt)
        lead = res.scalars().first()

        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead '{lead_id}' not found.",
            )

        # Multi-tenant isolation check
        org_matches = False
        if hasattr(lead, "organization_id") and lead.organization_id:
            org_matches = str(lead.organization_id) == str(organization_id)
        elif lead.broker_id:
            org_matches = (str(lead.broker_id) == str(organization_id))

        if broker and not org_matches:
            if str(lead.broker_id) == str(broker.id):
                org_matches = True

        if not org_matches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Lead '{lead_id}' does not belong to organization '{organization_id}'.",
            )

        return lead

    async def get_or_create_policy(self, organization_id: str) -> FollowUpPolicy:
        """Loads organization follow-up policy or initializes default."""
        stmt = select(FollowUpPolicy).where(FollowUpPolicy.organization_id == organization_id)
        res = await self.db.execute(stmt)
        policy = res.scalars().first()

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
                high_value_threshold_aed=5000000.0,
            )
            self.db.add(policy)
            await self.db.flush()

        return policy

    @staticmethod
    def _to_communication_channel(channel) -> CommunicationChannel:
        """Map a canonical Channel to the sales-action channel enum."""
        from app.modules.communication.channels import Channel
        if channel is Channel.EMAIL:
            return CommunicationChannel.EMAIL
        if channel is Channel.SMS:
            return CommunicationChannel.SMS
        if channel is Channel.WHATSAPP:
            return CommunicationChannel.WHATSAPP
        if channel is Channel.WEB:
            return CommunicationChannel.IN_APP
        return CommunicationChannel.IN_APP

    async def _ordered_available_channels(self, policy: FollowUpPolicy) -> List[Any]:
        """Ordered canonical channels that are ENABLED right now.

        Policy-allowed channels come first, followed by the platform fallbacks.
        Disabled / unconfigured channels (WhatsApp, unconfigured SMS, future
        channels) are excluded entirely so nothing downstream can select them.
        """
        from app.modules.communication.channels import (
            Channel,
            ChannelEnablementState,
            ChannelStatusService,
        )

        candidates: List[Any] = [Channel.normalize(t) for t in (policy.allowed_channels or ["WHATSAPP", "EMAIL"])]
        # Platform fallbacks (web/in-app is always available when enabled).
        candidates.extend([Channel.WEB, Channel.EMAIL, Channel.SMS])

        status_service = ChannelStatusService()
        available: List[Any] = []
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            status = await status_service.get_status(candidate)
            if status.state == ChannelEnablementState.ENABLED:
                available.append(candidate)
        return available

    async def _resolve_default_channel(self, policy: FollowUpPolicy) -> CommunicationChannel:
        """Resolve the outbound channel from availability instead of hardcoding WhatsApp.

        Part 12: prefers a policy-allowed channel that is currently ENABLED, then the
        platform's own web/in-app channel. Never returns a disabled channel when an
        enabled one exists.
        """
        available = await self._ordered_available_channels(policy)
        if not available:
            logger.warning(
                "[SalesActionService] No enabled communication channel available for org=%s; "
                "falling back to policy default.",
                getattr(policy, "organization_id", None),
            )
            return CommunicationChannel.WHATSAPP
        return self._to_communication_channel(available[0])

    async def _resolve_channel_and_consent(
        self,
        policy: FollowUpPolicy,
        lead_id: str,
        organization_id: str,
        is_direct_customer_inquiry: bool,
    ) -> Tuple[CommunicationChannel, ConsentStatus, Optional[str]]:
        """Resolve the outbound channel *and* the consent decision for that channel.

        Part 12: the channel is resolved from real availability (never a hardcoded
        WhatsApp default) and consent is subsequently evaluated for that exact
        channel. When several channels are available we prefer one the customer has
        actually consented to; if none is consented, the first available channel is
        returned with its own (blocking) consent status so the decision is blocked
        honestly instead of silently switching to a different channel.
        """
        available = await self._ordered_available_channels(policy)
        if not available:
            logger.warning(
                "[SalesActionService] No enabled communication channel available for org=%s.",
                getattr(policy, "organization_id", None),
            )
            return (
                CommunicationChannel.WHATSAPP,
                ConsentStatus.UNKNOWN,
                "No enabled communication channel is currently available.",
            )

        fallback: Optional[Tuple[CommunicationChannel, ConsentStatus, Optional[str]]] = None
        for candidate in available:
            mapped = self._to_communication_channel(candidate)
            permitted, consent_status, reason = await self.consent_guard.evaluate_consent(
                lead_id=lead_id,
                organization_id=organization_id,
                channel=mapped,
                is_direct_customer_inquiry=is_direct_customer_inquiry,
            )
            if permitted:
                return mapped, consent_status, reason
            if fallback is None:
                fallback = (mapped, consent_status, reason)

        logger.info(
            "[SalesActionService] No consented available channel for lead=%s; blocking "
            "outbound on channel=%s (consent=%s).",
            lead_id,
            fallback[0].value,
            fallback[1].value,
        )
        return fallback

    async def evaluate_next_sales_action(
        self,
        lead_id: str,
        organization_id: str,
        trigger_event: Optional[str] = None,
        target_property_id: Optional[str] = None,
        broker: Optional[Broker] = None,
    ) -> SalesActionDecisionDTO:
        """
        Main decision pipeline:
        1. Tenant validation.
        2. Ingests Qualification Snapshot (Part 21.4.3) & Fact state.
        3. Queries verified property recommendations (Part 21.3).
        4. Ingests Calendar Viewings.
        5. Runs Consent, Quiet Hours, Fatigue compliance guards.
        6. Evaluates deterministic priority policy.
        7. Phrases grounded message.
        8. Records NextBestAction and observability metrics.
        """
        start_time = time.perf_counter()
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        policy = await self.get_or_create_policy(organization_id)
        org_hash = mask_org_id(organization_id)

        # ── 2. Ingest Qualification Data via Part 21.4.3 ─────────────────────
        from app.modules.lead_qualification.service import LeadQualificationDomainService
        qual_service = LeadQualificationDomainService(self.db)
        qual_snapshot = await qual_service.get_lead_qualification_snapshot(organization_id, str(lead.id), broker)
        active_facts = await qual_service.get_lead_facts(organization_id, str(lead.id), False, broker)
        open_conflicts = await qual_service.get_lead_conflicts(organization_id, str(lead.id), broker)

        facts_summary = {f.field_name: f.normalized_value or f.raw_value for f in active_facts}
        has_blocking_conflicts = len(open_conflicts) > 0 or (qual_snapshot.state == "NEEDS_HUMAN_REVIEW")

        # ── 3. Query Verified Property Recommendations via Part 21.3 ──────────
        matched_props_list: List[Dict[str, Any]] = []
        try:
            from app.modules.property_recommendation.service import PropertyRecommendationService
            from app.modules.property_recommendation.dto import PropertyRecommendationRequestDTO
            rec_svc = PropertyRecommendationService(self.db)
            rec_res = await rec_svc.generate_recommendations(
                dto=PropertyRecommendationRequestDTO(lead_id=str(lead.id), limit=3),
                organization_id=organization_id,
            )
            if rec_res and rec_res.items:
                matched_props_list = [
                    {
                        "property_id": str(item.property_id),
                        "title": item.title,
                        "price": item.price,
                        "currency": getattr(item, "currency_code", "AED"),
                        "bedrooms": item.bedrooms,
                        "location": getattr(item, "locality", "") or getattr(item, "city", "") or getattr(item, "location", "Dubai"),
                        "match_score": item.match_score,
                    }
                    for item in rec_res.items
                ]
        except Exception as ex:
            logger.debug(f"[SALES_ACTION_SERVICE] Recommendation lookup info: {ex}")

        # ── 4. Ingest Calendar Viewings ──────────────────────────────────────
        # Meeting.lead_id is UUID(as_uuid=True); use the uuid.UUID object directly
        stmt_v = select(Meeting).where(Meeting.lead_id == lead.id).order_by(desc(Meeting.start_utc))
        res_v = await self.db.execute(stmt_v)
        viewings = list(res_v.scalars().all())

        # ── 5. Ingest Previous Executions & Latest Message ────────────────────
        stmt_exec = (
            select(FollowUpExecution)
            .where(FollowUpExecution.lead_id == str(lead.id))
            .order_by(desc(FollowUpExecution.executed_at))
        )
        res_exec = await self.db.execute(stmt_exec)
        prev_execs = list(res_exec.scalars().all())

        stmt_conv = (
            select(Conversation)
            .where(Conversation.lead_id == lead.id)
            .order_by(desc(Conversation.created_at))
            .limit(1)
        )
        res_conv = await self.db.execute(stmt_conv)
        latest_conv = res_conv.scalars().first()
        latest_msg = latest_conv.message if latest_conv else None

        # ── 6. Compliance & Safety Guards ────────────────────────────────────
        # Consent Guard — evaluated against the *available* channel that will actually
        # be used (Part 12), never a hardcoded WhatsApp proxy.
        is_direct = bool(latest_msg and len(prev_execs) == 0)
        default_channel, consent_status, consent_reason = await self._resolve_channel_and_consent(
            policy=policy,
            lead_id=str(lead.id),
            organization_id=organization_id,
            is_direct_customer_inquiry=is_direct,
        )

        # Quiet Hours Guard
        is_timing_ok, sched_utc, cust_tz, timing_reason = QuietHoursGuard.evaluate_timing(
            lead=lead,
            policy=policy,
        )

        # Fatigue Guard
        is_fatigued, fatigue_score, fatigue_reason, is_dormant_candidate = await self.fatigue_guard.evaluate_fatigue(
            lead_id=str(lead.id),
            organization_id=organization_id,
            policy=policy,
        )

        # ── 7. Evaluate Deterministic Next Best Action Policy ─────────────────
        decision = SalesActionPolicyEngine.evaluate_decision(
            lead=lead,
            organization_id=organization_id,
            qualification_snapshot=qual_snapshot,
            active_facts_summary=facts_summary,
            has_blocking_conflicts=has_blocking_conflicts,
            latest_customer_message=latest_msg,
            matched_properties=matched_props_list,
            viewings=viewings,
            policy=policy,
            consent_status=consent_status,
            consent_blocked_reason=consent_reason,
            is_timing_permitted=is_timing_ok,
            scheduled_for_utc=sched_utc,
            customer_timezone=cust_tz,
            timing_reason=timing_reason,
            is_fatigued=is_fatigued,
            fatigue_score=fatigue_score,
            fatigue_reason=fatigue_reason,
            is_dormant_candidate=is_dormant_candidate,
            previous_executions=prev_execs,
            default_channel=default_channel,
        )

        # ── 8. Phrase Grounded Message Draft ─────────────────────────────────
        missing_field = decision.required_facts[0] if decision.required_facts else None
        location_val = facts_summary.get("location") or (", ".join(lead.preferred_locations) if lead.preferred_locations else None)
        ptype_val = facts_summary.get("property_type") or lead.property_type

        body, subject, is_fallback = await SalesActionMessageGenerator.generate_message(
            action_type=decision.action_type,
            lead_name=lead.name or "there",
            channel=decision.recommended_channel,
            language="en",
            property_summaries=matched_props_list,
            location=location_val,
            property_type=ptype_val,
            missing_field_name=missing_field,
        )
        decision.draft_message_body = body
        decision.draft_message_subject = subject

        # ── 9. Save or Update NextBestAction Record in DB ────────────────────
        stmt_nba = select(NextBestAction).where(NextBestAction.lead_id == str(lead.id))
        res_nba = await self.db.execute(stmt_nba)
        nba_record = res_nba.scalars().first()

        if not nba_record:
            nba_record = NextBestAction(
                lead_id=str(lead.id),
                organization_id=organization_id,
                recommended_action=decision.action_type.value,
                action_reason=decision.reason,
                priority_score=decision.priority,
                confidence=decision.confidence,
                expected_outcome=f"Status: {decision.status.value}",
                target_property_id=matched_props_list[0].get("property_id") if matched_props_list else None,
                calculated_at=datetime.now(timezone.utc),
            )
            self.db.add(nba_record)
        else:
            nba_record.recommended_action = decision.action_type.value
            nba_record.action_reason = decision.reason
            nba_record.priority_score = decision.priority
            nba_record.confidence = decision.confidence
            nba_record.expected_outcome = f"Status: {decision.status.value}"
            nba_record.target_property_id = matched_props_list[0].get("property_id") if matched_props_list else None
            nba_record.calculated_at = datetime.now(timezone.utc)

        await self.db.commit()

        # Observability Metrics
        SALES_ACTIONS_PROPOSED_TOTAL.labels(org_hash=org_hash, action_type=decision.action_type.value).inc()
        if decision.status == SalesActionStatus.BLOCKED:
            SALES_ACTIONS_BLOCKED_TOTAL.labels(org_hash=org_hash, reason=decision.blocked_reason or "COMPLIANCE").inc()
        elif decision.status == SalesActionStatus.APPROVED:
            SALES_ACTIONS_APPROVED_TOTAL.labels(org_hash=org_hash, action_type=decision.action_type.value).inc()

        SALES_ACTION_EVALUATION_LATENCY.labels(org_hash=org_hash).observe(time.perf_counter() - start_time)

        return decision

    async def get_lead_sales_actions(
        self,
        lead_id: str,
        organization_id: str,
        broker: Optional[Broker] = None,
    ) -> List[SalesActionDecisionDTO]:
        """Returns the active Next Best Action and recent action decisions."""
        await self._validate_and_get_lead(lead_id, organization_id, broker)
        decision = await self.evaluate_next_sales_action(lead_id, organization_id, broker=broker)
        return [decision]

    async def approve_sales_action(
        self,
        action_id: str,
        lead_id: str,
        organization_id: str,
        custom_message: Optional[str] = None,
        broker: Optional[Broker] = None,
    ) -> SalesActionDecisionDTO:
        """Approves a proposed or review-pending sales action."""
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        decision = await self.evaluate_next_sales_action(lead_id, organization_id, broker=broker)
        decision.action_id = action_id
        decision.status = SalesActionStatus.APPROVED
        decision.automation_allowed = True
        if custom_message:
            decision.draft_message_body = custom_message
        return decision

    async def execute_sales_action(
        self,
        action_id: str,
        lead_id: str,
        organization_id: str,
        custom_message: Optional[str] = None,
        broker: Optional[Broker] = None,
    ) -> SalesActionExecutionResultDTO:
        """Directly dispatches an approved sales action."""
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        effective_broker = broker or (await self.db.execute(select(Broker).where(Broker.id == lead.broker_id))).scalars().first()
        if not effective_broker:
            effective_broker = Broker(id=lead.broker_id, name="Default Broker", email="broker@example.com")

        decision = await self.evaluate_next_sales_action(lead_id, organization_id, broker=effective_broker)
        decision.action_id = action_id

        # Execute through truthful dispatcher
        return await self.executor.execute_action(
            decision=decision,
            lead=lead,
            broker=effective_broker,
            custom_message=custom_message,
        )

    async def cancel_sales_action(
        self,
        action_id: str,
        lead_id: str,
        organization_id: str,
        broker: Optional[Broker] = None,
    ) -> Dict[str, Any]:
        """Cancels a scheduled or pending sales action."""
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        stmt = (
            update(FollowUpExecution)
            .where(
                FollowUpExecution.lead_id == str(lead.id),
                FollowUpExecution.status.in_(["SCHEDULED", "PENDING_APPROVAL", "QUEUED"]),
            )
            .values(status="CANCELLED")
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return {"action_id": action_id, "status": "CANCELLED", "lead_id": str(lead.id)}

    async def get_follow_up_state(
        self,
        lead_id: str,
        organization_id: str,
        broker: Optional[Broker] = None,
    ) -> FollowUpStateDTO:
        """Retrieves real-time fatigue score, consecutive unanswered count, and active scheduled actions."""
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        fatigue = await self.fatigue_guard.get_or_create_fatigue(str(lead.id), organization_id)

        stmt_exec = select(FollowUpExecution).where(
            FollowUpExecution.lead_id == str(lead.id),
            FollowUpExecution.status.in_(["SCHEDULED", "QUEUED", "PENDING_APPROVAL"]),
        )
        res_exec = await self.db.execute(stmt_exec)
        scheduled = list(res_exec.scalars().all())

        is_dormant = fatigue.consecutive_no_replies >= 3 or fatigue.is_suppressed
        stage = (lead.pipeline_stage or lead.status or "new").upper()
        is_paused = stage in ("DO_NOT_CONTACT", "PAUSED")

        return FollowUpStateDTO(
            lead_id=str(lead.id),
            organization_id=organization_id,
            is_paused=is_paused,
            is_dormant=is_dormant,
            is_suppressed=fatigue.is_suppressed,
            suppression_reason="Excessive unanswered communication attempts" if fatigue.is_suppressed else None,
            fatigue_score=fatigue.current_fatigue_score,
            consecutive_no_replies=fatigue.consecutive_no_replies,
            total_messages_sent=fatigue.total_messages_sent,
            last_contacted_at=fatigue.last_contacted_at,
            last_responded_at=fatigue.last_responded_at,
            active_scheduled_actions=[
                {
                    "id": e.id,
                    "channel": e.channel,
                    "reason_type": e.reason_type,
                    "status": e.status,
                    "scheduled_for_utc": e.scheduled_for_utc,
                }
                for e in scheduled
            ],
        )

    async def pause_follow_up(
        self,
        lead_id: str,
        organization_id: str,
        broker: Optional[Broker] = None,
    ) -> FollowUpStateDTO:
        """Pauses automated follow-up for a lead."""
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        lead.pipeline_stage = "DO_NOT_CONTACT"
        await self.cancel_sales_action("all", lead_id, organization_id, broker)
        await self.db.commit()
        return await self.get_follow_up_state(lead_id, organization_id, broker)

    async def resume_follow_up(
        self,
        lead_id: str,
        organization_id: str,
        broker: Optional[Broker] = None,
    ) -> FollowUpStateDTO:
        """Resets fatigue counters and resumes follow-up for a lead."""
        lead = await self._validate_and_get_lead(lead_id, organization_id, broker)
        if (lead.pipeline_stage or "").upper() == "DO_NOT_CONTACT":
            lead.pipeline_stage = "QUALIFYING"
        await self.fatigue_guard.record_inbound_response(str(lead.id), organization_id)
        await self.db.commit()
        return await self.get_follow_up_state(lead_id, organization_id, broker)
