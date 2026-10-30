"""Production Baseline - represents all 215 live Supabase tables (2026-08-21).

Revision ID: 9999_production_baseline
Revises: 0014_global_infrastructure
Create Date: 2026-08-21

IMPORTANT: upgrade() is intentionally empty (pass).
This is a STAMP-ONLY baseline. The full schema already exists in production.

To use:  alembic stamp 9999_production_baseline
DO NOT:  alembic upgrade 9999_production_baseline

PostgreSQL extensions required:
  pgcrypto, uuid-ossp, vector 0.8.2

Out-of-band schema already present in production:
  ALTER TABLE knowledge_embeddings
    ADD COLUMN IF NOT EXISTS embedding vector(768);
  CREATE INDEX IF NOT EXISTS ix_ke_vector_hnsw
    ON knowledge_embeddings USING hnsw (embedding vector_cosine_ops);

215 tables represented:
  [Branch A]  brokers, leads, conversations, scores, follow_ups,
              subscriptions, users
  [Branch B]  agent_sessions, conversation_states, qualification_profiles,
              agent_memories, conversation_summaries, tool_executions,
              prompt_versions, decision_records, escalations, llm_usage,
              agent_configurations, knowledge_sources, knowledge_documents,
              knowledge_document_versions, knowledge_chunks,
              knowledge_embeddings, knowledge_facts, knowledge_conflicts,
              knowledge_verifications, knowledge_permissions,
              knowledge_collections, knowledge_collection_documents,
              knowledge_indexes, knowledge_queries, knowledge_retrievals,
              knowledge_citations, knowledge_feedback, knowledge_evaluations,
              knowledge_providers, knowledge_processing_jobs,
              knowledge_deletion_jobs, knowledge_freshness_policies
  [Branch C]  currencies, countries, markets, market_configurations,
              market_rollouts, exchange_rates, exchange_rate_snapshots,
              holiday_calendars, holidays, translations, property_schemas,
              property_fields, provider_configurations, provider_health,
              compliance_policies, consent_records, data_residency_policies,
              regional_pipelines, regional_pipeline_stages, market_feature_flags
  [Untracked 156 tables now catalogued in this baseline]
    action_executions, activities, agent_daily_briefs,
    agent_workload_snapshots, anomaly_events, api_keys, audit_logs,
    availability_rules, buyer_constraints, buyer_preference_evidences,
    buyer_preferences, buyer_profiles, calendar_accounts, calendar_conflicts,
    calendar_connections, calendar_events, call_detail_records,
    channel_messages, communication_consents, confidence_scores,
    connector_configs, contact_fatigues, contacts, conversation_channel_links,
    conversation_controls, country_configuration_versions,
    crm_operational_actions, custom_fields, deal_milestones,
    deal_payment_schedules, deal_transactions, delivery_status_records,
    demand_prediction_snapshots, departments, developer_api_keys,
    duplicate_candidates, enrichment_histories, enrichment_providers,
    enrichment_sources, feature_vectors, follow_up_attributions,
    follow_up_decisions, follow_up_enrollments, follow_up_executions,
    follow_up_policies, follow_up_sequence_steps, follow_up_sequences,
    forecast_scenario_records, forecast_snapshot_records, identities,
    identity_aliases, identity_conflicts, identity_histories, identity_links,
    inbound_queue, ingestion_logs, insight_dismissals, lead_enrichments,
    lead_health_snapshots, lead_import_batches, lead_import_items,
    lead_intelligence_profiles, lead_notes, lead_predictions,
    lead_recommendations, lead_risks, lead_tag_assignments, lead_tags,
    manager_daily_briefs, manual_reviews, meeting_holds, meeting_outcomes,
    meeting_preparation_briefs, meeting_reminders, meetings,
    memory_audit_logs, memory_deletion_requests, memory_evidence,
    memory_objections, memory_property_feedback, memory_records,
    memory_retention_policies, memory_versions, merge_histories,
    merge_operations, message_attachments, message_templates,
    ml_model_versions, next_best_actions, no_show_predictions, notifications,
    omnichannel_conversations, opportunity_health_snapshots,
    organization_members, organizations, original_payloads, outbound_queue,
    pipeline_health_snapshots, pipeline_stages, prediction_calibration_records,
    prediction_drift_records, prediction_explanations,
    prediction_feature_definitions, prediction_histories,
    prediction_inference_records, prediction_model_versions, prediction_models,
    prediction_outcome_records, prediction_training_datasets, presence_records,
    property_feature_vectors, property_listings, property_media,
    property_price_history, provider_credentials, rbac_permissions,
    rbac_role_permissions, rbac_roles, recommendation_business_rules,
    recommendation_comparisons, recommendation_configurations,
    recommendation_experiments, recommendation_explanations,
    recommendation_features, recommendation_feedback, recommendation_histories,
    recommendation_items, recommendation_model_versions, recommendation_scores,
    recommendation_simulations, recommendations, revenue_forecasts,
    sales_cycle_prediction_snapshots, sales_insights, scheduling_meetings,
    scoring_rules, similarity_scores, sla_breaches, sla_instances, sla_policies,
    tasks, template_variables, typing_events, unified_conversations,
    unified_messages, viewings, webhook_subscriptions, workflow_approvals,
    workflow_definitions, workflow_execution_locks, workflow_instances,
    workflow_node_executions, workflow_templates, workflow_versions,
    workflow_wait_states, workspaces

Decoupled FKs confirmed in live DB (String(36), no FK constraint):
  viewings.property_id, omnichannel_conversations.lead_id,
  sales_cycle_prediction_snapshots.lead_id, property_feature_vectors.property_id
"""
from alembic import op
import sqlalchemy as sa

