"""Build 09 — Revenue Intelligence OS: New canonical tables

Revision ID: 0039_build09_revenue_intelligence
Revises: 0038_build08_sales_pipeline
Create Date: 2026-09-26 16:30:00.000000

Creates:
  - metric_definitions
  - attribution_touchpoints
  - attribution_results
  - forecast_snapshots_v2
  - revenue_leakage_events_v2
  - revenue_anomalies
  - unit_economics_records
  - revenue_reconciliation_records
  - ai_contribution_records
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0039_build09_revenue_intelligence"
down_revision = "0038_build08_sales_pipeline"
branch_labels = None
depends_on = None

_IS_PG = True


def _uuid_col(name, **kwargs):
    if _IS_PG:
        return sa.Column(name, postgresql.UUID(as_uuid=True), **kwargs)
    return sa.Column(name, sa.String(36), **kwargs)


def _jsonb_col(name, **kwargs):
    if _IS_PG:
        return sa.Column(name, postgresql.JSONB(), **kwargs)
    return sa.Column(name, sa.JSON(), **kwargs)


def _money_col(name, **kwargs):
    return sa.Column(name, sa.Numeric(precision=20, scale=4), **kwargs)


def _pct_col(name, **kwargs):
    return sa.Column(name, sa.Numeric(precision=7, scale=4), **kwargs)


def upgrade():
    # ------------------------------------------------------------------
    # 1. metric_definitions
    # ------------------------------------------------------------------
    op.create_table(
        "metric_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_id", sa.String(100), nullable=False),
        sa.Column("metric_version", sa.String(20), nullable=False, server_default="v1"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("formula", sa.Text, nullable=False),
        sa.Column("numerator_definition", sa.Text, nullable=True),
        sa.Column("denominator_definition", sa.Text, nullable=True),
        _jsonb_col("source_tables", nullable=False, server_default=sa.text("'[]'::jsonb")),
        _jsonb_col("filters", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("requires_currency", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("requires_date_range", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("timezone_sensitive", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("metric_id", "metric_version", name="uq_metric_def_id_version"),
    )
    op.create_index("ix_metric_definitions_organization_id", "metric_definitions", ["organization_id"])
    op.create_index("ix_metric_definitions_metric_id", "metric_definitions", ["metric_id"])
    op.create_index("ix_metric_def_org", "metric_definitions", ["organization_id", "metric_id"])

    # ------------------------------------------------------------------
    # 2. attribution_touchpoints
    # ------------------------------------------------------------------
    op.create_table(
        "attribution_touchpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_name", sa.String(255), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("utm_source", sa.String(255), nullable=True),
        sa.Column("utm_medium", sa.String(255), nullable=True),
        sa.Column("utm_campaign", sa.String(255), nullable=True),
        sa.Column("utm_content", sa.String(255), nullable=True),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="lead"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        _pct_col("weight_first_touch", nullable=True),
        _pct_col("weight_last_touch", nullable=True),
        _pct_col("weight_linear", nullable=True),
        _pct_col("weight_time_decay", nullable=True),
        _pct_col("weight_position_based", nullable=True),
        _jsonb_col("payload", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_attribution_touchpoints_organization_id", "attribution_touchpoints", ["organization_id"])
    op.create_index("ix_attribution_touchpoints_lead_id", "attribution_touchpoints", ["lead_id"])
    op.create_index("ix_attribution_touchpoints_identity_id", "attribution_touchpoints", ["identity_id"])
    op.create_index("ix_attribution_touchpoints_occurred_at", "attribution_touchpoints", ["occurred_at"])
    op.create_index("ix_attr_touch_org_lead", "attribution_touchpoints", ["organization_id", "lead_id"])
    op.create_index("ix_attr_touch_org_identity", "attribution_touchpoints", ["organization_id", "identity_id"])
    op.create_index("ix_attr_touch_org_time", "attribution_touchpoints", ["organization_id", "occurred_at"])
    op.create_index("ix_attr_touch_channel", "attribution_touchpoints", ["organization_id", "channel"])

    # ------------------------------------------------------------------
    # 3. attribution_results
    # ------------------------------------------------------------------
    op.create_table(
        "attribution_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revenue_event_id", sa.String(64), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        _money_col("attributed_amount", nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("attribution_model", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(20), nullable=False, server_default="v1"),
        sa.Column("window_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("touchpoint_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("first_touch_channel", sa.String(50), nullable=True),
        sa.Column("first_touch_source", sa.String(100), nullable=True),
        sa.Column("first_touch_campaign", sa.String(255), nullable=True),
        sa.Column("first_touch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_touch_channel", sa.String(50), nullable=True),
        sa.Column("last_touch_source", sa.String(100), nullable=True),
        sa.Column("last_touch_campaign", sa.String(255), nullable=True),
        sa.Column("last_touch_at", sa.DateTime(timezone=True), nullable=True),
        _jsonb_col("touchpoint_breakdown", nullable=False, server_default=sa.text("'{}'::jsonb")),
        _jsonb_col("calculation_inputs", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "organization_id", "revenue_event_id", "attribution_model", "model_version",
            name="uq_attribution_result_event_model"
        ),
    )
    op.create_index("ix_attribution_results_organization_id", "attribution_results", ["organization_id"])
    op.create_index("ix_attribution_results_revenue_event_id", "attribution_results", ["revenue_event_id"])
    op.create_index("ix_attribution_results_lead_id", "attribution_results", ["lead_id"])
    op.create_index("ix_attribution_results_attribution_model", "attribution_results", ["attribution_model"])
    op.create_index("ix_attr_result_org_model", "attribution_results", ["organization_id", "attribution_model"])
    op.create_index("ix_attr_result_event", "attribution_results", ["revenue_event_id"])

    # ------------------------------------------------------------------
    # 4. forecast_snapshots_v2
    # ------------------------------------------------------------------
    op.create_table(
        "forecast_snapshots_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("method_version", sa.String(20), nullable=False, server_default="v2"),
        sa.Column("scenario", sa.String(20), nullable=False, server_default="BASE"),
        _money_col("pipeline_value", nullable=True),
        _money_col("weighted_pipeline", nullable=True),
        _money_col("forecast_value", nullable=True),
        _money_col("upside_value", nullable=True),
        _money_col("downside_value", nullable=True),
        sa.Column("reporting_currency", sa.String(3), nullable=False, server_default="AED"),
        sa.Column("quality", sa.String(20), nullable=False, server_default="GOOD"),
        sa.Column("quality_notes", sa.Text, nullable=True),
        sa.Column("opportunity_count", sa.Integer, nullable=False, server_default="0"),
        _jsonb_col("stage_distribution", nullable=False, server_default=sa.text("'{}'::jsonb")),
        _jsonb_col("probability_assumptions", nullable=False, server_default=sa.text("'{}'::jsonb")),
        _jsonb_col("opportunity_ids_included", nullable=False, server_default=sa.text("'[]'::jsonb")),
        _money_col("actual_revenue", nullable=True),
        sa.Column("actual_bookings", sa.Integer, nullable=True),
        _pct_col("forecast_error_pct", nullable=True),
        sa.Column("is_reconciled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_forecast_snapshots_v2_organization_id", "forecast_snapshots_v2", ["organization_id"])
    op.create_index("ix_forecast_snapshots_v2_period_type", "forecast_snapshots_v2", ["period_type"])
    op.create_index("ix_forecast_snapshots_v2_period_start", "forecast_snapshots_v2", ["period_start"])
    op.create_index("ix_forecast_snapshots_v2_created_at", "forecast_snapshots_v2", ["created_at"])
    op.create_index("ix_forecast_v2_org_period", "forecast_snapshots_v2", ["organization_id", "period_start"])
    op.create_index("ix_forecast_v2_org_method", "forecast_snapshots_v2", ["organization_id", "method"])

    # ------------------------------------------------------------------
    # 5. revenue_leakage_events_v2
    # ------------------------------------------------------------------
    op.create_table(
        "revenue_leakage_events_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("site_visit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("booking_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("condition", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("age_days", sa.Integer, nullable=False, server_default="0"),
        _money_col("estimated_value_at_risk", nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        _jsonb_col("evidence", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("owner_id", sa.String(64), nullable=True),
        sa.Column("owner_type", sa.String(20), nullable=False, server_default="broker"),
        sa.Column("work_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommended_action", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_suppressed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppression_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolution_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_action", sa.Text, nullable=True),
        sa.Column("resolution_outcome", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_revenue_leakage_events_v2_organization_id", "revenue_leakage_events_v2", ["organization_id"])
    op.create_index("ix_revenue_leakage_events_v2_lead_id", "revenue_leakage_events_v2", ["lead_id"])
    op.create_index("ix_revenue_leakage_events_v2_opportunity_id", "revenue_leakage_events_v2", ["opportunity_id"])
    op.create_index("ix_revenue_leakage_events_v2_condition", "revenue_leakage_events_v2", ["condition"])
    op.create_index("ix_revenue_leakage_events_v2_severity", "revenue_leakage_events_v2", ["severity"])
    op.create_index("ix_revenue_leakage_events_v2_detected_at", "revenue_leakage_events_v2", ["detected_at"])
    op.create_index("ix_revenue_leakage_events_v2_is_resolved", "revenue_leakage_events_v2", ["is_resolved"])
    op.create_index("ix_leakage_v2_org_condition", "revenue_leakage_events_v2", ["organization_id", "condition"])
    op.create_index("ix_leakage_v2_org_severity", "revenue_leakage_events_v2", ["organization_id", "severity"])
    op.create_index("ix_leakage_v2_org_resolved", "revenue_leakage_events_v2", ["organization_id", "is_resolved"])
    op.create_index("ix_leakage_v2_org_detected", "revenue_leakage_events_v2", ["organization_id", "detected_at"])

    # ------------------------------------------------------------------
    # 6. revenue_anomalies
    # ------------------------------------------------------------------
    op.create_table(
        "revenue_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        _money_col("baseline_value", nullable=True),
        _money_col("observed_value", nullable=True),
        _pct_col("threshold_pct", nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        _jsonb_col("evidence", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolution_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_revenue_anomalies_organization_id", "revenue_anomalies", ["organization_id"])
    op.create_index("ix_revenue_anomalies_metric", "revenue_anomalies", ["metric"])
    op.create_index("ix_revenue_anomalies_detected_at", "revenue_anomalies", ["detected_at"])
    op.create_index("ix_revenue_anomalies_is_resolved", "revenue_anomalies", ["is_resolved"])
    op.create_index("ix_anomaly_org_metric", "revenue_anomalies", ["organization_id", "metric"])
    op.create_index("ix_anomaly_org_detected", "revenue_anomalies", ["organization_id", "detected_at"])

    # ------------------------------------------------------------------
    # 7. unit_economics_records
    # ------------------------------------------------------------------
    op.create_table(
        "unit_economics_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reporting_currency", sa.String(3), nullable=False, server_default="AED"),
        sa.Column("total_leads", sa.Integer, nullable=True),
        sa.Column("qualified_leads", sa.Integer, nullable=True),
        sa.Column("total_appointments", sa.Integer, nullable=True),
        sa.Column("total_site_visits", sa.Integer, nullable=True),
        sa.Column("total_bookings", sa.Integer, nullable=True),
        _money_col("gross_booking_value", nullable=True),
        _money_col("collected_revenue", nullable=True),
        _money_col("net_revenue", nullable=True),
        _money_col("refunded_amount", nullable=True),
        _money_col("total_acquisition_cost", nullable=True),
        _money_col("ai_cost", nullable=True),
        _money_col("communication_cost", nullable=True),
        _money_col("cac", nullable=True),
        _money_col("cost_per_qualified_lead", nullable=True),
        _money_col("cost_per_appointment", nullable=True),
        _money_col("cost_per_site_visit", nullable=True),
        _money_col("cost_per_booking", nullable=True),
        _money_col("revenue_per_lead", nullable=True),
        _money_col("revenue_per_booking", nullable=True),
        _pct_col("contribution_margin", nullable=True),
        _jsonb_col("data_quality_notes", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_unit_economics_records_organization_id", "unit_economics_records", ["organization_id"])
    op.create_index("ix_unit_economics_records_period_start", "unit_economics_records", ["period_start"])
    op.create_index("ix_unit_econ_org_period", "unit_economics_records", ["organization_id", "period_start"])

    # ------------------------------------------------------------------
    # 8. revenue_reconciliation_records
    # ------------------------------------------------------------------
    op.create_table(
        "revenue_reconciliation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_run_id", sa.String(64), nullable=False),
        sa.Column("difference_type", sa.String(100), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revenue_event_id", sa.String(64), nullable=True),
        _money_col("expected_amount", nullable=True),
        _money_col("actual_amount", nullable=True),
        sa.Column("expected_currency", sa.String(3), nullable=True),
        sa.Column("actual_currency", sa.String(3), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        _jsonb_col("evidence", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("work_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolution_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_revenue_reconciliation_records_organization_id", "revenue_reconciliation_records", ["organization_id"])
    op.create_index("ix_revenue_reconciliation_records_reconciliation_run_id", "revenue_reconciliation_records", ["reconciliation_run_id"])
    op.create_index("ix_revenue_reconciliation_records_difference_type", "revenue_reconciliation_records", ["difference_type"])
    op.create_index("ix_revenue_reconciliation_records_is_resolved", "revenue_reconciliation_records", ["is_resolved"])
    op.create_index("ix_recon_org_type", "revenue_reconciliation_records", ["organization_id", "difference_type"])
    op.create_index("ix_recon_run", "revenue_reconciliation_records", ["reconciliation_run_id"])

    # ------------------------------------------------------------------
    # 9. ai_contribution_records
    # ------------------------------------------------------------------
    op.create_table(
        "ai_contribution_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revenue_event_id", sa.String(64), nullable=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("agent_run_id", sa.String(64), nullable=True),
        sa.Column("action_type", sa.String(100), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subsequent_event_type", sa.String(100), nullable=True),
        sa.Column("subsequent_event_at", sa.DateTime(timezone=True), nullable=True),
        _jsonb_col("payload", nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_contribution_records_organization_id", "ai_contribution_records", ["organization_id"])
    op.create_index("ix_ai_contribution_records_lead_id", "ai_contribution_records", ["lead_id"])
    op.create_index("ix_ai_contribution_records_category", "ai_contribution_records", ["category"])
    op.create_index("ix_ai_contribution_records_occurred_at", "ai_contribution_records", ["occurred_at"])
    op.create_index("ix_ai_contrib_org_category", "ai_contribution_records", ["organization_id", "category"])
    op.create_index("ix_ai_contrib_org_lead", "ai_contribution_records", ["organization_id", "lead_id"])


def downgrade():
    op.drop_table("ai_contribution_records")
    op.drop_table("revenue_reconciliation_records")
    op.drop_table("unit_economics_records")
    op.drop_table("revenue_anomalies")
    op.drop_table("revenue_leakage_events_v2")
    op.drop_table("forecast_snapshots_v2")
    op.drop_table("attribution_results")
    op.drop_table("attribution_touchpoints")
    op.drop_table("metric_definitions")
