"""
Part 27 — Alembic Migration 0020: Follow-Up Automation Engine
============================================================
Additive forward migration creating tables and settings for:
- follow_up_rules
- follow_up_automation_events (Idempotency Ledger)
- follow_up_policies (Extended automation settings)

Data Safety: ZERO destructive operations. All existing tables and data preserved.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0020_followup_automation_engine"
down_revision = "0019_copilot_conversations"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Extend follow_up_policies with Part 27 organization settings ──────────
    with op.batch_alter_table("follow_up_policies") as batch_op:
        batch_op.add_column(sa.Column("first_contact_sla_minutes", sa.Integer(), server_default="15", nullable=False))
        batch_op.add_column(sa.Column("stale_lead_days", sa.Integer(), server_default="7", nullable=False))
        batch_op.add_column(sa.Column("reengagement_days", sa.Integer(), server_default="14", nullable=False))
        batch_op.add_column(sa.Column("escalation_delay_hours", sa.Integer(), server_default="2", nullable=False))
        batch_op.add_column(sa.Column("manager_escalation_hours", sa.Integer(), server_default="24", nullable=False))
        batch_op.add_column(sa.Column("hot_lead_sla_minutes", sa.Integer(), server_default="30", nullable=False))
        batch_op.add_column(sa.Column("working_hours_start", sa.String(10), server_default="09:00", nullable=False))
        batch_op.add_column(sa.Column("working_hours_end", sa.String(10), server_default="18:00", nullable=False))
        batch_op.add_column(sa.Column("timezone", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("auto_send_email", sa.Boolean(), server_default=sa.text("false"), nullable=False))
        batch_op.add_column(sa.Column("automation_settings", sa.JSON(), server_default="{}", nullable=False))

    # ── 2. Create follow_up_rules ─────────────────────────────────────────────
    op.create_table(
        "follow_up_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("action_config", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("conditions", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("priority", sa.String(20), server_default="normal", nullable=False),
        sa.Column("max_runs", sa.Integer(), server_default="1", nullable=False),
        sa.Column("cooldown_hours", sa.Integer(), server_default="24", nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fu_rules_org_id", "follow_up_rules", ["organization_id"], if_not_exists=True)
    op.create_index("ix_fu_rules_trigger", "follow_up_rules", ["trigger"], if_not_exists=True)
    op.create_index("ix_fu_rules_org_trigger", "follow_up_rules", ["organization_id", "trigger", "enabled"], if_not_exists=True)

    # ── 3. Create follow_up_automation_events (Idempotency Ledger) ─────────────
    op.create_table(
        "follow_up_automation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("follow_up_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("notification_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(30), server_default="COMPLETED", nullable=False),
        sa.Column("execution_details", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fu_auto_idempotency_key", "follow_up_automation_events", ["idempotency_key"], unique=True, if_not_exists=True)
    op.create_index("ix_fu_auto_org_id", "follow_up_automation_events", ["organization_id"], if_not_exists=True)
    op.create_index("ix_fu_auto_lead_id", "follow_up_automation_events", ["lead_id"], if_not_exists=True)
    op.create_index("ix_fu_auto_lead_created", "follow_up_automation_events", ["lead_id", "created_at"], if_not_exists=True)
    op.create_index("ix_fu_auto_org_status", "follow_up_automation_events", ["organization_id", "status"], if_not_exists=True)


def downgrade():
    op.drop_index("ix_fu_auto_org_status", table_name="follow_up_automation_events")
    op.drop_index("ix_fu_auto_lead_created", table_name="follow_up_automation_events")
    op.drop_index("ix_fu_auto_lead_id", table_name="follow_up_automation_events")
    op.drop_index("ix_fu_auto_org_id", table_name="follow_up_automation_events")
    op.drop_index("ix_fu_auto_idempotency_key", table_name="follow_up_automation_events")
    op.drop_table("follow_up_automation_events")

    op.drop_index("ix_fu_rules_org_trigger", table_name="follow_up_rules")
    op.drop_index("ix_fu_rules_trigger", table_name="follow_up_rules")
    op.drop_index("ix_fu_rules_org_id", table_name="follow_up_rules")
    op.drop_table("follow_up_rules")

    with op.batch_alter_table("follow_up_policies") as batch_op:
        batch_op.drop_column("automation_settings")
        batch_op.drop_column("auto_send_email")
        batch_op.drop_column("timezone")
        batch_op.drop_column("working_hours_end")
        batch_op.drop_column("working_hours_start")
        batch_op.drop_column("hot_lead_sla_minutes")
        batch_op.drop_column("manager_escalation_hours")
        batch_op.drop_column("escalation_delay_hours")
        batch_op.drop_column("reengagement_days")
        batch_op.drop_column("stale_lead_days")
        batch_op.drop_column("first_contact_sla_minutes")
