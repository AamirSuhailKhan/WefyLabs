"""
Volume 2 PART 5 — Autonomous AI Sales Agent Models
===================================================
SQLAlchemy 2.0 models for the AI Agent system:

 1. AgentSession          — One per lead per channel; persists FSM state across restarts
 2. ConversationState     — Immutable FSM transition log (full audit trail)
 3. QualificationProfile  — Structured buyer profile built incrementally across turns
 4. AgentMemory           — Long-term preference facts; never overwrite confirmed facts
 5. ConversationSummary   — Compressed window summary written every N turns or on escalation
 6. ToolExecution         — Immutable audit of every tool call (grounding source)
 7. PromptVersion         — Versioned system prompt templates per tenant
 8. DecisionRecord        — Immutable AI decision audit with reasoning
 9. Escalation            — Human handoff record with full context briefing
10. LLMUsage              — Per-call token + cost tracking for billing/monitoring
11. AgentConfiguration    — Per-tenant agent capability + model configuration
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float,
    JSON, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ─── 1. AgentSession ─────────────────────────────────────────────────────────

class AgentSession(Base):
    """
    One session per (lead, channel, organization) tuple.
    Persists FSM current state across server restarts.
    Restart-safe: ConversationManager loads this on every message.
    """
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # FSM state: new | greeting | discovering | qualifying | explaining |
    #            recommending | negotiating | booking | waiting |
    #            follow_up | human_handoff | closed
    current_state: Mapped[str] = mapped_column(String(30), nullable=False, default="new", index=True)
    strategy: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # buyer profiles: first_time_buyer | investor | luxury_buyer | nri | urgent_buyer | returning_customer
    buyer_profile: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_agent_sessions_org_lead", "organization_id", "lead_id"),
        Index("ix_agent_sessions_org_active", "organization_id", "is_active"),
    )


# ─── 2. ConversationState ────────────────────────────────────────────────────

class ConversationState(Base):
    """
    Immutable log of every FSM state transition.
    Each row is one turn (one customer message + one agent response).
    Append-only: never update existing rows.
    """
    __tablename__ = "conversation_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str] = mapped_column(String(30), nullable=False)
    to_state: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transition_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The raw customer message
    customer_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The agent response actually sent
    agent_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Tool calls made in this turn
    tools_called: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    # Metadata: intent signals, sentiment, confidence
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_conv_states_session_turn", "session_id", "turn_index"),
        UniqueConstraint("session_id", "turn_index", name="uq_conv_state_session_turn"),
    )


# ─── 3. QualificationProfile ─────────────────────────────────────────────────

class QualificationProfile(Base):
    """
    Structured buyer qualification data collected incrementally across turns.
    One profile per AgentSession. Updated (patched) as new facts are discovered.
    Covers all 18 qualification fields from the spec.
    """
    __tablename__ = "qualification_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Financial
    budget_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_cash_buyer: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    mortgage_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # pre_approved | in_process | not_started | not_required

    # Property
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    preferred_locations: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)  # list of areas
    preferred_amenities: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # Intent
    purpose: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # invest | end_user | both
    timeline: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # immediate | 1_month | 3_months | 6_months | 12_months
    expected_move_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Personal
    nationality: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    family_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_residence: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    previous_purchases: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Completion tracking
    fields_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fields_total: Mapped[int] = mapped_column(Integer, nullable=False, default=18)
    completion_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    qualified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


# ─── 4. AgentMemory ──────────────────────────────────────────────────────────

class AgentMemory(Base):
    """
    Long-term persistent memory facts per session.
    Facts are never overwritten once confidence >= 0.9.
    Instead, a new row is inserted with is_active=True and old row set to is_active=False.
    Source: conversation | crm | tool_call | human_agent
    """
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="conversation")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    superseded_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_agent_memory_session_key", "session_id", "fact_key"),
        Index("ix_agent_memory_lead_active", "lead_id", "is_active"),
    )


# ─── 5. ConversationSummary ──────────────────────────────────────────────────

class ConversationSummary(Base):
    """
    Compressed conversation window summary.
    Written every 8 turns or on escalation.
    Used to compress context window without losing business-critical facts.
    """
    __tablename__ = "conversation_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    turn_start: Mapped[int] = mapped_column(Integer, nullable=False)
    turn_end: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    key_facts_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    objections_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    buying_signals_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    properties_discussed_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_conv_summaries_session", "session_id", "turn_end"),
    )


# ─── 6. ToolExecution ────────────────────────────────────────────────────────

class ToolExecution(Base):
    """
    Immutable audit record of every tool call made by the AI agent.
    Grounding anchor: every factual claim in a response must link to a ToolExecution.
    Never updated after write.
    """
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    input_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    output_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Data source: property_service | crm_service | knowledge_base | booking_service
    data_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_tool_exec_session_tool", "session_id", "tool_name"),
    )


# ─── 7. PromptVersion ────────────────────────────────────────────────────────

class PromptVersion(Base):
    """
    Versioned system prompt templates.
    One active version per (prompt_key, organization_id) at any time.
    Enables A/B testing and rollback without code deployments.
    """
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)  # None = global default
    prompt_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    system_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)  # variable name → description
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_prompt_ver_key_org_active", "prompt_key", "organization_id", "is_active"),
    )


# ─── 8. DecisionRecord ───────────────────────────────────────────────────────

class DecisionRecord(Base):
    """
    Immutable audit of every AI decision with full reasoning chain.
    Required for CTO audit requirement: "Can managers audit every AI decision?"
    """
    __tablename__ = "decision_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Decision types: CONTINUE | RECOMMEND | BOOK | ESCALATE | SUMMARIZE | CLOSE | ASK_QUESTION
    decision_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    selected_action: Mapped[str] = mapped_column(String(60), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    alternative_actions_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    fsm_state_before: Mapped[str] = mapped_column(String(30), nullable=False)
    fsm_state_after: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_decision_rec_session_turn", "session_id", "turn_index"),
    )


# ─── 9. Escalation ───────────────────────────────────────────────────────────

class Escalation(Base):
    """
    Human handoff record.
    Created when the AI decides to escalate a conversation.
    Contains a full context briefing for the human agent.
    Status: pending | active | resolved
    Priority: low | medium | high | urgent
    """
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    # Reasons: human_requested | high_value_lead | low_confidence | complaint |
    #          legal_question | financial_advice | unsupported_request | inactivity
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium", index=True)
    # Human-readable briefing for the receiving agent
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    qualification_snapshot_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    conversation_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    recommended_actions_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    pending_questions_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_escalations_org_status", "organization_id", "status"),
        Index("ix_escalations_org_priority", "organization_id", "priority"),
    )


# ─── 10. LLMUsage ────────────────────────────────────────────────────────────

class LLMUsage(Base):
    """
    Per-call LLM token + cost + latency tracking.
    Used for billing dashboards, cost alerts, and model routing decisions.
    """
    __tablename__ = "llm_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # openai | anthropic | google | azure
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_llm_usage_org_provider", "organization_id", "provider"),
        Index("ix_llm_usage_session", "session_id"),
    )


# ─── 11. AgentConfiguration ──────────────────────────────────────────────────

class AgentConfiguration(Base):
    """
    Per-tenant agent configuration.
    Controls: enabled channels, LLM provider/model, max turns,
    escalation thresholds, and strategy overrides.
    One active configuration per organization.
    """
    __tablename__ = "agent_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False, default="WefyLabs AI Agent")
    enabled_channels_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)  # list of channel strings
    llm_provider: Mapped[str] = mapped_column(String(30), nullable=False, default="openai")
    llm_model: Mapped[str] = mapped_column(String(60), nullable=False, default="gpt-4o")
    fallback_provider: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="anthropic")
    fallback_model: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, default="claude-3-5-sonnet-20241022")
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_tokens_per_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    context_window_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    summary_every_n_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    # Escalation thresholds
    escalation_confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    escalation_high_value_score: Mapped[float] = mapped_column(Float, nullable=False, default=85.0)
    # Strategy overrides per buyer profile
    strategy_overrides_json: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    # Safety
    allow_price_disclosure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_tool_grounding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
