"""
WefyLabs AI Workforce — Qualification Agent Specialist
Part 10 Canonical Qualification Role
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus
from app.modules.ai_agent.workforce.protocols import AgentHandoffDTO, AgentResultDTO
from app.modules.ai_agent.workforce.specialists.base import BaseWorkforceSpecialist


class QualificationAgentSpecialist(BaseWorkforceSpecialist):
    @property
    def role(self) -> WorkforceRole:
        return WorkforceRole.QUALIFICATION_AGENT

    async def execute(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
        handoff: Optional[AgentHandoffDTO] = None,
    ) -> AgentResultDTO:
        t0 = time.monotonic()
        qual = context.get("qualification", {})
        customer_msg = context.get("customer_message", "")

        # Canonical required fields for baseline qualification
        REQUIRED_FIELDS = ["budget_max", "bedrooms", "preferred_locations"]
        collected = {k: v for k, v in qual.items() if v is not None}
        missing = [f for f in REQUIRED_FIELDS if not collected.get(f)]

        # Suggest next question based on highest priority missing field
        QUESTION_MAP = {
            "budget_max": "What is your target budget range for this property?",
            "bedrooms": "How many bedrooms are you seeking (e.g. 2 BHK, 3 BHK, 4 BHK)?",
            "preferred_locations": "Which localities or micro-markets do you prefer?",
        }
        next_question = QUESTION_MAP.get(missing[0]) if missing else None

        is_qualified = len(missing) == 0
        summary = (
            f"Buyer qualification analysis: {len(collected)} facts collected, {len(missing)} missing."
            if not is_qualified else "Buyer is fully qualified for active property recommendations."
        )

        return AgentResultDTO(
            agent_id=self.role,
            status=HandoffStatus.SUCCESS,
            summary=summary,
            data={
                "collected_facts": collected,
                "missing_fields": missing,
                "is_qualified": is_qualified,
                "suggested_question": next_question,
            },
            recommended_next_action="ask_next_qualification_question" if next_question else "present_matching_properties",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
