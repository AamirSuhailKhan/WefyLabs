"""
Decision Engine — decides the next agent action after each LLM response.

Decision types:
  CONTINUE       — Ask the next qualification question and keep the conversation going
  RECOMMEND      — Qualification is sufficient; present property recommendations
  BOOK           — Buyer has signaled intent to view; initiate booking flow
  ESCALATE       — Trigger human handoff (multiple conditions)
  SUMMARIZE      — Write a conversation summary (every N turns)
  CLOSE          — Mark conversation as closed
  ASK_QUESTION   — Ask a specific qualification question (returned with question text)

Every decision is persisted as a DecisionRecord for audit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.context_builder.builder import AgentContext
from app.modules.ai_agent.tool_executor.executor import ToolResult


# ─── Decision Result ──────────────────────────────────────────────────────────

@dataclass
class DecisionResult:
    decision_type: str                   # CONTINUE | RECOMMEND | BOOK | ESCALATE | SUMMARIZE | CLOSE | ASK_QUESTION
    selected_action: str                 # Human-readable action description
    reasoning: str                       # Explanation for audit
    confidence: float                    # 0.0 – 1.0
    should_escalate: bool = False
    escalation_reason: Optional[str] = None
    escalation_priority: str = "medium"
    should_summarize: bool = False
    next_question: Optional[str] = None
    fsm_trigger: Optional[str] = None   # FSM trigger to fire after this decision
    alternative_actions: List[str] = None

    def __post_init__(self):
        if self.alternative_actions is None:
            self.alternative_actions = []


# ─── Escalation Detector ─────────────────────────────────────────────────────

_HUMAN_REQUEST_KEYWORDS = [
    "talk to human", "speak to agent", "real person", "human agent",
    "transfer me", "connect me", "i want to speak", "call me",
    "your manager", "supervisor",
]

_COMPLAINT_KEYWORDS = [
    "complaint", "unhappy", "frustrated", "terrible", "worst",
    "unacceptable", "disgusted", "threatening",
]

_LEGAL_KEYWORDS = [
    "legal", "lawyer", "lawsuit", "court", "sue", "contract dispute",
    "breach", "nda", "illegal",
]

_FINANCIAL_ADVICE_KEYWORDS = [
    "should i invest", "will price go up", "guaranteed return", "sure profit",
    "financial advice", "portfolio advice", "wealth management",
]


class EscalationDetector:
    """Rule-based escalation triggers."""

    def detect(
        self,
        customer_message: str,
        ctx: AgentContext,
        llm_confidence: float,
        tool_results: List[ToolResult],
    ) -> tuple[bool, str, str]:
        """
        Returns (should_escalate, reason, priority).
        """
        msg_lower = customer_message.lower()

        # Human explicitly requested
        if any(kw in msg_lower for kw in _HUMAN_REQUEST_KEYWORDS):
            return True, "human_requested", "high"

        # Complaint sentiment
        if any(kw in msg_lower for kw in _COMPLAINT_KEYWORDS):
            return True, "complaint", "high"

        # Legal question
        if any(kw in msg_lower for kw in _LEGAL_KEYWORDS):
            return True, "legal_question", "urgent"

        # Financial advice request
        if any(kw in msg_lower for kw in _FINANCIAL_ADVICE_KEYWORDS):
            return True, "financial_advice", "medium"

        # High-value lead (score > threshold)
        if ctx.intelligence_score and ctx.intelligence_score >= ctx.escalation_high_value_score:
            return True, "high_value_lead", "urgent"

        # Low confidence
        if llm_confidence < ctx.escalation_confidence_threshold:
            return True, "low_confidence", "medium"

        return False, "", "medium"


# ─── Qualification Tracker ────────────────────────────────────────────────────

# Ordered by importance for each general strategy
_DEFAULT_QUESTION_SEQUENCE = [
    ("budget_min",           "What is your minimum budget?"),
    ("budget_max",           "What is your maximum budget for this property?"),
    ("property_type",        "Are you looking for an apartment, villa, or townhouse?"),
    ("bedrooms",             "How many bedrooms do you need?"),
    ("preferred_locations",  "Which areas or communities are you most interested in?"),
    ("purpose",              "Is this property for your own use or as an investment?"),
    ("timeline",             "When are you looking to complete the purchase?"),
    ("is_cash_buyer",        "Are you planning to pay cash, or will you need a mortgage?"),
    ("mortgage_status",      "Have you started the mortgage pre-approval process?"),
    ("nationality",          "May I ask your nationality? This helps with financing options."),
    ("family_size",          "How many family members will be living in the property?"),
    ("preferred_amenities",  "Are there specific amenities that are important to you — like a pool, gym, or school nearby?"),
    ("expected_move_date",   "When would you ideally like to move in?"),
    ("previous_purchases",   "Have you purchased property before?"),
]


class QualificationTracker:
    """Tracks qualification progress and generates the next best question."""

    def get_next_question(
        self,
        ctx: AgentContext,
        strategy_question_order: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Return the next qualification question to ask, or None if all collected.
        Respects strategy-specific question order.
        """
        if not ctx.fields_remaining:
            return None

        # Use strategy question order if provided
        if strategy_question_order:
            for field in strategy_question_order:
                if field in ctx.fields_remaining:
                    # Find question text
                    for f, q in _DEFAULT_QUESTION_SEQUENCE:
                        if f == field:
                            return q

        # Fall back to default sequence
        for field, question in _DEFAULT_QUESTION_SEQUENCE:
            if field in ctx.fields_remaining:
                return question

        return None

    def qualification_completion(self, ctx: AgentContext) -> float:
        return ctx.qualification_pct

    def is_ready_to_recommend(self, ctx: AgentContext) -> bool:
        """Returns True if enough qualification data exists to recommend properties."""
        qual = ctx.qualification or {}
        # Minimum: budget + property type + at least one location
        has_budget = bool(qual.get("budget_max") or qual.get("budget_min"))
        has_type = bool(qual.get("property_type"))
        has_location = bool(qual.get("preferred_locations"))
        return has_budget and (has_type or has_location)


