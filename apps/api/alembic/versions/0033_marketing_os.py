"""Part 20 - Real Estate Marketing, Listing Distribution, Project Launch & Demand Generation OS.

Revision ID: 0033_marketing_os
Revises: 0032_supply_side_inventory_os
Create Date: 2026-09-24 19:30:00.000000

Creates:
  - marketing_campaigns
  - campaign_approvals
  - campaign_audit_logs
  - marketing_assets
  - property_listing_publications
  - listing_distributions
  - marketing_landing_pages
  - tracking_links
  - campaign_events
  - project_launches
  - campaign_listing_links
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0033_marketing_os"
down_revision = "0032_supply_side_inventory_os"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── marketing_campaigns ─────────────────────────────────────────────────
    op.create_table(
        "marketing_campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("campaign_code", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("objective", sa.String(50), nullable=False, server_default="lead_generation"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        # Inventory scope
        sa.Column("project_id", sa.String(36), nullable=True),  # no FK: real_estate_projects.id is UUID vs VARCHAR
        sa.Column("phase_scope", sa.String(36), nullable=True),
        sa.Column("bhk_scope", sa.String(255), nullable=True),
        sa.Column("unit_status_scope", sa.String(30), nullable=True, server_default="available"),
        sa.Column("price_range_min", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("price_range_max", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("inventory_scope_metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        # Budget
        sa.Column("budget_planned", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("budget_approved", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("budget_spent", sa.Numeric(precision=20, scale=4), nullable=True, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=True, server_default="INR"),
        # Timing
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone_name", sa.String(100), nullable=True),
        # Attribution
        sa.Column("utm_source", sa.String(255), nullable=True),
        sa.Column("utm_medium", sa.String(255), nullable=True),
        sa.Column("utm_campaign", sa.String(255), nullable=True),
        # Part 9 bridge
        sa.Column("lead_campaign_id", sa.String(36), sa.ForeignKey("lead_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=True),
        sa.Column("is_ai_assisted", sa.Boolean, nullable=False, server_default="false"),
        # Approval
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        # Performance (NULL until real data received)
        sa.Column("impressions", sa.Integer, nullable=True),
        sa.Column("clicks", sa.Integer, nullable=True),
        sa.Column("leads_count", sa.Integer, nullable=True),
        sa.Column("qualified_leads_count", sa.Integer, nullable=True),
        sa.Column("appointments_count", sa.Integer, nullable=True),
        sa.Column("bookings_count", sa.Integer, nullable=True),
        sa.Column("revenue_attributed", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("metrics_provenance", sa.String(50), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mktg_campaign_org_status", "marketing_campaigns", ["organization_id", "status"])
    op.create_index("ix_mktg_campaign_org_project", "marketing_campaigns", ["organization_id", "project_id"])
    op.create_index("ix_mktg_campaign_org_objective", "marketing_campaigns", ["organization_id", "objective"])
    op.create_index("ix_mktg_campaign_code", "marketing_campaigns", ["campaign_code"], unique=True)

    # ─── campaign_approvals ───────────────────────────────────────────────────
    op.create_table(
        "campaign_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("budget_requested", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("channels_requested", sa.Text, nullable=True),
        sa.Column("target_summary", sa.Text, nullable=True),
        sa.Column("creative_version", sa.String(50), nullable=True),
        sa.Column("decision", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text, nullable=True),
        sa.Column("budget_approved", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_approval_org_campaign", "campaign_approvals", ["organization_id", "campaign_id"])
    op.create_index("ix_campaign_approval_decision", "campaign_approvals", ["decision"])

    # ─── campaign_audit_logs ─────────────────────────────────────────────────
    op.create_table(
        "campaign_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("from_value", sa.Text, nullable=True),
        sa.Column("to_value", sa.Text, nullable=True),
        sa.Column("performed_by", sa.String(36), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_audit_org_campaign", "campaign_audit_logs", ["organization_id", "campaign_id"])
    op.create_index("ix_campaign_audit_performed_at", "campaign_audit_logs", ["performed_at"])

    # ─── marketing_assets ────────────────────────────────────────────────────
    op.create_table(
        "marketing_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("project_id", sa.String(36), nullable=True),  # no FK: real_estate_projects.id is UUID
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("storage_url", sa.Text, nullable=True),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("previous_version_id", sa.String(36), nullable=True),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_model_version", sa.String(50), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mktg_asset_org_project", "marketing_assets", ["organization_id", "project_id"])
    op.create_index("ix_mktg_asset_org_campaign", "marketing_assets", ["organization_id", "campaign_id"])
    op.create_index("ix_mktg_asset_org_type_status", "marketing_assets", ["organization_id", "asset_type", "status"])

    # ─── property_listing_publications ───────────────────────────────────────
    op.create_table(
        "property_listing_publications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),  # no FK: real_estate_projects.id is UUID
        sa.Column("unit_id", sa.String(36), nullable=True),  # no FK: project_units.id is UUID
        sa.Column("property_listing_id", sa.String(36), nullable=True),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        # Marketing copy (AI flags)
        sa.Column("listing_title", sa.String(255), nullable=True),
        sa.Column("listing_title_ai", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("short_description", sa.Text, nullable=True),
        sa.Column("short_description_ai", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("full_description", sa.Text, nullable=True),
        sa.Column("full_description_ai", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("highlights", sa.Text, nullable=True),
        sa.Column("highlights_ai", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("faq_content", sa.Text, nullable=True),
        sa.Column("faq_ai", sa.Boolean, nullable=False, server_default="false"),
        # SEO
        sa.Column("slug", sa.String(255), nullable=True),
        sa.Column("seo_title", sa.String(255), nullable=True),
        sa.Column("seo_description", sa.String(500), nullable=True),
        sa.Column("canonical_url", sa.Text, nullable=True),
        sa.Column("indexing_state", sa.String(20), nullable=False, server_default="noindex"),
        # Publication state
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        # Stale detection
        sa.Column("last_inventory_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_stale", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("stale_reason", sa.String(255), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_plp_org_project_status", "property_listing_publications", ["organization_id", "project_id", "status"])
    op.create_index("ix_plp_org_unit", "property_listing_publications", ["organization_id", "unit_id"])
    op.create_index("ix_plp_slug", "property_listing_publications", ["slug"])
    op.create_index("ix_plp_stale", "property_listing_publications", ["is_stale"])

    # ─── listing_distributions ───────────────────────────────────────────────
    op.create_table(
        "listing_distributions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("listing_publication_id", sa.String(36), sa.ForeignKey("property_listing_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=True),
        sa.Column("external_listing_reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("listing_publication_id", "channel", "provider_name", name="uq_listing_dist_channel_provider"),
    )
    op.create_index("ix_listing_dist_org_channel", "listing_distributions", ["organization_id", "channel"])
    op.create_index("ix_listing_dist_publication", "listing_distributions", ["listing_publication_id"])

    # ─── marketing_landing_pages ─────────────────────────────────────────────
    op.create_table(
        "marketing_landing_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),  # no FK: real_estate_projects.id is UUID
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("page_title", sa.String(255), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        sa.Column("canonical_url", sa.Text, nullable=True),
        sa.Column("indexing_state", sa.String(20), nullable=False, server_default="noindex"),
        sa.Column("hero_content", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("inventory_highlights", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("pricing_disclosure", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("amenities_content", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("location_content", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("trust_content", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("form_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("form_config", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("utm_source", sa.String(255), nullable=True),
        sa.Column("utm_medium", sa.String(255), nullable=True),
        sa.Column("utm_campaign", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "slug", name="uq_landing_page_org_slug"),
    )
    op.create_index("ix_landing_page_org_status", "marketing_landing_pages", ["organization_id", "status"])
    op.create_index("ix_landing_page_org_project", "marketing_landing_pages", ["organization_id", "project_id"])
    op.create_index("ix_landing_page_slug", "marketing_landing_pages", ["slug"])

    # ─── tracking_links ───────────────────────────────────────────────────────
    op.create_table(
        "tracking_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("landing_page_id", sa.String(36), sa.ForeignKey("marketing_landing_pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel_partner_id", sa.String(36), nullable=True),  # no FK: channel_partners.id is UUID
        sa.Column("destination_url", sa.Text, nullable=False),
        sa.Column("utm_source", sa.String(255), nullable=True),
        sa.Column("utm_medium", sa.String(255), nullable=True),
        sa.Column("utm_campaign", sa.String(255), nullable=True),
        sa.Column("utm_content", sa.String(255), nullable=True),
        sa.Column("utm_term", sa.String(255), nullable=True),
        sa.Column("short_token", sa.String(16), nullable=False, unique=True),
        sa.Column("qr_asset_id", sa.String(36), nullable=True),
        sa.Column("click_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tracking_link_org_campaign", "tracking_links", ["organization_id", "campaign_id"])
    op.create_index("ix_tracking_link_short_token", "tracking_links", ["short_token"])

    # ─── campaign_events ─────────────────────────────────────────────────────
    op.create_table(
        "campaign_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("deal_id", sa.String(36), nullable=True),
        sa.Column("unit_id", sa.String(36), nullable=True),
        sa.Column("tracking_link_id", sa.String(36), nullable=True),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True, unique=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_event_org_campaign", "campaign_events", ["organization_id", "campaign_id"])
    op.create_index("ix_campaign_event_type", "campaign_events", ["event_type"])
    op.create_index("ix_campaign_event_occurred", "campaign_events", ["occurred_at"])

    # ─── project_launches ────────────────────────────────────────────────────
    op.create_table(
        "project_launches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),  # no FK: real_estate_projects.id is UUID
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("landing_page_id", sa.String(36), sa.ForeignKey("marketing_landing_pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        # Checklist gates
        sa.Column("gate_project_configured", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_inventory_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_pricing_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_media_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_landing_page_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_lead_form_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_tracking_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_partner_distribution_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_campaign_ready", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gate_approval_complete", sa.Boolean, nullable=False, server_default="false"),
        # Schedule & approval
        sa.Column("scheduled_launch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_project_launch_org_project", "project_launches", ["organization_id", "project_id"])
    op.create_index("ix_project_launch_status", "project_launches", ["status"])

    # ─── campaign_listing_links ───────────────────────────────────────────────
    op.create_table(
        "campaign_listing_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_publication_id", sa.String(36), sa.ForeignKey("property_listing_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("campaign_id", "listing_publication_id", name="uq_campaign_listing_link"),
    )


def downgrade() -> None:
    op.drop_table("campaign_listing_links")
    op.drop_table("project_launches")
    op.drop_table("campaign_events")
    op.drop_table("tracking_links")
    op.drop_table("marketing_landing_pages")
    op.drop_table("listing_distributions")
    op.drop_table("property_listing_publications")
    op.drop_table("marketing_assets")
    op.drop_table("campaign_audit_logs")
    op.drop_table("campaign_approvals")
    op.drop_table("marketing_campaigns")
