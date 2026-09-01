"""
Multi-Agent Orchestrator — production-ready architecture for specialized sub-agents.

BeetleLabs' competitive advantage: instead of one monolithic prompt,
route to specialized agents based on conversation state and buyer need.

Current Agents:
  ├── QualificationAgent   → Asks BANT/MEDDIC questions, extracts structured data
  ├── PropertyAgent        → Searches, filters, and recommends matched listings
  ├── FinancingAgent       → Mortgage eligibility, payment plans, NRI financing
  ├── SchedulingAgent      → Calendar check, meeting booking, reminder creation
  └── FollowUpAgent        → Re-engagement sequences, drip campaigns

Coordination:
  - ConversationManager decides which agent handles each turn
  - Shared AgentContext is passed to all agents
  - Tool Executor + Memory Engine are shared services

Extension:
  - Add new agents by implementing BaseSpecialistAgent and registering below
  - Agents can be deployed independently (separate microservices) or in-process
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.context_builder.builder import AgentContext


# ─── Base Specialist Agent ────────────────────────────────────────────────────

class BaseSpecialistAgent(ABC):
    """
    Interface all specialist agents must implement.
    Agents receive a resolved AgentContext and return a response string.
    They may call tools via the shared ToolExecutor.
    """

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Unique name for this specialist agent."""
        ...

    @property
    @abstractmethod
    def handles_states(self) -> List[str]:
        """List of FSM states this agent is responsible for."""
        ...

    @abstractmethod
    async def process(self, ctx: AgentContext, customer_message: str) -> Dict[str, Any]:
        """
        Process one turn.
        Returns: {"response": str, "tool_calls": list, "handoff_to": Optional[str]}
        handoff_to: name of next specialist agent (or None to stay with this one)
        """
        ...

    def can_handle(self, current_state: str) -> bool:
        return current_state in self.handles_states


# ─── Specialist Agent Stubs (production-wirable) ─────────────────────────────

class QualificationAgent(BaseSpecialistAgent):
    """
    Focused qualification: asks BANT questions in the optimal order
    for the current buyer profile strategy.
    Owned by: state machine states [discovering, qualifying]
    """
    @property
    def agent_name(self) -> str:
        return "qualification_agent"

    @property
    def handles_states(self) -> List[str]:
        return ["discovering", "qualifying"]

    async def process(self, ctx: AgentContext, customer_message: str) -> Dict[str, Any]:
        # TODO: Wire to dedicated LLM call with qualification-specific prompt
        next_question = (ctx.fields_remaining or [None])[0]
        return {
            "response": f"Thank you! To find the best property for you, {next_question or 'could you share more?'}",
            "tool_calls": [{"name": "update_qualification", "arguments": {}}],
            "handoff_to": "property_agent" if ctx.is_qualified else None,
        }


class PropertyAgent(BaseSpecialistAgent):
    """
    Property recommendation: searches verified inventory and presents matched listings.
    Owned by: [explaining, recommending]
    """
    @property
    def agent_name(self) -> str:
        return "property_agent"

    @property
    def handles_states(self) -> List[str]:
        return ["explaining", "recommending"]

    async def process(self, ctx: AgentContext, customer_message: str) -> Dict[str, Any]:
        qual = ctx.qualification or {}
        search_args = {
            k: v for k, v in {
                "property_type": qual.get("property_type"),
                "bedrooms": qual.get("bedrooms"),
                "budget_max": qual.get("budget_max"),
                "locations": qual.get("preferred_locations"),
                "purpose": qual.get("purpose"),
            }.items() if v
        }
        return {
            "response": "Let me search our verified inventory for matching properties...",
            "tool_calls": [{"name": "search_properties", "arguments": search_args}],
            "handoff_to": None,
        }


class FinancingAgent(BaseSpecialistAgent):
    """
    Handles mortgage eligibility, payment plans, NRI financing.
    Routes to human if financial advice territory.
    Owned by: [negotiating]
    """
    @property
    def agent_name(self) -> str:
        return "financing_agent"

    @property
    def handles_states(self) -> List[str]:
        return ["negotiating"]

    async def process(self, ctx: AgentContext, customer_message: str) -> Dict[str, Any]:
        return {
            "response": "I can share verified payment plan options. Let me retrieve those for you.",
            "tool_calls": [],
            "handoff_to": None,
        }


class SchedulingAgent(BaseSpecialistAgent):
    """
    Calendar management: checks availability, books viewings, creates reminders.
    Owned by: [booking]
    """
    @property
    def agent_name(self) -> str:
        return "scheduling_agent"

    @property
    def handles_states(self) -> List[str]:
        return ["booking"]

    async def process(self, ctx: AgentContext, customer_message: str) -> Dict[str, Any]:
        return {
            "response": "I'll book that viewing for you. What date works best?",
            "tool_calls": [],
            "handoff_to": None,
        }


class FollowUpAgent(BaseSpecialistAgent):
    """
    Re-engagement: drip campaigns, follow-up messages, win-back sequences.
    Owned by: [follow_up, waiting]
    """
    @property
    def agent_name(self) -> str:
        return "followup_agent"

    @property
    def handles_states(self) -> List[str]:
        return ["follow_up", "waiting"]

    async def process(self, ctx: AgentContext, customer_message: str) -> Dict[str, Any]:
        return {
            "response": "Welcome back! I have some exciting new options that match your requirements.",
            "tool_calls": [{"name": "trigger_workflow", "arguments": {"workflow_name": "re_engagement"}}],
            "handoff_to": "qualification_agent",
        }


# ─── Agent Registry ──────────────────────────────────────────────────────────

_AGENTS: List[BaseSpecialistAgent] = [
    QualificationAgent(),
    PropertyAgent(),
    FinancingAgent(),
    SchedulingAgent(),
    FollowUpAgent(),
]

_AGENT_MAP: Dict[str, BaseSpecialistAgent] = {a.agent_name: a for a in _AGENTS}


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class MultiAgentOrchestrator:
    """
    Routes each conversation turn to the best specialist agent
    based on FSM state and buyer context.

    In multi-agent mode (enabled in AgentConfiguration):
      - Orchestrator selects specialist agent
      - Specialist generates response via its own dedicated prompt
      - ConversationManager stitches tool calls + safety guard

    In single-agent mode (default):
      - ConversationManager handles everything via single GPT-4o call
    """

    def select_agent(self, current_state: str) -> Optional[BaseSpecialistAgent]:
        """Find the specialist agent that handles the current FSM state."""
        for agent in _AGENTS:
            if agent.can_handle(current_state):
                return agent
        return None

    def get_agent(self, name: str) -> Optional[BaseSpecialistAgent]:
        return _AGENT_MAP.get(name)

    def list_agents(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": a.agent_name,
                "handles_states": a.handles_states,
            }
            for a in _AGENTS
        ]
