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


def upgrade() -> None:
    # INTENTIONALLY EMPTY -- stamp-only baseline.
    # All 215 tables already exist in production Supabase.
    # Run:     python -m alembic stamp 9999_production_baseline
    # DO NOT:  python -m alembic upgrade 9999_production_baseline
    pass


def downgrade() -> None:
    raise NotImplementedError(
        "Cannot downgrade the production baseline. "
        "The live Supabase database must be managed manually."
    )
