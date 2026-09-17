"""
Part 28 — Alembic Migration 0021: Property Inventory & Property CRM Engine
========================================================================
Additive forward migration creating:
- PropertyListing enterprise attributes (code, share token, location, pricing, ownership, internal notes)
- PropertyMedia enterprise fields (sort order, size, privacy, verification)
- PropertyPriceHistory audit attributes (changed by, reason)
- lead_property_interests table (canonical Lead ↔ Property junction with CRM metadata)

Data Safety: ZERO destructive operations. All existing tables and data preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "0021_property_inventory_crm"
down_revision = "0020_followup_automation_engine"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Extend property_listings with Part 28 canonical fields ──────────────
    with op.batch_alter_table("property_listings") as batch_op:
        batch_op.add_column(sa.Column("property_code", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("share_token", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("listing_type", sa.String(50), server_default="exclusive", nullable=False))
        batch_op.add_column(sa.Column("price_min", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("price_max", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("monthly_rent", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("security_deposit", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("price_per_sqft", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("carpet_area", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("super_built_up_area", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("plot_area", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("balconies", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("facing", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("furnishing", sa.String(30), server_default="unfurnished", nullable=False))
        batch_op.add_column(sa.Column("age_years", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("possession_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("construction_status", sa.String(50), server_default="ready_to_move", nullable=False))
        batch_op.add_column(sa.Column("developer_name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("address", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("state", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("postal_code", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("marketing_highlights", sa.JSON(), server_default="[]", nullable=True))
        batch_op.add_column(sa.Column("owner_name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("owner_phone", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("owner_email", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("assigned_agent_id", UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("commission_amount", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("commission_percentage", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("internal_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("listing_start", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("listing_end", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_property_listings_code", "property_listings", ["property_code"], if_not_exists=True)
    op.create_index("ix_property_listings_share", "property_listings", ["share_token"], unique=True, if_not_exists=True)
    op.create_index("ix_property_listings_agent", "property_listings", ["assigned_agent_id"], if_not_exists=True)
    op.create_index("ix_property_listings_dev", "property_listings", ["developer_name"], if_not_exists=True)

    # ── 2. Extend property_media with privacy and ordering ─────────────────────
    with op.batch_alter_table("property_media") as batch_op:
        batch_op.add_column(sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("mime_type", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("is_private", sa.Boolean(), server_default=sa.text("false"), nullable=False))
        batch_op.add_column(sa.Column("verification_status", sa.String(30), server_default="uploaded", nullable=False))

    # ── 3. Extend property_price_history with audit columns ────────────────────
    with op.batch_alter_table("property_price_history") as batch_op:
        batch_op.add_column(sa.Column("changed_by_id", UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("reason", sa.String(255), nullable=True))

    # ── 4. Create lead_property_interests table ───────────────────────────────
    op.create_table(
        "lead_property_interests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", UUID(as_uuid=True), sa.ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), server_default="INTERESTED", nullable=False),
        sa.Column("interest_level", sa.String(20), server_default="medium", nullable=False),
        sa.Column("first_matched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("interested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("match_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("source_of_match", sa.String(50), server_default="manual", nullable=False),
        sa.Column("assigned_agent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "lead_id", "property_id", name="uq_org_lead_property")
    )
    op.create_index("ix_lpi_org_status", "lead_property_interests", ["organization_id", "status"], if_not_exists=True)
    op.create_index("ix_lpi_lead_status", "lead_property_interests", ["lead_id", "status"], if_not_exists=True)
    op.create_index("ix_lpi_property_status", "lead_property_interests", ["property_id", "status"], if_not_exists=True)


def downgrade():
    op.drop_table("lead_property_interests")
    with op.batch_alter_table("property_price_history") as batch_op:
        batch_op.drop_column("reason")
        batch_op.drop_column("changed_by_id")
    with op.batch_alter_table("property_media") as batch_op:
        batch_op.drop_column("verification_status")
        batch_op.drop_column("is_private")
        batch_op.drop_column("mime_type")
        batch_op.drop_column("file_size_bytes")
        batch_op.drop_column("sort_order")
    with op.batch_alter_table("property_listings") as batch_op:
        batch_op.drop_column("listing_end")
        batch_op.drop_column("listing_start")
        batch_op.drop_column("internal_notes")
        batch_op.drop_column("commission_percentage")
        batch_op.drop_column("commission_amount")
        batch_op.drop_column("assigned_agent_id")
        batch_op.drop_column("owner_email")
        batch_op.drop_column("owner_phone")
        batch_op.drop_column("owner_name")
        batch_op.drop_column("marketing_highlights")
        batch_op.drop_column("postal_code")
        batch_op.drop_column("state")
        batch_op.drop_column("address")
        batch_op.drop_column("developer_name")
        batch_op.drop_column("construction_status")
        batch_op.drop_column("possession_date")
        batch_op.drop_column("age_years")
        batch_op.drop_column("furnishing")
        batch_op.drop_column("facing")
        batch_op.drop_column("balconies")
        batch_op.drop_column("plot_area")
        batch_op.drop_column("super_built_up_area")
        batch_op.drop_column("carpet_area")
        batch_op.drop_column("price_per_sqft")
        batch_op.drop_column("security_deposit")
        batch_op.drop_column("monthly_rent")
        batch_op.drop_column("price_max")
        batch_op.drop_column("price_min")
        batch_op.drop_column("listing_type")
        batch_op.drop_column("share_token")
        batch_op.drop_column("property_code")
