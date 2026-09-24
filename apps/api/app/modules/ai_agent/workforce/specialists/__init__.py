"""
WefyLabs AI Workforce — Specialist Roles
Part 10 Canonical Registry
"""
from __future__ import annotations

from typing import Dict

from app.modules.ai_agent.workforce.enums import WorkforceRole
from app.modules.ai_agent.workforce.specialists.base import BaseWorkforceSpecialist
from app.modules.ai_agent.workforce.specialists.sales_agent import SalesAgentSpecialist
from app.modules.ai_agent.workforce.specialists.qualification_agent import QualificationAgentSpecialist
from app.modules.ai_agent.workforce.specialists.property_advisor import PropertyAdvisorSpecialist
from app.modules.ai_agent.workforce.specialists.followup_agent import FollowUpAgentSpecialist
from app.modules.ai_agent.workforce.specialists.appointment_assistant import AppointmentAssistantSpecialist
from app.modules.ai_agent.workforce.specialists.handoff_assistant import HandoffAssistantSpecialist
from app.modules.ai_agent.workforce.specialists.revenue_copilot import RevenueCopilotSpecialist
from app.modules.ai_agent.workforce.specialists.manager_command_agent import ManagerCommandAgentSpecialist

_SPECIALISTS: Dict[WorkforceRole, BaseWorkforceSpecialist] = {
    WorkforceRole.SALES_AGENT: SalesAgentSpecialist(),
    WorkforceRole.QUALIFICATION_AGENT: QualificationAgentSpecialist(),
    WorkforceRole.PROPERTY_ADVISOR: PropertyAdvisorSpecialist(),
    WorkforceRole.FOLLOW_UP_AGENT: FollowUpAgentSpecialist(),
    WorkforceRole.APPOINTMENT_ASSISTANT: AppointmentAssistantSpecialist(),
    WorkforceRole.HANDOFF_ASSISTANT: HandoffAssistantSpecialist(),
    WorkforceRole.REVENUE_COPILOT: RevenueCopilotSpecialist(),
    WorkforceRole.MANAGER_COMMAND_AGENT: ManagerCommandAgentSpecialist(),
}


def get_specialist(role: WorkforceRole) -> BaseWorkforceSpecialist:
    """Retrieve specialist singleton instance for a given role."""
    if role not in _SPECIALISTS:
        raise KeyError(f"No specialist implementation registered for role: {role}")
    return _SPECIALISTS[role]
