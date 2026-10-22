"""Create the token blacklist table used for authenticated-session revocation.

Revision ID: 0044_token_blacklist_revocation
Revises: 0043_schema_drift_remediation
Create Date: 2026-10-21
"""
from alembic import op


revision = "0044_token_blacklist_revocation"
down_revision = "0043_schema_drift_remediation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The table may already exist in environments created from SQLAlchemy
    # metadata, so keep this migration safe for those databases as well.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS token_blacklist (
            id VARCHAR(36) PRIMARY KEY,
            jti VARCHAR(255) NOT NULL UNIQUE,
            user_id VARCHAR(36) NOT NULL,
            reason VARCHAR(100) NOT NULL DEFAULT 'logout',
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_blacklist_jti ON token_blacklist (jti)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_blacklist_user_id ON token_blacklist (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_blacklist_expires_at ON token_blacklist (expires_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_token_blacklist_expires_at")
    op.execute("DROP INDEX IF EXISTS ix_token_blacklist_user_id")
    op.execute("DROP INDEX IF EXISTS ix_token_blacklist_jti")
    op.execute("DROP TABLE IF EXISTS token_blacklist")
