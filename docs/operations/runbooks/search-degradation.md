# RUNBOOK — SEARCH ENGINE (PGVECTOR) DEGRADATION
## Code: RB-SEARCH-009 | Severity: P2

---

## 1. Symptoms & Triggers
- Property search latency p95 exceeds 500ms.
- Vector distance calculation timeouts or high CPU on database node.

## 2. Diagnostics
1. Check HNSW / IVFFLAT index status on `property_embeddings`:
   ```sql
   SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) FROM pg_stat_user_indexes WHERE indexrelname LIKE '%embedding%';
   ```
2. Verify embedding model API response latency.

## 3. Mitigation & Recovery
- Fallback to relational B-Tree property filters (price, bedrooms, location).
- Rebuild HNSW index concurrently if index bloat detected (`REINDEX INDEX CONCURRENTLY`).
- Cache frequent search result sets in Redis with 1-hour TTL.
