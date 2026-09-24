"""Part 14 — Native CRM Core: Performance Indexes.

Revision ID: 0029_native_crm_indexes
Revises: 0028_revenue_intelligence
Create Date: 2026-09-23 00:00:00.000000

Adds composite indexes on `leads` table to optimize native CRM operator queries:
  - ix_leads_broker_status on (broker_id, status)
  - ix_leads_broker_source on (broker_id, source)
"""
from alembic import op
import sqlalchemy as sa

revision = '0029_native_crm_indexes'
down_revision = '0028_revenue_intelligence'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes('leads')]

    if 'ix_leads_broker_status' not in indexes:
        op.create_index(
            'ix_leads_broker_status',
            'leads',
            ['broker_id', 'status'],
            unique=False
        )

    if 'ix_leads_broker_source' not in indexes:
        op.create_index(
            'ix_leads_broker_source',
            'leads',
            ['broker_id', 'source'],
            unique=False
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes('leads')]

    if 'ix_leads_broker_source' in indexes:
        op.drop_index('ix_leads_broker_source', table_name='leads')

    if 'ix_leads_broker_status' in indexes:
        op.drop_index('ix_leads_broker_status', table_name='leads')
