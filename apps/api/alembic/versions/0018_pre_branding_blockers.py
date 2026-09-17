"""
Part 24.1 — Alembic Migration 0018: Password Reset Tokens & Organization Invitations
===================================================================================
Additive forward migration creating tables for:
- password_reset_tokens
- organization_invitations

Data Safety: ZERO destructive operations. All existing tables and data preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0018_pre_branding_blockers"
down_revision = "0017_razorpay_billing"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. password_reset_tokens ──────────────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "broker_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("brokers.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_broker_id", "password_reset_tokens", ["broker_id"], if_not_exists=True)
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True, if_not_exists=True)
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"], if_not_exists=True)

    # ── 2. organization_invitations ───────────────────────────────────────────
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "invited_by_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("brokers.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), server_default="agent", nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organization_invitations_organization_id", "organization_invitations", ["organization_id"], if_not_exists=True)
    op.create_index("ix_organization_invitations_invited_by_id", "organization_invitations", ["invited_by_id"], if_not_exists=True)
    op.create_index("ix_organization_invitations_email", "organization_invitations", ["email"], if_not_exists=True)
    op.create_index("ix_organization_invitations_token_hash", "organization_invitations", ["token_hash"], unique=True, if_not_exists=True)
    op.create_index("ix_organization_invitations_expires_at", "organization_invitations", ["expires_at"], if_not_exists=True)
    op.create_index("ix_organization_invitations_status", "organization_invitations", ["status"], if_not_exists=True)


def downgrade():
    op.drop_table("organization_invitations")
    op.drop_table("password_reset_tokens")
