"""Alembic migration: Knowledge Intelligence Platform — 21 Tables

Revision ID: b8e2d4f1a9c3
Revises: a5c9f1e78b2d
Create Date: 2026-08-10

Tables created (21):
  1.  knowledge_sources
  2.  knowledge_documents
  3.  knowledge_document_versions
  4.  knowledge_chunks
  5.  knowledge_embeddings
  6.  knowledge_facts
  7.  knowledge_conflicts
  8.  knowledge_verifications
  9.  knowledge_permissions
  10. knowledge_collections
  11. knowledge_collection_documents
  12. knowledge_indexes
  13. knowledge_queries
  14. knowledge_retrievals
  15. knowledge_citations
  16. knowledge_feedback
  17. knowledge_evaluations
  18. knowledge_providers
  19. knowledge_processing_jobs
  20. knowledge_deletion_jobs
  21. knowledge_freshness_policies

Production pgvector setup:
  After running this migration on a PostgreSQL instance with pgvector installed:
    CREATE EXTENSION IF NOT EXISTS vector;
    ALTER TABLE knowledge_embeddings ADD COLUMN IF NOT EXISTS
      embedding vector(1536);
    CREATE INDEX IF NOT EXISTS ix_ke_vector_hnsw
      ON knowledge_embeddings USING hnsw (embedding vector_cosine_ops);

  The embedding_json column is the SQLite-compatible fallback.
  In production the native vector column is used for ANN search.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "b8e2d4f1a9c3"
down_revision = "a5c9f1e78b2d"
branch_labels = None
depends_on = None

JSONB = sa.JSON()  # Use JSON() for both PostgreSQL (via SQLAlchemy) and SQLite


def upgrade() -> None:
    # ── 1. knowledge_sources ─────────────────────────────────────────────────
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("credentials_encrypted", sa.Text, nullable=True),
        sa.Column("priority_rank", sa.Integer, default=50, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("robots_txt_respected", sa.Boolean, default=True, nullable=False),
        sa.Column("config", JSONB, default={}, nullable=False),
        sa.Column("total_documents", sa.Integer, default=0, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ks_org_type", "knowledge_sources", ["organization_id", "source_type"])
    op.create_index("ix_ks_org_active", "knowledge_sources", ["organization_id", "is_active"])

    # ── 2. knowledge_documents ───────────────────────────────────────────────
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("property_id", sa.String(36), nullable=True),
        sa.Column("collection_id", sa.String(36), nullable=True),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, default=0, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_type", sa.String(30), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("storage_provider", sa.String(30), default="local", nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(30), default="UPLOADED", nullable=False),
        sa.Column("knowledge_type", sa.String(50), nullable=False),
        sa.Column("language", sa.String(10), default="en", nullable=False),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("visibility", sa.String(30), default="INTERNAL", nullable=False),
        sa.Column("ai_allowed", sa.Boolean, default=True, nullable=False),
        sa.Column("customer_facing_allowed", sa.Boolean, default=False, nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_pages", sa.Integer, default=0, nullable=False),
        sa.Column("total_chunks", sa.Integer, default=0, nullable=False),
        sa.Column("total_facts", sa.Integer, default=0, nullable=False),
        sa.Column("total_conflicts", sa.Integer, default=0, nullable=False),
        sa.Column("ocr_used", sa.Boolean, default=False, nullable=False),
        sa.Column("ocr_provider", sa.String(50), nullable=True),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("uploaded_by", sa.String(36), nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kd_org_status", "knowledge_documents", ["organization_id", "status"])
    op.create_index("ix_kd_org_type", "knowledge_documents", ["organization_id", "knowledge_type"])
    op.create_index("ix_kd_org_lang", "knowledge_documents", ["organization_id", "language"])
    op.create_index("ix_kd_project_status", "knowledge_documents", ["project_id", "status"])
    op.create_index("ix_kd_expires", "knowledge_documents", ["expires_at", "status"])

    # ── 3. knowledge_document_versions ───────────────────────────────────────
    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, default=0, nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean, default=False, nullable=False),
        sa.Column("previous_version_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kdv_doc_version", "knowledge_document_versions", ["document_id", "version_number"])
    op.create_index("ix_kdv_doc_active", "knowledge_document_versions", ["document_id", "is_active"])
    op.create_unique_constraint("uq_kdv_doc_version", "knowledge_document_versions", ["document_id", "version_number"])

    # ── 4. knowledge_chunks ──────────────────────────────────────────────────
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("property_id", sa.String(36), nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("section", sa.String(300), nullable=True),
        sa.Column("heading", sa.String(300), nullable=True),
        sa.Column("subheading", sa.String(300), nullable=True),
        sa.Column("chunk_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("token_count", sa.Integer, default=0, nullable=False),
        sa.Column("char_count", sa.Integer, default=0, nullable=False),
        sa.Column("language", sa.String(10), default="en", nullable=False),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("knowledge_type", sa.String(50), nullable=False),
        sa.Column("visibility", sa.String(30), default="INTERNAL", nullable=False),
        sa.Column("ai_allowed", sa.Boolean, default=True, nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_expired", sa.Boolean, default=False, nullable=False),
        sa.Column("table_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kc_doc_idx", "knowledge_chunks", ["document_id", "chunk_index"])
    op.create_index("ix_kc_org_type", "knowledge_chunks", ["organization_id", "knowledge_type"])
    op.create_index("ix_kc_project", "knowledge_chunks", ["project_id"])
    op.create_index("ix_kc_org_expired", "knowledge_chunks", ["organization_id", "is_expired"])
    op.create_index("ix_kc_expires", "knowledge_chunks", ["expires_at"])

    # ── 5. knowledge_embeddings ──────────────────────────────────────────────
    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("embedding_dim", sa.Integer, nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer, default=0, nullable=False),
        sa.Column("cost_tokens", sa.Integer, default=0, nullable=False),
        sa.Column("embedding_json", JSONB, nullable=True),
        # In production PostgreSQL with pgvector:
        # ALTER TABLE knowledge_embeddings ADD COLUMN embedding vector(1536);
        # CREATE INDEX ix_ke_vector_hnsw ON knowledge_embeddings
        #   USING hnsw (embedding vector_cosine_ops);
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ke_chunk_active", "knowledge_embeddings", ["chunk_id", "is_active"])
    op.create_index("ix_ke_org_provider", "knowledge_embeddings", ["organization_id", "provider"])
    op.create_index("ix_ke_text_hash", "knowledge_embeddings", ["text_hash", "provider"])

    # ── 6. knowledge_facts ───────────────────────────────────────────────────
    op.create_table(
        "knowledge_facts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("property_id", sa.String(36), nullable=True),
        sa.Column("fact_type", sa.String(50), nullable=False),
        sa.Column("value_text", sa.Text, nullable=True),
        sa.Column("value_numeric", sa.Float, nullable=True),
        sa.Column("value_json", JSONB, nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("scope", sa.String(30), nullable=True),
        sa.Column("confidence", sa.Float, default=0.0, nullable=False),
        sa.Column("extraction_method", sa.String(30), default="llm", nullable=False),
        sa.Column("ai_model", sa.String(100), nullable=True),
        sa.Column("source_page", sa.Integer, nullable=True),
        sa.Column("source_text", sa.Text, nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_status", sa.String(20), default="UNVERIFIED", nullable=False),
        sa.Column("verified_by", sa.String(36), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kf_org_type", "knowledge_facts", ["organization_id", "fact_type"])
    op.create_index("ix_kf_org_verification", "knowledge_facts", ["organization_id", "verification_status"])
    op.create_index("ix_kf_project_type", "knowledge_facts", ["project_id", "fact_type"])
    op.create_index("ix_kf_doc", "knowledge_facts", ["document_id"])

    # ── 7. knowledge_conflicts ───────────────────────────────────────────────
    op.create_table(
        "knowledge_conflicts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("fact_type", sa.String(50), nullable=False),
        sa.Column("fact_a_id", sa.String(36), nullable=False),
        sa.Column("fact_a_value", sa.Text, nullable=True),
        sa.Column("fact_a_source_id", sa.String(36), nullable=True),
        sa.Column("fact_a_document_id", sa.String(36), nullable=True),
        sa.Column("fact_a_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fact_a_confidence", sa.Float, default=0.0, nullable=False),
        sa.Column("fact_b_id", sa.String(36), nullable=False),
        sa.Column("fact_b_value", sa.Text, nullable=True),
        sa.Column("fact_b_source_id", sa.String(36), nullable=True),
        sa.Column("fact_b_document_id", sa.String(36), nullable=True),
        sa.Column("fact_b_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fact_b_confidence", sa.Float, default=0.0, nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("property_id", sa.String(36), nullable=True),
        sa.Column("resolution_status", sa.String(20), default="OPEN", nullable=False),
        sa.Column("resolution_strategy", sa.String(30), nullable=True),
        sa.Column("winning_fact_id", sa.String(36), nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kcon_org_status", "knowledge_conflicts", ["organization_id", "resolution_status"])
    op.create_index("ix_kcon_project", "knowledge_conflicts", ["project_id"])

    # ── 8. knowledge_verifications ───────────────────────────────────────────
    op.create_table(
        "knowledge_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("reviewer_id", sa.String(36), nullable=False),
        sa.Column("reviewer_name", sa.String(200), nullable=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("confidence_override", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kv_org_target", "knowledge_verifications", ["organization_id", "target_type", "target_id"])

    # ── 9. knowledge_permissions ─────────────────────────────────────────────
    op.create_table(
        "knowledge_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("knowledge_type", sa.String(50), nullable=True),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("collection_id", sa.String(36), nullable=True),
        sa.Column("principal_type", sa.String(20), nullable=False),
        sa.Column("principal_id", sa.String(36), nullable=False),
        sa.Column("visibility_level", sa.String(30), default="INTERNAL", nullable=False),
        sa.Column("ai_allowed", sa.Boolean, default=True, nullable=False),
        sa.Column("customer_facing_allowed", sa.Boolean, default=False, nullable=False),
        sa.Column("can_edit", sa.Boolean, default=False, nullable=False),
        sa.Column("can_delete", sa.Boolean, default=False, nullable=False),
        sa.Column("can_publish", sa.Boolean, default=False, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_kp_org_principal", "knowledge_permissions", ["organization_id", "principal_type", "principal_id"])
    op.create_index("ix_kp_document", "knowledge_permissions", ["document_id"])

    # ── 10. knowledge_collections ────────────────────────────────────────────
    op.create_table(
        "knowledge_collections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("knowledge_type", sa.String(50), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("property_id", sa.String(36), nullable=True),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("language", sa.String(10), default="en", nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("visibility", sa.String(30), default="INTERNAL", nullable=False),
        sa.Column("ai_allowed", sa.Boolean, default=True, nullable=False),
        sa.Column("document_count", sa.Integer, default=0, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kcol_org_active", "knowledge_collections", ["organization_id", "is_active"])

    # ── 11. knowledge_collection_documents ───────────────────────────────────
    op.create_table(
        "knowledge_collection_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("collection_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("added_by", sa.String(36), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_kcol_doc", "knowledge_collection_documents", ["collection_id", "document_id"])

    # ── 12. knowledge_indexes ────────────────────────────────────────────────
    op.create_table(
        "knowledge_indexes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("vector_index_status", sa.String(20), default="pending", nullable=False),
        sa.Column("keyword_index_status", sa.String(20), default="pending", nullable=False),
        sa.Column("vector_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("keyword_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_provider", sa.String(30), default="pgvector", nullable=False),
        sa.Column("vector_index_error", sa.Text, nullable=True),
        sa.Column("keyword_index_error", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, default=0, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_ki_chunk_provider", "knowledge_indexes", ["chunk_id", "index_provider"])
    op.create_index("ix_ki_org_status", "knowledge_indexes", ["organization_id", "vector_index_status"])
    op.create_index("ix_ki_doc", "knowledge_indexes", ["document_id"])

    # ── 13. knowledge_queries ────────────────────────────────────────────────
    op.create_table(
        "knowledge_queries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(36), nullable=True),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("query_language", sa.String(10), default="en", nullable=False),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("entities_extracted", JSONB, nullable=False),
        sa.Column("filters_applied", JSONB, nullable=False),
        sa.Column("knowledge_types_queried", JSONB, nullable=False),
        sa.Column("top_k", sa.Integer, default=10, nullable=False),
        sa.Column("vector_hits", sa.Integer, default=0, nullable=False),
        sa.Column("keyword_hits", sa.Integer, default=0, nullable=False),
        sa.Column("reranked_hits", sa.Integer, default=0, nullable=False),
        sa.Column("context_chunks_used", sa.Integer, default=0, nullable=False),
        sa.Column("retrieval_latency_ms", sa.Integer, nullable=True),
        sa.Column("reranking_latency_ms", sa.Integer, nullable=True),
        sa.Column("llm_latency_ms", sa.Integer, nullable=True),
        sa.Column("total_latency_ms", sa.Integer, nullable=True),
        sa.Column("embedding_tokens", sa.Integer, default=0, nullable=False),
        sa.Column("context_tokens", sa.Integer, default=0, nullable=False),
        sa.Column("llm_tokens_input", sa.Integer, default=0, nullable=False),
        sa.Column("llm_tokens_output", sa.Integer, default=0, nullable=False),
        sa.Column("answer_confidence", sa.Float, nullable=True),
        sa.Column("grounding_passed", sa.Boolean, nullable=True),
        sa.Column("had_citation", sa.Boolean, default=False, nullable=False),
        sa.Column("hallucination_flagged", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kq_org_created", "knowledge_queries", ["organization_id", "created_at"])
    op.create_index("ix_kq_session", "knowledge_queries", ["session_id"])
    op.create_index("ix_kq_lead", "knowledge_queries", ["lead_id"])

    # ── 14. knowledge_retrievals ─────────────────────────────────────────────
    op.create_table(
        "knowledge_retrievals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query_id", sa.String(36), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("retrieval_method", sa.String(20), nullable=False),
        sa.Column("rank_position", sa.Integer, nullable=False),
        sa.Column("vector_score", sa.Float, nullable=True),
        sa.Column("keyword_score", sa.Float, nullable=True),
        sa.Column("reranker_score", sa.Float, nullable=True),
        sa.Column("final_score", sa.Float, nullable=True),
        sa.Column("was_used_in_context", sa.Boolean, default=False, nullable=False),
        sa.Column("was_cited", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kr_query", "knowledge_retrievals", ["query_id"])
    op.create_index("ix_kr_chunk", "knowledge_retrievals", ["chunk_id"])

    # ── 15. knowledge_citations ──────────────────────────────────────────────
    op.create_table(
        "knowledge_citations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("document_version_id", sa.String(36), nullable=True),
        sa.Column("chunk_id", sa.String(36), nullable=True),
        sa.Column("fact_id", sa.String(36), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("section", sa.String(300), nullable=True),
        sa.Column("heading", sa.String(300), nullable=True),
        sa.Column("cited_text", sa.Text, nullable=True),
        sa.Column("source_display_name", sa.String(300), nullable=True),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("citation_index", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kcit_query", "knowledge_citations", ["query_id"])
    op.create_index("ix_kcit_doc", "knowledge_citations", ["document_id"])

    # ── 16. knowledge_feedback ───────────────────────────────────────────────
    op.create_table(
        "knowledge_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("given_by", sa.String(36), nullable=True),
        sa.Column("given_by_type", sa.String(20), nullable=False),
        sa.Column("feedback_type", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("document_ids_flagged", JSONB, nullable=False),
        sa.Column("chunk_ids_flagged", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kfb_org_type", "knowledge_feedback", ["organization_id", "feedback_type"])
    op.create_index("ix_kfb_query", "knowledge_feedback", ["query_id"])

    # ── 17. knowledge_evaluations ────────────────────────────────────────────
    op.create_table(
        "knowledge_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("eval_dataset_id", sa.String(36), nullable=True),
        sa.Column("eval_type", sa.String(50), nullable=False),
        sa.Column("retrieval_precision", sa.Float, nullable=True),
        sa.Column("retrieval_recall", sa.Float, nullable=True),
        sa.Column("mrr", sa.Float, nullable=True),
        sa.Column("ndcg", sa.Float, nullable=True),
        sa.Column("groundedness_score", sa.Float, nullable=True),
        sa.Column("citation_accuracy", sa.Float, nullable=True),
        sa.Column("answer_relevance", sa.Float, nullable=True),
        sa.Column("freshness_accuracy", sa.Float, nullable=True),
        sa.Column("hallucination_rate", sa.Float, nullable=True),
        sa.Column("permission_leakage_rate", sa.Float, nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("chunking_version", sa.String(50), nullable=True),
        sa.Column("reranker_version", sa.String(50), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("total_queries", sa.Integer, default=0, nullable=False),
        sa.Column("passed", sa.Integer, default=0, nullable=False),
        sa.Column("failed", sa.Integer, default=0, nullable=False),
        sa.Column("skipped", sa.Integer, default=0, nullable=False),
        sa.Column("run_by", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_keval_org_type", "knowledge_evaluations", ["organization_id", "eval_type"])

    # ── 18. knowledge_providers ──────────────────────────────────────────────
    op.create_table(
        "knowledge_providers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("provider_type", sa.String(30), nullable=False),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("is_default", sa.Boolean, default=False, nullable=False),
        sa.Column("cost_per_1k_tokens", sa.Float, nullable=True),
        sa.Column("rate_limit_rpm", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kprov_type", "knowledge_providers", ["provider_type", "is_active"])
    op.create_unique_constraint("uq_kprov_org_type_name", "knowledge_providers",
                                ["organization_id", "provider_type", "provider_name"])

    # ── 19. knowledge_processing_jobs ────────────────────────────────────────
    op.create_table(
        "knowledge_processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=True),
        sa.Column("job_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("worker_id", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer, default=0, nullable=False),
        sa.Column("max_retries", sa.Integer, default=3, nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("result_summary", JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("priority", sa.Integer, default=5, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kpj_org_status", "knowledge_processing_jobs", ["organization_id", "status"])
    op.create_index("ix_kpj_doc_type", "knowledge_processing_jobs", ["document_id", "job_type"])
    op.create_index("ix_kpj_next_attempt", "knowledge_processing_jobs", ["next_attempt_at", "status"])

    # ── 20. knowledge_deletion_jobs ───────────────────────────────────────────
    op.create_table(
        "knowledge_deletion_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("reason", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("audit_metadata", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kdel_org_status", "knowledge_deletion_jobs", ["organization_id", "status"])

    # ── 21. knowledge_freshness_policies ─────────────────────────────────────
    op.create_table(
        "knowledge_freshness_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("knowledge_type", sa.String(50), nullable=False),
        sa.Column("max_age_days", sa.Integer, default=90, nullable=False),
        sa.Column("warn_at_days", sa.Integer, default=75, nullable=False),
        sa.Column("auto_expire", sa.Boolean, default=False, nullable=False),
        sa.Column("require_re_verification_after_days", sa.Integer, nullable=True),
        sa.Column("auto_publish", sa.Boolean, default=False, nullable=False),
        sa.Column("applies_to_ai", sa.Boolean, default=True, nullable=False),
        sa.Column("applies_to_customer_facing", sa.Boolean, default=True, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_kfp_org_type", "knowledge_freshness_policies",
                                ["organization_id", "knowledge_type"])
    op.create_index("ix_kfp_org", "knowledge_freshness_policies", ["organization_id"])


def downgrade() -> None:
    # Drop in reverse order of creation
    op.drop_table("knowledge_freshness_policies")
    op.drop_table("knowledge_deletion_jobs")
    op.drop_table("knowledge_processing_jobs")
    op.drop_table("knowledge_providers")
    op.drop_table("knowledge_evaluations")
    op.drop_table("knowledge_feedback")
    op.drop_table("knowledge_citations")
    op.drop_table("knowledge_retrievals")
    op.drop_table("knowledge_queries")
    op.drop_table("knowledge_indexes")
    op.drop_table("knowledge_collection_documents")
    op.drop_table("knowledge_collections")
    op.drop_table("knowledge_permissions")
    op.drop_table("knowledge_verifications")
    op.drop_table("knowledge_conflicts")
    op.drop_table("knowledge_facts")
    op.drop_table("knowledge_embeddings")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_document_versions")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_sources")