revision = "9999_production_baseline"
down_revision = "0014_global_infrastructure"
branch_labels = None
depends_on = None


POST_MERGE_TABLES = {
    "ai_action_authorizations", "ai_action_outcomes", "ai_contribution_records",
    "ai_request_records", "attribution_results", "attribution_touchpoints",
    "benchmark_definitions", "benchmark_snapshots", "billing_accounts",
    "billing_adjustments", "billing_customers", "billing_periods",
    "booking_intents", "booking_reconciliation_tasks", "campaign_approvals",
    "campaign_audit_logs", "campaign_events", "campaign_listing_links",
    "canonical_invoice_lines", "canonical_invoices", "canonical_subscriptions",
    "channel_partners", "command_center_dismissals", "commitments",
    "copilot_conversations", "copilot_messages", "cost_events",
    "cp_commissions", "cp_project_agreements", "credit_balances",
    "credit_ledger_entries", "credit_notes", "customer_payment_proofs",
    "customer_portal_invites", "customer_support_requests",
    "customer_transaction_acknowledgements", "data_quality_issues",
    "deal_approval_requests", "deal_bookings", "deal_closings",
    "deal_commercial_audit_logs", "deal_commissions", "deal_documents",
    "deal_offers", "deal_post_sales", "deal_reservations",
    "deal_stage_history", "deals", "demo_sessions",
    "drift_alert_records", "entitlement_consumptions", "entitlement_grants",
    "experiment_assignments", "experiment_conversions", "experiment_variants",
    "experiments", "follow_up_automation_events", "follow_up_rules",
    "forecast_snapshots_v2", "funnel_transition_records", "insight_records",
    "intelligence_snapshots", "inventory_availability_snapshots",
    "lead_automation_states", "lead_property_interests", "learning_events",
    "listing_distributions", "marketing_assets", "marketing_campaigns",
    "marketing_landing_pages", "metric_definitions", "negotiation_rounds",
    "objection_records", "onboarding_states", "opportunity_stage_history",
    "organization_invitations", "organization_learning_profiles",
    "outbox_events", "outcome_events", "password_reset_tokens",
    "payment_audit_logs", "payment_orders", "payment_refunds",
    "payment_transactions", "payment_webhook_events", "pilot_action_records",
    "pilot_approval_items", "pilot_audit_events", "pilot_evidence_records",
    "pilot_human_decisions", "pilot_metric_snapshots", "pilot_observations",
    "pilot_stage_transitions", "pilot_tenants", "pipeline_stage_configs",
    "plan_entitlements", "plan_versions", "plans",
    "policy_registry_entries", "price_book_entries", "project_buildings",
    "project_floors", "project_launches", "project_media",
    "project_phases", "project_price_books", "project_unit_status_logs",
    "project_units", "property_listing_publications",
    "property_payment_transactions", "property_shortlists",
    "real_estate_developers", "real_estate_projects",
    "recommendation_quality_snapshots", "revenue_anomalies", "revenue_events",
    "revenue_feedback_logs", "revenue_funnel_snapshots",
    "revenue_leakage_events", "revenue_leakage_events_v2",
    "revenue_opportunities", "revenue_reconciliation_records",
    "sales_loop_audit_entries", "sales_loop_dead_letters",
    "sales_loop_events", "sales_outcome_edges", "sales_pipelines",
    "site_visit_outcomes", "site_visits", "subscription_items",
    "tenant_activations", "token_blacklist", "tracking_links",
    "unit_economics_records", "unit_economics_snapshots", "unit_holds",
    "usage_aggregates", "usage_events", "usage_meters", "webhook_event_claims"
}


def upgrade() -> None:
    # Production Baseline:
    # Path 2 (Existing database): If baseline tables (e.g. organizations) already exist,
    # this is a no-op, preserving existing data and state.
    # Path 1 (Fresh database): Provisions untracked baseline tables catalogued in this baseline.
    bind = op.get_bind()
    curr_schema = bind.execute(sa.text("SELECT current_schema()")).scalar()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names(schema=curr_schema))

    if "organizations" in existing_tables:
        return

    from app.database import Base
    import app.models

    baseline_tables = [
        t for name, t in Base.metadata.tables.items()
        if name not in POST_MERGE_TABLES and name not in existing_tables
    ]

    if baseline_tables:
        Base.metadata.create_all(bind, tables=baseline_tables, checkfirst=False)


def downgrade() -> None:
    raise NotImplementedError(
        "Cannot downgrade the production baseline. "
        "The live Supabase database must be managed manually."
    )
