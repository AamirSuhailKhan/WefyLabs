"""
Phase 2C — Production Event → Pilot Observation Bridge
=======================================================
Connects REAL production domain events from SalesLoopEvent table
to the Phase 2C pilot observation pipeline.

This is NOT a synthetic event generator.
This is NOT a manual trigger.

This bridge consumes REAL events that already flow through the
AutonomousSalesLoopService (Part 21.8) and additionally routes
them to the Phase 2C pilot engine for agent evaluation.

Flow:
  REAL_DOMAIN_EVENT (e.g. LeadCreated, MessageReceived, FollowUpDue)
    ↓  [existing autonomous loop worker — loop_tasks.py]
    ↓  AutonomousSalesLoopService.process_event()
    ↓  [Phase2C bridge hook — added here]
    Phase2CEventBridge.route_to_pilot_engine()
    ↓
    Phase2CContextBuilder.build()          ← real DB context
    ↓
    Phase2BAgent.execute(mode=SHADOW)      ← shadow decision
    ↓
    PilotRepository.record_observation()   ← durable persistence
    ↓
    pilot_observations table               ← DB

Only tenants enrolled in a pilot receive bridge routing.
Non-enrolled tenants pass through unchanged.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autonomous_loop.phase2_governance import (
    Phase2ExecutionMode,
    RevenueActionPolicyEngine,
    get_policy_engine,
)
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService

logger = logging.getLogger("wefylabs.phase2c.event_bridge")

# Event types that trigger pilot observations
PILOT_TRIGGER_EVENTS = {
    "NEW_LEAD",
    "LEAD_QUALIFIED",
    "LEAD_UPDATED",
    "MESSAGE_RECEIVED",
    "FOLLOW_UP_DUE",
    "SITE_VISIT_SCHEDULED",
    "SITE_VISIT_COMPLETED",
    "DEAL_UPDATED",
    "INACTIVITY_ALERT",
    "REACTIVATION_TRIGGERED",
}


class Phase2CEventBridge:
    """
    Routes production domain events to the Phase 2C pilot observation pipeline.

    Called from the existing loop worker AFTER standard processing completes,
    so pilot observation is additive and does not block standard flow.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def route_event(
        self,
        event_type: str,
        organization_id: str,
        lead_id: Optional[str],
        event_id: Optional[str],
        correlation_id: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Routes a production event to the pilot observation pipeline.
        Returns observation summary if routed, None if not applicable.

        IMPORTANT: Errors in this method MUST NOT propagate to the caller.
        Pilot observation is additive — it must not break the primary loop.
        """
        try:
            # Gate 1: Kill switch
            is_global_paused, _ = EmergencyAutomationPauseService.is_global_paused()
            if is_global_paused:
                return None
            is_tenant_paused, _ = EmergencyAutomationPauseService.is_tenant_paused(organization_id)
            if is_tenant_paused:
                return None

            # Gate 2: Event must be pilot-relevant
            if event_type not in PILOT_TRIGGER_EVENTS:
                return None

            # Gate 3: Lead must exist
            if not lead_id:
                return None

            # Gate 4: Tenant must be enrolled
            from app.modules.autonomous_loop.phase2c_pilot_repository import PilotRepository
            repo = PilotRepository(self.db)
            pilot = await repo.get_pilot_tenant(organization_id)
            if pilot is None or pilot.pilot_status != "ACTIVE":
                return None

            # Gate 5: Run pilot observation
            return await self._run_pilot_observation(
                repo=repo,
                pilot=pilot,
                event_type=event_type,
                organization_id=organization_id,
                lead_id=lead_id,
                event_id=event_id,
                correlation_id=correlation_id,
                payload=payload,
            )

        except Exception as exc:
            # CRITICAL: Never let bridge errors crash the primary loop
            logger.error(
                f"[EVENT_BRIDGE] Non-fatal pilot bridge error "
                f"org={organization_id} event={event_type} lead={lead_id}: {exc}",
                exc_info=True,
            )
            return None

    async def _run_pilot_observation(
        self,
        repo,
        pilot,
        event_type: str,
        organization_id: str,
        lead_id: str,
        event_id: Optional[str],
        correlation_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Runs the full pilot observation cycle for a single event.
        Selects the appropriate agent based on event type.
        """
        from app.modules.autonomous_loop.phase2_governance import Phase2RiskClass
        from app.modules.autonomous_loop.phase2c_context_builder import Phase2CContextBuilder
        from app.modules.autonomous_loop.phase2_agent_contracts import AgentExecutionRecord, AgentDomain
        from app.modules.autonomous_loop.phase2b_agents import (
            LeadIntelligenceAgent, QualificationAgent, EngagementAgent,
            FollowUpAgent, RecoveryAgent,
        )

        execution_id = str(uuid.uuid4())

        # Select agent by event type
        agent_map = {
            "NEW_LEAD": LeadIntelligenceAgent(),
            "LEAD_UPDATED": LeadIntelligenceAgent(),
            "LEAD_QUALIFIED": QualificationAgent(),
            "MESSAGE_RECEIVED": EngagementAgent(),
            "FOLLOW_UP_DUE": FollowUpAgent(),
            "INACTIVITY_ALERT": RecoveryAgent(),
            "REACTIVATION_TRIGGERED": RecoveryAgent(),
        }
        agent = agent_map.get(event_type, LeadIntelligenceAgent())

        # Build real context
        builder = Phase2CContextBuilder(self.db)
        try:
            context = await builder.build(
                organization_id=organization_id,
                lead_id=lead_id,
                action_risk_class=Phase2RiskClass.MEDIUM,
            )
        except Exception as ctx_exc:
            logger.warning(
                f"[EVENT_BRIDGE] Context build failed org={organization_id} lead={lead_id}: {ctx_exc}"
            )
            return {"status": "CONTEXT_BUILD_FAILED", "error": str(ctx_exc)}

        # Verify context freshness
        if not context.is_fresh():
            logger.warning(f"[EVENT_BRIDGE] Stale context org={organization_id} lead={lead_id} — skipping")
            return {"status": "STALE_CONTEXT"}

        # Execute agent in shadow mode (ALWAYS shadow at event bridge — real execution handled separately)
        policy_engine = get_policy_engine()
        record = AgentExecutionRecord(
            execution_id=execution_id,
            organization_id=organization_id,
            lead_id=lead_id,
            agent_domain=agent.domain,
            agent_version=agent.version,
            goal=f"Pilot shadow observation for {event_type}",
            execution_mode=Phase2ExecutionMode.SHADOW,
        )

        try:
            completed_record = await agent.execute(context, record, policy_engine, dry_run=True)
        except Exception as agent_exc:
            logger.warning(f"[EVENT_BRIDGE] Agent execution error: {agent_exc}")
            return {"status": "AGENT_EXECUTION_FAILED", "error": str(agent_exc)}

        # Extract recommended action
        recommended_action = None
        reasoning = None
        if completed_record.actions_taken:
            last_action = completed_record.actions_taken[-1]
            recommended_action = last_action.get("action")
            reasoning = last_action.get("reasoning", "")

        # Persist observation to DB
        obs = await repo.record_observation(
            organization_id=organization_id,
            pilot_id=pilot.id,
            lead_id=lead_id,
            agent_id=agent.agent_id,
            agent_domain=agent.domain.value,
            execution_id=execution_id,
            pilot_stage=pilot.current_stage,
            execution_mode=Phase2ExecutionMode.SHADOW.value,
            recommended_action=recommended_action,
            reasoning=reasoning,
            agent_confidence=completed_record.confidence.value if completed_record.confidence else None,
            policy_decision="SHADOW_PROJECTED",
            source_event_id=event_id,
            source_event_type=event_type,
        )

        logger.info(
            f"[EVENT_BRIDGE] Observation recorded "
            f"org={organization_id} lead={lead_id} event={event_type} "
            f"obs_id={obs.id} agent={agent.agent_id} action={recommended_action}"
        )

        return {
            "status": "OBSERVATION_RECORDED",
            "observation_id": obs.id,
            "agent_id": agent.agent_id,
            "recommended_action": recommended_action,
            "pilot_stage": pilot.current_stage,
        }
