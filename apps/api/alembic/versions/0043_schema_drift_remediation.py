"""Schema drift remediation — document manually-applied production columns

Revision ID: 0043_schema_drift_remediation
Revises: 0042_phase2c_pilot_tables
Create Date: 2026-10-06

Captures two sets of columns that were applied to the live database via
runtime remediation scripts during Phase 2C.6C but were NOT previously
backed by an Alembic migration:

  1. omnichannel_conversations.identity_id
     omnichannel_conversations.external_conversation_id
     (applied by scripts/add_missing_omnichannel_columns.py)

  2. property_price_history.currency
     property_price_history.price_type
     property_price_history.unit_id
     property_price_history.source
     property_price_history.effective_from
     property_price_history.effective_to
     property_price_history.observed_at
     (applied by scripts/add_missing_price_history_columns.py)

Phase 2C.6D Phase-1 requirement:
  UNEXPLAINED_SCHEMA_DIFFERENCES = 0
  All production-only schema mutations must be captured in Alembic.

Each column uses ADD COLUMN IF NOT EXISTS so this migration is safe to
apply even on a database that already received the manual patch.  The
downgrade removes these columns if rolling back.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0043_schema_drift_remediation"
down_revision = "0042_phase2c_pilot_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. omnichannel_conversations ────────────────────────────────────────
    # These two columns were added manually in Phase 2C.6C to support
    # identity-linked conversations in the omnichannel inbox.
    with op.batch_alter_table("omnichannel_conversations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "identity_id",
                sa.String(36),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "external_conversation_id",
                sa.String(255),
                nullable=True,
            )
        )

    op.create_index(
        "ix_oc_identity_id",
        "omnichannel_conversations",
        ["identity_id"],
    )
    op.create_index(
        "ix_oc_external_conv_id",
        "omnichannel_conversations",
        ["external_conversation_id"],
    )

    # ── 2. property_price_history ────────────────────────────────────────────
    # These columns were added manually in Phase 2C.6C to support
    # enriched price-history tracking (multi-currency, type, unit linkage,
    # source provenance, and time-bounded validity windows).
    with op.batch_alter_table("property_price_history") as batch_op:
        batch_op.add_column(
            sa.Column(
                "currency",
                sa.String(3),
                nullable=True,
                server_default="INR",
            )
        )
        batch_op.add_column(
            sa.Column(
                "price_type",
                sa.String(50),
                nullable=True,
                server_default="LIST_PRICE",
            )
        )
        batch_op.add_column(
            sa.Column(
                "unit_id",
                sa.UUID(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(100),
                nullable=True,
                server_default="manual",
            )
        )
        batch_op.add_column(
            sa.Column(
                "effective_from",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "effective_to",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "observed_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.text("NOW()"),
            )
        )

    op.create_index(
        "ix_pph_unit_id",
        "property_price_history",
        ["unit_id"],
    )
    op.create_index(
        "ix_pph_effective_window",
        "property_price_history",
        ["property_id", "effective_from", "effective_to"],
    )


def downgrade() -> None:
    # ── 2. property_price_history rollback ───────────────────────────────────
    op.drop_index("ix_pph_effective_window", table_name="property_price_history")
    op.drop_index("ix_pph_unit_id", table_name="property_price_history")
    with op.batch_alter_table("property_price_history") as batch_op:
        batch_op.drop_column("observed_at")
        batch_op.drop_column("effective_to")
        batch_op.drop_column("effective_from")
        batch_op.drop_column("source")
        batch_op.drop_column("unit_id")
        batch_op.drop_column("price_type")
        batch_op.drop_column("currency")

    # ── 1. omnichannel_conversations rollback ────────────────────────────────
    op.drop_index("ix_oc_external_conv_id", table_name="omnichannel_conversations")
    op.drop_index("ix_oc_identity_id", table_name="omnichannel_conversations")
    with op.batch_alter_table("omnichannel_conversations") as batch_op:
        batch_op.drop_column("external_conversation_id")
        batch_op.drop_column("identity_id")
