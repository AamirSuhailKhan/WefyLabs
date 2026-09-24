"""
WefyLabs AI Workforce — Human Handoff Assistant Specialist
Part 10 Canonical Human Escalation Role
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus
from app.modules.ai_agent.workforce.protocols import AgentHandoffDTO, AgentResultDTO
from app.modules.ai_agent.workforce.specialists.base import BaseWorkforceSpecialist
from app.modules.ai_agent.tool_executor.executor import ToolExecutor
from app.modules.ai_agent.workforce.policy import WorkforcePolicyEngine


class HandoffAssistantSpecialist(BaseWorkforceSpecialist):
    @property
    def role(self) -> WorkforceRole:
        return WorkforceRole.HANDOFF_ASSISTANT

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
        session_id = context.get("session_id", "session-default")
        reason = context.get("reason") or "human_requested"

        # 1. Fetch structured handoff briefing context
        WorkforcePolicyEngine.validate_tool_call(
            self.role, "get_handoff_context", {}, {"organization_id": org_id}
        )
        ctx_res = await self.tool_executor.run(
            db=db,
            session_id=session_id,
            turn_index=1,
            tool_name="get_handoff_context",
            arguments={"include_shortlist": True, "include_objections": True},
            context={
                "organization_id": org_id,
                "lead_id": lead_id,
                "qualification": context.get("qualification", {}),
                "lead_data": {"lead_id": lead_id},
            },
        )

        # 2. Trigger escalation intent
        WorkforcePolicyEngine.validate_tool_call(
            self.role, "escalate_to_human", {"reason": reason}, {"organization_id": org_id}
        )
        esc_res = await self.tool_executor.run(
            db=db,
            session_id=session_id,
            turn_index=2,
            tool_name="escalate_to_human",
            arguments={"reason": reason, "priority": "high"},
            context={"organization_id": org_id, "lead_id": lead_id},
        )

        return AgentResultDTO(
            agent_id=self.role,
            status=HandoffStatus.SUCCESS,
            summary="Structured human handoff briefing prepared and escalated to human broker queue.",
            data={
                "handoff_briefing": ctx_res.result,
                "escalation_status": esc_res.result,
                "assigned_human_queue": "enterprise_sales",
            },
            tool_results=[
                {"tool": "get_handoff_context", "result": ctx_res.result, "success": ctx_res.success},
                {"tool": "escalate_to_human", "result": esc_res.result, "success": esc_res.success},
            ],
            recommended_next_action="transfer_to_live_human_broker",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
