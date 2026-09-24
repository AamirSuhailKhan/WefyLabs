"""
WefyLabs AI Workforce — Orchestration Engine
Part 10 Canonical Multi-Agent Orchestrator
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus, ExecutionState
from app.modules.ai_agent.workforce.protocols import (
    AgentHandoffDTO, AgentResultDTO, WorkforceSessionTrace, WorkforceTraceStep
)
from app.modules.ai_agent.workforce.registry import get_agent_definition
from app.modules.ai_agent.workforce.policy import (
    WorkforcePolicyEngine, WorkforcePolicyViolation, MAX_AGENT_DEPTH
)
from app.modules.ai_agent.workforce.context import WorkforceContextBuilder
from app.modules.ai_agent.workforce.router import WorkforceRouter, RoutingDecision
from app.modules.ai_agent.workforce.specialists import get_specialist

logger = logging.getLogger("wefylabs.workforce.orchestrator")


class WorkforceOrchestrator:
    """
    Central AI Workforce Orchestrator.
    Enforces the single-platform multi-specialist architecture:
    - Bounded context & shared memory
    - Policy-gated tool execution
    - Controlled, non-cyclic delegation
    - Safe fallback and timeout boundaries
    - Cohesive customer response assembly (customer sees one assistant)
    - Operational-only trace emission (NO chain-of-thought storage)
    """

    def __init__(self):
        self.router = WorkforceRouter()
        self.context_builder = WorkforceContextBuilder()

    async def execute_turn(
        self,
        db: AsyncSession,
        organization_id: str,
        lead_id: str,
        customer_message: str,
        session_id: Optional[str] = None,
        is_internal_manager: bool = False,
        supplementary_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute one complete turn across the workforce.
        Returns:
            {
                "response": str,
                "selected_role": str,
                "status": str,
                "trace": WorkforceSessionTrace,
                "confirmation_required": bool,
                "confirmation_action": Optional[str],
                "receipt": Optional[Dict[str, Any]],
                "tool_results": List[Dict[str, Any]],
            }
        """
        t0 = time.monotonic()
        trace_id = str(uuid.uuid4())
        session_id = session_id or str(uuid.uuid4())

        # 1. Tenant boundary enforcement
        WorkforcePolicyEngine.validate_tenant_boundary(organization_id, organization_id)

        # 2. Sanitize untrusted input
        clean_msg, injection_detected = WorkforcePolicyEngine.sanitize_untrusted_input(customer_message)

        # 3. Router decision
        decision = self.router.route(
            query=clean_msg,
            is_internal_manager=is_internal_manager,
            context=supplementary_data,
        )
        selected_role = decision.selected_role

        # 4. Enforce role spoofing protection
        WorkforcePolicyEngine.validate_agent_execution_role(
            requested_role=selected_role,
            caller_is_internal_manager=is_internal_manager,
            is_customer_facing=not is_internal_manager,
        )

        trace_steps: List[WorkforceTraceStep] = []
        delegations: List[str] = []
        tools_called: List[str] = []
        policy_outcomes: List[str] = []

        # 5. Build bounded context for selected agent
        context = await self.context_builder.build_context(
            db=db,
            role=selected_role,
            organization_id=organization_id,
            lead_id=lead_id,
            session_id=session_id,
            customer_message=clean_msg,
            supplementary_data=supplementary_data,
        )

        # Step trace: routing
        trace_steps.append(
            WorkforceTraceStep(
                step_index=1,
                agent_role=selected_role,
                state=ExecutionState.RUNNING,
                policy_outcome="allowed",
                summary=f"Routed query to {selected_role.value}: {decision.reason}",
            )
        )

        # 6. Execute Primary Agent with timeout boundary
        defn = get_agent_definition(selected_role)
        specialist = get_specialist(selected_role)

        try:
            primary_result = await asyncio.wait_for(
                specialist.execute(db=db, context=context),
                timeout=defn.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(f"[WorkforceOrchestrator] Specialist {selected_role.value} timed out after {defn.timeout_seconds}s.")
            primary_result = AgentResultDTO(
                agent_id=selected_role,
                status=HandoffStatus.FALLBACK,
                summary=f"Specialist {selected_role.value} timed out; safe fallback engaged.",
                fallback_used=True,
            )
        except Exception as exc:
            logger.error(f"[WorkforceOrchestrator] Specialist execution error: {exc}", exc_info=True)
            primary_result = AgentResultDTO(
                agent_id=selected_role,
                status=HandoffStatus.FAILED,
                summary=f"Execution error in {selected_role.value}: {str(exc)}",
                fallback_used=True,
            )

        # Record tools called by primary agent
        for tr in primary_result.tool_results:
            tools_called.append(tr.get("tool", "unknown_tool"))

        # 7. Controlled Delegation Handling
        final_result = primary_result
        if primary_result.handoff_needed and primary_result.handoff_target:
            target_role = primary_result.handoff_target
            try:
                # Validate delegation policy
                WorkforcePolicyEngine.validate_delegation(
                    from_role=selected_role,
                    to_role=target_role,
                    current_depth=1,
                    delegation_chain=[selected_role.value],
                    authenticated_tenant_id=organization_id,
                )
                delegations.append(f"{selected_role.value}->{target_role.value}")
                policy_outcomes.append("delegation_authorized")

                # Build bounded context for delegate
                child_context = await self.context_builder.build_context(
                    db=db,
                    role=target_role,
                    organization_id=organization_id,
                    lead_id=lead_id,
                    session_id=session_id,
                    customer_message=clean_msg,
                    supplementary_data=supplementary_data,
                )
                child_defn = get_agent_definition(target_role)
                child_specialist = get_specialist(target_role)

                trace_steps.append(
                    WorkforceTraceStep(
                        step_index=len(trace_steps) + 1,
                        agent_role=selected_role,
                        state=ExecutionState.WAITING_AGENT,
                        delegation_target=target_role,
                        summary=f"Delegating specialized task to {target_role.value}",
                    )
                )

                # Execute delegate with its configured timeout
                child_result = await asyncio.wait_for(
                    child_specialist.execute(
                        db=db,
                        context=child_context,
                        handoff=AgentHandoffDTO(
                            from_agent=selected_role,
                            to_agent=target_role,
                            tenant_id=organization_id,
                            lead_id=lead_id,
                            objective=clean_msg,
                            depth=2,
                            delegation_chain=[selected_role.value],
                        ),
                    ),
                    timeout=child_defn.timeout_seconds,
                )

                for tr in child_result.tool_results:
                    tools_called.append(tr.get("tool", "unknown_tool"))

                final_result = child_result

                trace_steps.append(
                    WorkforceTraceStep(
                        step_index=len(trace_steps) + 1,
                        agent_role=target_role,
                        state=ExecutionState.COMPLETED,
                        summary=child_result.summary,
                    )
                )

            except WorkforcePolicyViolation as pv:
                logger.warning(f"[WorkforceOrchestrator] Delegation blocked by policy: {pv}")
                policy_outcomes.append(f"blocked:{pv.rule}")
                # Fall back safely to primary agent results
                final_result = primary_result

        # 8. Assemble Cohesive Customer Response (Phase 53 / Phase 70)
        # Unified assistant persona: customer never sees internal agent delegation names
        if is_internal_manager:
            customer_response = final_result.summary
        elif final_result.confirmation_required:
            customer_response = (
                f"{final_result.summary}\n\n"
                f"Would you like me to proceed and confirm this appointment for you?"
            )
        elif final_result.handoff_needed or selected_role == WorkforceRole.HANDOFF_ASSISTANT:
            customer_response = (
                "I am connecting you with one of our specialized senior property advisors. "
                "I have prepared your requirements, shortlist, and preferences so you will not need to repeat anything."
            )
        else:
            customer_response = final_result.summary

        total_duration = int((time.monotonic() - t0) * 1000)

        # 9. Build Operational Trace (strictly NO chain-of-thought stored)
        trace = WorkforceSessionTrace(
            trace_id=trace_id,
            session_id=session_id,
            tenant_id=organization_id,
            lead_id=lead_id,
            initial_query=customer_message,
            routing_decision=selected_role,
            routing_reason=decision.reason,
            steps=trace_steps,
            delegations=delegations,
            tools_called=tools_called,
            policy_outcomes=policy_outcomes,
            final_response=customer_response,
            total_duration_ms=total_duration,
        )

        return {
            "response": customer_response,
            "selected_role": selected_role.value,
            "status": final_result.status.value,
            "confirmation_required": final_result.confirmation_required,
            "confirmation_action": final_result.confirmation_action,
            "receipt": final_result.receipt.model_dump() if final_result.receipt else None,
            "tool_results": final_result.tool_results,
            "data": final_result.data,
            "trace": trace.model_dump(),
        }
