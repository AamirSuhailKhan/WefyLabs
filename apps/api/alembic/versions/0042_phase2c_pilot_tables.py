"""Phase 2C pilot tables — durable pilot state

Revision ID: 0042_phase2c_pilot_tables
Revises: 0041_master_build_14_intelligence
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0042_phase2c_pilot_tables"
down_revision = "0041_master_build_14_intelligence"
branch_labels = None
depends_on = None

JSON_TYPE = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    # ── 1. pilot_tenants ────────────────────────────────────────────────────
    op.create_table(
        "pilot_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("current_stage", sa.String(40), nullable=False, server_default="STAGE_1_SHADOW"),
        sa.Column("pilot_status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("enrolled_by", sa.String(120), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("configured_autonomy_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("policy_version", sa.String(40), nullable=False, server_default="phase2-v1.0"),
        sa.Column("enrolled_agent_ids", JSON_TYPE, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_pt_org_id", "pilot_tenants", ["organization_id"])
    op.create_index("ix_pt_stage_status", "pilot_tenants", ["current_stage", "pilot_status"])
    op.create_index("ix_pt_org_id", "pilot_tenants", ["organization_id"])

    # ── 2. pilot_stage_transitions ───────────────────────────────────────────
    op.create_table(
        "pilot_stage_transitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pilot_id", sa.String(36), sa.ForeignKey("pilot_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("from_stage", sa.String(40), nullable=False),
        sa.Column("to_stage", sa.String(40), nullable=False),
        sa.Column("transition_type", sa.String(20), nullable=False, server_default="ADVANCE"),
        sa.Column("triggered_by", sa.String(120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_snapshot", JSON_TYPE, nullable=True),
        sa.Column("evidence_hash", sa.String(64), nullable=True),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pst_pilot_id", "pilot_stage_transitions", ["pilot_id"])
    op.create_index("ix_pst_pilot_at", "pilot_stage_transitions", ["pilot_id", "transitioned_at"])

    # ── 3. pilot_observations ────────────────────────────────────────────────
    op.create_table(
        "pilot_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pilot_id", sa.String(36), sa.ForeignKey("pilot_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_domain", sa.String(60), nullable=False),
        sa.Column("agent_version", sa.String(40), nullable=False, server_default="v2c.1.0"),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column("source_event_type", sa.String(100), nullable=True),
        sa.Column("recommended_action", sa.String(100), nullable=True),
        sa.Column("recommended_action_reasoning", sa.Text(), nullable=True),
        sa.Column("agent_confidence", sa.String(20), nullable=True),
        sa.Column("policy_decision", sa.String(40), nullable=True),
        sa.Column("human_action", sa.String(100), nullable=True),
        sa.Column("human_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("human_actor_id", sa.String(100), nullable=True),
        sa.Column("human_notes", sa.Text(), nullable=True),
        sa.Column("comparison_category", sa.String(40), nullable=True),
        sa.Column("agreement_score", sa.Float(), nullable=True),
        sa.Column("comparison_notes", sa.Text(), nullable=True),
        sa.Column("customer_response", sa.String(60), nullable=True),
        sa.Column("outcome_event_id", sa.String(36), nullable=True),
        sa.Column("revenue_linked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pilot_stage", sa.String(40), nullable=False),
        sa.Column("execution_mode", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False, server_default="phase2-v1.0"),
        sa.Column("is_eligible_for_shadow_accuracy", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_po_pilot_id", "pilot_observations", ["pilot_id"])
    op.create_index("ix_po_lead_id", "pilot_observations", ["lead_id"])
    op.create_index("ix_po_execution_id", "pilot_observations", ["execution_id"])
    op.create_index("ix_po_pilot_lead_agent", "pilot_observations", ["pilot_id", "lead_id", "agent_domain"])
    op.create_index("ix_po_observed_at", "pilot_observations", ["pilot_id", "observed_at"])
    op.create_index("ix_po_comparison", "pilot_observations",
                    ["pilot_id", "comparison_category", "is_eligible_for_shadow_accuracy"])

    # ── 4. pilot_metric_snapshots ────────────────────────────────────────────
    op.create_table(
        "pilot_metric_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pilot_id", sa.String(36), sa.ForeignKey("pilot_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("minimum_sample", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("numerator", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("denominator", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(60), nullable=False, server_default="pilot_observations"),
        sa.Column("calculation_version", sa.String(20), nullable=False, server_default="v2c.1.0"),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pms_pilot_metric", "pilot_metric_snapshots", ["pilot_id", "metric_name", "period_start"])
    op.create_unique_constraint(
        "uq_pms_metric_period", "pilot_metric_snapshots",
        ["pilot_id", "metric_name", "period_start", "calculation_version"]
    )

    # ── 5. pilot_evidence_records ────────────────────────────────────────────
    op.create_table(
        "pilot_evidence_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pilot_id", sa.String(36), sa.ForeignKey("pilot_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("from_stage", sa.String(40), nullable=False),
        sa.Column("to_stage", sa.String(40), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("minimum_sample", sa.Integer(), nullable=False),
        sa.Column("gate_result", sa.String(20), nullable=False),
        sa.Column("blocking_reasons", JSON_TYPE, nullable=True),
        sa.Column("passing_criteria", JSON_TYPE, nullable=True),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("calculation_version", sa.String(20), nullable=False, server_default="v2c.1.0"),
        sa.Column("policy_version", sa.String(40), nullable=False, server_default="phase2-v1.0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_per_pilot_stage", "pilot_evidence_records", ["pilot_id", "from_stage", "generated_at"])

    # ── 6. pilot_audit_events ────────────────────────────────────────────────
    op.create_table(
        "pilot_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pilot_id", sa.String(36), sa.ForeignKey("pilot_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=True),
        sa.Column("payload", JSON_TYPE, nullable=False, server_default="{}"),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pae_pilot_id", "pilot_audit_events", ["pilot_id"])
    op.create_index("ix_pae_pilot_seq", "pilot_audit_events", ["pilot_id", "sequence_number"])
    op.create_index("ix_pae_event_type", "pilot_audit_events", ["pilot_id", "event_type", "occurred_at"])
    op.create_unique_constraint("uq_pae_pilot_seq", "pilot_audit_events", ["pilot_id", "sequence_number"])

    # ── 7. pilot_action_records ──────────────────────────────────────────────
    op.create_table(
        "pilot_action_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("record_id", sa.String(36), nullable=False),
        sa.Column("pilot_id", sa.String(36), sa.ForeignKey("pilot_tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_version", sa.String(40), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("risk_class", sa.String(40), nullable=False),
        sa.Column("action_description", sa.Text(), nullable=True),
        sa.Column("semantic_state", sa.String(40), nullable=False),
        sa.Column("state_history", JSON_TYPE, nullable=False, server_default="[]"),
        sa.Column("pilot_stage", sa.String(40), nullable=False),
        sa.Column("execution_mode", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("provider_name", sa.String(60), nullable=True),
        sa.Column("provider_request_id", sa.String(200), nullable=True),
        sa.Column("provider_status", sa.String(40), nullable=True),
        sa.Column("provider_error", sa.Text(), nullable=True),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_par_record_id", "pilot_action_records", ["record_id"])
    op.create_unique_constraint("uq_par_idem_key", "pilot_action_records", ["idempotency_key"])
    op.create_index("ix_par_org_action_state", "pilot_action_records", ["organization_id", "action_type", "semantic_state"])
    op.create_index("ix_par_execution", "pilot_action_records", ["execution_id"])
    op.create_index("ix_par_completed", "pilot_action_records", ["completed_at"])

    # ── 8. pilot_human_decisions ─────────────────────────────────────────────
    op.create_table(
        "pilot_human_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("observation_id", sa.String(36), sa.ForeignKey("pilot_observations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("human_actor_id", sa.String(120), nullable=False),
        sa.Column("human_actor_role", sa.String(60), nullable=True),
        sa.Column("decision_type", sa.String(30), nullable=False),
        sa.Column("action_taken", sa.String(100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("modified_content", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_phd_observation", "pilot_human_decisions", ["observation_id"])
    op.create_index("ix_phd_org_decided", "pilot_human_decisions", ["organization_id", "decided_at"])

    # ── 9. pilot_approval_items ──────────────────────────────────────────────
    op.create_table(
        "pilot_approval_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("pilot_id", sa.String(36), sa.ForeignKey("pilot_tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(100), nullable=True),
        sa.Column("agent_domain", sa.String(60), nullable=False),
        sa.Column("execution_id", sa.String(36), nullable=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("risk_class", sa.String(40), nullable=False),
        sa.Column("action_description", sa.Text(), nullable=False),
        sa.Column("proposed_content", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("lead_summary", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("resource_hash", sa.String(64), nullable=True),
        sa.Column("policy_version", sa.String(40), nullable=False, server_default="phase2-v1.0"),
        sa.Column("urgency", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hash_matched_at_review", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_pai_approval_id", "pilot_approval_items", ["approval_id"])
    op.create_index("ix_pai_org_status", "pilot_approval_items", ["organization_id", "approval_status"])
    op.create_index("ix_pai_expires", "pilot_approval_items", ["approval_status", "expires_at"])


def downgrade():
    op.drop_table("pilot_approval_items")
    op.drop_table("pilot_human_decisions")
    op.drop_table("pilot_action_records")
    op.drop_table("pilot_audit_events")
    op.drop_table("pilot_evidence_records")
    op.drop_table("pilot_metric_snapshots")
    op.drop_table("pilot_observations")
    op.drop_table("pilot_stage_transitions")
    op.drop_table("pilot_tenants")
