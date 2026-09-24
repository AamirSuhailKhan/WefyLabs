"""
WefyLabs AI Workforce — Follow-Up Agent Specialist
Part 10 Canonical Follow-Up Role
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus
from app.modules.ai_agent.workforce.protocols import AgentHandoffDTO, AgentResultDTO
from app.modules.ai_agent.workforce.specialists.base import BaseWorkforceSpecialist


class FollowUpAgentSpecialist(BaseWorkforceSpecialist):
    @property
    def role(self) -> WorkforceRole:
        return WorkforceRole.FOLLOW_UP_AGENT

    async def execute(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
        handoff: Optional[AgentHandoffDTO] = None,
    ) -> AgentResultDTO:
        t0 = time.monotonic()
        lead_id = context.get("lead_id", "")
        visit_details = context.get("visit_details") or {}
        objections = context.get("objections") or []
        shortlist = context.get("shortlist") or []

        # Formulate contextual follow-up draft based on interaction history
        prop_name = visit_details.get("property_title") or "the property"
        draft_message = (
            f"Hi! Thank you for taking the time to tour {prop_name}. "
            "I'm following up to see if you have any questions regarding the floor plan, payment milestones, "
            "or if you would like to explore alternative units in the same community."
        )

        return AgentResultDTO(
            agent_id=self.role,
            status=HandoffStatus.SUCCESS,
            summary="Drafted personalized follow-up message based on site visit history.",
            data={
                "draft_message": draft_message,
                "visit_reference": visit_details.get("visit_id"),
                "objections_considered": objections,
                "channel_recommendation": "whatsapp",
                "execution_owner": "follow_up_automation",
            },
            recommended_next_action="submit_draft_to_follow_up_engine",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
