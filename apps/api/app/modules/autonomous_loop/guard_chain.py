"""
Part 21.8 — Orchestrator Guard Chain
=====================================
Wraps existing Part 21.5 guards (ConsentGuard, QuietHoursGuard, FatigueGuard,
HumanApprovalGuard) plus new loop-protection and lifecycle-state guards.

FAIL-CLOSED CONTRACT:
  Any guard failure → overall_passed=False → NO outbound action.
  Guards are evaluated in strict priority order (highest-risk first).
  Guard results are always recorded for audit/explainability.

Guard Order:
  1. LEAD_LIFECYCLE — Terminal/opted-out states abort immediately
  2. CONSENT       — Customer consent (Part 21.5 ConsentGuard)
  3. QUIET_HOURS   — Timezone-respecting quiet hours (Part 21.5 QuietHoursGuard)
  4. FATIGUE       — Message frequency limits (Part 21.5 FatigueGuard)
  5. LOOP_PROTECTION — Daily budget, depth, consecutive failures
  6. HUMAN_APPROVAL  — Escalation check (Part 21.5 HumanApprovalGuard)
  7. AUTOMATION_POLICY — Permission evaluation
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy
from app.modules.autonomous_loop.models import LeadAutomationState
from app.modules.autonomous_loop.dto import GuardResultDTO, GuardChainResultDTO
from app.modules.autonomous_loop.taxonomies import (
    GuardName,
    LeadLifecycleState,
    AutomationPermission,
)
from app.modules.autonomous_loop.state_machine import NO_OUTBOUND_STATES
from app.modules.autonomous_loop.loop_protection import LoopProtectionService
from app.modules.sales_action.guards.consent_guard import ConsentGuard
from app.modules.sales_action.guards.quiet_hours_guard import QuietHoursGuard
from app.modules.sales_action.guards.fatigue_guard import FatigueGuard
from app.modules.sales_action.guards.human_approval_guard import HumanApprovalGuard
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
from app.modules.sales_action.taxonomies import CommunicationChannel, SalesActionType

logger = logging.getLogger(__name__)


class OrchestratorGuardChain:
    """
    Unified guard chain for the autonomous sales loop orchestrator.
    Delegates to existing Part 21.5 guards — does NOT duplicate their logic.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.consent_guard = ConsentGuard(db)
        self.fatigue_guard = FatigueGuard(db)
        self.loop_protection = LoopProtectionService(db)

    async def evaluate(
        self,
        lead: Lead,
        automation_state: LeadAutomationState,
        action_type: SalesActionType,
        automation_permission: AutomationPermission,
        policy: Optional[FollowUpPolicy] = None,
        latest_customer_message: Optional[str] = None,
        channel: CommunicationChannel = CommunicationChannel.WHATSAPP,
        organization_id: str = "",
    ) -> GuardChainResultDTO:
        """
        Runs the full guard chain in priority order.
        Returns GuardChainResultDTO with all guard results.
        """
        guard_results: List[GuardResultDTO] = []

        # ── 1. Lifecycle Guard (Including Emergency Pause & Broker Takeover) ──
        lifecycle_result = self._evaluate_lifecycle_guard(
            automation_state, organization_id=organization_id or str(getattr(lead, "broker_id", ""))
        )
        guard_results.append(lifecycle_result)
        if not lifecycle_result.passed:
            return self._blocked(GuardName.LEAD_LIFECYCLE, lifecycle_result.reason, guard_results)

        # ── 2. Consent Guard (Part 21.5) ──────────────────────────────────────
        try:
            consent_ok, consent_status, consent_reason = await self.consent_guard.evaluate_consent(
                lead_id=str(lead.id),
                organization_id=organization_id,
                channel=channel,
                is_direct_customer_inquiry=False,
            )
            consent_result = GuardResultDTO(
                guard_name=GuardName.CONSENT,
                passed=consent_ok,
                reason=consent_reason,
                details={"consent_status": consent_status.value if consent_status else "UNKNOWN"},
            )
        except Exception as exc:
            consent_result = GuardResultDTO(
                guard_name=GuardName.CONSENT,
                passed=False,
                reason=f"Consent guard error: {exc}",
            )
        guard_results.append(consent_result)
        if not consent_result.passed:
            return self._blocked(GuardName.CONSENT, consent_result.reason, guard_results)

        # ── 3. Quiet Hours Guard (Part 21.5) ──────────────────────────────────
        try:
            is_timing_ok, scheduled_for_utc, customer_tz, timing_reason = \
                QuietHoursGuard.evaluate_timing(lead, policy)
            quiet_result = GuardResultDTO(
                guard_name=GuardName.QUIET_HOURS,
                passed=is_timing_ok,
                reason=timing_reason,
                details={
                    "scheduled_for_utc": scheduled_for_utc.isoformat() if scheduled_for_utc else None,
                    "customer_timezone": customer_tz,
                },
            )
        except Exception as exc:
            # S-002: FAIL CLOSED — guard error must block, not permit
            is_timing_ok = False
            scheduled_for_utc = None
            customer_tz = "UTC"
            quiet_result = GuardResultDTO(
                guard_name=GuardName.QUIET_HOURS,
                passed=False,
                reason=f"Quiet hours guard raised an unexpected error — blocked for safety: {type(exc).__name__}",
            )
            logger.error(f"[GUARD] QuietHoursGuard raised exception (fail-closed): {exc}")
        guard_results.append(quiet_result)
        if not quiet_result.passed:
            return self._blocked(GuardName.QUIET_HOURS, quiet_result.reason, guard_results)

        # ── 4. Fatigue Guard (Part 21.5) ──────────────────────────────────────
        try:
            is_fatigued, fatigue_score, fatigue_reason, is_dormant = \
                await self.fatigue_guard.evaluate_fatigue(
                    lead_id=str(lead.id),
                    organization_id=organization_id,
                    policy=policy,
                )
            fatigue_result = GuardResultDTO(
                guard_name=GuardName.FATIGUE,
                passed=not is_fatigued,
                reason=fatigue_reason,
                details={"fatigue_score": fatigue_score, "is_dormant_candidate": is_dormant},
            )
        except Exception as exc:
            # S-003: FAIL CLOSED — guard error must block, not permit
            is_fatigued = True
            fatigue_result = GuardResultDTO(
                guard_name=GuardName.FATIGUE,
                passed=False,
                reason=f"Fatigue guard raised an unexpected error — blocked for safety: {type(exc).__name__}",
            )
            logger.error(f"[GUARD] FatigueGuard raised exception (fail-closed): {exc}")
        guard_results.append(fatigue_result)
        if not fatigue_result.passed:
            return self._blocked(GuardName.FATIGUE, fatigue_result.reason, guard_results)

        # ── 5. Loop Protection ────────────────────────────────────────────────
        lp_ok, lp_reason = self.loop_protection.evaluate(automation_state, policy)
        lp_result = GuardResultDTO(
            guard_name=GuardName.LOOP_PROTECTION,
            passed=lp_ok,
            reason=lp_reason,
        )
        guard_results.append(lp_result)
        if not lp_result.passed:
            return self._blocked(GuardName.LOOP_PROTECTION, lp_result.reason, guard_results)

        # ── 6. Human Approval Guard (Part 21.5) ───────────────────────────────
        human_approval_required = False
        ha_reason = None
        try:
            req_human, handoff_reason, ha_explanation = HumanApprovalGuard.check_message_triggers(
                latest_customer_message
            )
            if not req_human:
                # Also check lead-level triggers
                req_human, ha_reason, _ = HumanApprovalGuard.evaluate_approval_requirement(
                    lead=lead,
                    policy=policy,
                    latest_message=latest_customer_message,
                )
            else:
                ha_reason = ha_explanation
            human_approval_required = req_human

            ha_result = GuardResultDTO(
                guard_name=GuardName.HUMAN_APPROVAL,
                passed=not req_human,
                reason=ha_reason,
                details={"human_approval_required": req_human},
            )
        except Exception as exc:
            # S-004: FAIL CLOSED — guard error must escalate to human review, not permit
            human_approval_required = True
            ha_result = GuardResultDTO(
                guard_name=GuardName.HUMAN_APPROVAL,
                passed=False,
                reason=f"Human approval guard raised an unexpected error — escalated for safety: {type(exc).__name__}",
                details={"human_approval_required": True, "guard_exception": True},
            )
            logger.error(f"[GUARD] HumanApprovalGuard raised exception (fail-closed): {exc}")
        guard_results.append(ha_result)

        # ── 7. Automation Policy Guard ────────────────────────────────────────
        policy_ok = automation_permission in (
            AutomationPermission.AUTOMATIC,
            AutomationPermission.SCHEDULED,
        )
        policy_result = GuardResultDTO(
            guard_name=GuardName.AUTOMATION_POLICY,
            passed=policy_ok or human_approval_required,  # HUMAN_APPROVAL is a valid outcome
            reason=(
                None if policy_ok
                else f"Automation permission {automation_permission.value} does not allow automatic dispatch."
            ),
            details={"automation_permission": automation_permission.value},
        )
        guard_results.append(policy_result)

        # Build result
        all_passed = all(g.passed for g in guard_results)
        if all_passed:
            return GuardChainResultDTO(
                overall_passed=True,
                guard_results=guard_results,
                human_approval_required=human_approval_required,
                scheduled_for_utc=scheduled_for_utc if not is_timing_ok else None,
                customer_timezone=customer_tz,
            )

        # Find first failing guard
        blocking = next((g for g in guard_results if not g.passed), None)
        return self._blocked(
            blocking.guard_name if blocking else GuardName.AUTOMATION_POLICY,
            blocking.reason if blocking else "Policy evaluation failed.",
            guard_results,
            human_approval_required=human_approval_required,
        )

    def _evaluate_lifecycle_guard(
        self,
        automation_state: LeadAutomationState,
        organization_id: str = "",
    ) -> GuardResultDTO:
        """Checks if lead is in a state that allows autonomous outbound action."""
        # 0. Emergency Kill-Switch Check (Global or Organization-level pause)
        tenant_to_check = organization_id or str(getattr(automation_state, "tenant_id", "") or "")
        if tenant_to_check:
            is_paused, pause_reason = EmergencyAutomationPauseService.is_tenant_paused(tenant_to_check)
            if is_paused:
                return GuardResultDTO(
                    guard_name=GuardName.LEAD_LIFECYCLE,
                    passed=False,
                    reason=pause_reason or "Emergency automation pause is active for this tenant.",
                    details={"emergency_pause": True, "tenant_id": str(tenant_to_check)},
                )
        else:
            is_g_paused, g_reason = EmergencyAutomationPauseService.is_global_paused()
            if is_g_paused:
                return GuardResultDTO(
                    guard_name=GuardName.LEAD_LIFECYCLE,
                    passed=False,
                    reason=g_reason or "Emergency global automation pause is active.",
                    details={"emergency_pause": True, "global": True},
                )

        try:
            state = LeadLifecycleState(automation_state.current_lifecycle_state)
        except ValueError:
            state = LeadLifecycleState.NEW

        if state in NO_OUTBOUND_STATES:
            return GuardResultDTO(
                guard_name=GuardName.LEAD_LIFECYCLE,
                passed=False,
                reason=f"Lead is in state '{state.value}' — no autonomous outbound permitted.",
                details={"lifecycle_state": state.value},
            )

        if automation_state.is_paused:
            return GuardResultDTO(
                guard_name=GuardName.LEAD_LIFECYCLE,
                passed=False,
                reason=f"Automation is paused for this lead. Reason: {automation_state.pause_reason or 'Not specified'}",
                details={"lifecycle_state": state.value, "is_paused": True},
            )

        # S-005: Broker takeover blocks all autonomous action
        if automation_state.is_broker_takeover:
            return GuardResultDTO(
                guard_name=GuardName.LEAD_LIFECYCLE,
                passed=False,
                reason="Broker takeover is active — autonomous outreach is suspended until broker releases control.",
                details={"lifecycle_state": state.value, "is_broker_takeover": True},
            )

        return GuardResultDTO(
            guard_name=GuardName.LEAD_LIFECYCLE,
            passed=True,
            details={"lifecycle_state": state.value},
        )

    @staticmethod
    def _blocked(
        guard_name: GuardName,
        reason: Optional[str],
        guard_results: List[GuardResultDTO],
        human_approval_required: bool = False,
    ) -> GuardChainResultDTO:
        return GuardChainResultDTO(
            overall_passed=False,
            blocking_guard=guard_name,
            blocking_reason=reason or f"Blocked by {guard_name.value}",
            guard_results=guard_results,
            human_approval_required=human_approval_required,
        )
