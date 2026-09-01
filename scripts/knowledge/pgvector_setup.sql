-- ============================================================
-- BeetleLabs Knowledge Intelligence Platform
-- Production pgvector Setup Script
-- ============================================================
--
-- Run this AFTER running Alembic migrations:
--   cd apps/api && alembic upgrade head
--
-- Then run this script against your PostgreSQL database:
--   psql $DATABASE_URL -f scripts/knowledge/pgvector_setup.sql
--
-- Requirements:
--   - PostgreSQL 14+ with pgvector extension installed
--   - Install pgvector: https://github.com/pgvector/pgvector
--     Ubuntu: sudo apt install postgresql-14-pgvector
--     macOS:  brew install pgvector
-- ============================================================

-- Step 1: Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Add native vector column to knowledge_embeddings
-- (The Alembic migration uses embedding_json for SQLite compatibility.
--  In production PostgreSQL, we add the native vector column.)
ALTER TABLE knowledge_embeddings
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Step 3: Backfill native vector column from JSON column
-- Run this to migrate existing JSON embeddings to vector type.
-- This is a one-time operation after adding the column.
-- IMPORTANT: Only run this if you have existing data in embedding_json.
--
-- UPDATE knowledge_embeddings
-- SET embedding = embedding_json::vector
-- WHERE embedding IS NULL AND embedding_json IS NOT NULL;

-- Step 4: Create HNSW index for fast ANN search
-- HNSW is recommended for production (vs IVFFlat) - better recall/speed trade-off.
-- m=16 and ef_construction=64 are good defaults for most workloads.
CREATE INDEX IF NOT EXISTS ix_ke_vector_hnsw
    ON knowledge_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Step 5: Create GIN index on knowledge_chunks for full-text keyword search
-- This powers the keyword retrieval component of hybrid search.
ALTER TABLE knowledge_chunks
    ADD COLUMN IF NOT EXISTS fts_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english', coalesce(content, ''))
        ) STORED;

CREATE INDEX IF NOT EXISTS ix_kc_fts_gin
    ON knowledge_chunks
    USING gin(fts_vector);

-- Step 6: Create supporting composite indexes for hybrid search performance
-- These ensure organization_id filtering is always fast.
CREATE INDEX IF NOT EXISTS ix_ke_org_chunk
    ON knowledge_embeddings(organization_id, chunk_id)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS ix_kc_org_expired_ai
    ON knowledge_chunks(organization_id, is_expired, ai_allowed)
    WHERE is_expired = FALSE;

CREATE INDEX IF NOT EXISTS ix_kd_org_status_type
    ON knowledge_documents(organization_id, status, knowledge_type);

-- Step 7: Verify setup
SELECT
    extname,
    extversion
FROM pg_extension
WHERE extname = 'vector';

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('knowledge_embeddings', 'knowledge_chunks')
  AND indexname LIKE '%hnsw%' OR indexname LIKE '%gin%'
ORDER BY tablename, indexname;

-- ============================================================
-- Native vector search query (replaces Python cosine similarity)
-- Use this in production PgVectorStoreProvider.search():
--
-- SELECT ke.chunk_id, ke.organization_id, kc.document_id,
--        1 - (ke.embedding <=> :query_vec::vector) AS score
-- FROM knowledge_embeddings ke
-- JOIN knowledge_chunks kc ON ke.chunk_id = kc.id
-- WHERE ke.organization_id = :org_id
--   AND ke.is_active = TRUE
--   AND kc.is_expired = FALSE
--   AND kc.ai_allowed = TRUE
-- ORDER BY ke.embedding <=> :query_vec::vector
-- LIMIT :top_k;
--
-- ============================================================