# ─── Decision Engine ──────────────────────────────────────────────────────────

_BOOKING_SIGNAL_KEYWORDS = [
    "book", "viewing", "visit", "see the property", "schedule",
    "appointment", "tour", "when can i come", "i want to see",
    "take it", "i'll take", "confirm", "proceed", "deposit",
]


class DecisionEngine:
    """
    Decides next action after each LLM response and tool execution.
    Every decision includes reasoning for audit trail.
    """

    def __init__(self):
        self.escalation_detector = EscalationDetector()
        self.qualification_tracker = QualificationTracker()

    def decide(
        self,
        ctx: AgentContext,
        customer_message: str,
        llm_response_content: str,
        tool_results: List[ToolResult],
        llm_confidence: float = 0.7,
        strategy_question_order: Optional[List[str]] = None,
    ) -> DecisionResult:
        """
        Core decision logic. Called after every LLM response.
        Returns DecisionResult with action + FSM trigger.
        """
        msg_lower = customer_message.lower()

        # ── 1. Escalation check (highest priority) ────────────────────────────
        should_esc, esc_reason, esc_priority = self.escalation_detector.detect(
            customer_message, ctx, llm_confidence, tool_results
        )
        if should_esc:
            return DecisionResult(
                decision_type="ESCALATE",
                selected_action=f"escalate_to_human:{esc_reason}",
                reasoning=f"Escalation triggered: {esc_reason}. Confidence: {llm_confidence:.2f}",
                confidence=llm_confidence,
                should_escalate=True,
                escalation_reason=esc_reason,
                escalation_priority=esc_priority,
                fsm_trigger="HUMAN_REQUESTED",
            )

        # ── 2. Booking intent detected ─────────────────────────────────────────
        if any(kw in msg_lower for kw in _BOOKING_SIGNAL_KEYWORDS):
            return DecisionResult(
                decision_type="BOOK",
                selected_action="initiate_viewing_booking",
                reasoning="Buyer expressed viewing/booking intent in message.",
                confidence=0.85,
                fsm_trigger="RECOMMENDATION_ACCEPTED",
            )

        # ── 3. Booking tool executed successfully ──────────────────────────────
        booking_results = [r for r in tool_results if r.tool == "book_viewing" and r.success]
        if booking_results:
            return DecisionResult(
                decision_type="BOOK",
                selected_action="confirm_booking",
                reasoning="book_viewing tool executed successfully.",
                confidence=0.95,
                fsm_trigger="BOOKING_CONFIRMED",
            )

        # ── 4. Summarize trigger ───────────────────────────────────────────────
        if ctx.turn_count > 0 and ctx.turn_count % 8 == 0:
            return DecisionResult(
                decision_type="SUMMARIZE",
                selected_action="write_conversation_summary",
                reasoning=f"Turn {ctx.turn_count} — summary checkpoint reached.",
                confidence=1.0,
                should_summarize=True,
                # Continue conversation after summarizing
                fsm_trigger="INFO_COLLECTED",
            )

        # ── 5. Ready to recommend properties ──────────────────────────────────
        if self.qualification_tracker.is_ready_to_recommend(ctx):
            property_results = [r for r in tool_results if r.tool == "search_properties" and r.success]
            if property_results:
                return DecisionResult(
                    decision_type="RECOMMEND",
                    selected_action="present_property_recommendations",
                    reasoning="Qualification sufficient and property search results available.",
                    confidence=0.9,
                    fsm_trigger="PROPERTY_SHOWN",
                )
            else:
                return DecisionResult(
                    decision_type="RECOMMEND",
                    selected_action="search_and_recommend_properties",
                    reasoning="Qualification sufficient; triggering property search.",
                    confidence=0.85,
                    fsm_trigger="QUALIFIED",
                )

        # ── 6. Continue qualification ──────────────────────────────────────────
        next_q = self.qualification_tracker.get_next_question(ctx, strategy_question_order)
        return DecisionResult(
            decision_type="ASK_QUESTION" if next_q else "CONTINUE",
            selected_action="ask_qualification_question" if next_q else "continue_conversation",
            reasoning=(
                f"Qualification {ctx.qualification_pct:.0%} complete. "
                f"Next question: {next_q or 'None'}"
            ),
            confidence=0.8,
            next_question=next_q,
            fsm_trigger="INFO_COLLECTED",
        )
