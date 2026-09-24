"""
WefyLabs AI Workforce — Property Advisor Specialist
Part 10 Canonical Property Intelligence Role
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


class PropertyAdvisorSpecialist(BaseWorkforceSpecialist):
    @property
    def role(self) -> WorkforceRole:
        return WorkforceRole.PROPERTY_ADVISOR

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
        property_ids = context.get("property_ids") or (handoff.relevant_context.get("property_ids") if handoff else [])
        session_id = context.get("session_id", "session-default")

        tool_results = []
        # If comparison requested
        if len(property_ids) >= 2 or "compare" in customer_msg.lower():
            WorkforcePolicyEngine.validate_tool_call(
                self.role, "compare_properties", {"property_ids": property_ids[:4]}, {"organization_id": org_id}
            )
            res = await self.tool_executor.run(
                db=db,
                session_id=session_id,
                turn_index=1,
                tool_name="compare_properties",
                arguments={"property_ids": property_ids[:4]},
                context={"organization_id": org_id, "lead_id": lead_id},
            )
            tool_results.append({"tool": "compare_properties", "result": res.result, "success": res.success})
            summary = f"Compared {len(property_ids[:4])} properties using canonical property truth."
        elif property_ids:
            # Check availability / single property details
            target_id = property_ids[0]
            WorkforcePolicyEngine.validate_tool_call(
                self.role, "check_availability", {"property_id": target_id}, {"organization_id": org_id}
            )
            res = await self.tool_executor.run(
                db=db,
                session_id=session_id,
                turn_index=1,
                tool_name="check_availability",
                arguments={"property_id": target_id},
                context={"organization_id": org_id, "lead_id": lead_id},
            )
            tool_results.append({"tool": "check_availability", "result": res.result, "success": res.success})
            summary = f"Retrieved verified status and details for property {target_id}."
        else:
            # Search verified properties
            qual = context.get("qualification", {})
            WorkforcePolicyEngine.validate_tool_call(
                self.role, "search_properties", {}, {"organization_id": org_id}
            )
            res = await self.tool_executor.run(
                db=db,
                session_id=session_id,
                turn_index=1,
                tool_name="search_properties",
                arguments={
                    "property_type": qual.get("property_type"),
                    "bedrooms": qual.get("bedrooms"),
                    "budget_max": qual.get("budget_max"),
                    "limit": 3,
                },
                context={"organization_id": org_id, "lead_id": lead_id},
            )
            tool_results.append({"tool": "search_properties", "result": res.result, "success": res.success})
            summary = "Queried verified inventory matching buyer specifications."

        return AgentResultDTO(
            agent_id=self.role,
            status=HandoffStatus.SUCCESS,
            summary=summary,
            data={"grounded_in_canonical_truth": True},
            tool_results=tool_results,
            recommended_next_action="advise_buyer_on_verified_listings",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
