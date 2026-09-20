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

    Uses a dedicated LLM call with a qualification-specific prompt to:
    1. Extract structured buyer facts from the customer's message
    2. Call update_qualification with the extracted data
    3. Ask the single most important missing question
    """
    @property
    def agent_name(self) -> str:
        return "qualification_agent"

    @property
    def handles_states(self) -> List[str]:
        return ["discovering", "qualifying"]

    async def process(self, ctx: AgentContext, customer_message: str) -> Dict[str, Any]:
        """
        Run a focused qualification LLM pass.

        Returns update_qualification tool call arguments extracted from the
        customer message, plus a natural next question for any missing field.
        Falls back gracefully when LLM is unavailable.
        """
        import logging
        _log = logging.getLogger("wefylabs.orchestrator.qualification")

        qual = ctx.qualification or {}
        collected_facts = {k: v for k, v in qual.items() if v is not None}
        fields_needed = ctx.fields_remaining or []
        next_priority = fields_needed[0] if fields_needed else None

        # ── Build qualification extraction prompt ──────────────────────────
        system_prompt = (
            "You are a real estate buyer qualification specialist. "
            "Extract ONLY buyer facts explicitly stated in the customer message. "
            "Do NOT invent or assume facts not present in the message. "
            "Return a JSON object with ONLY the fields the customer explicitly mentioned.\n\n"
            "Fields you may extract: budget_min, budget_max, budget_currency, "
            "is_cash_buyer, mortgage_status, property_type, bedrooms, bathrooms, "
            "preferred_locations (array), purpose (invest|end_user|both), "
            "timeline, nationality, family_size.\n\n"
            "Respond with ONLY valid JSON. Example:\n"
            '{"bedrooms": 3, "preferred_locations": ["Noida"], "budget_max": 15000000}\n\n'
            "If no facts are present, respond with: {}"
        )
        user_prompt = (
            f"Customer message: {customer_message}\n\n"
            f"Already collected: {collected_facts}\n"
            f"Extract NEW facts only from the customer message above."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # ── Call LLM for extraction ────────────────────────────────────────
        extracted_args: Dict[str, Any] = {}
        try:
            from app.modules.ai_agent.llm_router.router import build_router_from_env
            router = build_router_from_env()
            llm_resp = await router.route(
                messages=messages,
                tools=None,         # Pure extraction pass — no tools needed
                max_tokens=256,     # Small; just JSON output
                temperature=0.1,    # Low temperature for deterministic extraction
            )
            if llm_resp.success and llm_resp.content:
                import json
                # Strip markdown fences if model wrapped in ```json ... ```
                raw = llm_resp.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                extracted_args = json.loads(raw.strip()) or {}
                _log.debug(f"[QualificationAgent] Extracted: {extracted_args}")
        except Exception as exc:
            _log.warning(f"[QualificationAgent] LLM extraction failed: {exc}")

        # ── Build the next qualification question ──────────────────────────
        FIELD_QUESTIONS: Dict[str, str] = {
            "budget_min": "What is your minimum budget for this property?",
            "budget_max": "What is your approximate budget for this property?",
            "bedrooms": "How many bedrooms are you looking for?",
            "property_type": "Are you looking for an apartment, villa, or townhouse?",
            "preferred_locations": "Which areas or localities are you most interested in?",
            "purpose": "Is this property for your own use or as an investment?",
            "timeline": "When are you planning to move in or complete the purchase?",
            "is_cash_buyer": "Are you planning to pay cash or use a home loan?",
            "mortgage_status": "Have you been pre-approved for a home loan?",
            "nationality": "May I ask your nationality? It helps with ownership requirements.",
        }

        # Pick the next question — prefer fields the LLM didn't just extract
        remaining_after_extraction = [
            f for f in fields_needed
            if f not in extracted_args and f in FIELD_QUESTIONS
        ]
        next_question = None
        if remaining_after_extraction:
            next_question = FIELD_QUESTIONS[remaining_after_extraction[0]]
        elif next_priority and next_priority in FIELD_QUESTIONS:
            next_question = FIELD_QUESTIONS[next_priority]

        # ── Determine if qualified after this extraction ───────────────────
        updated_facts = {**collected_facts, **extracted_args}
        REQUIRED_FOR_QUALIFICATION = {
            "budget_max", "property_type", "preferred_locations"
        }
        now_qualified = all(updated_facts.get(f) for f in REQUIRED_FOR_QUALIFICATION)

        # ── Construct response text ────────────────────────────────────────
        if next_question:
            response_text = next_question
        elif now_qualified:
            response_text = (
                "Thank you! I have enough information to find matching properties for you. "
                "Let me search our verified inventory now."
            )
        else:
            response_text = "Could you share a bit more about what you're looking for?"

        return {
            "response": response_text,
            "tool_calls": [{"name": "update_qualification", "arguments": extracted_args}],
            "handoff_to": "property_agent" if now_qualified else None,
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
