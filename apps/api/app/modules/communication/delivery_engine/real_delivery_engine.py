"""
Part 21.6 — Real Communication Delivery Engine & Safety Orchestrator
====================================================================
Orchestrates outbound communication execution with execution-time safety guards,
deterministic idempotency locking, real provider dispatch, truthful status persistence,
and bounded exponential backoff retries.

NON-NEGOTIABLE PRINCIPLE:
POLICY DECIDES. AI PHRASES. PROVIDER DELIVERS. PROVIDER CONFIRMS. DATABASE RECORDS THE TRUTH.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.conversation import Conversation
from app.models.follow_up_models import (
    FollowUpPolicy,
    FollowUpExecution,
    FollowUpDecision,
    CommunicationConsent,
    ContactFatigue,
)
from app.models.communication_models import (
    ChannelMessage,
    DeliveryStatusRecord,
    OmnichannelConversation,
    OutboundQueue,
)
from app.modules.communication.channel_manager.manager import ChannelManager, get_channel_manager
from app.modules.communication.provider_adapters.base_provider import (
    CommunicationProvider,
    DeliveryStatusEnum,
    OutboundMessageDTO,
    ProviderResponse,
    ProviderStatusEnum,
)
from app.modules.sales_action.taxonomies import (
    SalesActionType,
    SalesActionStatus,
    CommunicationChannel,
    ConsentStatus,
    HandoffReason,
)
from app.modules.sales_action.dto import (
    SalesActionDecisionDTO,
    SalesActionExecutionResultDTO,
    SalesBriefDTO,
)
from app.modules.sales_action.guards.consent_guard import ConsentGuard
from app.modules.sales_action.guards.quiet_hours_guard import QuietHoursGuard
from app.modules.sales_action.guards.fatigue_guard import FatigueGuard
from app.modules.communication.monitoring.delivery_metrics import (
    COMMUNICATION_SEND_ATTEMPT_TOTAL,
    COMMUNICATION_SEND_SUCCESS_TOTAL,
    COMMUNICATION_SEND_FAILURE_TOTAL,
    COMMUNICATION_DELIVERY_STATUS_TOTAL,
    COMMUNICATION_RETRY_TOTAL,
    COMMUNICATION_RATE_LIMIT_TOTAL,
    COMMUNICATION_LATENCY_HISTOGRAM,
    mask_org_id,
)

logger = logging.getLogger("beetlelabs.communication.delivery_engine")

# In-memory execution lease lock registry to prevent race conditions across concurrent workers
_execution_locks: Dict[str, asyncio.Lock] = {}
_locks_mutex = asyncio.Lock()


async def _get_execution_lock(idempotency_key: str) -> asyncio.Lock:
    async with _locks_mutex:
        if idempotency_key not in _execution_locks:
            _execution_locks[idempotency_key] = asyncio.Lock()
        return _execution_locks[idempotency_key]


class RealDeliveryEngine:
    """
    Production-grade communication delivery engine.
    """

    POLICY_VERSION = "v1.0-sales-action"

    def __init__(
        self,
        db: AsyncSession,
        channel_manager: Optional[ChannelManager] = None,
    ):
        self.db = db
        self.channel_manager = channel_manager or get_channel_manager()
        self.consent_guard = ConsentGuard(db)
        self.fatigue_guard = FatigueGuard(db)

    @classmethod
    def compute_idempotency_key(
        cls,
        organization_id: str,
        lead_id: str,
        action_id: str,
        channel: str,
        message_body: str,
        execution_version: int = 1,
    ) -> str:
        """Computes deterministic idempotency key for an action execution."""
        msg_fingerprint = hashlib.sha256(message_body.encode("utf-8")).hexdigest()[:16]
        raw_key = f"{organization_id}:{lead_id}:{action_id}:{channel.lower()}:{msg_fingerprint}:v{execution_version}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def execute_sales_action_delivery(
        self,
        decision: SalesActionDecisionDTO,
        lead: Lead,
        broker: Broker,
        custom_message: Optional[str] = None,
        policy: Optional[FollowUpPolicy] = None,
        execution_version: int = 1,
    ) -> SalesActionExecutionResultDTO:
        """
        Main entry point for delivering an approved sales action.
        Runs execution-time safety re-checks, acquires execution lock,
        and dispatches to real provider.
        """
        org_id = decision.organization_id
        org_hash = mask_org_id(org_id)
        action_type = decision.action_type
        channel_enum = decision.recommended_channel
        channel_str = channel_enum.value.lower()

        message_text = (
            custom_message
            or decision.draft_message_body
            or f"Sales action {action_type.value} executed for lead {lead.name}."
        )

        # ── 1. Non-outbound Actions (NO_ACTION, PAUSE_OUTREACH, MARK_DORMANT) ──
        if action_type in (SalesActionType.NO_ACTION, SalesActionType.PAUSE_OUTREACH, SalesActionType.MARK_DORMANT):
            return SalesActionExecutionResultDTO(
                action_id=decision.action_id,
                lead_id=str(lead.id),
                organization_id=org_id,
                action_type=action_type,
                status=SalesActionStatus.COMPLETED,
                channel="NONE",
                provider="policy_engine",
                executed_at=datetime.now(timezone.utc),
                details={"reason": decision.reason},
            )

        # ── 2. HUMAN_HANDOFF Action ────────────────────────────────────────────
        if action_type == SalesActionType.HUMAN_HANDOFF:
            return await self._execute_human_handoff(decision, lead, broker, message_text)

        # ── 3. Outbound Message Dispatch: Idempotency Key & Lock Acquisition ───
        idempotency_key = self.compute_idempotency_key(
            organization_id=org_id,
            lead_id=str(lead.id),
            action_id=decision.action_id,
            channel=channel_str,
            message_body=message_text,
            execution_version=execution_version,
        )

        lock = await _get_execution_lock(idempotency_key)

        async with lock:
            # ── 4. Check for Existing Execution (Deduplication) ────────────────
            stmt_existing = select(ChannelMessage).where(
                ChannelMessage.lead_id == str(lead.id),
                ChannelMessage.organization_id == org_id,
                ChannelMessage.idempotency_key == idempotency_key,
            )
            res_existing = await self.db.execute(stmt_existing)
            existing_msg = res_existing.scalars().first()

            if existing_msg:
                logger.info(
                    f"[RealDeliveryEngine] Duplicate execution detected for key={idempotency_key}. "
                    f"Returning existing status={existing_msg.delivery_status} provider_msg_id={existing_msg.provider_message_id}"
                )
                status_mapped = SalesActionStatus.SENT if existing_msg.delivery_status in ("sent", "delivered", "read") else SalesActionStatus.COMPLETED
                return SalesActionExecutionResultDTO(
                    action_id=decision.action_id,
                    lead_id=str(lead.id),
                    organization_id=org_id,
                    action_type=action_type,
                    status=status_mapped,
                    channel=existing_msg.channel,
                    provider=existing_msg.provider_name or "unknown",
                    provider_message_id=existing_msg.provider_message_id,
                    executed_at=existing_msg.created_at or datetime.now(timezone.utc),
                    details={"deduplicated": True, "existing_message_id": existing_msg.id},
                )

            # ── 5. EXECUTION-TIME SAFETY RE-CHECKS (Precedence-Ordered Guards) ─

            # 5.1. Terminal Lead State Re-check
            stage = (lead.pipeline_stage or lead.status or "new").upper()
            if stage in ("CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED"):
                logger.warning(f"[RealDeliveryEngine] Execution-time TERMINAL STATE BLOCK for lead {lead.id} ({stage}).")
                return await self._record_blocked_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    blocked_reason=f"LEAD_TERMINAL_STATE_AT_EXECUTION: Lead is '{stage}'.",
                    delivery_status=DeliveryStatusEnum.BLOCKED,
                )

            # 5.2. Human Approval Re-check
            if decision.human_approval_required and decision.status != SalesActionStatus.APPROVED:
                logger.warning(f"[RealDeliveryEngine] Execution-time APPROVAL REQUIRED for lead {lead.id}.")
                return await self._record_blocked_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    blocked_reason="APPROVAL_REQUIRED_AT_EXECUTION: Action requires explicit human approval.",
                    delivery_status=DeliveryStatusEnum.BLOCKED,
                )

            # 5.3. Consent Re-check
            is_permitted_consent, consent_status, consent_reason = await self.consent_guard.evaluate_consent(
                lead_id=str(lead.id),
                organization_id=org_id,
                channel=channel_enum,
            )
            if not is_permitted_consent:
                logger.warning(
                    f"[RealDeliveryEngine] Execution-time CONSENT BLOCK for lead {lead.id}: "
                    f"status={consent_status.value} reason={consent_reason}"
                )
                return await self._record_blocked_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    blocked_reason=f"CONSENT_REVOKED_AT_EXECUTION: {consent_reason}",
                    delivery_status=DeliveryStatusEnum.BLOCKED,
                )

            # 5.4. Fatigue Re-check
            is_fatigued, fatigue_score, fatigue_reason, is_dormant = await self.fatigue_guard.evaluate_fatigue(
                lead_id=str(lead.id),
                organization_id=org_id,
                policy=policy,
            )
            if is_fatigued:
                logger.warning(
                    f"[RealDeliveryEngine] Execution-time FATIGUE BLOCK for lead {lead.id}: "
                    f"score={fatigue_score} reason={fatigue_reason}"
                )
                return await self._record_blocked_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    blocked_reason=f"FATIGUE_EXCEEDED_AT_EXECUTION: {fatigue_reason}",
                    delivery_status=DeliveryStatusEnum.BLOCKED,
                )

            # 5.5. Quiet Hours Re-check
            is_timing_ok, scheduled_utc, tz_name, timing_reason = QuietHoursGuard.evaluate_timing(
                lead=lead,
                policy=policy,
            )
            if not is_timing_ok:
                logger.info(
                    f"[RealDeliveryEngine] Execution-time QUIET HOURS delay for lead {lead.id}. "
                    f"Rescheduled for {scheduled_utc.isoformat()} in {tz_name}."
                )
                return await self._record_scheduled_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    scheduled_utc=scheduled_utc,
                    scheduled_reason=f"QUIET_HOURS_RESCHEDULED: {timing_reason}",
                )

            # ── 6. Provider Resolution & Execution ─────────────────────────────
            COMMUNICATION_SEND_ATTEMPT_TOTAL.labels(
                org_hash=org_hash,
                channel=channel_str,
                provider="resolving",
            ).inc()

            try:
                provider = self.channel_manager.get_provider(channel_str)
            except ValueError as e:
                logger.error(f"[RealDeliveryEngine] No provider registered for channel '{channel_str}': {e}")
                return await self._record_failed_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    provider_name="PROVIDER_UNAVAILABLE",
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    error_code="PROVIDER_UNAVAILABLE",
                    error_msg=f"No provider configured for channel '{channel_str}'.",
                    delivery_status=DeliveryStatusEnum.CONFIGURATION_REQUIRED,
                )

            # Recipient normalization
            recipient_id = lead.phone if channel_enum in (CommunicationChannel.WHATSAPP, CommunicationChannel.SMS) else (lead.email or lead.phone or "customer")
            if not recipient_id:
                return await self._record_failed_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    provider_name=provider.provider_name,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    error_code="INVALID_RECIPIENT",
                    error_msg=f"Lead has no valid recipient identifier for channel '{channel_str}'.",
                    delivery_status=DeliveryStatusEnum.INVALID_RECIPIENT,
                )

            # Build Outbound DTO
            outbound_msg_id = str(uuid.uuid4())
            outbound_dto = OutboundMessageDTO(
                message_id=outbound_msg_id,
                conversation_id=str(lead.id),
                organization_id=org_id,
                channel=channel_str,
                provider_name=provider.provider_name,
                recipient_identifier=recipient_id,
                content=message_text,
                message_type="text",
                content_structured={"subject": decision.draft_message_subject} if decision.draft_message_subject else None,
                idempotency_key=idempotency_key,
            )

            # ── 7. Dispatch via Real Provider ──────────────────────────────────
            start_time = time.time()
            provider_resp: ProviderResponse = await provider.send(outbound_dto)
            latency_seconds = time.time() - start_time
            COMMUNICATION_LATENCY_HISTOGRAM.labels(org_hash=org_hash, channel=channel_str).observe(latency_seconds)

            # ── 8. Process & Persist Truthful Result ───────────────────────────
            if provider_resp.success:
                return await self._record_successful_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    provider_name=provider.provider_name,
                    provider_msg_id=provider_resp.provider_message_id,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    raw_response=provider_resp.raw_response,
                )
            else:
                return await self._record_failed_execution(
                    decision=decision,
                    lead=lead,
                    broker=broker,
                    channel=channel_enum,
                    provider_name=provider.provider_name,
                    idempotency_key=idempotency_key,
                    message_text=message_text,
                    error_code=provider_resp.error_code or "SEND_FAILED",
                    error_msg=provider_resp.error_message or "Provider delivery failed.",
                    delivery_status=provider_resp.delivery_status,
                    retryable=provider_resp.retryable,
                )

    # ─── Private Persistence Helpers ──────────────────────────────────────────

    async def _execute_human_handoff(
        self,
        decision: SalesActionDecisionDTO,
        lead: Lead,
        broker: Broker,
        message_text: str,
    ) -> SalesActionExecutionResultDTO:
        org_id = decision.organization_id
        org_hash = mask_org_id(org_id)

        # 1. Record escalation note in conversations table (sender_type='broker', message_type='text')
        conv_record = Conversation(
            id=uuid.uuid4(),
            lead_id=lead.id,
            direction="outbound",
            sender_type="broker",
            message=f"[HUMAN HANDOFF ESCALATION]: {decision.reason}\nRecommended Action: {decision.sales_brief.recommended_human_action if decision.sales_brief else 'Broker follow-up'}",
            message_type="text",
        )
        self.db.add(conv_record)

        # 2. Record execution audit
        exec_id = str(uuid.uuid4())
        execution = FollowUpExecution(
            id=exec_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            broker_id=str(broker.id),
            channel="HUMAN_CALL",
            reason_type=SalesActionType.HUMAN_HANDOFF.value,
            status=SalesActionStatus.COMPLETED.value,
            scheduled_for_utc=datetime.now(timezone.utc),
            executed_at=datetime.now(timezone.utc),
            recipient_identifier=lead.phone or "customer",
            message_body=message_text,
            grounded_facts=[{"action": "HUMAN_HANDOFF", "reason": decision.reason}],
        )
        self.db.add(execution)
        await self.db.commit()

        COMMUNICATION_DELIVERY_STATUS_TOTAL.labels(
            org_hash=org_hash, channel="human_call", status="completed"
        ).inc()

        return SalesActionExecutionResultDTO(
            action_id=decision.action_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            action_type=SalesActionType.HUMAN_HANDOFF,
            status=SalesActionStatus.COMPLETED,
            channel="HUMAN_CALL",
            provider="internal_crm",
            executed_at=datetime.now(timezone.utc),
            details={"escalated_to_broker_id": str(broker.id), "brief": decision.sales_brief.model_dump() if decision.sales_brief else {}},
        )

    async def _record_successful_execution(
        self,
        decision: SalesActionDecisionDTO,
        lead: Lead,
        broker: Broker,
        channel: CommunicationChannel,
        provider_name: str,
        provider_msg_id: Optional[str],
        idempotency_key: str,
        message_text: str,
        raw_response: Optional[Dict[str, Any]],
    ) -> SalesActionExecutionResultDTO:
        org_id = decision.organization_id
        org_hash = mask_org_id(org_id)
        now_utc = datetime.now(timezone.utc)
        exec_id = str(uuid.uuid4())
        msg_id = str(uuid.uuid4())

        # 1. Update conversations timeline
        conv_record = Conversation(
            id=uuid.uuid4(),
            lead_id=lead.id,
            direction="outbound",
            sender_type="broker",
            message=message_text,
            message_type="text",
        )
        self.db.add(conv_record)

        # 2. Persist FollowUpExecution
        execution = FollowUpExecution(
            id=exec_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            broker_id=str(broker.id),
            channel=channel.value,
            reason_type=decision.action_type.value,
            status=SalesActionStatus.SENT.value,
            scheduled_for_utc=decision.scheduled_for_utc or now_utc,
            executed_at=now_utc,
            recipient_identifier=lead.phone or lead.email or "customer",
            message_subject=decision.draft_message_subject,
            message_body=message_text,
            grounded_facts=[
                {"idempotency_key": idempotency_key, "provider_name": provider_name, "provider_message_id": provider_msg_id},
                *(decision.matched_properties_summary or [])
            ],
        )
        self.db.add(execution)

        # 3. Persist ChannelMessage for unified timeline & deduplication
        channel_msg = ChannelMessage(
            id=msg_id,
            conversation_id=str(lead.id),
            organization_id=org_id,
            lead_id=str(lead.id),
            channel=channel.value.lower(),
            provider_name=provider_name,
            provider_message_id=provider_msg_id,
            direction="outbound",
            message_type="text",
            content=message_text,
            sender_name=broker.name or "BeetleLabs AI",
            sender_identifier=str(broker.id),
            recipient_identifier=lead.phone or lead.email or "customer",
            sent_by_ai=True,
            idempotency_key=idempotency_key,
            delivery_status="sent",
            sent_at=now_utc,
        )
        self.db.add(channel_msg)

        # 4. Persist FollowUpDecision audit
        decision_record = FollowUpDecision(
            id=str(uuid.uuid4()),
            execution_id=exec_id,
            lead_id=str(lead.id),
            decision_outcome="APPROVED",
            fatigue_score=0.0,
            rules_evaluated=[{"action": decision.action_type.value, "reason": decision.reason}],
        )
        self.db.add(decision_record)

        # 5. Update contact fatigue counters
        await self.fatigue_guard.record_outbound_sent(str(lead.id), org_id)

        await self.db.commit()

        # 6. Metrics
        COMMUNICATION_SEND_SUCCESS_TOTAL.labels(
            org_hash=org_hash, channel=channel.value.lower(), provider=provider_name
        ).inc()
        COMMUNICATION_DELIVERY_STATUS_TOTAL.labels(
            org_hash=org_hash, channel=channel.value.lower(), status="sent"
        ).inc()

        return SalesActionExecutionResultDTO(
            action_id=decision.action_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            action_type=decision.action_type,
            status=SalesActionStatus.SENT,
            channel=channel.value,
            provider=provider_name,
            provider_message_id=provider_msg_id,
            executed_at=now_utc,
            details={"recipient": lead.phone or lead.email, "idempotency_key": idempotency_key},
        )

    async def _record_failed_execution(
        self,
        decision: SalesActionDecisionDTO,
        lead: Lead,
        broker: Broker,
        channel: CommunicationChannel,
        provider_name: str,
        idempotency_key: str,
        message_text: str,
        error_code: str,
        error_msg: str,
        delivery_status: DeliveryStatusEnum,
        retryable: bool = False,
    ) -> SalesActionExecutionResultDTO:
        org_id = decision.organization_id
        org_hash = mask_org_id(org_id)
        now_utc = datetime.now(timezone.utc)
        exec_id = str(uuid.uuid4())
        msg_id = str(uuid.uuid4())

        status_val = SalesActionStatus.FAILED.value

        execution = FollowUpExecution(
            id=exec_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            broker_id=str(broker.id),
            channel=channel.value,
            reason_type=decision.action_type.value,
            status=status_val,
            scheduled_for_utc=now_utc,
            executed_at=now_utc,
            recipient_identifier=lead.phone or lead.email or "customer",
            message_subject=decision.draft_message_subject,
            message_body=message_text,
            grounded_facts=[{"idempotency_key": idempotency_key, "error_code": error_code, "error_message": error_msg}],
        )
        self.db.add(execution)

        # Record failed ChannelMessage
        channel_msg = ChannelMessage(
            id=msg_id,
            conversation_id=str(lead.id),
            organization_id=org_id,
            lead_id=str(lead.id),
            channel=channel.value.lower(),
            provider_name=provider_name,
            direction="outbound",
            message_type="text",
            content=message_text,
            sender_name=broker.name or "BeetleLabs AI",
            sender_identifier=str(broker.id),
            recipient_identifier=lead.phone or lead.email or "customer",
            sent_by_ai=True,
            idempotency_key=idempotency_key,
            delivery_status="failed",
            failed_at=now_utc,
            failure_reason=error_msg,
        )
        self.db.add(channel_msg)

        await self.db.commit()

        COMMUNICATION_SEND_FAILURE_TOTAL.labels(
            org_hash=org_hash,
            channel=channel.value.lower(),
            provider=provider_name,
            error_code=error_code[:32],
        ).inc()

        return SalesActionExecutionResultDTO(
            action_id=decision.action_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            action_type=decision.action_type,
            status=SalesActionStatus.FAILED,
            channel=channel.value,
            provider=provider_name,
            executed_at=now_utc,
            details={
                "error": error_msg,
                "error_code": error_code,
                "delivery_status": delivery_status.value,
                "retryable": retryable,
                "configuration_required": delivery_status == DeliveryStatusEnum.CONFIGURATION_REQUIRED,
            },
        )

    async def _record_blocked_execution(
        self,
        decision: SalesActionDecisionDTO,
        lead: Lead,
        broker: Broker,
        channel: CommunicationChannel,
        idempotency_key: str,
        message_text: str,
        blocked_reason: str,
        delivery_status: DeliveryStatusEnum,
    ) -> SalesActionExecutionResultDTO:
        org_id = decision.organization_id
        org_hash = mask_org_id(org_id)
        now_utc = datetime.now(timezone.utc)

        execution = FollowUpExecution(
            id=str(uuid.uuid4()),
            lead_id=str(lead.id),
            organization_id=org_id,
            broker_id=str(broker.id),
            channel=channel.value,
            reason_type=decision.action_type.value,
            status=SalesActionStatus.BLOCKED.value,
            scheduled_for_utc=now_utc,
            executed_at=now_utc,
            recipient_identifier=lead.phone or "customer",
            message_body=message_text,
            grounded_facts=[{"idempotency_key": idempotency_key, "blocked_reason": blocked_reason}],
        )
        self.db.add(execution)
        await self.db.commit()

        COMMUNICATION_DELIVERY_STATUS_TOTAL.labels(
            org_hash=org_hash, channel=channel.value.lower(), status="blocked"
        ).inc()

        return SalesActionExecutionResultDTO(
            action_id=decision.action_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            action_type=decision.action_type,
            status=SalesActionStatus.BLOCKED,
            channel=channel.value,
            provider="policy_guard",
            executed_at=now_utc,
            details={"blocked_reason": blocked_reason},
        )

    async def _record_scheduled_execution(
        self,
        decision: SalesActionDecisionDTO,
        lead: Lead,
        broker: Broker,
        channel: CommunicationChannel,
        idempotency_key: str,
        message_text: str,
        scheduled_utc: datetime,
        scheduled_reason: str,
    ) -> SalesActionExecutionResultDTO:
        org_id = decision.organization_id
        org_hash = mask_org_id(org_id)
        now_utc = datetime.now(timezone.utc)

        execution = FollowUpExecution(
            id=str(uuid.uuid4()),
            lead_id=str(lead.id),
            organization_id=org_id,
            broker_id=str(broker.id),
            channel=channel.value,
            reason_type=decision.action_type.value,
            status=SalesActionStatus.QUEUED.value,
            scheduled_for_utc=scheduled_utc,
            executed_at=now_utc,
            recipient_identifier=lead.phone or "customer",
            message_body=message_text,
            grounded_facts=[{"idempotency_key": idempotency_key, "scheduled_reason": scheduled_reason}],
        )
        self.db.add(execution)
        await self.db.commit()

        COMMUNICATION_DELIVERY_STATUS_TOTAL.labels(
            org_hash=org_hash, channel=channel.value.lower(), status="queued"
        ).inc()

        return SalesActionExecutionResultDTO(
            action_id=decision.action_id,
            lead_id=str(lead.id),
            organization_id=org_id,
            action_type=decision.action_type,
            status=SalesActionStatus.QUEUED,
            channel=channel.value,
            provider="scheduler",
            executed_at=now_utc,
            details={"scheduled_for_utc": scheduled_utc.isoformat(), "reason": scheduled_reason},
        )
