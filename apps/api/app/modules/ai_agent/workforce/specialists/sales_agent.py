"""
WefyLabs AI Workforce — Sales Agent Specialist
Part 10 Canonical Sales Role
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus
from app.modules.ai_agent.workforce.protocols import AgentHandoffDTO, AgentResultDTO
from app.modules.ai_agent.workforce.specialists.base import BaseWorkforceSpecialist
from app.modules.ai_agent.tool_executor.executor import ToolExecutor
from app.modules.ai_agent.workforce.policy import WorkforcePolicyEngine


class SalesAgentSpecialist(BaseWorkforceSpecialist):
    @property
    def role(self) -> WorkforceRole:
        return WorkforceRole.SALES_AGENT

    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        self.tool_executor = tool_executor or ToolExecutor()

    async def execute(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
        handoff: Optional[AgentHandoffDTO] = None,
    ) -> AgentResultDTO:
        t0 = time.monotonic()
        org_id = context.get("organization_id", "")
        lead_id = context.get("lead_id", "")
        customer_msg = context.get("customer_message", "")
        session_id = context.get("session_id", "session-default")
        qual = context.get("qualification", {})

        # Check for delegation triggers
        msg_lower = customer_msg.lower()
        if "compare" in msg_lower or "which is better" in msg_lower or "parking" in msg_lower or "amenities" in msg_lower:
            return AgentResultDTO(
                agent_id=self.role,
                status=HandoffStatus.DELEGATED,
                summary="Delegating property deep-dive to Property Advisor.",
                handoff_needed=True,
                handoff_target=WorkforceRole.PROPERTY_ADVISOR,
                recommended_next_action="delegate_property_advisor",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        
        if "visit" in msg_lower or "appointment" in msg_lower or "saturday" in msg_lower or "slot" in msg_lower or "schedule" in msg_lower:
            return AgentResultDTO(
                agent_id=self.role,
                status=HandoffStatus.DELEGATED,
                summary="Delegating viewing schedule to Appointment Assistant.",
                handoff_needed=True,
                handoff_target=WorkforceRole.APPOINTMENT_ASSISTANT,
                recommended_next_action="delegate_appointment_assistant",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )

        if "human" in msg_lower or "person" in msg_lower or "manager" in msg_lower or "complaint" in msg_lower:
            return AgentResultDTO(
                agent_id=self.role,
                status=HandoffStatus.DELEGATED,
                summary="Delegating escalation to Human Handoff Assistant.",
                handoff_needed=True,
                handoff_target=WorkforceRole.HANDOFF_ASSISTANT,
                recommended_next_action="delegate_handoff_assistant",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )

        # Execute direct property search if buyer expressed budget / preferences
        tool_results = []
        summary = "Engaged with buyer, gathering requirements."
        if qual.get("budget_max") or "bhk" in msg_lower or "budget" in msg_lower or "crore" in msg_lower or "lakh" in msg_lower:
            WorkforcePolicyEngine.validate_tool_call(
                self.role, "search_properties", {}, {"organization_id": org_id}
            )
            search_res = await self.tool_executor.run(
                db=db,
                session_id=session_id,
                turn_index=1,
                tool_name="search_properties",
                arguments={
                    "budget_max": qual.get("budget_max"),
                    "bedrooms": qual.get("bedrooms"),
                    "locations": qual.get("preferred_locations"),
                    "limit": 3,
                },
                context={"organization_id": org_id, "lead_id": lead_id},
            )
            tool_results.append({"tool": "search_properties", "result": search_res.result, "success": search_res.success})
            summary = "Retrieved verified properties matching buyer criteria."

        return AgentResultDTO(
            agent_id=self.role,
            status=HandoffStatus.SUCCESS,
            summary=summary,
            data={"qualification": qual},
            tool_results=tool_results,
            recommended_next_action="continue_consultation",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
