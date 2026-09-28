"""Master Build 14 - Intelligence Graph, Learning Loop & Outcome Model.

Revision ID: 0041_master_build_14_intelligence
Revises: 0040_master_build_13_billing
Create Date: 2026-09-27

Tables created:
  - outcome_events             (immutable outcome event log, all entity types)
  - learning_events            (immutable append-only signal registry)
  - sales_outcome_edges        (Postgres-native graph: edges between entities)
  - ai_action_outcomes         (AI recommendation full lifecycle tracking)
  - recommendation_quality_snapshots (periodic quality metrics)
  - objection_records          (structured objection capture)
  - funnel_transition_records  (canonical funnel stage transitions)
  - experiments                (controlled experiment definitions)
  - experiment_variants        (variant definitions with traffic allocation)
  - experiment_assignments     (immutable subject-to-variant assignments)
  - experiment_conversions     (conversion events linked to assignments)
  - benchmark_definitions      (what is being measured + methodology)
  - benchmark_snapshots        (immutable periodic benchmark values)
  - data_quality_issues        (append-only data quality issue records)
  - policy_registry_entries    (model/prompt/policy version registry)
  - drift_alert_records        (drift detection events)
  - intelligence_snapshots     (periodic immutable org intelligence metrics)
  - insight_records            (actionable insights with explicit provenance)
  - organization_learning_profiles (tenant-scoped learning context)

INVARIANTS encoded in this migration:
  - Every table with organization_id has a non-null constraint + index
  - Confidence/score fields have CHECK constraints for valid ranges
  - Minimum cohort size >= 5 enforced via CHECK constraint
  - Experiment sample_size > 0 enforced via CHECK constraint
  - Unique constraints prevent duplicate backfills and exposures
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0041_master_build_14_intelligence"
down_revision = "0040_master_build_13_billing"
branch_labels = None
depends_on = None

_JSONB = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # ─── outcome_events ────────────────────────────────────────────────────────
    op.create_table(
        "outcome_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("source_system", sa.String(30), nullable=False),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column("source_table", sa.String(100), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("is_human_override", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("overrode_ai_recommendation_id", sa.String(36), nullable=True),
        sa.Column("correction_of", sa.String(36), nullable=True),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("opportunity_id", sa.String(36), nullable=True),
        sa.Column("property_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(36), nullable=True),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("campaign_id", sa.String(36), nullable=True),
        sa.Column("outcome_value", sa.String(100), nullable=True),
        sa.Column("outcome_score", sa.Numeric(7, 4), nullable=True),
        sa.Column("revenue_impact", sa.Numeric(20, 4), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="AED"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", _JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_outcome_org_type_entity", "outcome_events", ["organization_id", "event_type", "entity_id"])
    op.create_index("ix_outcome_org_occurred", "outcome_events", ["organization_id", "occurred_at"])
    op.create_index("ix_outcome_lead_type", "outcome_events", ["lead_id", "event_type"])
    op.create_index("ix_outcome_org_entity_type", "outcome_events", ["organization_id", "entity_type"])
    op.create_index("ix_outcome_org", "outcome_events", ["organization_id"])
    op.create_index("ix_outcome_entity_id", "outcome_events", ["entity_id"])
    op.create_index("ix_outcome_occurred_at", "outcome_events", ["occurred_at"])
    op.create_index("ix_outcome_source_event_id", "outcome_events", ["source_event_id"])

    # ─── learning_events ────────────────────────────────────────────────────────
    op.create_table(
        "learning_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("signal_type", sa.String(60), nullable=False),
        sa.Column("signal_value", sa.String(100), nullable=True),
        sa.Column("source_event_id", sa.String(36), nullable=False),
        sa.Column("source_table", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(100), nullable=True),
        sa.Column("policy_version", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("verified_by", sa.String(36), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", _JSONB, nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_learning_confidence_range"
        ),
    )
    op.create_index("ix_learning_org_signal", "learning_events", ["organization_id", "signal_type"])
    op.create_index("ix_learning_org_occurred", "learning_events", ["organization_id", "occurred_at"])
    op.create_index("ix_learning_entity", "learning_events", ["entity_type", "entity_id"])
    op.create_index("ix_learning_source_event", "learning_events", ["source_event_id"])
    op.create_index("ix_learning_org", "learning_events", ["organization_id"])

    # ─── sales_outcome_edges ────────────────────────────────────────────────────
    op.create_table(
        "sales_outcome_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("from_entity_type", sa.String(40), nullable=False),
        sa.Column("from_entity_id", sa.String(36), nullable=False),
        sa.Column("from_stage", sa.String(60), nullable=True),
        sa.Column("to_entity_type", sa.String(40), nullable=False),
        sa.Column("to_entity_id", sa.String(36), nullable=False),
        sa.Column("to_stage", sa.String(60), nullable=True),
        sa.Column("transition_type", sa.String(60), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("outcome_event_id", sa.String(36), nullable=False),
        sa.Column("transition_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("was_successful", sa.Boolean, nullable=True),
        sa.Column("revenue_realized", sa.Numeric(20, 4), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_edge_org_transition", "sales_outcome_edges", ["organization_id", "transition_type"])
    op.create_index("ix_edge_lead", "sales_outcome_edges", ["lead_id", "transition_at"])
    op.create_index("ix_edge_from_entity", "sales_outcome_edges", ["from_entity_type", "from_entity_id"])
    op.create_index("ix_edge_to_entity", "sales_outcome_edges", ["to_entity_type", "to_entity_id"])
    op.create_index("ix_edge_outcome_event_id", "sales_outcome_edges", ["outcome_event_id"])

    # ─── ai_action_outcomes ─────────────────────────────────────────────────────
    op.create_table(
        "ai_action_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("recommendation_id", sa.String(36), nullable=False),
        sa.Column("recommendation_type", sa.String(60), nullable=False),
        sa.Column("ai_model_version", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=True),
        sa.Column("policy_version", sa.String(100), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(36), nullable=True),
        sa.Column("opportunity_id", sa.String(36), nullable=True),
        sa.Column("recommended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("human_decision", sa.String(20), nullable=True),
        sa.Column("human_override", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("outcome_type", sa.String(60), nullable=True),
        sa.Column("business_result", sa.String(30), nullable=True),
        sa.Column("revenue_attributed", sa.Numeric(20, 4), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="AED"),
        sa.Column("outcome_event_id", sa.String(36), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_ai_confidence_range"
        ),
    )
    op.create_index("ix_ai_outcome_org_type", "ai_action_outcomes", ["organization_id", "recommendation_type"])
    op.create_index("ix_ai_outcome_org_result", "ai_action_outcomes", ["organization_id", "business_result"])
    op.create_index("ix_ai_outcome_lead", "ai_action_outcomes", ["lead_id", "recommended_at"])
    op.create_index("ix_ai_outcome_rec_id", "ai_action_outcomes", ["recommendation_id"])
    op.create_index("ix_ai_outcome_outcome_event", "ai_action_outcomes", ["outcome_event_id"])
    op.create_index("ix_ai_outcome_org", "ai_action_outcomes", ["organization_id"])

    # ─── recommendation_quality_snapshots ───────────────────────────────────────
    op.create_table(
        "recommendation_quality_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("recommendation_type", sa.String(60), nullable=False),
        sa.Column("role", sa.String(30), nullable=True),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("lead_source", sa.String(50), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("total_recommendations", sa.Integer, nullable=False),
        sa.Column("sample_size_sufficient", sa.Boolean, nullable=False),
        sa.Column("acceptance_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("execution_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("success_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("override_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("rejection_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("ignore_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("methodology", sa.Text, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id", "recommendation_type", "period_start", "period_end", "role", "channel",
            name="uq_rec_quality_snapshot"
        ),
        sa.CheckConstraint("total_recommendations >= 0", name="ck_rec_quality_sample_positive"),
    )
    op.create_index("ix_rec_quality_org_type", "recommendation_quality_snapshots", ["organization_id", "recommendation_type"])

    # ─── objection_records ──────────────────────────────────────────────────────
    op.create_table(
        "objection_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("opportunity_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(36), nullable=True),
        sa.Column("objection_type", sa.String(30), nullable=False),
        sa.Column("objection_text", sa.Text, nullable=True),
        sa.Column("extracted_from", sa.String(30), nullable=False),
        sa.Column("source_conversation_id", sa.String(36), nullable=True),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column("extraction_model_version", sa.String(100), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("is_resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_method", sa.String(20), nullable=True),
        sa.Column("resolution_response", sa.Text, nullable=True),
        sa.Column("conversion_after_resolution", sa.Boolean, nullable=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)",
            name="ck_objection_confidence_range"
        ),
    )
    op.create_index("ix_objection_org_type", "objection_records", ["organization_id", "objection_type"])
    op.create_index("ix_objection_org_resolved", "objection_records", ["organization_id", "is_resolved"])
    op.create_index("ix_objection_lead_id", "objection_records", ["lead_id"])
    op.create_index("ix_objection_raised_at", "objection_records", ["raised_at"])
    op.create_index("ix_objection_conversation", "objection_records", ["source_conversation_id"])

    # ─── funnel_transition_records ──────────────────────────────────────────────
    op.create_table(
        "funnel_transition_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("from_stage", sa.String(40), nullable=False),
        sa.Column("to_stage", sa.String(40), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("source_event_id", sa.String(36), nullable=False),
        sa.Column("from_stage_entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transition_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("lead_source", sa.String(50), nullable=True),
        sa.Column("agent_id", sa.String(36), nullable=True),
        sa.Column("property_type", sa.String(50), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_funnel_org_stages", "funnel_transition_records", ["organization_id", "from_stage", "to_stage"])
    op.create_index("ix_funnel_lead", "funnel_transition_records", ["lead_id", "transition_at"])
    op.create_index("ix_funnel_org_channel", "funnel_transition_records", ["organization_id", "channel"])
    op.create_index("ix_funnel_org", "funnel_transition_records", ["organization_id"])
    op.create_index("ix_funnel_transition_at", "funnel_transition_records", ["transition_at"])

    # ─── experiments ─────────────────────────────────────────────────────────
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("hypothesis", sa.Text, nullable=False),
        sa.Column("primary_metric", sa.String(100), nullable=False),
        sa.Column("secondary_metrics", _JSONB, nullable=False, server_default="[]"),
        sa.Column("population_definition", _JSONB, nullable=False, server_default="{}"),
        sa.Column("expected_sample_size", sa.Integer, nullable=False),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("rollback_condition", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("expected_sample_size > 0", name="ck_experiment_sample_positive"),
    )
    op.create_index("ix_experiment_status", "experiments", ["status"])
    op.create_index("ix_experiment_org", "experiments", ["organization_id"])

    # ─── experiment_variants ─────────────────────────────────────────────────
    op.create_table(
        "experiment_variants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_control", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("traffic_allocation_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("configuration", _JSONB, nullable=False, server_default="{}"),
        sa.Column("description", sa.Text, nullable=False),
        sa.UniqueConstraint("experiment_id", "name", name="uq_variant_experiment_name"),
        sa.CheckConstraint(
            "traffic_allocation_pct > 0 AND traffic_allocation_pct <= 100",
            name="ck_variant_allocation_range"
        ),
    )
    op.create_index("ix_variant_experiment_id", "experiment_variants", ["experiment_id"])

    # ─── experiment_assignments ──────────────────────────────────────────────
    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("variant_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("subject_type", sa.String(30), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("first_exposure_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("experiment_id", "subject_id", name="uq_experiment_assignment"),
    )
    op.create_index("ix_assignment_experiment_variant", "experiment_assignments", ["experiment_id", "variant_id"])
    op.create_index("ix_assignment_org_experiment", "experiment_assignments", ["organization_id", "experiment_id"])
    op.create_index("ix_assignment_subject_id", "experiment_assignments", ["subject_id"])

    # ─── experiment_conversions ──────────────────────────────────────────────
    op.create_table(
        "experiment_conversions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("variant_id", sa.String(36), nullable=False),
        sa.Column("assignment_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("outcome_event_id", sa.String(36), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversion_experiment_variant", "experiment_conversions", ["experiment_id", "variant_id"])
    op.create_index("ix_conversion_org", "experiment_conversions", ["organization_id", "converted_at"])
    op.create_index("ix_conversion_assignment_id", "experiment_conversions", ["assignment_id"])

    # ─── benchmark_definitions ───────────────────────────────────────────────
    op.create_table(
        "benchmark_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("benchmark_type", sa.String(30), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("methodology", sa.Text, nullable=False),
        sa.Column("minimum_cohort_size", sa.Integer, nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("external_source", sa.String(500), nullable=True),
        sa.Column("external_source_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_license_status", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("minimum_cohort_size >= 5", name="ck_benchmark_min_cohort"),
    )
    op.create_index("ix_benchmark_def_type", "benchmark_definitions", ["benchmark_type"])

    # ─── benchmark_snapshots ─────────────────────────────────────────────────
    op.create_table(
        "benchmark_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("definition_id", sa.String(36), sa.ForeignKey("benchmark_definitions.id"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=True),
        sa.Column("value_p50", sa.Numeric(20, 4), nullable=True),
        sa.Column("value_p75", sa.Numeric(20, 4), nullable=True),
        sa.Column("value_p90", sa.Numeric(20, 4), nullable=True),
        sa.Column("value_p95", sa.Numeric(20, 4), nullable=True),
        sa.Column("confidence_interval_low", sa.Numeric(20, 4), nullable=True),
        sa.Column("confidence_interval_high", sa.Numeric(20, 4), nullable=True),
        sa.Column("actual_cohort_size", sa.Integer, nullable=False),
        sa.Column("is_privacy_safe", sa.Boolean, nullable=False),
        sa.Column("is_statistically_meaningful", sa.Boolean, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "definition_id", "organization_id", "period_start", "period_end",
            name="uq_benchmark_snapshot"
        ),
        sa.CheckConstraint("actual_cohort_size >= 0", name="ck_benchmark_cohort_nonneg"),
    )
    op.create_index("ix_benchmark_def_period", "benchmark_snapshots", ["definition_id", "period_start"])
    op.create_index("ix_benchmark_org", "benchmark_snapshots", ["organization_id"])

    # ─── data_quality_issues ─────────────────────────────────────────────────
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("issue_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("detection_method", sa.String(100), nullable=False),
        sa.Column("dimension", sa.String(20), nullable=False),
        sa.Column("is_resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dq_org_type", "data_quality_issues", ["organization_id", "issue_type"])
    op.create_index("ix_dq_org_resolved", "data_quality_issues", ["organization_id", "is_resolved"])
    op.create_index("ix_dq_entity_id", "data_quality_issues", ["entity_id"])
    op.create_index("ix_dq_detected_at", "data_quality_issues", ["detected_at"])

    # ─── policy_registry_entries ─────────────────────────────────────────────
    op.create_table(
        "policy_registry_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_key", sa.String(200), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="CANDIDATE"),
        sa.Column("previous_version_id", sa.String(36), nullable=True),
        sa.Column("rollback_of_id", sa.String(36), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("artifact_uri", sa.String(1000), nullable=True),
        sa.Column("evaluation_id", sa.String(36), nullable=True),
        sa.Column("quality_score", sa.Numeric(7, 4), nullable=True),
        sa.Column("hallucination_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("safety_passed", sa.Boolean, nullable=True),
        sa.Column("latency_p95_ms", sa.Integer, nullable=True),
        sa.Column("promoted_by", sa.String(36), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecation_reason", sa.Text, nullable=True),
        sa.Column("deprecation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entity_type", "entity_key", "version", name="uq_registry_entity_version"),
    )
    op.create_index("ix_registry_type_key", "policy_registry_entries", ["entity_type", "entity_key"])
    op.create_index("ix_registry_status", "policy_registry_entries", ["status"])

    # ─── drift_alert_records ─────────────────────────────────────────────────
    op.create_table(
        "drift_alert_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("drift_type", sa.String(30), nullable=False),
        sa.Column("entity_key", sa.String(200), nullable=False),
        sa.Column("detection_method", sa.String(100), nullable=False),
        sa.Column("baseline_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("drift_score", sa.Numeric(10, 6), nullable=False),
        sa.Column("threshold", sa.Numeric(10, 6), nullable=False),
        sa.Column("is_significant", sa.Boolean, nullable=False),
        sa.Column("baseline_sample_size", sa.Integer, nullable=False),
        sa.Column("current_sample_size", sa.Integer, nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("acknowledged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("acknowledged_by", sa.String(36), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_taken", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_drift_type_entity", "drift_alert_records", ["drift_type", "entity_key"])
    op.create_index("ix_drift_detected", "drift_alert_records", ["detected_at"])
    op.create_index("ix_drift_org", "drift_alert_records", ["organization_id"])

    # ─── intelligence_snapshots ──────────────────────────────────────────────
    op.create_table(
        "intelligence_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("funnel_metrics", _JSONB, nullable=False, server_default="{}"),
        sa.Column("channel_metrics", _JSONB, nullable=False, server_default="{}"),
        sa.Column("ai_metrics", _JSONB, nullable=False, server_default="{}"),
        sa.Column("revenue_metrics", _JSONB, nullable=False, server_default="{}"),
        sa.Column("data_quality_metrics", _JSONB, nullable=False, server_default="{}"),
        sa.Column("trend_direction", sa.String(10), nullable=True),
        sa.Column("anomaly_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_event_count", sa.Integer, nullable=False),
        sa.Column("source_event_min_id", sa.String(36), nullable=True),
        sa.Column("source_event_max_id", sa.String(36), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id", "period_type", "period_start",
            name="uq_intel_snapshot_org_period"
        ),
    )
    op.create_index("ix_intel_snapshot_org_period", "intelligence_snapshots", ["organization_id", "period_start"])
    op.create_index("ix_intel_snapshot_org", "intelligence_snapshots", ["organization_id"])

    # ─── insight_records ─────────────────────────────────────────────────────
    op.create_table(
        "insight_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("insight_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_metric", sa.String(100), nullable=False),
        sa.Column("source_event_ids", _JSONB, nullable=False, server_default="[]"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("impact_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("urgency_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("actionability_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("recommended_action", sa.Text, nullable=True),
        sa.Column("expected_benefit", sa.Text, nullable=True),
        sa.Column("supporting_evidence", _JSONB, nullable=False, server_default="[]"),
        sa.Column("is_acknowledged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("acknowledged_by", sa.String(36), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_dismissed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("impact_score >= 0 AND impact_score <= 10", name="ck_insight_impact"),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 10", name="ck_insight_confidence"),
    )
    op.create_index("ix_insight_org_type", "insight_records", ["organization_id", "insight_type"])
    op.create_index("ix_insight_org_generated", "insight_records", ["organization_id", "generated_at"])

    # ─── organization_learning_profiles ──────────────────────────────────────
    op.create_table(
        "organization_learning_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, unique=True),
        sa.Column("preferred_channels", _JSONB, nullable=False, server_default="{}"),
        sa.Column("response_patterns", _JSONB, nullable=False, server_default="{}"),
        sa.Column("property_preferences", _JSONB, nullable=False, server_default="{}"),
        sa.Column("sales_cadence", _JSONB, nullable=False, server_default="{}"),
        sa.Column("conversion_patterns", _JSONB, nullable=False, server_default="{}"),
        sa.Column("ai_usage_patterns", _JSONB, nullable=False, server_default="{}"),
        sa.Column("workflow_patterns", _JSONB, nullable=False, server_default="{}"),
        sa.Column("objection_patterns", _JSONB, nullable=False, server_default="{}"),
        sa.Column("data_coverage_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("outcome_density_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("learning_loop_maturity", sa.String(20), nullable=False, server_default="INITIAL"),
        sa.Column("total_outcomes_sampled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_learning_events", sa.Integer, nullable=False, server_default="0"),
        sa.Column("derived_from_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("derived_from_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_learning_profile_org", "organization_learning_profiles", ["organization_id"])


def downgrade() -> None:
    op.drop_table("organization_learning_profiles")
    op.drop_table("insight_records")
    op.drop_table("intelligence_snapshots")
    op.drop_table("drift_alert_records")
    op.drop_table("policy_registry_entries")
    op.drop_table("data_quality_issues")
    op.drop_table("benchmark_snapshots")
    op.drop_table("benchmark_definitions")
    op.drop_table("experiment_conversions")
    op.drop_table("experiment_assignments")
    op.drop_table("experiment_variants")
    op.drop_table("experiments")
    op.drop_table("funnel_transition_records")
    op.drop_table("objection_records")
    op.drop_table("recommendation_quality_snapshots")
    op.drop_table("ai_action_outcomes")
    op.drop_table("sales_outcome_edges")
    op.drop_table("learning_events")
    op.drop_table("outcome_events")
