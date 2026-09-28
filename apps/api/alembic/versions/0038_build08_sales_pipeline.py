"""Build 08 — Sales Pipeline OS: New canonical tables

Revision ID: 0038_build08_sales_pipeline
Revises: 0036_build07_workitem_commitment
Create Date: 2026-09-26 15:25:00.000000

Creates:
  - sales_pipelines
  - pipeline_stage_configs
  - opportunity_stage_history
  - site_visits
  - site_visit_outcomes
  - negotiation_rounds
  - property_shortlists
  - booking_intents
  - unit_holds
  - property_payment_transactions
  - revenue_events
  - booking_reconciliation_tasks

Also adds (additive, nullable columns):
  - scheduling_meetings.opportunity_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0038_build08_sales_pipeline"
down_revision = "0036_build07_workitem_commitment"
branch_labels = None
depends_on = None

_IS_PG = True  # Set to False for SQLite testing


def _uuid_col(name, **kwargs):
    if _IS_PG:
        return sa.Column(name, postgresql.UUID(as_uuid=True), **kwargs)
    return sa.Column(name, sa.String(36), **kwargs)


def _jsonb_col(name, **kwargs):
    if _IS_PG:
        return sa.Column(name, postgresql.JSONB(), **kwargs)
    return sa.Column(name, sa.JSON(), **kwargs)


def upgrade():
    # ------------------------------------------------------------------
    # sales_pipelines
    # ------------------------------------------------------------------
    op.create_table(
        "sales_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("pipeline_type", sa.String(50), nullable=False, server_default="RESIDENTIAL_SALES"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_sales_pipelines_org_active", "sales_pipelines", ["organization_id", "is_active"])
    op.create_index("ix_sales_pipelines_org_type", "sales_pipelines", ["organization_id", "pipeline_type"])

    # ------------------------------------------------------------------
    # pipeline_stage_configs
    # ------------------------------------------------------------------
    op.create_table(
        "pipeline_stage_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("semantic_type", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#3B82F6"),
        sa.Column("sla_hours", sa.Integer, nullable=True),
        sa.Column("required_fields", postgresql.JSONB(), nullable=True),
        sa.Column("allowed_actions", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("pipeline_id", "semantic_type", name="uq_stage_config_pipeline_semantic"),
    )
    op.create_index("ix_stage_config_pipeline_pos", "pipeline_stage_configs", ["pipeline_id", "position"])

    # ------------------------------------------------------------------
    # opportunity_stage_history
    # ------------------------------------------------------------------
    op.create_table(
        "opportunity_stage_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_pipelines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pipeline_version", sa.Integer, nullable=True),
        sa.Column("from_stage", sa.String(50), nullable=True),
        sa.Column("to_stage", sa.String(50), nullable=False),
        sa.Column("changed_by_id", sa.String(64), nullable=True),
        sa.Column("changed_by_type", sa.String(20), nullable=False, server_default="HUMAN"),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("duration_hours_in_previous_stage", sa.Integer, nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_opp_stage_hist_deal_at", "opportunity_stage_history", ["deal_id", "changed_at"])
    op.create_index("ix_opp_stage_hist_org_stage", "opportunity_stage_history", ["organization_id", "to_stage"])

    # ------------------------------------------------------------------
    # property_shortlists
    # ------------------------------------------------------------------
    op.create_table(
        "property_shortlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("property_listing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="SHORTLISTED"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("added_by_id", sa.String(64), nullable=True),
        sa.Column("added_by_type", sa.String(20), nullable=False, server_default="HUMAN"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissal_reason", sa.Text, nullable=True),
        sa.Column("property_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_shortlist_deal_status", "property_shortlists", ["deal_id", "status"])
    op.create_index("ix_shortlist_org_unit", "property_shortlists", ["organization_id", "unit_id"])

    # ------------------------------------------------------------------
    # site_visits
    # ------------------------------------------------------------------
    op.create_table(
        "site_visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("property_listing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scheduling_meeting_id", sa.String(36), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("meeting_point", sa.String(255), nullable=True),
        sa.Column("location_address", sa.String(500), nullable=True),
        sa.Column("location_type", sa.String(30), nullable=False, server_default="PHYSICAL"),
        sa.Column("assigned_agent_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="REQUESTED"),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendance_status", sa.String(30), nullable=True),
        sa.Column("visit_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_site_visits_deal_status", "site_visits", ["deal_id", "status"])
    op.create_index("ix_site_visits_org_scheduled", "site_visits", ["organization_id", "scheduled_at"])
    op.create_index("ix_site_visits_org_status", "site_visits", ["organization_id", "status"])

    # ------------------------------------------------------------------
    # site_visit_outcomes
    # ------------------------------------------------------------------
    op.create_table(
        "site_visit_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("site_visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("site_visits.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_interest_level", sa.Integer, nullable=True),
        sa.Column("customer_feedback", sa.Text, nullable=True),
        sa.Column("preferred_property_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("preferred_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("objections", postgresql.JSONB(), nullable=True),
        sa.Column("positive_signals", postgresql.JSONB(), nullable=True),
        sa.Column("next_action", sa.String(100), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_notes", sa.Text, nullable=True),
        sa.Column("recorded_by_id", sa.String(64), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_site_visit_outcomes_org", "site_visit_outcomes", ["organization_id"])

    # ------------------------------------------------------------------
    # negotiation_rounds
    # ------------------------------------------------------------------
    op.create_table(
        "negotiation_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("round_type", sa.String(30), nullable=False),
        sa.Column("actor", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("price", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AED"),
        sa.Column("original_price", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("payment_plan", sa.String(100), nullable=True),
        sa.Column("payment_terms", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("approved_by_id", sa.String(64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("deal_id", "round_number", name="uq_negotiation_round_number"),
    )
    op.create_index("ix_neg_rounds_deal_at", "negotiation_rounds", ["deal_id", "occurred_at"])
    op.create_index("ix_neg_rounds_org", "negotiation_rounds", ["organization_id"])

    # ------------------------------------------------------------------
    # booking_intents
    # ------------------------------------------------------------------
    op.create_table(
        "booking_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("property_listing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intended_price", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AED"),
        sa.Column("intended_payment_terms", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="CREATED"),
        sa.Column("created_by_id", sa.String(64), nullable=True),
        sa.Column("created_by_type", sa.String(20), nullable=False, server_default="HUMAN"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_booking_intents_deal_status", "booking_intents", ["deal_id", "status"])
    op.create_index("ix_booking_intents_org_status", "booking_intents", ["organization_id", "status"])
    op.create_index("ix_booking_intents_expires", "booking_intents", ["expires_at"])

    # ------------------------------------------------------------------
    # unit_holds
    # ------------------------------------------------------------------
    op.create_table(
        "unit_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by_id", sa.String(64), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by_id", sa.String(64), nullable=True),
        sa.Column("release_reason", sa.Text, nullable=True),
        sa.Column("converted_to_reservation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "unit_id", "status", name="uq_unit_hold_active_per_unit"),
    )
    op.create_index("ix_unit_holds_unit_status", "unit_holds", ["unit_id", "status"])
    op.create_index("ix_unit_holds_org_expires", "unit_holds", ["organization_id", "expires_at"])

    # ------------------------------------------------------------------
    # property_payment_transactions
    # ------------------------------------------------------------------
    op.create_table(
        "property_payment_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_provider", sa.String(50), nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
        sa.Column("provider_order_id", sa.String(255), nullable=True),
        sa.Column("provider_event_id", sa.String(255), nullable=True, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("original_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("refund_reason", sa.Text, nullable=True),
        sa.Column("refund_approved_by_id", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("recorded_by_id", sa.String(64), nullable=True),
        sa.Column("recorded_by_type", sa.String(20), nullable=False, server_default="SYSTEM"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_prop_payments_deal_status", "property_payment_transactions", ["deal_id", "status"])
    op.create_index("ix_prop_payments_org_status", "property_payment_transactions", ["organization_id", "status"])
    op.create_index("ix_prop_payments_provider_id", "property_payment_transactions", ["provider_payment_id"])

    # ------------------------------------------------------------------
    # revenue_events
    # ------------------------------------------------------------------
    op.create_table(
        "revenue_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False, unique=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("site_visit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("booking_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="SYSTEM"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="v1"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_revenue_events_org_type", "revenue_events", ["organization_id", "event_type"])
    op.create_index("ix_revenue_events_org_time", "revenue_events", ["organization_id", "occurred_at"])
    op.create_index("ix_revenue_events_lead", "revenue_events", ["lead_id"])
    op.create_index("ix_revenue_events_opportunity", "revenue_events", ["opportunity_id"])

    # ------------------------------------------------------------------
    # booking_reconciliation_tasks
    # ------------------------------------------------------------------
    op.create_table(
        "booking_reconciliation_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inconsistency_type", sa.String(100), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", sa.String(64), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_recon_tasks_org_status", "booking_reconciliation_tasks", ["organization_id", "status"])
    op.create_index("ix_recon_tasks_deal", "booking_reconciliation_tasks", ["deal_id"])

    # ------------------------------------------------------------------
    # Additive column: scheduling_meetings.opportunity_id
    # Nullable — backward compatible
    # ------------------------------------------------------------------
    op.add_column(
        "scheduling_meetings",
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    try:
        op.create_index("ix_scheduling_meetings_opportunity", "scheduling_meetings", ["opportunity_id"])
    except Exception:
        pass  # Index may already exist


def downgrade():
    # Drop indexes first
    op.drop_index("ix_recon_tasks_deal", table_name="booking_reconciliation_tasks")
    op.drop_index("ix_recon_tasks_org_status", table_name="booking_reconciliation_tasks")
    op.drop_index("ix_revenue_events_opportunity", table_name="revenue_events")
    op.drop_index("ix_revenue_events_lead", table_name="revenue_events")
    op.drop_index("ix_revenue_events_org_time", table_name="revenue_events")
    op.drop_index("ix_revenue_events_org_type", table_name="revenue_events")
    op.drop_index("ix_prop_payments_provider_id", table_name="property_payment_transactions")
    op.drop_index("ix_prop_payments_org_status", table_name="property_payment_transactions")
    op.drop_index("ix_prop_payments_deal_status", table_name="property_payment_transactions")
    op.drop_index("ix_unit_holds_org_expires", table_name="unit_holds")
    op.drop_index("ix_unit_holds_unit_status", table_name="unit_holds")
    op.drop_index("ix_booking_intents_expires", table_name="booking_intents")
    op.drop_index("ix_booking_intents_org_status", table_name="booking_intents")
    op.drop_index("ix_booking_intents_deal_status", table_name="booking_intents")
    op.drop_index("ix_neg_rounds_org", table_name="negotiation_rounds")
    op.drop_index("ix_neg_rounds_deal_at", table_name="negotiation_rounds")
    op.drop_index("ix_shortlist_org_unit", table_name="property_shortlists")
    op.drop_index("ix_shortlist_deal_status", table_name="property_shortlists")
    op.drop_index("ix_site_visit_outcomes_org", table_name="site_visit_outcomes")
    op.drop_index("ix_site_visits_org_status", table_name="site_visits")
    op.drop_index("ix_site_visits_org_scheduled", table_name="site_visits")
    op.drop_index("ix_site_visits_deal_status", table_name="site_visits")
    op.drop_index("ix_opp_stage_hist_org_stage", table_name="opportunity_stage_history")
    op.drop_index("ix_opp_stage_hist_deal_at", table_name="opportunity_stage_history")
    op.drop_index("ix_stage_config_pipeline_pos", table_name="pipeline_stage_configs")
    op.drop_index("ix_sales_pipelines_org_type", table_name="sales_pipelines")
    op.drop_index("ix_sales_pipelines_org_active", table_name="sales_pipelines")

    # Drop tables in reverse dependency order
    op.drop_table("booking_reconciliation_tasks")
    op.drop_table("revenue_events")
    op.drop_table("property_payment_transactions")
    op.drop_table("unit_holds")
    op.drop_table("booking_intents")
    op.drop_table("negotiation_rounds")
    op.drop_table("site_visit_outcomes")
    op.drop_table("site_visits")
    op.drop_table("property_shortlists")
    op.drop_table("opportunity_stage_history")
    op.drop_table("pipeline_stage_configs")
    op.drop_table("sales_pipelines")

    # Remove additive column
    op.drop_column("scheduling_meetings", "opportunity_id")
