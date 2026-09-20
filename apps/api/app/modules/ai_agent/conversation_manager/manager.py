"""
Conversation Manager — the central orchestrator for the Autonomous AI Sales Agent.

process(incoming) → OutgoingMessage:
  1.  Load or create AgentSession (restart-safe)
  2.  Restore FSM from DB
  3.  Build AgentContext from all CRM sources
  4.  Select/update conversation strategy
  5.  Build LLM prompt
  6.  Route to LLM
  7.  Execute tool calls (parallel reads, sequential writes)
  8.  Run response safety guard
  9.  Run decision engine
  10. Transition FSM state
  11. Persist ConversationState + DecisionRecord
  12. Trigger background workers (summary, CRM update, events)
  13. Return OutgoingMessage

Every step is auditable. No state is held in memory — all in DB.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent_models import (
    AgentSession, QualificationProfile, DecisionRecord, LLMUsage,
    ConversationState
)
from app.modules.ai_agent.state_machine.fsm import ConversationFSM, State, Trigger
from app.modules.ai_agent.state_machine.persistence import save_state, restore_state
from app.modules.ai_agent.context_builder.builder import ContextBuilder
from app.modules.ai_agent.strategy_engine.selector import StrategySelector
from app.modules.ai_agent.prompt_engine.builder import PromptBuilder
from app.modules.ai_agent.llm_router.router import LLMRouter, build_router_from_env
from app.modules.ai_agent.tool_executor.executor import ToolExecutor
from app.modules.ai_agent.tool_executor.registry import get_tool_definitions_for_llm
from app.modules.ai_agent.decision_engine.engine import DecisionEngine, DecisionResult
from app.modules.ai_agent.response_generator.safety_guard import ResponseSafetyGuard
from app.modules.ai_agent.handoff.handoff_service import HandoffService
from app.modules.ai_agent.memory_adapter.summary_writer import SummaryWriter
from app.modules.ai_agent.memory_adapter.long_term import bulk_write_facts
from app.modules.ai_agent.seeder import seed_default_agent_configuration


# ─── DTOs ─────────────────────────────────────────────────────────────────────

@dataclass
class IncomingMessage:
    """Channel-agnostic inbound message DTO."""
    lead_id: str
    organization_id: str
    channel: str                       # whatsapp | telegram | web | email
    content: str
    sender_phone: Optional[str] = None
    sender_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OutgoingMessage:
    """Channel-agnostic outbound message DTO."""
    session_id: str
    lead_id: str
    content: str
    channel: str
    turn_index: int
    current_state: str
    decision_type: str
    escalated: bool = False
    escalation_id: Optional[str] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    safety_violations: Optional[List[str]] = None
    was_blocked: bool = False


def _make_session_token(lead_id: str, organization_id: str, channel: str) -> str:
    raw = f"{organization_id}:{lead_id}:{channel}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


# ─── Conversation Manager ─────────────────────────────────────────────────────

class ConversationManager:
    """
    Central orchestrator. One instance per FastAPI application.
    All async I/O uses the injected SQLAlchemy AsyncSession.
    """

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self.context_builder = ContextBuilder()
        self.strategy_selector = StrategySelector()
        self.prompt_builder = PromptBuilder()
        self.llm_router = llm_router or build_router_from_env()
        self.tool_executor = ToolExecutor()
        self.decision_engine = DecisionEngine()
        self.safety_guard = ResponseSafetyGuard()
        self.handoff_service = HandoffService()
        self.summary_writer = SummaryWriter()

    async def process(
        self,
        db: AsyncSession,
        incoming: IncomingMessage,
    ) -> OutgoingMessage:
        """Process one customer message end-to-end. Returns OutgoingMessage."""

        # ── Step 1: Load or create AgentSession ─────────────────────────────
        token = _make_session_token(
            incoming.lead_id, incoming.organization_id, incoming.channel
        )
        session = await self._get_or_create_session(db, token, incoming)
        session_id = session.id

        # ── Step 2: Restore FSM ──────────────────────────────────────────────
        fsm = await restore_state(db, session_id)

        # Enforce Human Ownership: If session is currently escalated, autonomous AI is suppressed
        if session.escalated:
            return OutgoingMessage(
                session_id=session_id,
                lead_id=incoming.lead_id,
                content=(
                    "You are currently connected with a dedicated human property specialist. "
                    "They are reviewing your requirements and will respond shortly."
                ),
                channel=incoming.channel,
                turn_index=session.turn_count,
                current_state=session.current_state,
                decision_type="HUMAN_ACTIVE",
                escalated=True,
            )

        # Terminal sessions — return closed message
        if fsm.is_terminal() and session.current_state != State.HUMAN_HANDOFF:
            return OutgoingMessage(
                session_id=session_id,
                lead_id=incoming.lead_id,
                content="This conversation has been closed. Start a new chat to continue.",
                channel=incoming.channel,
                turn_index=session.turn_count,
                current_state=session.current_state,
                decision_type="CLOSE",
            )

        turn_index = session.turn_count + 1

        # ── Step 3: Build Context ────────────────────────────────────────────
        ctx = await self.context_builder.build(db=db, session=session)

        # ── Step 4: Select Strategy ──────────────────────────────────────────
        strategy = self.strategy_selector.select(ctx)
        if strategy.name != session.strategy:
            session.strategy = strategy.name
            session.buyer_profile = strategy.name

        # ── Step 5: First greeting transition ────────────────────────────────
        if fsm.current_state == State.NEW:
            fsm.transition(Trigger.GREETING_SENT, reason="Session initialized")

        # ── Step 6: Build Prompt ─────────────────────────────────────────────
        messages = await self.prompt_builder.build(
            db=db,
            ctx=ctx,
            strategy=strategy,
            customer_message=incoming.content,
        )

        # ── Step 7: Route to LLM ─────────────────────────────────────────────
        tools_def = get_tool_definitions_for_llm()
        llm_response = await self.llm_router.route(
            messages=messages,
            tools=tools_def,
            max_tokens=ctx.max_turns,  # max tokens per turn from config
            current_state=fsm.current_state,
        )

        # Check explicit customer booking confirmation from metadata
        is_confirmed_action = bool(
            incoming.metadata and (
                incoming.metadata.get("intent") in ("book_viewing", "confirm_booking", "confirm_viewing") or
                incoming.metadata.get("confirmed_action") is True
            )
        )

        if is_confirmed_action and incoming.metadata.get("property_id") and incoming.metadata.get("preferred_date"):
            has_booking_call = any(tc.get("name") == "book_viewing" for tc in (llm_response.tool_calls or []))
            if not has_booking_call:
                forced_call = {
                    "name": "book_viewing",
                    "arguments": {
                        "property_id": str(incoming.metadata["property_id"]),
                        "preferred_date": str(incoming.metadata["preferred_date"]),
                        "preferred_time": incoming.metadata.get("preferred_time"),
                        "notes": incoming.metadata.get("notes"),
                    }
                }
                if not llm_response.tool_calls:
                    llm_response.tool_calls = []
                llm_response.tool_calls.append(forced_call)

        # ── Step 8: Execute Tool Calls ────────────────────────────────────────
        tool_results = []
        if llm_response.tool_calls:
            tool_results = await self.tool_executor.run_parallel(
                db=db,
                session_id=session_id,
                turn_index=turn_index,
                tool_calls=llm_response.tool_calls,
                # The application, not the model, establishes this security
                # context. All tool handlers receive tenant and resource scope.
                context={
                    "organization_id": ctx.organization_id,
                    "enforce_tenant_scope": True,
                    "lead_id": ctx.lead_id,
                    "session_id": ctx.session_id,
                    "qualification": ctx.qualification or {},
                    "lead_data": {"name": ctx.lead_name, "phone": ctx.lead_phone},
                    "confirmed_action": is_confirmed_action,
                },
            )

            # If LLM called update_qualification, patch QualificationProfile
            for tc in llm_response.tool_calls:
                if tc["name"] == "update_qualification":
                    await self._patch_qualification(db, session, tc.get("arguments", {}))

            # If LLM called escalate_to_human, build second prompt pass with tool data
            esc_calls = [tc for tc in llm_response.tool_calls if tc["name"] == "escalate_to_human"]
            if esc_calls:
                messages2 = await self.prompt_builder.build(
                    db=db, ctx=ctx, strategy=strategy,
                    customer_message=incoming.content,
                    tool_results=[
                        {"tool": r.tool, "success": r.success, "result": r.result}
                        for r in tool_results
                    ],
                )
                llm_response = await self.llm_router.route(
                    messages=messages2, tools=None,
                    current_state=fsm.current_state,
                )

        # ── Step 9: Safety Guard ─────────────────────────────────────────────
        safety = self.safety_guard.validate(
            content=llm_response.content,
            tool_results=tool_results,
            channel=incoming.channel,
        )
        final_content = safety.final_content

        # ── Step 10: Decision Engine ─────────────────────────────────────────
        decision = self.decision_engine.decide(
            ctx=ctx,
            customer_message=incoming.content,
            llm_response_content=final_content,
            tool_results=tool_results,
            llm_confidence=0.8 if llm_response.success else 0.2,
            strategy_question_order=strategy.question_order,
        )

        # ── Step 11: FSM Transition ───────────────────────────────────────────
        if decision.fsm_trigger and fsm.can_transition(decision.fsm_trigger):
            fsm.transition(decision.fsm_trigger, reason=decision.reasoning)

        # ── Step 12: Handle Escalation ────────────────────────────────────────
        escalation_id: Optional[str] = None
        if decision.should_escalate:
            escalation = await self.handoff_service.create_escalation(
                db=db, ctx=ctx,
                reason=decision.escalation_reason or "unknown",
                priority=decision.escalation_priority,
            )
            escalation_id = escalation.id
            session.escalated = True
            if fsm.can_transition(Trigger.HUMAN_REQUESTED):
                fsm.transition(Trigger.HUMAN_REQUESTED, reason=decision.escalation_reason)

        # ── Step 13: Persist State ────────────────────────────────────────────
        tools_called_log = [
            {"tool": tc["name"], "args": tc.get("arguments", {})}
            for tc in (llm_response.tool_calls or [])
        ]
        await save_state(
            db=db,
            session_id=session_id,
            fsm=fsm,
            turn_index=turn_index,
            customer_message=incoming.content,
            agent_response=final_content,
            tools_called={"calls": tools_called_log},
            trigger=decision.fsm_trigger,
            reason=decision.reasoning,
        )

        # ── Step 14: Persist Decision Record ──────────────────────────────────
        decision_record = DecisionRecord(
            session_id=session_id,
            turn_index=turn_index,
            decision_type=decision.decision_type,
            selected_action=decision.selected_action,
            reasoning=decision.reasoning,
            confidence=decision.confidence,
            alternative_actions_json={"alternatives": decision.alternative_actions},
            fsm_state_before=ctx.current_state,
            fsm_state_after=fsm.current_state,
        )
        db.add(decision_record)

        # ── Step 15: Persist LLM Usage ────────────────────────────────────────
        llm_usage = LLMUsage(
            session_id=session_id,
            organization_id=incoming.organization_id,
            turn_index=turn_index,
            provider=llm_response.provider,
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            cost_usd=llm_response.cost_usd,
            latency_ms=llm_response.latency_ms,
            success=llm_response.success,
        )
        db.add(llm_usage)

        # ── Step 16: Summarize if needed ──────────────────────────────────────
        if decision.should_summarize:
            from sqlalchemy import desc
            turns_result = await db.execute(
                select(ConversationState)
                .where(ConversationState.session_id == session_id)
                .order_by(desc(ConversationState.turn_index))
                .limit(8)
            )
            recent_turns = list(reversed(turns_result.scalars().all()))
            await self.summary_writer.write_summary(db, session_id, recent_turns)

        await db.commit()

        return OutgoingMessage(
            session_id=session_id,
            lead_id=incoming.lead_id,
            content=final_content,
            channel=incoming.channel,
            turn_index=turn_index,
            current_state=fsm.current_state,
            decision_type=decision.decision_type,
            escalated=decision.should_escalate,
            escalation_id=escalation_id,
            tool_results=[
                {"tool": r.tool, "success": r.success, "result": r.result}
                for r in tool_results
            ],
            safety_violations=safety.violations if safety.violations else None,
            was_blocked=safety.was_blocked,
        )

    async def _get_or_create_session(
        self,
        db: AsyncSession,
        token: str,
        incoming: IncomingMessage,
    ) -> AgentSession:
        """Load existing session or create a new one. Restart-safe."""
        # A client may never pair an arbitrary lead ID with an arbitrary
        # organization. Resolve ownership from the canonical CRM record before
        # creating or resuming a conversation session.
        from app.models.lead import Lead
        import uuid as _uuid
        try:
            l_uuid = _uuid.UUID(str(incoming.lead_id))
        except Exception:
            l_uuid = incoming.lead_id
        lead_result = await db.execute(select(Lead).where(Lead.id == l_uuid))
        lead = lead_result.scalar_one_or_none()
        if not lead or str(lead.broker_id) != str(incoming.organization_id):
            raise PermissionError("Lead is not available in this organization")

        result = await db.execute(
            select(AgentSession).where(AgentSession.session_token == token)
        )
        session = result.scalar_one_or_none()
        if session:
            return session

        session = AgentSession(
            session_token=token,
            organization_id=incoming.organization_id,
            lead_id=incoming.lead_id,
            channel=incoming.channel,
            current_state=State.NEW,
        )
        db.add(session)
        await db.flush()

        # Create qualification profile
        qual = QualificationProfile(
            session_id=session.id,
            organization_id=incoming.organization_id,
            lead_id=incoming.lead_id,
        )
        db.add(qual)
        await db.flush()

        # Ensure default AgentConfiguration exists for this org (idempotent)
        await seed_default_agent_configuration(db, incoming.organization_id)

        return session

    async def _patch_qualification(
        self,
        db: AsyncSession,
        session: AgentSession,
        updates: Dict[str, Any],
    ) -> None:
        """Patch QualificationProfile with new fields from tool call arguments."""
        from sqlalchemy import update
        if not updates:
            return

        # Calculate completion percentage
        TOTAL_FIELDS = 17
        result = await db.execute(
            select(QualificationProfile).where(
                QualificationProfile.session_id == session.id
            )
        )
        qual = result.scalar_one_or_none()
        if not qual:
            return

        field_map = {
            "budget_min": "budget_min",
            "budget_max": "budget_max",
            "budget_currency": "budget_currency",
            "is_cash_buyer": "is_cash_buyer",
            "mortgage_status": "mortgage_status",
            "property_type": "property_type",
            "bedrooms": "bedrooms",
            "bathrooms": "bathrooms",
            "preferred_locations": "preferred_locations",
            "preferred_amenities": "preferred_amenities",
            "purpose": "purpose",
            "timeline": "timeline",
            "expected_move_date": "expected_move_date",
            "nationality": "nationality",
            "family_size": "family_size",
            "current_residence": "current_residence",
            "previous_purchases": "previous_purchases",
        }
        for api_key, db_field in field_map.items():
            if api_key in updates and updates[api_key] is not None:
                setattr(qual, db_field, updates[api_key])

        # Recalculate completion
        filled = sum(
            1 for f in field_map.values()
            if getattr(qual, f, None) is not None
        )
        qual.fields_collected = filled
        qual.completion_pct = round(filled / TOTAL_FIELDS * 100, 1)
        qual.is_qualified = qual.completion_pct >= 50.0
        await db.flush()
