"""
Part 23 — Alembic Migration 0016: Lead Sources Schema Alignment
===============================================================
Additive forward migration to align lead_sources table columns with
Part 21.1 Real-Estate Lead Acquisition domain model.

Added Columns:
  - description          (TEXT, nullable=True)
  - channel              (VARCHAR(50), nullable=True, server_default='WEBSITE')
  - webhook_secret_hash  (VARCHAR(128), nullable=True)
  - webhook_url_token    (VARCHAR(64), nullable=True)
  - rate_limit_per_hour  (INTEGER, nullable=True)
  - is_active            (BOOLEAN, nullable=False, server_default=true)

Data Safety: ZERO destructive operations. All existing columns & data preserved.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0016_lead_sources_alignment"
down_revision = "0015_sales_loop_orchestration"
branch_labels = None
depends_on = None


def upgrade():
    # Safely alter lead_sources by adding missing columns
    with op.batch_alter_table("lead_sources") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("channel", sa.String(50), nullable=True, server_default="WEBSITE"))
        batch_op.add_column(sa.Column("webhook_secret_hash", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("webhook_url_token", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("rate_limit_per_hour", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        # Make broker_id nullable if present to support organization-level sources
        batch_op.alter_column("broker_id", existing_type=sa.UUID(), nullable=True)

    # Add indexes for fast querying
    op.create_index("ix_lead_sources_channel", "lead_sources", ["channel"], if_not_exists=True)
    op.create_index("ix_lead_sources_webhook_token", "lead_sources", ["webhook_url_token"], unique=True, if_not_exists=True)


def downgrade():
    with op.batch_alter_table("lead_sources") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("rate_limit_per_hour")
        batch_op.drop_column("webhook_url_token")
        batch_op.drop_column("webhook_secret_hash")
        batch_op.drop_column("channel")
        batch_op.drop_column("description")
