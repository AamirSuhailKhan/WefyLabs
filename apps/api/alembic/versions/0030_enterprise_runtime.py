"""Part 17 — Enterprise Production Runtime: Transactional Outbox & Performance Indexes.

Revision ID: 0030_enterprise_runtime
Revises: 0029_native_crm_indexes
Create Date: 2026-09-24 00:00:00.000000

Creates:
  - `outbox_events` table for reliable, idempotent domain-event publishing
  - Composite indexes for multi-tenant isolation and fast lookup
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0030_enterprise_runtime'
down_revision = '0029_native_crm_indexes'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Create outbox_events table if not exists
    if 'outbox_events' not in tables:
        op.create_table(
            'outbox_events',
            sa.Column('id', postgresql.UUID(as_uuid=True) if bind.dialect.name == 'postgresql' else sa.CHAR(36), primary_key=True),
            sa.Column('event_id', sa.String(64), nullable=False, unique=True),
            sa.Column('tenant_id', sa.String(64), nullable=False),
            sa.Column('event_type', sa.String(128), nullable=False),
            sa.Column('aggregate_type', sa.String(64), nullable=False),
            sa.Column('aggregate_id', sa.String(128), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, server_default='PENDING'),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('max_retries', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('idempotency_key', sa.String(128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        )

        op.create_index('ix_outbox_events_event_id', 'outbox_events', ['event_id'], unique=True)
        op.create_index('ix_outbox_events_tenant_id', 'outbox_events', ['tenant_id'])
        op.create_index('ix_outbox_events_status', 'outbox_events', ['status'])
        op.create_index('ix_outbox_events_event_type', 'outbox_events', ['event_type'])
        op.create_index('ix_outbox_tenant_status', 'outbox_events', ['tenant_id', 'status'])
        op.create_index('ix_outbox_status_next_retry', 'outbox_events', ['status', 'next_retry_at'])
        op.create_index('ix_outbox_tenant_idempotency', 'outbox_events', ['tenant_id', 'idempotency_key'])

    # 2. Add composite performance indexes on leads if not existing
    if 'leads' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('leads')]
        if 'ix_leads_broker_created' not in indexes:
            op.create_index(
                'ix_leads_broker_created',
                'leads',
                ['broker_id', 'created_at'],
                unique=False
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'leads' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('leads')]
        if 'ix_leads_broker_created' in indexes:
            op.drop_index('ix_leads_broker_created', table_name='leads')

    if 'outbox_events' in tables:
        op.drop_table('outbox_events')
