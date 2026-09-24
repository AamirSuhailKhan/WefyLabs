"""
WefyLabs AI Workforce — Base Specialist Agent Interface
Part 10 Canonical Agent Contract
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_agent.workforce.enums import WorkforceRole
from app.modules.ai_agent.workforce.protocols import AgentHandoffDTO, AgentResultDTO
from app.modules.ai_agent.workforce.registry import get_agent_definition


class BaseWorkforceSpecialist(ABC):
    """
    Interface all specialist agents must implement.
    Agents are consumers and operators over existing domain services.
    They never own independent databases or override canonical policies.
    """

    @property
    @abstractmethod
    def role(self) -> WorkforceRole:
        """The canonical role this specialist fulfills."""
        ...

    @property
    def definition(self):
        return get_agent_definition(self.role)

    @abstractmethod
    async def execute(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
        handoff: Optional[AgentHandoffDTO] = None,
    ) -> AgentResultDTO:
        """
        Execute one reasoning turn within the bounded context.
        Returns validated, structured AgentResultDTO.
        """
        ...
