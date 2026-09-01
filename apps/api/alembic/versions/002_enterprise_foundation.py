"""enterprise foundation schema

Revision ID: 002_enterprise_foundation
Revises: 001_initial_schema
Create Date: 2026-08-02 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_enterprise_foundation'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=True),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('whatsapp_number', sa.String(length=20), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('avatar_url', sa.String(length=1000), nullable=True),
        sa.Column('timezone', sa.String(length=50), server_default=sa.text("'Asia/Kolkata'"), nullable=False),
        sa.Column('locale', sa.String(length=10), server_default=sa.text("'en'"), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('auth_provider', sa.String(length=30), server_default=sa.text("'supabase'"), nullable=False),
        sa.Column('external_auth_id', sa.String(length=255), nullable=True),
        sa.Column('subscription_status', sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column('subscription_plan', sa.String(length=50), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(length=36), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)
    op.create_index(op.f('ix_users_external_auth_id'), 'users', ['external_auth_id'], unique=False)
    op.create_index('ix_users_org_active', 'users', ['organization_id', 'is_active'], unique=False)

    # 2. Add version and audit columns to leads if missing
    with op.batch_alter_table('leads') as batch_op:
        batch_op.add_column(sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False))
        batch_op.add_column(sa.Column('deleted_by', sa.String(length=36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('leads') as batch_op:
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('version')
    op.drop_table('users')
