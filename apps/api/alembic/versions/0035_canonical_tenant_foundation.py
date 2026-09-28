"""Foundation Convergence: Canonical Tenant Model & AI Foundation Records.

Revision ID: 0035_canonical_tenant_foundation
Revises: 0034_customer_portal_os
Create Date: 2026-09-25 12:00:00.000000

Changes:
  1. Add organization_id column and indices to `leads`.
  2. Add organization_id column and indices to `property_listings`.
  3. Add organization_id column and indices to `conversations`.
  4. Create `ai_request_records` table for AI observability.
  5. Create `ai_action_authorizations` table for human-in-the-loop action security.
  6. Backfill existing records with organization_id from organization_members.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0035_canonical_tenant_foundation"
down_revision = "0034_customer_portal_os"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")

    # ─── 1. Add organization_id to `leads` ────────────────────────────────────
    op.add_column(
        "leads",
        sa.Column(
            "organization_id",
            uuid_type,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_leads_organization_id", "leads", ["organization_id"])
    op.create_index("ix_leads_org_status", "leads", ["organization_id", "status"])

    # ─── 2. Add organization_id to `property_listings` ────────────────────────
    op.add_column(
        "property_listings",
        sa.Column(
            "organization_id",
            uuid_type,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_property_listings_organization_id", "property_listings", ["organization_id"])
    op.create_index("ix_property_listings_org_status", "property_listings", ["organization_id", "status"])

    # ─── 3. Add organization_id to `conversations` ────────────────────────────
    op.add_column(
        "conversations",
        sa.Column(
            "organization_id",
            uuid_type,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])

    # ─── 4. Create `ai_request_records` ──────────────────────────────────────
    op.create_table(
        "ai_request_records",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("organization_id", uuid_type, nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("feature", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(80), nullable=False, server_default="completion"),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("provider", sa.String(50), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(40), nullable=False, server_default="FAILED"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("retrieval_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tool_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("human_override", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_req_org", "ai_request_records", ["organization_id"])
    op.create_index("ix_ai_req_feature", "ai_request_records", ["feature"])
    op.create_index("ix_ai_req_status", "ai_request_records", ["status"])
    op.create_index("ix_ai_req_request_id", "ai_request_records", ["request_id"])

    # ─── 5. Create `ai_action_authorizations` ────────────────────────────────
    op.create_table(
        "ai_action_authorizations",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("organization_id", uuid_type, nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("parameters_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("confirmation_method", sa.String(40), nullable=False, server_default="human"),
        sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True),
        sa.Column("safety_level", sa.String(20), nullable=False, server_default="CONFIRM"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_ai_act_auth_org", "ai_action_authorizations", ["organization_id"])
    op.create_index("ix_ai_act_auth_actor", "ai_action_authorizations", ["actor_id"])
    op.create_index("ix_ai_act_auth_status", "ai_action_authorizations", ["status"])

    # ─── 6. Safe Backfill ────────────────────────────────────────────────────
    # Backfill leads.organization_id from organization_members where available
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        conn.execute(sa.text("""
            UPDATE leads
            SET organization_id = om.organization_id
            FROM organization_members om
            WHERE leads.organization_id IS NULL AND leads.broker_id = om.broker_id;
        """))
        conn.execute(sa.text("""
            UPDATE property_listings
            SET organization_id = om.organization_id
            FROM organization_members om
            WHERE property_listings.organization_id IS NULL AND property_listings.broker_id = om.broker_id;
        """))
        conn.execute(sa.text("""
            UPDATE conversations
            SET organization_id = l.organization_id
            FROM leads l
            WHERE conversations.organization_id IS NULL AND conversations.lead_id = l.id;
        """))
    elif dialect == "sqlite":
        # SQLite correlated subquery update
        conn.execute(sa.text("""
            UPDATE leads
            SET organization_id = (
                SELECT organization_id FROM organization_members
                WHERE organization_members.broker_id = leads.broker_id LIMIT 1
            )
            WHERE organization_id IS NULL;
        """))
        conn.execute(sa.text("""
            UPDATE property_listings
            SET organization_id = (
                SELECT organization_id FROM organization_members
                WHERE organization_members.broker_id = property_listings.broker_id LIMIT 1
            )
            WHERE organization_id IS NULL;
        """))
        conn.execute(sa.text("""
            UPDATE conversations
            SET organization_id = (
                SELECT organization_id FROM leads
                WHERE leads.id = conversations.lead_id LIMIT 1
            )
            WHERE organization_id IS NULL;
        """))


def downgrade() -> None:
    op.drop_table("ai_action_authorizations")
    op.drop_table("ai_request_records")
    op.drop_index("ix_conversations_organization_id", table_name="conversations")
    op.drop_column("conversations", "organization_id")
    op.drop_index("ix_property_listings_org_status", table_name="property_listings")
    op.drop_index("ix_property_listings_organization_id", table_name="property_listings")
    op.drop_column("property_listings", "organization_id")
    op.drop_index("ix_leads_org_status", table_name="leads")
    op.drop_index("ix_leads_organization_id", table_name="leads")
    op.drop_column("leads", "organization_id")
