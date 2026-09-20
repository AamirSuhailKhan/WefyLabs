"""Part 1 Core Product — Canonical Customer Identity and Conversation Foundation

Revision ID: 0027_customer_identity_canonical
Revises: 0026_revenue_autopilot
Create Date: 2026-09-18 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0027_customer_identity_canonical'
down_revision = '0026_revenue_autopilot'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Add email column to leads if not present
    if "leads" in tables:
        leads_cols = [c["name"] for c in inspector.get_columns("leads")]
        if "email" not in leads_cols:
            op.add_column("leads", sa.Column("email", sa.String(length=255), nullable=True))
            op.create_index("ix_leads_email", "leads", ["email"], unique=False)

    # 2. Add sender_type column to channel_messages if not present
    if "channel_messages" in tables:
        msg_cols = [c["name"] for c in inspector.get_columns("channel_messages")]
        if "sender_type" not in msg_cols:
            op.add_column("channel_messages", sa.Column("sender_type", sa.String(length=30), nullable=True))
            op.create_index("ix_channel_messages_sender_type", "channel_messages", ["sender_type"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "channel_messages" in tables:
        msg_cols = [c["name"] for c in inspector.get_columns("channel_messages")]
        if "sender_type" in msg_cols:
            op.drop_index("ix_channel_messages_sender_type", table_name="channel_messages")
            op.drop_column("channel_messages", "sender_type")

    if "leads" in tables:
        leads_cols = [c["name"] for c in inspector.get_columns("leads")]
        if "email" in leads_cols:
            op.drop_index("ix_leads_email", table_name="leads")
            op.drop_column("leads", "email")
