"""
Part 21.8 — Alembic Migration 0015: Autonomous Sales Loop Orchestration
=========================================================================
Adds 4 new tables ONLY. Zero destructive operations.

Tables:
  - sales_loop_events         (durable idempotent event store)
  - sales_loop_audit_entries  (explainability audit trail)
  - sales_loop_dead_letters   (permanently failed events)
  - lead_automation_states    (per-lead pause/resume/takeover)

Revision chain: merges 0014 into 0015.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_sales_loop_orchestration"
down_revision = "merge_002_and_9999_heads"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. sales_loop_events ─────────────────────────────────────────────────
    op.create_table(
        "sales_loop_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("broker_id", sa.String(36), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("causation_id", sa.String(100), nullable=True),
        sa.Column("actor_type", sa.String(30), nullable=False, server_default="SYSTEM"),
        sa.Column("actor_id", sa.String(100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("processing_state", sa.String(30), nullable=False, server_default="RECEIVED"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("failure_class", sa.String(60), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sle_idempotency", "sales_loop_events", ["idempotency_key"], unique=True)
    op.create_index("ix_sle_tenant_lead_type", "sales_loop_events", ["tenant_id", "lead_id", "event_type"])
    op.create_index("ix_sle_state_occurred", "sales_loop_events", ["processing_state", "occurred_at"])
    op.create_index("ix_sle_correlation", "sales_loop_events", ["correlation_id"])
    op.create_index("ix_sle_lead_id", "sales_loop_events", ["lead_id"])

    # ── 2. sales_loop_audit_entries ──────────────────────────────────────────
    op.create_table(
        "sales_loop_audit_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("sales_loop_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("causation_id", sa.String(100), nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("lifecycle_state_before", sa.String(50), nullable=True),
        sa.Column("lifecycle_state_after", sa.String(50), nullable=True),
        sa.Column("qualification_completeness", sa.Float(), nullable=True),
        sa.Column("qualification_state", sa.String(50), nullable=True),
        sa.Column("matched_properties_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("buying_signal_level", sa.String(30), nullable=True),
        sa.Column("action_type", sa.String(100), nullable=True),
        sa.Column("automation_permission", sa.String(30), nullable=True),
        sa.Column("guard_results", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("provider_name", sa.String(60), nullable=True),
        sa.Column("provider_status", sa.String(60), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(50), nullable=True),
        sa.Column("actor_type", sa.String(30), nullable=False, server_default="SYSTEM"),
        sa.Column("actor_id", sa.String(100), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_slae_tenant_lead", "sales_loop_audit_entries", ["tenant_id", "lead_id"])
    op.create_index("ix_slae_occurred", "sales_loop_audit_entries", ["occurred_at"])
    op.create_index("ix_slae_correlation", "sales_loop_audit_entries", ["correlation_id"])

    # ── 3. sales_loop_dead_letters ───────────────────────────────────────────
    op.create_table(
        "sales_loop_dead_letters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("causation_id", sa.String(100), nullable=True),
        sa.Column("failure_class", sa.String(60), nullable=False),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("safe_error_message", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(100), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sldl_tenant_unresolved", "sales_loop_dead_letters", ["tenant_id", "is_resolved"])
    op.create_index("ix_sldl_event_id", "sales_loop_dead_letters", ["original_event_id"], unique=True)

    # ── 4. lead_automation_states ────────────────────────────────────────────
    op.create_table(
        "lead_automation_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lead_id", sa.String(36), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_broker_takeover", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_by", sa.String(100), nullable=True),
        sa.Column("pause_reason", sa.Text(), nullable=True),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_by", sa.String(100), nullable=True),
        sa.Column("current_lifecycle_state", sa.String(50), nullable=False, server_default="NEW"),
        sa.Column("previous_lifecycle_state", sa.String(50), nullable=True),
        sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_change_reason", sa.Text(), nullable=True),
        sa.Column("daily_action_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_action_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("orchestration_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_event_id", sa.String(36), nullable=True),
        sa.Column("last_event_type", sa.String(100), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_action_id", sa.String(36), nullable=True),
        sa.Column("pending_action_type", sa.String(100), nullable=True),
        sa.Column("pending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_las_lead_id", "lead_automation_states", ["lead_id"], unique=True)
    op.create_index("ix_las_tenant_id", "lead_automation_states", ["tenant_id"])


def downgrade():
    op.drop_table("lead_automation_states")
    op.drop_table("sales_loop_dead_letters")
    op.drop_table("sales_loop_audit_entries")
    op.drop_table("sales_loop_events")
