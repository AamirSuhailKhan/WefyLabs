"""Part 30 AI Real-Estate Agent Daily Command Center Schema

Revision ID: 0023_agent_command_center
Revises: 0022_ai_matching_engine
Create Date: 2026-09-12 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '0023_agent_command_center'
down_revision = '0022_ai_matching_engine'
branch_labels = None
depends_on = None

UUIDType = UUID(as_uuid=True).with_variant(sa.CHAR(36), "sqlite")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "command_center_dismissals" not in tables:
        op.create_table(
            "command_center_dismissals",
            sa.Column("id", sa.String(36), primary_key=True, nullable=False),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("broker_id", UUIDType, sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_key", sa.String(255), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.String(64), nullable=False),
            sa.Column("action_type", sa.String(30), server_default="dismissed", nullable=False),
            sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("organization_id", "broker_id", "item_key", name="uq_cmd_center_dismissal")
        )
        op.create_index("ix_cmd_center_org", "command_center_dismissals", ["organization_id"])
        op.create_index("ix_cmd_center_broker", "command_center_dismissals", ["broker_id"])
        op.create_index("ix_cmd_center_item", "command_center_dismissals", ["item_key"])
        op.create_index("ix_cmd_center_broker_item", "command_center_dismissals", ["broker_id", "item_key"])
        op.create_index("ix_cmd_center_snooze", "command_center_dismissals", ["broker_id", "snoozed_until"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "command_center_dismissals" in tables:
        op.drop_index("ix_cmd_center_snooze", table_name="command_center_dismissals")
        op.drop_index("ix_cmd_center_broker_item", table_name="command_center_dismissals")
        op.drop_index("ix_cmd_center_item", table_name="command_center_dismissals")
        op.drop_index("ix_cmd_center_broker", table_name="command_center_dismissals")
        op.drop_index("ix_cmd_center_org", table_name="command_center_dismissals")
        op.drop_table("command_center_dismissals")
