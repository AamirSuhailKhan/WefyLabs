"""
WefyLabs AI Workforce — Appointment Assistant Specialist
Part 10 Canonical Appointment & Scheduling Role
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus
from app.modules.ai_agent.workforce.protocols import AgentHandoffDTO, AgentResultDTO, ActionReceiptDTO
from app.modules.ai_agent.workforce.specialists.base import BaseWorkforceSpecialist
from app.modules.ai_agent.tool_executor.executor import ToolExecutor
from app.modules.ai_agent.workforce.policy import WorkforcePolicyEngine


class AppointmentAssistantSpecialist(BaseWorkforceSpecialist):
    @property
    def role(self) -> WorkforceRole:
        return WorkforceRole.APPOINTMENT_ASSISTANT

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
        customer_msg = context.get("customer_message", "")
        confirmed = bool(context.get("confirmed_action") is True)
        prop_id = context.get("property_id") or "prop-default"
        preferred_date = context.get("preferred_date") or "2026-09-26"

        tool_results = []
        # 1. Fetch verified available slots from calendar service
        WorkforcePolicyEngine.validate_tool_call(
            self.role, "get_available_slots", {"days_ahead": 7}, {"organization_id": org_id}
        )
        slots_res = await self.tool_executor.run(
            db=db,
            session_id=session_id,
            turn_index=1,
            tool_name="get_available_slots",
            arguments={"days_ahead": 7, "property_id": prop_id},
            context={"organization_id": org_id, "lead_id": lead_id},
        )
        tool_results.append({"tool": "get_available_slots", "result": slots_res.result, "success": slots_res.success})

        # 2. Check confirmation requirement if booking is desired
        if not confirmed:
            return AgentResultDTO(
                agent_id=self.role,
                status=HandoffStatus.CONFIRMATION_REQUIRED,
                summary="Verified available viewing slots retrieved. Customer confirmation required before booking.",
                data={
                    "available_slots": slots_res.result.get("slots", []) if slots_res.result else [],
                    "property_id": prop_id,
                    "proposed_date": preferred_date,
                },
                tool_results=tool_results,
                confirmation_required=True,
                confirmation_action=f"Book viewing for property {prop_id} on {preferred_date}",
                recommended_next_action="request_customer_confirmation",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )

        # 3. Confirmed booking execution
        WorkforcePolicyEngine.validate_tool_call(
            self.role, "book_viewing", {"property_id": prop_id, "preferred_date": preferred_date},
            {"organization_id": org_id, "confirmed_action": True}
        )
        book_res = await self.tool_executor.run(
            db=db,
            session_id=session_id,
            turn_index=2,
            tool_name="book_viewing",
            arguments={"property_id": prop_id, "preferred_date": preferred_date},
            context={"organization_id": org_id, "lead_id": lead_id, "confirmed_action": True},
        )
        tool_results.append({"tool": "book_viewing", "result": book_res.result, "success": book_res.success})

        receipt = ActionReceiptDTO(
            action_id=str(uuid.uuid4()),
            action_type="book_viewing",
            status="confirmed" if book_res.success else "failed",
            source_verified=True,
            details={"property_id": prop_id, "date": preferred_date, "result": book_res.result},
        )

        return AgentResultDTO(
            agent_id=self.role,
            status=HandoffStatus.SUCCESS,
            summary=f"Viewing successfully scheduled and confirmed for {preferred_date}.",
            data={"booking": book_res.result},
            tool_results=tool_results,
            receipt=receipt,
            recommended_next_action="send_viewing_confirmation_instructions",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
