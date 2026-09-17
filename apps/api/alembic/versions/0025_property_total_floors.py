"""Part 33.1 Fix Property Listings Schema Drift - Add total_floors column

Revision ID: 0025_property_total_floors
Revises: 0024_onboarding_activation_demo
Create Date: 2026-09-13 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0025_property_total_floors'
down_revision = '0024_onboarding_activation_demo'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "property_listings" in tables:
        prop_cols = [c["name"] for c in inspector.get_columns("property_listings")]
        with op.batch_alter_table("property_listings") as batch_op:
            if "total_floors" not in prop_cols:
                batch_op.add_column(sa.Column("total_floors", sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "property_listings" in tables:
        prop_cols = [c["name"] for c in inspector.get_columns("property_listings")]
        with op.batch_alter_table("property_listings") as batch_op:
            if "total_floors" in prop_cols:
                batch_op.drop_column("total_floors")
