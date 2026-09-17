"""Part 35 AI Real Estate Revenue Autopilot

Revision ID: 0026_revenue_autopilot
Revises: 0025_property_total_floors
Create Date: 2026-09-16 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0026_revenue_autopilot'
down_revision = '0025_property_total_floors'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. revenue_opportunities table
    if "revenue_opportunities" not in tables:
        op.create_table(
            "revenue_opportunities",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("property_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_listings.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("opportunity_type", sa.String(length=50), nullable=False),
            sa.Column("priority", sa.String(length=20), server_default="MEDIUM", nullable=False),
            sa.Column("urgency", sa.String(length=20), server_default="MEDIUM", nullable=False),
            sa.Column("opportunity_score", sa.Float(), server_default="50.0", nullable=False),
            sa.Column("match_score", sa.Float(), server_default="0.0", nullable=False),
            sa.Column("confidence", sa.Float(), server_default="0.8", nullable=False),
            sa.Column("status", sa.String(length=30), server_default="NEW", nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("why_now", sa.Text(), nullable=False),
            sa.Column("why_property", sa.Text(), nullable=True),
            sa.Column("risk_of_inactivity", sa.Text(), nullable=True),
            sa.Column("recommended_action", sa.String(length=50), server_default="CALL_LEAD", nullable=False),
            sa.Column("recommended_channel", sa.String(length=30), server_default="CALL", nullable=False),
            sa.Column("recommended_property_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("alternative_properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("positive_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("negative_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("data_freshness", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("call_brief", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("email_draft", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("dedup_key", sa.String(length=255), nullable=False),
            sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("scoring_version", sa.String(length=20), server_default="v1", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dismissal_reason", sa.String(length=255), nullable=True),
            sa.Column("feedback_rating", sa.String(length=20), nullable=True),
            sa.Column("feedback_notes", sa.Text(), nullable=True),
            sa.Column("actual_outcome", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.String(length=36), nullable=True),
        )
        op.create_index("ix_rev_opp_org_status", "revenue_opportunities", ["organization_id", "status"])
        op.create_index("ix_rev_opp_org_score", "revenue_opportunities", ["organization_id", "opportunity_score"])
        op.create_index("ix_rev_opp_org_urgency", "revenue_opportunities", ["organization_id", "urgency"])
        op.create_index("ix_rev_opp_dedup", "revenue_opportunities", ["dedup_key"])
        op.create_index("ix_rev_opp_lead_status", "revenue_opportunities", ["lead_id", "status"])
        op.create_index("ix_rev_opp_broker", "revenue_opportunities", ["broker_id"])
        op.create_index("ix_rev_opp_property", "revenue_opportunities", ["property_id"])
        op.create_index("ix_rev_opp_assigned", "revenue_opportunities", ["assigned_agent_id"])

    # 2. revenue_feedback_logs table
    if "revenue_feedback_logs" not in tables:
        op.create_table(
            "revenue_feedback_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("revenue_opportunities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("property_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_listings.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action_type", sa.String(length=50), nullable=False),
            sa.Column("rating", sa.String(length=20), nullable=True),
            sa.Column("reason", sa.String(length=255), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("actual_outcome", sa.String(length=50), nullable=True),
            sa.Column("features_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_rev_fb_org_created", "revenue_feedback_logs", ["organization_id", "created_at"])
        op.create_index("ix_rev_fb_opp", "revenue_feedback_logs", ["opportunity_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "revenue_feedback_logs" in tables:
        op.drop_table("revenue_feedback_logs")
    if "revenue_opportunities" in tables:
        op.drop_table("revenue_opportunities")
