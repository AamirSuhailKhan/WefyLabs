"""
Conversation Summary Writer — triggered every N turns or on escalation.

Extracts from raw conversation turns:
  - summary_text: compressed narrative of what happened
  - key_facts: budget, location, property type, timeline, purpose
  - objections: price, location, trust, financing concerns raised
  - buying_signals: enthusiasm, urgency, booking intent markers
  - properties_discussed: property IDs and names mentioned

Uses extractive summarization (no LLM required by default).
LLM-based summarization can be plugged in via the optional llm_summarize flag.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent_models import ConversationState, ConversationSummary


# ─── Keyword dictionaries ────────────────────────────────────────────────────

_OBJECTION_KEYWORDS = [
    "too expensive", "out of budget", "can't afford", "not sure", "maybe later",
    "need to think", "compare other", "not convinced", "bad location", "don't trust",
    "heard bad things", "developer issues", "loan problem", "mortgage issue",
    "financing problem", "overpriced", "better option", "competitor",
]

_BUYING_SIGNAL_KEYWORDS = [
    "interested", "i like", "looks good", "when can i visit", "book a viewing",
    "ready to buy", "let's proceed", "can we meet", "available", "check the price",
    "payment plan", "i'll take it", "move forward", "sign", "deal", "confirm",
    "deposit", "urgent", "as soon as possible", "immediately",
]

_PROPERTY_ID_PATTERN = re.compile(r"\b[Pp]rop[_-]?\d{4,}\b|\bPR\d{5,}\b")


class SummaryWriter:
    """
    Writes a ConversationSummary every summary_every_n_turns turns.
    Uses extractive NLP on raw turn text.
    """

    def __init__(self, summary_every_n_turns: int = 8):
        self.summary_every_n_turns = summary_every_n_turns

    def should_summarize(self, turn_count: int) -> bool:
        """Returns True if a summary should be written at this turn count."""
        return turn_count > 0 and turn_count % self.summary_every_n_turns == 0

    async def write_summary(
        self,
        db: AsyncSession,
        session_id: str,
        turns: List[ConversationState],
    ) -> Optional[ConversationSummary]:
        """
        Write a ConversationSummary for the given turns.
        Returns None if turns is empty.
        """
        if not turns:
            return None

        turn_start = turns[0].turn_index
        turn_end = turns[-1].turn_index

        # Build combined text for extraction
        all_text = " ".join(
            f"{t.customer_message or ''} {t.agent_response or ''}"
            for t in turns
        ).lower()

        # Extract objections
        objections_found = [kw for kw in _OBJECTION_KEYWORDS if kw in all_text]
        objections_json = {"detected": objections_found} if objections_found else {}

        # Extract buying signals
        signals_found = [kw for kw in _BUYING_SIGNAL_KEYWORDS if kw in all_text]
        buying_signals_json = {"detected": signals_found} if signals_found else {}

        # Extract property IDs mentioned
        prop_ids = _PROPERTY_ID_PATTERN.findall(all_text)
        properties_json = {"mentioned": list(set(prop_ids))} if prop_ids else {}

        # Build extractive summary narrative
        messages_preview = []
        for t in turns[-4:]:  # Last 4 turns for narrative
            if t.customer_message:
                messages_preview.append(f"Customer: {t.customer_message[:120]}")
            if t.agent_response:
                messages_preview.append(f"Agent: {t.agent_response[:120]}")

        summary_text = (
            f"Conversation turns {turn_start}–{turn_end}. "
            f"Objections detected: {objections_found or 'none'}. "
            f"Buying signals: {signals_found or 'none'}. "
            f"Properties discussed: {list(set(prop_ids)) or 'none'}. "
            f"Recent exchange: {' | '.join(messages_preview[-4:])}"
        )

        # Key facts extraction (from tool_calls JSON on turns)
        key_facts: Dict[str, Any] = {}
        for t in turns:
            if t.tools_called:
                for tool_call in (t.tools_called if isinstance(t.tools_called, list) else []):
                    if isinstance(tool_call, dict) and tool_call.get("tool") == "update_qualification":
                        key_facts.update(tool_call.get("output", {}))

        summary = ConversationSummary(
            session_id=session_id,
            turn_start=turn_start,
            turn_end=turn_end,
            summary_text=summary_text,
            key_facts_json=key_facts if key_facts else None,
            objections_json=objections_json if objections_json else None,
            buying_signals_json=buying_signals_json if buying_signals_json else None,
            properties_discussed_json=properties_json if properties_json else None,
        )
        db.add(summary)
        await db.flush()
        return summary

    async def write_escalation_summary(
        self,
        db: AsyncSession,
        session_id: str,
        turns: List[ConversationState],
        escalation_reason: str,
    ) -> Optional[ConversationSummary]:
        """Write a summary specifically for human handoff context."""
        summary = await self.write_summary(db, session_id, turns)
        if summary:
            summary.summary_text = (
                f"[ESCALATION: {escalation_reason}] " + summary.summary_text
            )
        return summary
