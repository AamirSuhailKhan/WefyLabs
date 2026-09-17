"""
Part 25 — Alembic Migration 0019: Copilot Conversations & Messages
===================================================================
Additive forward migration creating tables for:
- copilot_conversations
- copilot_messages

Data Safety: ZERO destructive operations. All existing tables and data preserved.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0019_copilot_conversations"
down_revision = "0018_pre_branding_blockers"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. copilot_conversations ──────────────────────────────────────────────
    op.create_table(
        "copilot_conversations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column(
            "broker_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("brokers.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("title", sa.String(255), server_default="New Conversation", nullable=False),
        sa.Column("route_context", sa.String(100), server_default="/dashboard", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_copilot_conversations_org_id", "copilot_conversations", ["organization_id"], if_not_exists=True)
    op.create_index("ix_copilot_conversations_broker_id", "copilot_conversations", ["broker_id"], if_not_exists=True)
    op.create_index("ix_copilot_conversations_broker_updated", "copilot_conversations", ["broker_id", "updated_at"], if_not_exists=True)
    op.create_index("ix_copilot_conversations_org_created", "copilot_conversations", ["organization_id", "created_at"], if_not_exists=True)

    # ── 2. copilot_messages ───────────────────────────────────────────────────
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("sender", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("thought_reasoning", sa.Text(), nullable=True),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_results", sa.JSON(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("action_preview", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), server_default="0.98", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_copilot_messages_conversation_id", "copilot_messages", ["conversation_id"], if_not_exists=True)
    op.create_index("ix_copilot_messages_created_at", "copilot_messages", ["created_at"], if_not_exists=True)


def downgrade():
    op.drop_table("copilot_messages")
    op.drop_table("copilot_conversations")
