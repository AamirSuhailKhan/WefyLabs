"""
Part 21.8 — Autonomous Sales Loop Orchestrator
===============================================
Central domain orchestrator connecting Parts 21.1–21.7 into a reliable,
event-driven autonomous sales loop.

ARCHITECTURE:
  Event arrives → Idempotency check → Tenant validation → Lead validation
  → State machine check → Intelligence run (21.4, 21.3, 21.7) → NBA (21.5)
  → Guard chain (21.5 guards) → Automation policy → Execute (21.6) → Audit

INVARIANTS:
  1. Never fabricates data. Every field comes from verified DB state.
  2. Fail closed. If required data is unavailable → UNKNOWN / NO_ACTION / HUMAN_REVIEW.
  3. LLMs NEVER make policy decisions. Only phrase messages.
  4. Every action is auditable and explainable.
  5. Tenant isolation is enforced at every layer.
  6. Prompt injection defense: customer message text never becomes instruction.
  7. Idempotency enforced at DB level via unique idempotency_key.
  8. Loop protection prevents runaway automation.
"""
from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.broker import Broker
from app.modules.autonomous_loop.dto import (
    SalesLoopEventDTO,
    OrchestratorResultDTO,
    IntelligenceSummaryDTO,
    GuardChainResultDTO,
)
from app.modules.autonomous_loop.taxonomies import (
    SalesLoopEventType,
    EventProcessingState,
    AutomationPermission,
    FailureClass,
    LeadLifecycleState,
    ActorType,
)
from app.modules.autonomous_loop.event_store import SalesLoopEventStore
from app.modules.autonomous_loop.state_machine import LeadStateMachine, TERMINAL_STATES
from app.modules.autonomous_loop.guard_chain import OrchestratorGuardChain
from app.modules.autonomous_loop.automation_policy import AutonomyPolicyEngine
from app.modules.autonomous_loop.loop_protection import LoopProtectionService
from app.modules.autonomous_loop.audit_service import SalesLoopAuditService
from app.modules.autonomous_loop.dead_letter_service import DeadLetterService
from app.modules.autonomous_loop.metrics import (
    LOOP_EVENTS_TOTAL,
    LOOP_EVENTS_PROCESSED,
    LOOP_EVENTS_FAILED,
    LOOP_GUARD_BLOCKS,
    LOOP_ACTIONS_DISPATCHED,
    LOOP_DEAD_LETTERS,
    LOOP_DUPLICATE_EVENTS,
    LOOP_PROCESSING_LATENCY,
    mask_org_id,
)

logger = logging.getLogger(__name__)

ORCHESTRATOR_POLICY_VERSION = "v1.0-autonomous-loop"


