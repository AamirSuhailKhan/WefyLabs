"""Part 21 - Customer Portal, Digital Deal Room & Transaction Collaboration OS.

Revision ID: 0034_customer_portal_os
Revises: 0033_marketing_os
Create Date: 2026-09-24 21:00:00.000000

Creates:
  - customer_portal_invites
  - customer_support_requests
  - customer_payment_proofs
  - customer_transaction_acknowledgements
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0034_customer_portal_os"
down_revision = "0033_marketing_os"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── customer_portal_invites ─────────────────────────────────────────────
    op.create_table(
        "customer_portal_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("deals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_portal_invites_org_lead", "customer_portal_invites", ["organization_id", "lead_id"])
    op.create_index("ix_portal_invites_hash_status", "customer_portal_invites", ["token_hash", "status"])

    # ─── customer_support_requests ───────────────────────────────────────────
    op.create_table(
        "customer_support_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("deals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("assigned_broker_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attachment_urls", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_support_req_org_status", "customer_support_requests", ["organization_id", "status"])
    op.create_index("ix_support_req_lead", "customer_support_requests", ["lead_id"])

    # ─── customer_payment_proofs ─────────────────────────────────────────────
    op.create_table(
        "customer_payment_proofs",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_index", sa.Integer, nullable=False),
        sa.Column("milestone_name", sa.String(255), nullable=False),
        sa.Column("amount_reported", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AED"),
        sa.Column("payment_mode", sa.String(50), nullable=False),
        sa.Column("transaction_reference", sa.String(100), nullable=False),
        sa.Column("receipt_url", sa.String(512), nullable=False),
        sa.Column("customer_notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="REPORTED"),
        sa.Column("reviewed_by_id", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_proof_deal_status", "customer_payment_proofs", ["deal_id", "status"])
    op.create_index("ix_payment_proof_org", "customer_payment_proofs", ["organization_id"])

    # ─── customer_transaction_acknowledgements ───────────────────────────────
    op.create_table(
        "customer_transaction_acknowledgements",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("acknowledgement_type", sa.String(50), nullable=False),
        sa.Column("item_version", sa.String(50), nullable=False, server_default="v1.0"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ack_deal_type", "customer_transaction_acknowledgements", ["deal_id", "acknowledgement_type"])
    op.create_index("ix_ack_org_lead", "customer_transaction_acknowledgements", ["organization_id", "lead_id"])


def downgrade() -> None:
    op.drop_table("customer_transaction_acknowledgements")
    op.drop_table("customer_payment_proofs")
    op.drop_table("customer_support_requests")
    op.drop_table("customer_portal_invites")
