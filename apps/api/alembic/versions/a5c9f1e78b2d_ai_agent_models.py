"""Alembic migration: Volume 2 Part 5 — AI Agent Models (11 tables)

Revision ID: a5c9f1e78b2d
Revises: (previous migration)
Create Date: 2026-08-04

Tables created:
- agent_sessions
- conversation_states
- qualification_profiles
- agent_memories
- conversation_summaries
- tool_executions
- prompt_versions
- decision_records
- escalations
- llm_usage
- agent_configurations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "a5c9f1e78b2d"
down_revision = None  # set to previous migration ID
branch_labels = None
depends_on = None

JSONB = sa.JSON()  # JSONB for PostgreSQL, JSON for SQLite


def upgrade() -> None:

    # ── 1. agent_sessions ────────────────────────────────────────────────────
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_token", sa.String(128), nullable=False, unique=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("current_state", sa.String(30), nullable=False, server_default="new"),
        sa.Column("strategy", sa.String(30), nullable=True),
        sa.Column("buyer_profile", sa.String(30), nullable=True),
        sa.Column("turn_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_sessions_token", "agent_sessions", ["session_token"])
    op.create_index("ix_agent_sessions_org_lead", "agent_sessions", ["organization_id", "lead_id"])
    op.create_index("ix_agent_sessions_org_active", "agent_sessions", ["organization_id", "is_active"])

    # ── 2. conversation_states ────────────────────────────────────────────────
    op.create_table(
        "conversation_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("from_state", sa.String(30), nullable=False),
        sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=True),
        sa.Column("transition_reason", sa.Text, nullable=True),
        sa.Column("customer_message", sa.Text, nullable=True),
        sa.Column("agent_response", sa.Text, nullable=True),
        sa.Column("tools_called", JSONB, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conv_states_session_turn", "conversation_states", ["session_id", "turn_index"])
    op.create_unique_constraint("uq_conv_state_session_turn", "conversation_states", ["session_id", "turn_index"])

    # ── 3. qualification_profiles ────────────────────────────────────────────
    op.create_table(
        "qualification_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("budget_min", sa.Integer, nullable=True),
        sa.Column("budget_max", sa.Integer, nullable=True),
        sa.Column("budget_currency", sa.String(10), nullable=True),
        sa.Column("is_cash_buyer", sa.Boolean, nullable=True),
        sa.Column("mortgage_status", sa.String(30), nullable=True),
        sa.Column("property_type", sa.String(50), nullable=True),
        sa.Column("bedrooms", sa.Integer, nullable=True),
        sa.Column("bathrooms", sa.Integer, nullable=True),
        sa.Column("preferred_locations", JSONB, nullable=True),
        sa.Column("preferred_amenities", JSONB, nullable=True),
        sa.Column("purpose", sa.String(20), nullable=True),
        sa.Column("timeline", sa.String(30), nullable=True),
        sa.Column("expected_move_date", sa.String(30), nullable=True),
        sa.Column("nationality", sa.String(60), nullable=True),
        sa.Column("family_size", sa.Integer, nullable=True),
        sa.Column("current_residence", sa.String(100), nullable=True),
        sa.Column("previous_purchases", sa.Integer, nullable=True),
        sa.Column("fields_collected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fields_total", sa.Integer, nullable=False, server_default="18"),
        sa.Column("completion_pct", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("is_qualified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_qual_profiles_org_lead", "qualification_profiles", ["organization_id", "lead_id"])

    # ── 4. agent_memories ────────────────────────────────────────────────────
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("fact_key", sa.String(100), nullable=False),
        sa.Column("fact_value", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("source", sa.String(30), nullable=False, server_default="conversation"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("superseded_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_memory_session_key", "agent_memories", ["session_id", "fact_key"])
    op.create_index("ix_agent_memory_lead_active", "agent_memories", ["lead_id", "is_active"])

    # ── 5. conversation_summaries ─────────────────────────────────────────────
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_start", sa.Integer, nullable=False),
        sa.Column("turn_end", sa.Integer, nullable=False),
        sa.Column("summary_text", sa.Text, nullable=False),
        sa.Column("key_facts_json", JSONB, nullable=True),
        sa.Column("objections_json", JSONB, nullable=True),
        sa.Column("buying_signals_json", JSONB, nullable=True),
        sa.Column("properties_discussed_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conv_summaries_session", "conversation_summaries", ["session_id", "turn_end"])

    # ── 6. tool_executions ────────────────────────────────────────────────────
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("tool_name", sa.String(60), nullable=False),
        sa.Column("input_json", JSONB, nullable=True),
        sa.Column("output_json", JSONB, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("source_verified", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("data_source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_exec_session_tool", "tool_executions", ["session_id", "tool_name"])

    # ── 7. prompt_versions ────────────────────────────────────────────────────
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("prompt_key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("system_template", sa.Text, nullable=False),
        sa.Column("variables_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prompt_ver_key_org_active", "prompt_versions", ["prompt_key", "organization_id", "is_active"])

    # ── 8. decision_records ───────────────────────────────────────────────────
    op.create_table(
        "decision_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("decision_type", sa.String(30), nullable=False),
        sa.Column("selected_action", sa.String(60), nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("alternative_actions_json", JSONB, nullable=True),
        sa.Column("fsm_state_before", sa.String(30), nullable=False),
        sa.Column("fsm_state_after", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_decision_rec_session_turn", "decision_records", ["session_id", "turn_index"])

    # ── 9. escalations ────────────────────────────────────────────────────────
    op.create_table(
        "escalations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("qualification_snapshot_json", JSONB, nullable=True),
        sa.Column("conversation_json", JSONB, nullable=True),
        sa.Column("recommended_actions_json", JSONB, nullable=True),
        sa.Column("pending_questions_json", JSONB, nullable=True),
        sa.Column("assigned_to", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_escalations_org_status", "escalations", ["organization_id", "status"])
    op.create_index("ix_escalations_org_priority", "escalations", ["organization_id", "priority"])

    # ── 10. llm_usage ────────────────────────────────────────────────────────
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_code", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_llm_usage_org_provider", "llm_usage", ["organization_id", "provider"])
    op.create_index("ix_llm_usage_session", "llm_usage", ["session_id"])

    # ── 11. agent_configurations ──────────────────────────────────────────────
    op.create_table(
        "agent_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, unique=True),
        sa.Column("agent_name", sa.String(80), nullable=False, server_default="BeetleLabs AI Agent"),
        sa.Column("enabled_channels_json", JSONB, nullable=True),
        sa.Column("llm_provider", sa.String(30), nullable=False, server_default="openai"),
        sa.Column("llm_model", sa.String(60), nullable=False, server_default="gpt-4o"),
        sa.Column("fallback_provider", sa.String(30), nullable=True),
        sa.Column("fallback_model", sa.String(60), nullable=True),
        sa.Column("max_turns", sa.Integer, nullable=False, server_default="30"),
        sa.Column("max_tokens_per_turn", sa.Integer, nullable=False, server_default="4096"),
        sa.Column("context_window_turns", sa.Integer, nullable=False, server_default="10"),
        sa.Column("summary_every_n_turns", sa.Integer, nullable=False, server_default="8"),
        sa.Column("escalation_confidence_threshold", sa.Float, nullable=False, server_default="0.3"),
        sa.Column("escalation_high_value_score", sa.Float, nullable=False, server_default="85.0"),
        sa.Column("strategy_overrides_json", JSONB, nullable=True),
        sa.Column("allow_price_disclosure", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("require_tool_grounding", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_config_org", "agent_configurations", ["organization_id"])


def downgrade() -> None:
    op.drop_table("agent_configurations")
    op.drop_table("llm_usage")
    op.drop_table("escalations")
    op.drop_table("decision_records")
    op.drop_table("prompt_versions")
    op.drop_table("tool_executions")
    op.drop_table("conversation_summaries")
    op.drop_table("agent_memories")
    op.drop_table("qualification_profiles")
    op.drop_table("conversation_states")
    op.drop_table("agent_sessions")
