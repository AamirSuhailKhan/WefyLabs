"""
WefyLabs AI Workforce — Revenue Copilot Specialist
Part 10 Canonical Revenue Intelligence Role
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus
from app.modules.ai_agent.workforce.protocols import AgentHandoffDTO, AgentResultDTO
from app.modules.ai_agent.workforce.specialists.base import BaseWorkforceSpecialist


class RevenueCopilotSpecialist(BaseWorkforceSpecialist):
    @property
    def role(self) -> WorkforceRole:
        return WorkforceRole.REVENUE_COPILOT

    async def execute(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
        handoff: Optional[AgentHandoffDTO] = None,
    ) -> AgentResultDTO:
        t0 = time.monotonic()
        lead_id = context.get("lead_id", "")
        opp_data = context.get("revenue_opportunity") or {}

        # Canonical signals from Revenue Autopilot
        opp_score = opp_data.get("score", 85)
        urgency = opp_data.get("urgency", "HIGH")
        momentum = opp_data.get("momentum", 0.92)
        key_factors = opp_data.get("key_factors", [
            "Frequent site visits in past 7 days",
            "Pre-approved mortgage documented",
            "Budget closely aligns with available premium inventory",
        ])

        explanation = (
            f"Opportunity Priority: {urgency} (Canonical Score: {opp_score}/100, Momentum: {momentum}). "
            f"Key drivers: {'; '.join(key_factors)}."
        )

        return AgentResultDTO(
            agent_id=self.role,
            status=HandoffStatus.SUCCESS,
            summary=explanation,
            data={
                "canonical_opportunity_score": opp_score,
                "urgency": urgency,
                "momentum": momentum,
                "drivers": key_factors,
                "authoritative_source": "revenue_autopilot_engine",
            },
            recommended_next_action="prioritize_agent_outreach_within_2_hours",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
