"""Persist Google subject identifiers for stable OAuth account linking.

Revision ID: 0046_broker_google_subject
Revises: 0045_broker_auth_version
Create Date: 2026-10-21
"""
from alembic import op


revision = "0046_broker_google_subject"
down_revision = "0045_broker_auth_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE brokers ADD COLUMN IF NOT EXISTS google_subject VARCHAR(255)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_brokers_google_subject ON brokers (google_subject)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_brokers_google_subject")
    op.execute("ALTER TABLE brokers DROP COLUMN IF EXISTS google_subject")
