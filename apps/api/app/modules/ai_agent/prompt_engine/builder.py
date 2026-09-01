"""
Prompt Builder — assembles the full LLM message list for one conversation turn.

Message list structure:
  1. System message (from PromptVersion or built-in default)
  2. Assistant message: conversation summary (if available)
  3. Human/Assistant alternating turns (recent window)
  4. Human message: current customer message

All template variables are filled from AgentContext and ConversationStrategy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent_models import PromptVersion
from app.modules.ai_agent.context_builder.builder import AgentContext
from app.modules.ai_agent.strategy_engine.strategies import ConversationStrategy
from app.modules.ai_agent.prompt_engine.templates import (
    SALES_AGENT_SYSTEM_PROMPT,
    SALES_AGENT_PROMPT_KEY,
)


# ─── LLM Message Format ───────────────────────────────────────────────────────

def _msg(role: str, content: str) -> Dict[str, str]:
    return {"role": role, "content": content}


# ─── Prompt Builder ───────────────────────────────────────────────────────────

class PromptBuilder:
    """
    Builds the full messages list for LLM completion.
    Loads active prompt version from DB; falls back to built-in template.
    """

    async def build(
        self,
        db: AsyncSession,
        ctx: AgentContext,
        strategy: ConversationStrategy,
        customer_message: str,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        """
        Build messages list for LLM.
        Returns list of {role, content} dicts.
        """
        system_template = await self._load_template(db, ctx.organization_id)
        system_content = self._fill_template(system_template, ctx, strategy)

        messages: List[Dict[str, str]] = [_msg("system", system_content)]

        # Conversation summary as assistant context injection
        if ctx.summary_text:
            messages.append(_msg(
                "assistant",
                f"[CONVERSATION SUMMARY]: {ctx.summary_text}"
            ))

        # Recent conversation turns (sliding window)
        for turn in ctx.recent_turns:
            if turn.get("customer"):
                messages.append(_msg("user", turn["customer"]))
            if turn.get("agent"):
                messages.append(_msg("assistant", turn["agent"]))

        # Tool results injection (before current user message)
        if tool_results:
            tool_content = "\n".join(
                f"[TOOL: {r['tool']} → {'OK' if r['success'] else 'ERROR'}]\n{r.get('result', r.get('error', ''))}"
                for r in tool_results
            )
            messages.append(_msg("system", f"[VERIFIED TOOL DATA]:\n{tool_content}"))

        # Current customer message
        messages.append(_msg("user", customer_message))

        return messages

    async def _load_template(
        self, db: AsyncSession, organization_id: str
    ) -> str:
        """
        Load the active PromptVersion from DB for this organization.
        Falls back to org-agnostic global version, then built-in default.
        """
        # Try org-specific active version
        result = await db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.prompt_key == SALES_AGENT_PROMPT_KEY,
                PromptVersion.organization_id == organization_id,
                PromptVersion.is_active == True,
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        pv = result.scalar_one_or_none()
        if pv:
            return pv.system_template

        # Try global (organization_id=None) version
        global_result = await db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.prompt_key == SALES_AGENT_PROMPT_KEY,
                PromptVersion.organization_id.is_(None),
                PromptVersion.is_active == True,
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        global_pv = global_result.scalar_one_or_none()
        if global_pv:
            return global_pv.system_template

        # Built-in default
        return SALES_AGENT_SYSTEM_PROMPT

    def _fill_template(
        self,
        template: str,
        ctx: AgentContext,
        strategy: ConversationStrategy,
    ) -> str:
        """Fill all template variables from context and strategy."""

        # Qualification summary
        qual = ctx.qualification or {}
        qual_lines = []
        if qual.get("budget_min") or qual.get("budget_max"):
            currency = qual.get("budget_currency", "")
            qual_lines.append(
                f"Budget: {currency} {qual.get('budget_min', '?')} – {qual.get('budget_max', '?')}"
            )
        if qual.get("property_type"):
            qual_lines.append(f"Property type: {qual['property_type']}")
        if qual.get("bedrooms"):
            qual_lines.append(f"Bedrooms: {qual['bedrooms']}")
        if qual.get("preferred_locations"):
            qual_lines.append(f"Locations: {qual['preferred_locations']}")
        if qual.get("purpose"):
            qual_lines.append(f"Purpose: {qual['purpose']}")
        if qual.get("timeline"):
            qual_lines.append(f"Timeline: {qual['timeline']}")
        if qual.get("is_cash_buyer") is not None:
            qual_lines.append(f"Cash buyer: {qual['is_cash_buyer']}")
        if qual.get("nationality"):
            qual_lines.append(f"Nationality: {qual['nationality']}")

        qualification_summary = "\n".join(qual_lines) if qual_lines else "No qualification data yet."

        # Memory facts
        mem_lines = [
            f"• {f['key']}: {f['value']} (confidence: {f['confidence']:.0%}, source: {f['source']})"
            for f in (ctx.memory_facts or [])
        ]
        memory_facts = "\n".join(mem_lines) if mem_lines else "No memory facts yet."

        # Conversation summary
        conv_summary_section = ""
        if ctx.summary_text:
            conv_summary_section = (
                f"\n[PREVIOUS CONVERSATION SUMMARY]:\n{ctx.summary_text}\n"
            )

        variables = {
            "agent_name": ctx.agent_name,
            "org_name": ctx.organization_id,  # replaced with org name in production
            "strategy_name": strategy.display_name,
            "tone_directive": strategy.tone_directive,
            "intro_hook": strategy.intro_hook,
            "qualification_fields_remaining": ", ".join(ctx.fields_remaining) or "All fields collected!",
            "qualification_summary": qualification_summary,
            "memory_facts": memory_facts,
            "conversation_summary": conv_summary_section,
            "objection_approach": strategy.objection_approach,
            "focus_areas": ", ".join(strategy.focus_areas),
        }

        try:
            return template.format(**variables)
        except KeyError:
            # If custom template has missing variables, return as-is
            return template
