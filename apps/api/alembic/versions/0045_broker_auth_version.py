"""Add broker auth version for all-session invalidation after password reset.

Revision ID: 0045_broker_auth_version
Revises: 0044_token_blacklist_revocation
Create Date: 2026-10-21
"""
from alembic import op


revision = "0045_broker_auth_version"
down_revision = "0044_token_blacklist_revocation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE brokers ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE brokers DROP COLUMN IF EXISTS auth_version")
