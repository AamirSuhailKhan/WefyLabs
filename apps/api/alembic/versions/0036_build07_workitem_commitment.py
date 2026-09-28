"""Build 07 — Canonical WorkItem and Commitment Foundation.

Revision ID: 0036_build07_workitem_commitment
Revises: 0035_canonical_tenant_foundation
Create Date: 2026-09-26 12:00:00.000000

Changes:
  1. Add WorkItem fields to `tasks`:
     - scheduled_at, task_type, source, idempotency_key, correlation_id,
     - conversation_id, identity_id, opportunity_id, reason,
     - source_event_id, source_message_id, source_action_id,
     - source_workflow_id, source_agent_run_id, assigned_team,
     - expires_at, cancelled_at
  2. Create `commitments` table with full tracking and tenant isolation.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers
revision = "0036_build07_workitem_commitment"
down_revision = "0035_canonical_tenant_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = set(insp.get_table_names())

    json_type = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
    uuid_type = postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")

    # ─── 1. Extend `tasks` Table ─────────────────────────────────────────────
    if "tasks" in existing_tables:
        existing_cols = {c["name"] for c in insp.get_columns("tasks")}

        new_columns = [
            ("scheduled_at", sa.DateTime(timezone=True), True),
            ("task_type", sa.String(50), True),
            ("source", sa.String(50), True),
            ("idempotency_key", sa.String(255), True),
            ("correlation_id", sa.String(100), True),
            ("conversation_id", sa.String(36), True),
            ("identity_id", sa.String(36), True),
            ("opportunity_id", sa.String(36), True),
            ("reason", sa.Text(), True),
            ("source_event_id", sa.String(100), True),
            ("source_message_id", sa.String(100), True),
            ("source_action_id", sa.String(100), True),
            ("source_workflow_id", sa.String(100), True),
            ("source_agent_run_id", sa.String(100), True),
            ("assigned_team", sa.String(100), True),
            ("expires_at", sa.DateTime(timezone=True), True),
            ("cancelled_at", sa.DateTime(timezone=True), True),
        ]

        for col_name, col_type, col_nullable in new_columns:
            if col_name not in existing_cols:
                op.add_column("tasks", sa.Column(col_name, col_type, nullable=col_nullable))

        # Add indexes if not present
        existing_indexes = {ix["name"] for ix in insp.get_indexes("tasks")}
        if "ix_tasks_task_type" not in existing_indexes:
            op.create_index("ix_tasks_task_type", "tasks", ["task_type"])
        if "ix_tasks_idempotency_key" not in existing_indexes:
            op.create_index("ix_tasks_idempotency_key", "tasks", ["idempotency_key"], unique=True)
        if "ix_tasks_correlation_id" not in existing_indexes:
            op.create_index("ix_tasks_correlation_id", "tasks", ["correlation_id"])
        if "ix_tasks_conversation_id" not in existing_indexes:
            op.create_index("ix_tasks_conversation_id", "tasks", ["conversation_id"])
        if "ix_tasks_opportunity_id" not in existing_indexes:
            op.create_index("ix_tasks_opportunity_id", "tasks", ["opportunity_id"])

    # ─── 2. Create `commitments` Table ───────────────────────────────────────
    if "commitments" not in existing_tables:
        op.create_table(
            "commitments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False, index=True),
            sa.Column("lead_id", uuid_type, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("owner", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("commitment_type", sa.String(50), nullable=False),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("missed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("work_item_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("conversation_id", sa.String(36), nullable=True, index=True),
            sa.Column("source_message_id", sa.String(100), nullable=True),
            sa.Column("evidence", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_commitments_org_status", "commitments", ["organization_id", "status"])
        op.create_index("ix_commitments_owner_due", "commitments", ["owner", "due_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "commitments" in existing_tables:
        op.drop_table("commitments")

    if "tasks" in existing_tables:
        existing_cols = {c["name"] for c in insp.get_columns("tasks")}
        cols_to_drop = [
            "scheduled_at", "task_type", "source", "idempotency_key",
            "correlation_id", "conversation_id", "identity_id", "opportunity_id",
            "reason", "source_event_id", "source_message_id", "source_action_id",
            "source_workflow_id", "source_agent_run_id", "assigned_team",
            "expires_at", "cancelled_at"
        ]
        for col in cols_to_drop:
            if col in existing_cols:
                op.drop_column("tasks", col)
