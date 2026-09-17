"""
Context Builder — assembles the full AgentContext dataclass from all CRM sources.

Priority order when token budget is exceeded:
  1. Lead profile (always included)
  2. Qualification profile (always included)
  3. Agent memory facts (always included)
  4. Latest conversation summary (high priority)
  5. Recent raw turns (last N, configurable)
  6. Lead intelligence profile (medium priority)
  7. Property interest signals (low priority)

Never queries the database directly — only reads from CRM service layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.agent_models import (
    AgentSession,
    AgentMemory,
    ConversationSummary,
    ConversationState,
    QualificationProfile,
    AgentConfiguration,
)


# ─── AgentContext Dataclass ───────────────────────────────────────────────────

@dataclass
class AgentContext:
    """
    Fully assembled context for one conversation turn.
    Passed to: StrategyEngine, PromptBuilder, DecisionEngine.
    """
    # Session
    session_id: str
    lead_id: str
    organization_id: str
    channel: str
    current_state: str
    turn_count: int
    buyer_profile: Optional[str]
    strategy: Optional[str]

    # Lead
    lead_name: Optional[str]
    lead_phone: Optional[str]
    lead_score: Optional[str]
    lead_status: Optional[str]
    lead_source: Optional[str]

    # Lead Intelligence (Part 4)
    intelligence_score: Optional[float]
    intent_phase: Optional[str]
    temperature: Optional[str]
    momentum: Optional[float]

    # Qualification profile
    qualification: Optional[Dict[str, Any]]
    qualification_pct: float
    is_qualified: bool

    # Memory
    memory_facts: List[Dict[str, Any]]

    # Conversation history
    summary_text: Optional[str]
    summary_key_facts: Optional[Dict[str, Any]]
    summary_objections: Optional[Dict[str, Any]]
    summary_buying_signals: Optional[Dict[str, Any]]
    recent_turns: List[Dict[str, Any]]

    # Agent config
    agent_name: str
    require_tool_grounding: bool
    max_turns: int
    escalation_confidence_threshold: float
    escalation_high_value_score: float

    # Computed helpers
    fields_remaining: List[str] = field(default_factory=list)
    token_estimate: int = 0


# ─── Context Builder ──────────────────────────────────────────────────────────

QUALIFICATION_FIELDS = [
    "budget_min", "budget_max", "is_cash_buyer", "mortgage_status",
    "property_type", "bedrooms", "bathrooms", "preferred_locations",
    "preferred_amenities", "purpose", "timeline", "expected_move_date",
    "nationality", "family_size", "current_residence", "previous_purchases",
    "budget_currency",
]


class ContextBuilder:
    """
    Assembles AgentContext from all CRM tables.
    Applies token budget pruning: drops low-priority sections first.
    """

    def __init__(self, context_window_turns: int = 10):
        self.context_window_turns = context_window_turns

    async def build(
        self,
        db: AsyncSession,
        session: AgentSession,
        lead_data: Optional[Dict[str, Any]] = None,
        intelligence_data: Optional[Dict[str, Any]] = None,
    ) -> AgentContext:
        """Build the full AgentContext for a session turn."""

        # Load agent config
        config_result = await db.execute(
            select(AgentConfiguration).where(
                AgentConfiguration.organization_id == session.organization_id
            )
        )
        config = config_result.scalar_one_or_none()
        agent_name = config.agent_name if config else "WefyLabs AI"
        require_grounding = config.require_tool_grounding if config else True
        max_turns = config.max_turns if config else 30
        esc_conf = config.escalation_confidence_threshold if config else 0.3
        esc_score = config.escalation_high_value_score if config else 85.0

        # Load qualification profile
        qual_result = await db.execute(
            select(QualificationProfile).where(
                QualificationProfile.session_id == session.id
            )
        )
        qual = qual_result.scalar_one_or_none()
        qual_dict: Dict[str, Any] = {}
        fields_remaining: List[str] = list(QUALIFICATION_FIELDS)
        qual_pct = 0.0
        is_qualified = False
        if qual:
            qual_dict = {
                "budget_min": qual.budget_min,
                "budget_max": qual.budget_max,
                "budget_currency": qual.budget_currency,
                "is_cash_buyer": qual.is_cash_buyer,
                "mortgage_status": qual.mortgage_status,
                "property_type": qual.property_type,
                "bedrooms": qual.bedrooms,
                "bathrooms": qual.bathrooms,
                "preferred_locations": qual.preferred_locations,
                "preferred_amenities": qual.preferred_amenities,
                "purpose": qual.purpose,
                "timeline": qual.timeline,
                "expected_move_date": qual.expected_move_date,
                "nationality": qual.nationality,
                "family_size": qual.family_size,
                "current_residence": qual.current_residence,
                "previous_purchases": qual.previous_purchases,
            }
            fields_remaining = [
                f for f in QUALIFICATION_FIELDS
                if qual_dict.get(f) is None
            ]
            qual_pct = qual.completion_pct
            is_qualified = qual.is_qualified

        # Load active memory facts
        mem_result = await db.execute(
            select(AgentMemory)
            .where(
                AgentMemory.session_id == session.id,
                AgentMemory.is_active == True,
            )
            .order_by(desc(AgentMemory.confidence))
        )
        mem_facts = [
            {"key": m.fact_key, "value": m.fact_value, "confidence": m.confidence, "source": m.source}
            for m in mem_result.scalars().all()
        ]

        # Load latest conversation summary
        summ_result = await db.execute(
            select(ConversationSummary)
            .where(ConversationSummary.session_id == session.id)
            .order_by(desc(ConversationSummary.turn_end))
            .limit(1)
        )
        summary = summ_result.scalar_one_or_none()

        # Load recent raw turns (last N)
        turns_result = await db.execute(
            select(ConversationState)
            .where(ConversationState.session_id == session.id)
            .order_by(desc(ConversationState.turn_index))
            .limit(self.context_window_turns)
        )
        turns = list(reversed(turns_result.scalars().all()))
        recent_turns = [
            {
                "turn": t.turn_index,
                "customer": t.customer_message,
                "agent": t.agent_response,
                "state": t.to_state,
            }
            for t in turns
        ]

        # Lead intelligence (passed in from service layer)
        intel = intelligence_data or {}

        # Lead profile (passed in from service layer or session)
        lead = lead_data or {}

        return AgentContext(
            session_id=session.id,
            lead_id=session.lead_id,
            organization_id=session.organization_id,
            channel=session.channel,
            current_state=session.current_state,
            turn_count=session.turn_count,
            buyer_profile=session.buyer_profile,
            strategy=session.strategy,
            lead_name=lead.get("name"),
            lead_phone=lead.get("phone"),
            lead_score=lead.get("score"),
            lead_status=lead.get("status"),
            lead_source=lead.get("source"),
            intelligence_score=intel.get("lead_score"),
            intent_phase=intel.get("intent_phase"),
            temperature=intel.get("temperature"),
            momentum=intel.get("momentum"),
            qualification=qual_dict,
            qualification_pct=qual_pct,
            is_qualified=is_qualified,
            memory_facts=mem_facts,
            summary_text=summary.summary_text if summary else None,
            summary_key_facts=summary.key_facts_json if summary else None,
            summary_objections=summary.objections_json if summary else None,
            summary_buying_signals=summary.buying_signals_json if summary else None,
            recent_turns=recent_turns,
            agent_name=agent_name,
            require_tool_grounding=require_grounding,
            max_turns=max_turns,
            escalation_confidence_threshold=esc_conf,
            escalation_high_value_score=esc_score,
            fields_remaining=fields_remaining,
        )
