"""Part 11 — Revenue Intelligence Layer: New domain tables.

Revision ID: 0028_revenue_intelligence
Revises: 0027_customer_identity_canonical
Create Date: 2026-09-21 00:00:00.000000

Creates:
  revenue_funnel_snapshots  — periodic point-in-time funnel state per org
  revenue_leakage_events    — immutable record of funnel exit without conversion

Both tables are OBSERVATION-ONLY. They do not alter any canonical entity tables.
All guards use `if table not in tables` for idempotent upgrades.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0028_revenue_intelligence'
down_revision = '0027_customer_identity_canonical'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    is_sqlite = bind.dialect.name == "sqlite"

    # Dialect-aware JSONB vs JSON
    if is_sqlite:
        jsonb_type = sa.JSON()
        uuid_type = sa.String(36)
    else:
        jsonb_type = postgresql.JSONB(astext_type=sa.Text())
        uuid_type = postgresql.UUID(as_uuid=True)

    # ── 1. revenue_funnel_snapshots ───────────────────────────────────────────
    if "revenue_funnel_snapshots" not in tables:
        op.create_table(
            "revenue_funnel_snapshots",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("organization_id", uuid_type, nullable=False),
            sa.Column("period_type", sa.String(20), server_default="DAILY", nullable=False),
            sa.Column("snapshot_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("total_leads", sa.Integer(), server_default="0", nullable=False),
            sa.Column("leads_new", sa.Integer(), server_default="0", nullable=False),
            sa.Column("leads_contacted", sa.Integer(), server_default="0", nullable=False),
            sa.Column("leads_qualified", sa.Integer(), server_default="0", nullable=False),
            sa.Column("leads_site_visit", sa.Integer(), server_default="0", nullable=False),
            sa.Column("leads_negotiation", sa.Integer(), server_default="0", nullable=False),
            sa.Column("leads_converted", sa.Integer(), server_default="0", nullable=False),
            sa.Column("leads_lost", sa.Integer(), server_default="0", nullable=False),
            sa.Column("active_opportunities", sa.Integer(), server_default="0", nullable=False),
            sa.Column("estimated_pipeline_value", sa.Float(), nullable=True),
            sa.Column("confirmed_revenue", sa.Float(), nullable=True),
            sa.Column("metrics", jsonb_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if is_sqlite else "now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if is_sqlite else "now()"), nullable=False),
            sa.UniqueConstraint("organization_id", "snapshot_date", "period_type", name="uq_funnel_snapshot_org_date_period"),
        )
        op.create_index("ix_funnel_snap_org_date", "revenue_funnel_snapshots", ["organization_id", "snapshot_date"])
        op.create_index("ix_funnel_snap_org_id", "revenue_funnel_snapshots", ["organization_id"])

    # ── 2. revenue_leakage_events ────────────────────────────────────────────
    if "revenue_leakage_events" not in tables:
        op.create_table(
            "revenue_leakage_events",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("organization_id", uuid_type, nullable=False),
            sa.Column(
                "lead_id", uuid_type,
                sa.ForeignKey("leads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("lost_at_stage", sa.String(100), nullable=False),
            sa.Column("days_in_stage", sa.Integer(), nullable=True),
            sa.Column("leakage_reason", sa.String(50), server_default="UNKNOWN", nullable=False),
            sa.Column("source_channel", sa.String(50), nullable=True),
            sa.Column("estimated_value_lost", sa.Float(), nullable=True),
            sa.Column("lead_score_at_loss", sa.String(20), nullable=True),
            sa.Column("had_open_opportunity", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if is_sqlite else "now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if is_sqlite else "now()"), nullable=False),
        )
        op.create_index("ix_leakage_org_stage", "revenue_leakage_events", ["organization_id", "lost_at_stage"])
        op.create_index("ix_leakage_org_detected", "revenue_leakage_events", ["organization_id", "detected_at"])
        op.create_index("ix_leakage_lead", "revenue_leakage_events", ["lead_id"])
        op.create_index("ix_leakage_org_id", "revenue_leakage_events", ["organization_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "revenue_leakage_events" in tables:
        op.drop_table("revenue_leakage_events")
    if "revenue_funnel_snapshots" in tables:
        op.drop_table("revenue_funnel_snapshots")