class AutonomousSalesLoopService:
    """
    Central orchestrator for the AI Autonomous Sales Loop.

    Connects:
      - Part 21.1: Lead acquisition events
      - Part 21.2/21.2A: Prospect intelligence
      - Part 21.3: Property recommendations
      - Part 21.4: Qualification engine (facts, policy, snapshot)
      - Part 21.5: NBA policy engine + guards
      - Part 21.6: Real communication delivery engine
      - Part 21.7: Conversation intelligence (inbound message analysis)

    Does NOT duplicate any business logic from the above parts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_store = SalesLoopEventStore(db)
        self.state_machine = LeadStateMachine(db)
        self.guard_chain = OrchestratorGuardChain(db)
        self.loop_protection = LoopProtectionService(db)
        self.audit_service = SalesLoopAuditService(db)
        self.dead_letter_service = DeadLetterService(db)

    async def process_event(
        self,
        event_dto: SalesLoopEventDTO,
    ) -> OrchestratorResultDTO:
        """
        Main orchestration entry point.
        Processes one event through the full autonomous sales loop pipeline.
        """
        start_time = time.perf_counter()
        org_hash = mask_org_id(event_dto.tenant_id)
        LOOP_EVENTS_TOTAL.labels(
            event_type=event_dto.event_type.value,
            org=org_hash,
        ).inc()

        # ── Step 1: Idempotency enforcement ────────────────────────────────────
        event_record, is_new = await self.event_store.ingest_event(event_dto)

        if not is_new:
            LOOP_DUPLICATE_EVENTS.labels(org=org_hash).inc()
            return OrchestratorResultDTO(
                event_id=event_dto.event_id,
                lead_id=event_dto.lead_id,
                tenant_id=event_dto.tenant_id,
                correlation_id=event_dto.correlation_id,
                causation_id=event_dto.causation_id,
                processing_state=EventProcessingState.COMPLETED,
                failure_class=FailureClass.DUPLICATE_EVENT,
                decision_reason="Duplicate event suppressed via idempotency_key.",
            )

        # ── Step 2: Mark PROCESSING ─────────────────────────────────────────────
        await self.event_store.mark_processing(event_record.id)

        result = OrchestratorResultDTO(
            event_id=event_record.id,
            lead_id=event_dto.lead_id,
            tenant_id=event_dto.tenant_id,
            correlation_id=event_dto.correlation_id,
            causation_id=event_dto.causation_id,
        )

        try:
            result = await self._run_pipeline(event_dto, event_record.id, result)
            await self.event_store.mark_completed(event_record.id)
            LOOP_EVENTS_PROCESSED.labels(
                event_type=event_dto.event_type.value,
                org=org_hash,
            ).inc()

        except Exception as exc:
            LOOP_EVENTS_FAILED.labels(
                event_type=event_dto.event_type.value,
                org=org_hash,
            ).inc()
            failure_class, safe_msg = self._classify_exception(exc)
            result.processing_state = EventProcessingState.FAILED
            result.failure_class = failure_class
            result.safe_error_message = safe_msg
            result.decision_reason = f"Orchestration error: {safe_msg}"

            retry_count = event_record.retry_count + 1
            await self.event_store.mark_failed(
                event_id=event_record.id,
                failure_class=failure_class.value,
                error_message=safe_msg,
                retry_count=retry_count,
                max_retries=event_record.max_retries,
            )

            if retry_count >= event_record.max_retries:
                LOOP_DEAD_LETTERS.labels(org=org_hash).inc()
                await self.dead_letter_service.admit(
                    event=event_record,
                    failure_class=failure_class,
                    safe_error_message=safe_msg,
                )

            logger.error(
                f"[ORCHESTRATOR] Event failed: id={event_record.id} "
                f"type={event_dto.event_type.value} lead={event_dto.lead_id} "
                f"class={failure_class.value} msg={safe_msg}"
            )

        finally:
            elapsed = time.perf_counter() - start_time
            LOOP_PROCESSING_LATENCY.labels(
                event_type=event_dto.event_type.value,
                org=org_hash,
            ).observe(elapsed)

        # Always record audit entry
        try:
            await self.audit_service.record(
                result=result,
                event_type=event_dto.event_type.value,
                policy_version=ORCHESTRATOR_POLICY_VERSION,
            )
        except Exception as audit_exc:
            logger.error(f"[ORCHESTRATOR] Audit recording failed: {audit_exc}")

        return result

    async def _run_pipeline(
        self,
        event_dto: SalesLoopEventDTO,
        event_id: str,
        result: OrchestratorResultDTO,
    ) -> OrchestratorResultDTO:
        """
        Inner pipeline: lead loading → intelligence → NBA → guards → execute.
        """
        # Early exit for events with no lead_id
        if not event_dto.lead_id:
            result.processing_state = EventProcessingState.COMPLETED
            result.decision_reason = f"Event type {event_dto.event_type.value} processed (no lead context)."
            return result

        # ── Step 3: Load Lead + Tenant validation ──────────────────────────────
        lead = await self._load_and_validate_lead(event_dto.lead_id, event_dto.tenant_id)
        if not lead:
            result.processing_state = EventProcessingState.FAILED
            result.failure_class = FailureClass.VALIDATION_ERROR
            result.decision_reason = f"Lead {event_dto.lead_id} not found or tenant mismatch."
            return result

        # ── Step 4: Load automation state + loop protection depth inc ──────────
        automation_state = await self.state_machine.get_or_create_automation_state(
            event_dto.lead_id, event_dto.tenant_id
        )
        await self.loop_protection.increment_depth(automation_state)

        try:
            current_lc = LeadLifecycleState(automation_state.current_lifecycle_state)
        except ValueError:
            current_lc = LeadLifecycleState.NEW

        result.lifecycle_state_before = current_lc

        # ── Step 5: Terminal state check ──────────────────────────────────────
        if current_lc in TERMINAL_STATES:
            result.processing_state = EventProcessingState.COMPLETED
            result.decision_reason = (
                f"Lead is in terminal state '{current_lc.value}'. No autonomous action taken."
            )
            await self.loop_protection.record_failure(automation_state)
            return result

        # ── Step 6: Paused/broker-takeover check ──────────────────────────────
        if automation_state.is_paused or automation_state.is_broker_takeover:
            result.processing_state = EventProcessingState.COMPLETED
            result.decision_reason = (
                f"Automation paused or broker takeover in effect. Event recorded, no action dispatched."
            )
            return result

        # ── Step 7: Route event to domain handler ─────────────────────────────
        if event_dto.event_type in INTELLIGENCE_REQUIRED_EVENTS:
            result = await self._run_intelligence_and_action(
                event_dto, lead, automation_state, result
            )
        else:
            result = await self._handle_lifecycle_event(event_dto, lead, automation_state, result)

        return result

    async def _run_intelligence_and_action(
        self,
        event_dto: SalesLoopEventDTO,
        lead: Lead,
        automation_state,
        result: OrchestratorResultDTO,
    ) -> OrchestratorResultDTO:
        """
        Runs full intelligence → NBA → guard → execute pipeline.
        Delegates to existing Part 21.4, 21.3, 21.5, and 21.6 services.
        """
        org_id = event_dto.tenant_id

        # ── Step 7a: Load follow-up policy ────────────────────────────────────
        from app.modules.sales_action.service import SalesActionDomainService
        sales_svc = SalesActionDomainService(self.db)
        policy = await sales_svc.get_or_create_policy(org_id)

        # ── Step 7b: Get qualification snapshot (Part 21.4) ───────────────────
        intelligence = IntelligenceSummaryDTO()
        try:
            from app.modules.lead_qualification.service import LeadQualificationDomainService
            qual_svc = LeadQualificationDomainService(self.db)
            qual_snapshot = await qual_svc.get_lead_qualification_snapshot(org_id, event_dto.lead_id)
            intelligence.qualification_state = qual_snapshot.state or "UNKNOWN"
            intelligence.qualification_completeness = qual_snapshot.completeness_score or 0.0
            intelligence.qualification_confidence = qual_snapshot.confidence_score or 0.0
        except Exception as ex:
            logger.debug(f"[ORCHESTRATOR] Qualification snapshot info: {ex}")

        # ── Step 7c: Get property recommendations count (Part 21.3) ──────────
        try:
            from app.modules.property_recommendation.service import PropertyRecommendationService
            from app.modules.property_recommendation.dto import PropertyRecommendationRequestDTO
            rec_svc = PropertyRecommendationService(self.db)
            rec_res = await rec_svc.generate_recommendations(
                dto=PropertyRecommendationRequestDTO(lead_id=event_dto.lead_id, limit=5),
                organization_id=org_id,
            )
            if rec_res and rec_res.items:
                intelligence.matched_properties_count = len(rec_res.items)
        except Exception as ex:
            logger.debug(f"[ORCHESTRATOR] Property recommendation info: {ex}")

        result.intelligence = intelligence

        # ── Step 7d: Extract customer message from payload if present ─────────
        latest_customer_message: Optional[str] = None
        if event_dto.event_type in (
            SalesLoopEventType.CUSTOMER_MESSAGE_RECEIVED,
            SalesLoopEventType.CUSTOMER_MESSAGE_ANALYZED,
        ):
            # Safety: truncate customer message to prevent prompt injection widening
            raw_msg = event_dto.payload.get("message_text", "")
            latest_customer_message = raw_msg[:500] if raw_msg else None

        # ── Step 7e: Evaluate Next Best Action (Part 21.5) ────────────────────
        try:
            decision = await sales_svc.evaluate_next_sales_action(
                lead_id=event_dto.lead_id,
                organization_id=org_id,
            )
        except Exception as ex:
            logger.error(f"[ORCHESTRATOR] NBA evaluation failed: {ex}")
            result.processing_state = EventProcessingState.FAILED
            result.failure_class = FailureClass.DATA_UNAVAILABLE
            result.decision_reason = f"NBA evaluation failed: {ex}"
            await self.loop_protection.record_failure(automation_state)
            return result

        result.action_type = decision.action_type.value

        # ── Step 7f: Check high-value threshold ───────────────────────────────
        try:
            budget_max = float(event_dto.payload.get("budget_max", 0) or 0)
        except (TypeError, ValueError):
            budget_max = 0.0
        is_high_value = (
            policy.require_approval_high_value
            and budget_max >= (policy.high_value_threshold_aed or 5_000_000.0)
        )

        # ── Step 7g: Evaluate automation permission ───────────────────────────
        automation_permission = AutonomyPolicyEngine.evaluate(
            action_type=decision.action_type,
            policy=policy,
            is_high_value=is_high_value,
        )
        result.automation_permission = automation_permission

        # ── Step 7h: Run guard chain (wraps Part 21.5 guards) ────────────────
        from app.modules.sales_action.taxonomies import CommunicationChannel
        guard_result = await self.guard_chain.evaluate(
            lead=lead,
            automation_state=automation_state,
            action_type=decision.action_type,
            automation_permission=automation_permission,
            policy=policy,
            latest_customer_message=latest_customer_message,
            channel=decision.recommended_channel,
            organization_id=org_id,
        )
        result.guard_chain = guard_result

        # ── Step 7i: Human approval required → record and stop ───────────────
        if guard_result.human_approval_required and not guard_result.overall_passed:
            org_hash = mask_org_id(org_id)
            LOOP_GUARD_BLOCKS.labels(
                guard_name="HUMAN_APPROVAL",
                org=org_hash,
            ).inc()
            # Flush pending action state
            automation_state.pending_action_id = decision.action_id
            automation_state.pending_action_type = decision.action_type.value
            automation_state.pending_since = datetime.now(timezone.utc)
            automation_state.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

            result.processing_state = EventProcessingState.COMPLETED
            result.failure_class = FailureClass.HUMAN_APPROVAL_REQUIRED
            result.decision_reason = guard_result.blocking_reason or "Human approval required."
            return result

        # ── Step 7j: Guard blocked → record suppression ───────────────────────
        if not guard_result.overall_passed:
            org_hash = mask_org_id(org_id)
            LOOP_GUARD_BLOCKS.labels(
                guard_name=guard_result.blocking_guard.value if guard_result.blocking_guard else "UNKNOWN",
                org=org_hash,
            ).inc()
            result.processing_state = EventProcessingState.COMPLETED
            result.failure_class = FailureClass.POLICY_BLOCKED
            result.decision_reason = guard_result.blocking_reason or "Action blocked by guard chain."
            await self.loop_protection.record_failure(automation_state)
            return result

        # ── Step 7k: Permission is NO_ACTION → complete ───────────────────────
        if automation_permission == AutomationPermission.NO_ACTION:
            result.processing_state = EventProcessingState.COMPLETED
            result.decision_reason = f"NBA result: NO_ACTION ({decision.reason})"
            return result

        # ── Step 7l: Execute action via Part 21.5 SalesActionExecutor (→ 21.6) ─
        try:
            broker = await self._load_broker(org_id)
            from app.modules.sales_action.action_executor import SalesActionExecutor
            from app.modules.sales_action.taxonomies import SalesActionStatus
            executor = SalesActionExecutor(self.db)
            exec_result = await executor.execute_action(
                decision=decision,
                lead=lead,
                broker=broker,
                policy=policy,
            )

            result.provider_name = exec_result.provider
            result.provider_status = exec_result.status.value if hasattr(exec_result.status, 'value') else str(exec_result.status)
            result.provider_message_id = exec_result.provider_message_id

            if exec_result.status == SalesActionStatus.BLOCKED:
                result.processing_state = EventProcessingState.COMPLETED
                result.failure_class = FailureClass.POLICY_BLOCKED
                result.decision_reason = exec_result.details.get("reason", "Action blocked by Phase 2 Governance.")
                await self.loop_protection.record_failure(automation_state)
                return result

            result.processing_state = EventProcessingState.COMPLETED
            result.decision_reason = (
                f"Action {decision.action_type.value} dispatched via {exec_result.provider}. "
                f"Provider status: {result.provider_status}."
            )

            org_hash = mask_org_id(org_id)
            LOOP_ACTIONS_DISPATCHED.labels(
                action_type=decision.action_type.value,
                provider=exec_result.provider or "UNKNOWN",
                org=org_hash,
            ).inc()

            # Update fatigue counter
            await sales_svc.fatigue_guard.record_outbound_sent(
                lead_id=event_dto.lead_id,
                organization_id=org_id,
            )
            await self.loop_protection.record_action_executed(automation_state)

        except Exception as ex:
            logger.error(f"[ORCHESTRATOR] Action execution failed: {ex}", exc_info=True)
            result.processing_state = EventProcessingState.FAILED
            result.failure_class = FailureClass.TRANSIENT_PROVIDER_ERROR
            result.decision_reason = f"Execution error (transient): provider unavailable or config missing."
            await self.loop_protection.record_failure(automation_state)

        # ── Step 7m: Advance lifecycle state based on action ─────────────────
        new_state = _ACTION_TO_LIFECYCLE_STATE.get(decision.action_type)
        if new_state:
            _, _, updated_state = await self.state_machine.request_transition(
                lead_id=event_dto.lead_id,
                tenant_id=event_dto.tenant_id,
                to_state=new_state,
                actor="ORCHESTRATOR",
                reason=f"Action executed: {decision.action_type.value}",
            )
            if updated_state:
                try:
                    result.lifecycle_state_after = LeadLifecycleState(
                        updated_state.current_lifecycle_state
                    )
                except ValueError:
                    pass

        return result

    async def _handle_lifecycle_event(
        self,
        event_dto: SalesLoopEventDTO,
        lead: Lead,
        automation_state,
        result: OrchestratorResultDTO,
    ) -> OrchestratorResultDTO:
        """Handles lifecycle-only events (no outbound action required)."""
        event_type = event_dto.event_type

        # Map event type to state transition
        target_state = _EVENT_TO_LIFECYCLE_STATE.get(event_type)
        if target_state:
            _, error, _ = await self.state_machine.request_transition(
                lead_id=event_dto.lead_id,
                tenant_id=event_dto.tenant_id,
                to_state=target_state,
                actor=event_dto.actor_type.value,
                reason=f"Event: {event_type.value}",
            )
            if error:
                result.decision_reason = f"State transition not applied: {error}"
            else:
                result.lifecycle_state_after = target_state
                result.decision_reason = f"Lifecycle state advanced to {target_state.value}."

        result.processing_state = EventProcessingState.COMPLETED
        return result

    async def _load_and_validate_lead(
        self,
        lead_id: str,
        tenant_id: str,
    ) -> Optional[Lead]:
        """Loads and validates lead with tenant isolation."""
        from sqlalchemy import select as sa_select
        stmt = sa_select(Lead).where(Lead.id == lead_id)
        res = await self.db.execute(stmt)
        lead = res.scalars().first()

        if not lead:
            logger.warning(f"[ORCHESTRATOR] Lead not found: {lead_id}")
            return None

        # Tenant isolation check: broker_id must match tenant_id
        if str(lead.broker_id) != str(tenant_id):
            # Also allow if organization_id field matches (multi-tenant support)
            org_id_match = False
            if hasattr(lead, "organization_id") and lead.organization_id:
                org_id_match = str(lead.organization_id) == str(tenant_id)
            if not org_id_match:
                logger.error(
                    f"[ORCHESTRATOR] TENANT SECURITY: lead={lead_id} "
                    f"belongs to broker={lead.broker_id} but event tenant={tenant_id}"
                )
                return None

        return lead

    async def _load_broker(self, broker_id: str) -> Optional[Broker]:
        """Loads broker record for execution context."""
        try:
            stmt = select(Broker).where(Broker.id == broker_id)
            res = await self.db.execute(stmt)
            return res.scalars().first()
        except Exception:
            return None

    @staticmethod
    def _classify_exception(exc: Exception) -> tuple[FailureClass, str]:
        """Classifies an exception into a FailureClass without leaking sensitive information."""
        exc_type = type(exc).__name__
        safe_msg = f"{exc_type}: {str(exc)[:500]}"

        exc_msg_lower = str(exc).lower()
        if "unique constraint" in exc_msg_lower or "duplicate" in exc_msg_lower:
            return FailureClass.DUPLICATE_EVENT, "Duplicate key violation."
        if "permission" in exc_msg_lower or "tenant" in exc_msg_lower or "403" in exc_msg_lower:
            return FailureClass.TENANT_SECURITY_ERROR, "Tenant access violation."
        if "timeout" in exc_msg_lower or "connection" in exc_msg_lower:
            return FailureClass.TRANSIENT_PROVIDER_ERROR, "Transient connectivity issue."
        if "validation" in exc_msg_lower or "value error" in exc_msg_lower.replace(" ", ""):
            return FailureClass.VALIDATION_ERROR, "Input validation error."

        return FailureClass.UNKNOWN_ERROR, safe_msg


# ── Event → Lifecycle State Mapping ───────────────────────────────────────────
# Only for events that directly advance lifecycle without NBA evaluation
_EVENT_TO_LIFECYCLE_STATE: Dict[SalesLoopEventType, LeadLifecycleState] = {
    SalesLoopEventType.VIEWING_BOOKED: LeadLifecycleState.VIEWING_SCHEDULED,
    SalesLoopEventType.VIEWING_COMPLETED: LeadLifecycleState.VIEWING_COMPLETED,
    SalesLoopEventType.VIEWING_CANCELLED: LeadLifecycleState.PROPERTY_MATCHED,
    SalesLoopEventType.LEAD_CONVERTED: LeadLifecycleState.CONVERTED,
    SalesLoopEventType.LEAD_LOST: LeadLifecycleState.LOST,
    SalesLoopEventType.LEAD_DORMANT: LeadLifecycleState.DORMANT,
    SalesLoopEventType.CONSENT_REVOKED: LeadLifecycleState.OPTED_OUT,
    SalesLoopEventType.BROKER_HANDOFF_REQUIRED: LeadLifecycleState.HUMAN_HANDOFF,
    SalesLoopEventType.NEGOTIATION_DETECTED: LeadLifecycleState.NEGOTIATION,
}

# ── Action → Lifecycle State Mapping ──────────────────────────────────────────
from app.modules.sales_action.taxonomies import SalesActionType

_ACTION_TO_LIFECYCLE_STATE: Dict[SalesActionType, LeadLifecycleState] = {
    SalesActionType.ASK_QUALIFICATION: LeadLifecycleState.QUALIFYING,
    SalesActionType.SEND_PROPERTY_RECOMMENDATIONS: LeadLifecycleState.PROPERTY_MATCHED,
    SalesActionType.OFFER_VIEWING: LeadLifecycleState.VIEWING_PENDING,
    SalesActionType.BOOK_VIEWING: LeadLifecycleState.VIEWING_SCHEDULED,
    SalesActionType.HUMAN_HANDOFF: LeadLifecycleState.HUMAN_HANDOFF,
}

# ── Events requiring full intelligence + NBA pipeline ────────────────────────
INTELLIGENCE_REQUIRED_EVENTS = {
    SalesLoopEventType.NEW_LEAD,
    SalesLoopEventType.LEAD_IMPORTED,
    SalesLoopEventType.CUSTOMER_MESSAGE_RECEIVED,
    SalesLoopEventType.CUSTOMER_MESSAGE_ANALYZED,
    SalesLoopEventType.QUALIFICATION_UPDATED,
    SalesLoopEventType.QUALIFICATION_COMPLETED,
    SalesLoopEventType.BUYING_SIGNAL_CHANGED,
    SalesLoopEventType.PROPERTY_REQUIREMENTS_CHANGED,
    SalesLoopEventType.PROPERTY_MATCHES_CHANGED,
    SalesLoopEventType.VIEWING_COMPLETED,
    SalesLoopEventType.OBJECTION_DETECTED,
}
