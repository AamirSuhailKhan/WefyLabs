"""
Part 21.5 / Part 21.6 — Sales Action Execution & Real Delivery Engine
=====================================================================
Executes approved sales actions across real communication channels (WhatsApp, Email, SMS, WebChat)
and internal CRM escalations.

NON-NEGOTIABLE PRINCIPLE:
POLICY DECIDES. AI PHRASES. PROVIDER DELIVERS. PROVIDER CONFIRMS. DATABASE RECORDS THE TRUTH.

1. Truthful execution: If provider credentials are not present, strictly records
   CONFIGURATION_REQUIRED or PROVIDER_UNAVAILABLE (never fabricates fake success or mock IDs).
2. Performs execution-time safety re-checks (Consent, Fatigue, Quiet Hours, Approval).
3. Uses deterministic idempotency locks to prevent duplicate sends.
4. Uses only verified tenant-owned properties via Part 21.3.
5. Automatically halts conflicting automations upon HUMAN_HANDOFF.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.follow_up_models import FollowUpPolicy
from app.modules.sales_action.taxonomies import (
    SalesActionType,
    SalesActionStatus,
    CommunicationChannel,
)
from app.modules.sales_action.dto import (
    SalesActionDecisionDTO,
    SalesActionExecutionResultDTO,
)
from app.modules.sales_action.metrics import (
    SALES_ACTIONS_EXECUTED_TOTAL,
    SALES_ACTIONS_FAILED_TOTAL,
    SALES_ACTION_HUMAN_HANDOFFS_TOTAL,
    mask_org_id,
)

logger = logging.getLogger(__name__)


class SalesActionExecutor:
    """
    Handles truthful dispatching of approved sales actions via RealDeliveryEngine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._delivery_engine = None

    @property
    def delivery_engine(self):
        if self._delivery_engine is None:
            from app.modules.communication.delivery_engine.real_delivery_engine import RealDeliveryEngine
            self._delivery_engine = RealDeliveryEngine(self.db)
        return self._delivery_engine

    async def execute_action(
        self,
        decision: SalesActionDecisionDTO,
        lead: Lead,
        broker: Broker,
        custom_message: Optional[str] = None,
        policy: Optional[FollowUpPolicy] = None,
    ) -> SalesActionExecutionResultDTO:
        """
        Executes the specified sales action truthfully through RealDeliveryEngine.
        """
        org_id = decision.organization_id
        org_hash = mask_org_id(org_id)
        action_type = decision.action_type

        # Track handoff metric if human handoff
        if action_type == SalesActionType.HUMAN_HANDOFF:
            SALES_ACTION_HUMAN_HANDOFFS_TOTAL.labels(
                org_hash=org_hash,
                handoff_reason=decision.sales_brief.handoff_reason if decision.sales_brief else "MANUAL_ESCALATION"
            ).inc()

        # Phase 2 Governance Enforcement Gate (Canonical Gate Requirement - Sections 4, 5, 6)
        from app.modules.autonomous_loop.phase2_governance import get_policy_engine, Phase2ActionType
        from app.modules.autonomous_loop.guard_chain import SALES_TO_PHASE2_ACTION
        
        has_approval = (decision.status == SalesActionStatus.APPROVED)
        phase2_act = SALES_TO_PHASE2_ACTION.get(action_type, Phase2ActionType.NO_ACTION)
        policy_decision = get_policy_engine().evaluate(str(org_id), phase2_act, has_human_approval=has_approval)
        
        if not policy_decision.is_permitted:
            logger.warning(
                f"[SalesActionExecutor] Action {action_type.value} BLOCKED by Phase 2 Governance: "
                f"{policy_decision.block_reason}"
            )
            return SalesActionExecutionResultDTO(
                action_id=decision.action_id,
                lead_id=str(lead.id),
                organization_id=str(org_id),
                action_type=action_type,
                channel=decision.recommended_channel.value if decision.recommended_channel else "UNKNOWN",
                status=SalesActionStatus.BLOCKED,
                provider="PHASE2_GOVERNANCE",
                details={
                    "governance_blocked": True,
                    "reason": policy_decision.block_reason,
                    "decision_id": policy_decision.decision_id,
                    "execution_mode": policy_decision.execution_mode.value,
                    "effective_level": policy_decision.effective_level.value,
                },
            )

        # Delegate execution to RealDeliveryEngine
        result = await self.delivery_engine.execute_sales_action_delivery(
            decision=decision,
            lead=lead,
            broker=broker,
            custom_message=custom_message,
            policy=policy,
        )

        # Update sales action metrics based on outcome
        if result.status == SalesActionStatus.SENT or result.status == SalesActionStatus.COMPLETED:
            SALES_ACTIONS_EXECUTED_TOTAL.labels(
                org_hash=org_hash,
                action_type=action_type.value,
                channel=result.channel,
            ).inc()
        elif result.status == SalesActionStatus.FAILED:
            SALES_ACTIONS_FAILED_TOTAL.labels(
                org_hash=org_hash,
                action_type=action_type.value,
                channel=result.channel,
                error_type=result.details.get("error_code", "UNKNOWN_ERROR") if result.details else "UNKNOWN_ERROR",
            ).inc()

        return result
