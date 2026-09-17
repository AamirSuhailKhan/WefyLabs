"""Part 29 AI Lead Property Matching Engine Schema

Revision ID: 0022_ai_matching_engine
Revises: 0021_property_inventory_crm
Create Date: 2026-09-07 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '0022_ai_matching_engine'
down_revision = '0021_property_inventory_crm'
branch_labels = None
depends_on = None

JSONBType = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    # Extend lead_property_interests with explainable match result columns
    with op.batch_alter_table("lead_property_interests") as batch_op:
        batch_op.add_column(sa.Column("deterministic_score", sa.Float(), server_default="0.0", nullable=False))
        batch_op.add_column(sa.Column("ai_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False))
        batch_op.add_column(sa.Column("reasons", JSONBType, server_default="[]", nullable=True))
        batch_op.add_column(sa.Column("mismatches", JSONBType, server_default="[]", nullable=True))
        batch_op.add_column(sa.Column("score_breakdown", JSONBType, server_default="{}", nullable=True))

    op.create_index("ix_lpi_org_match_score", "lead_property_interests", ["organization_id", "match_score"], if_not_exists=True)


def downgrade():
    op.drop_index("ix_lpi_org_match_score", table_name="lead_property_interests", if_exists=True)
    with op.batch_alter_table("lead_property_interests") as batch_op:
        batch_op.drop_column("score_breakdown")
        batch_op.drop_column("mismatches")
        batch_op.drop_column("reasons")
        batch_op.drop_column("confidence")
        batch_op.drop_column("ai_score")
        batch_op.drop_column("deterministic_score")
