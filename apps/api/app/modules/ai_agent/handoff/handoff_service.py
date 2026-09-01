"""
Human Handoff Service — creates Escalation records with full context briefing.

The briefing gives the receiving broker:
  - Who the buyer is (profile, budget, intent)
  - What properties they discussed
  - What objections they raised
  - What the AI recommended
  - What still needs to happen
  - Full conversation transcript (last 20 turns)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.agent_models import AgentSession, ConversationState, QualificationProfile, Escalation
from app.modules.ai_agent.context_builder.builder import AgentContext


class HandoffService:
    """Creates escalation records with fully-assembled briefings."""

    async def create_escalation(
        self,
        db: AsyncSession,
        ctx: AgentContext,
        reason: str,
        priority: str = "medium",
        notes: Optional[str] = None,
    ) -> Escalation:
        """
        Create an Escalation record.
        Loads recent conversation turns for transcript.
        Builds human-readable briefing.
        """
        # Load last 20 conversation turns for transcript
        turns_result = await db.execute(
            select(ConversationState)
            .where(ConversationState.session_id == ctx.session_id)
            .order_by(desc(ConversationState.turn_index))
            .limit(20)
        )
        turns = list(reversed(turns_result.scalars().all()))

        conversation_json = [
            {
                "turn": t.turn_index,
                "state": t.to_state,
                "customer": t.customer_message,
                "agent": t.agent_response,
            }
            for t in turns
        ]

        # Build human-readable briefing
        summary = self._build_briefing(ctx, reason, turns, notes)

        # Qualification snapshot
        qual_snapshot = ctx.qualification or {}

        # Recommended actions for human agent
        recommended_actions = self._recommended_actions(ctx, reason)

        # Pending questions
        pending_questions = [
            q for _, q in [
                ("budget_min", "What is your exact budget?"),
                ("purpose", "Is this for investment or personal use?"),
                ("timeline", "When do you need to complete the purchase?"),
            ]
            if _ in (ctx.fields_remaining or [])
        ]

        escalation = Escalation(
            session_id=ctx.session_id,
            organization_id=ctx.organization_id,
            lead_id=ctx.lead_id,
            reason=reason,
            priority=priority,
            summary=summary,
            qualification_snapshot_json=qual_snapshot,
            conversation_json={"turns": conversation_json},
            recommended_actions_json={"actions": recommended_actions},
            pending_questions_json={"questions": pending_questions},
            status="pending",
        )
        db.add(escalation)
        await db.flush()
        return escalation

    def _build_briefing(
        self,
        ctx: AgentContext,
        reason: str,
        turns: List[ConversationState],
        notes: Optional[str],
    ) -> str:
        """Build a concise, human-readable briefing paragraph."""
        qual = ctx.qualification or {}
        parts = [f"🔔 ESCALATION — Reason: {reason.upper().replace('_', ' ')}"]
        parts.append(f"Lead: {ctx.lead_name or 'Unknown'} | Phone: {ctx.lead_phone or 'N/A'}")
        parts.append(f"Channel: {ctx.channel} | Turn #{ctx.turn_count} | Strategy: {ctx.strategy or 'N/A'}")

        if qual.get("budget_max"):
            currency = qual.get("budget_currency", "")
            parts.append(f"Budget: {currency} {qual.get('budget_min', '?')} – {qual.get('budget_max', '?')}")
        if qual.get("property_type"):
            parts.append(f"Looking for: {qual['property_type']} | {qual.get('bedrooms', '?')}BR")
        if qual.get("preferred_locations"):
            parts.append(f"Preferred areas: {qual['preferred_locations']}")
        if qual.get("purpose"):
            parts.append(f"Purpose: {qual['purpose']}")
        if qual.get("timeline"):
            parts.append(f"Timeline: {qual['timeline']}")
        if qual.get("is_cash_buyer") is not None:
            parts.append(f"Cash buyer: {qual['is_cash_buyer']}")

        if ctx.summary_text:
            parts.append(f"\nConversation context: {ctx.summary_text[:300]}")

        if notes:
            parts.append(f"\nAdditional notes: {notes}")

        parts.append(f"\nQualification: {ctx.qualification_pct:.0%} complete")
        if ctx.intelligence_score:
            parts.append(f"AI Lead Score: {ctx.intelligence_score:.0f}/100 | Temperature: {ctx.temperature}")

        return "\n".join(parts)

    def _recommended_actions(self, ctx: AgentContext, reason: str) -> List[str]:
        """Generate recommended actions for the human agent."""
        actions = []
        qual = ctx.qualification or {}

        if reason == "high_value_lead":
            actions.append("Priority callback within 30 minutes")
            actions.append("Offer private viewing with senior broker")
        elif reason == "complaint":
            actions.append("Acknowledge complaint immediately")
            actions.append("Escalate to manager if unresolved in 15 minutes")
        elif reason == "legal_question":
            actions.append("Transfer to legal/compliance team")
            actions.append("Do not provide any legal opinions — refer to approved counsel")
        elif reason == "financial_advice":
            actions.append("Refer to certified financial advisor")
            actions.append("Share approved market report documents only")
        else:
            actions.append("Resume qualification from where the AI left off")

        if not qual.get("budget_max"):
            actions.append("Clarify budget range")
        if not qual.get("preferred_locations"):
            actions.append("Confirm preferred locations")
        if ctx.qualification_pct >= 0.7:
            actions.append("Ready for property recommendation — suggest 2-3 units")

        return actions
