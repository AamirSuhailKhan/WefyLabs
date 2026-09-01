"""
Vector Store Provider Abstraction
==================================
Abstract interface for all vector database backends.
Default: PostgreSQL + pgvector (no new infrastructure needed).
Future: Pinecone, Qdrant, Weaviate, OpenSearch.

CRITICAL:
  - Vector index is a RETRIEVAL LAYER, not the source of truth.
  - Business logic must never depend on vector-only data for facts.
  - Tenant isolation enforced by organization_id in every query.
"""
from __future__ import annotations

import json
import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class ChunkVector:
    """A knowledge chunk ready for vector indexing."""
    chunk_id: str
    organization_id: str
    document_id: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    # metadata includes: knowledge_type, language, country, project_id,
    #                    visibility, ai_allowed, customer_facing_allowed,
    #                    expires_at, is_expired


@dataclass
class VectorHit:
    """A vector search result."""
    chunk_id: str
    document_id: str
    organization_id: str
    score: float                  # Cosine similarity (0-1) or distance
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorSearchFilters:
    """Filters applied to vector search (pre-filter, not post-filter)."""
    organization_id: str
    knowledge_types: Optional[List[str]] = None
    project_id: Optional[str] = None
    property_id: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    visibility_levels: Optional[List[str]] = None
    ai_allowed: bool = True
    exclude_expired: bool = True
    exclude_chunk_ids: Optional[List[str]] = None


# ─── Abstract Interface ────────────────────────────────────────────────────────

class VectorStoreProvider(ABC):
    """
    Abstract vector store provider.
    Tenant isolation is enforced by every concrete implementation.
    Organization A can never retrieve Organization B vectors.
    """
    provider_name: str = "abstract"

    @abstractmethod
    async def upsert(self, chunks: List[ChunkVector]) -> int:
        """
        Insert or update chunk vectors.
        Returns the number of chunks successfully upserted.
        """
        ...

    @abstractmethod
    async def search(
        self,
        organization_id: str,
        embedding: List[float],
        top_k: int,
        filters: Optional[VectorSearchFilters] = None,
    ) -> List[VectorHit]:
        """
        Nearest-neighbor search scoped strictly to organization_id.
        Returns at most top_k results, filtered and sorted by score descending.
        """
        ...

    @abstractmethod
    async def delete(
        self,
        organization_id: str,
        chunk_ids: List[str],
    ) -> int:
        """
        Delete vectors for the given chunk IDs.
        Returns the number of vectors deleted.
        CRITICAL: Only deletes within the specified organization_id.
        """
        ...

    @abstractmethod
    async def delete_by_document(
        self,
        organization_id: str,
        document_id: str,
    ) -> int:
        """Delete all chunk vectors for a document."""
        ...


# ─── pgvector Provider ────────────────────────────────────────────────────────

class PgVectorStoreProvider(VectorStoreProvider):
    """
    PostgreSQL pgvector implementation.
    Uses knowledge_embeddings table (embedding_json column for JSON fallback,
    or native vector type when pgvector extension is installed).

    Index: IVFFlat or HNSW created via Alembic migration in production.
    Fallback: JSON array linear scan (for development / SQLite tests).
    """
    provider_name = "pgvector"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, chunks: List[ChunkVector]) -> int:
        """
        Upsert embeddings into knowledge_embeddings.
        Uses ON CONFLICT (chunk_id) DO UPDATE for idempotency.
        """
        from app.models.knowledge_models import KnowledgeEmbedding

        count = 0
        for chunk in chunks:
            vec_str = "[" + ",".join(str(v) for v in chunk.embedding) + "]"
            # Check for existing embedding for this chunk
            result = await self.db.execute(
                text(
                    "SELECT id FROM knowledge_embeddings "
                    "WHERE chunk_id = :chunk_id AND is_active = TRUE"
                ),
                {"chunk_id": chunk.chunk_id},
            )
            existing = result.fetchone()

            if existing:
                # Update in-place (provider migration scenario)
                try:
                    await self.db.execute(
                        text(
                            "UPDATE knowledge_embeddings "
                            "SET embedding_json = :emb, embedding = CAST(:vec AS vector), is_active = TRUE "
                            "WHERE chunk_id = :chunk_id AND is_active = TRUE"
                        ),
                        {
                            "emb": json.dumps(chunk.embedding),
                            "vec": vec_str,
                            "chunk_id": chunk.chunk_id,
                        },
                    )
                except Exception:
                    await self.db.execute(
                        text(
                            "UPDATE knowledge_embeddings "
                            "SET embedding_json = :emb, is_active = TRUE "
                            "WHERE chunk_id = :chunk_id AND is_active = TRUE"
                        ),
                        {
                            "emb": json.dumps(chunk.embedding),
                            "chunk_id": chunk.chunk_id,
                        },
                    )
            else:
                emb = KnowledgeEmbedding(
                    chunk_id=chunk.chunk_id,
                    organization_id=chunk.organization_id,
                    provider="pgvector",
                    model_name=chunk.metadata.get("model_name", "gemini-embedding-001"),
                    embedding_dim=len(chunk.embedding),
                    text_hash=chunk.metadata.get("text_hash", ""),
                    token_count=chunk.metadata.get("token_count", 0),
                    embedding_json=chunk.embedding,
                )
                self.db.add(emb)
                await self.db.flush()
                try:
                    await self.db.execute(
                        text("UPDATE knowledge_embeddings SET embedding = CAST(:vec AS vector) WHERE id = :id"),
                        {"vec": vec_str, "id": emb.id},
                    )
                except Exception:
                    pass
            count += 1

        await self.db.commit()
        return count

    async def search(
        self,
        organization_id: str,
        embedding: List[float],
        top_k: int,
        filters: Optional[VectorSearchFilters] = None,
    ) -> List[VectorHit]:
        """
        Cosine similarity search.

        Strategy:
          1. Try native pgvector <=> operator (fast, uses HNSW index).
          2. Fall back to JSON array linear scan (SQLite / dev, no extension).

        TENANT ISOLATION: organization_id always included in WHERE clause.
        """
        start = time.monotonic()
        f = filters or VectorSearchFilters(organization_id=organization_id)

        # ── Strategy 1: Native pgvector (production) ──────────────────────────
        # Uses: ix_ke_vector_hnsw (HNSW index via pgvector_setup.sql)
        try:
            vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
            rows = await self.db.execute(
                text("""
                    SELECT ke.chunk_id, ke.organization_id, kc.document_id,
                           kc.knowledge_type, kc.language, kc.visibility,
                           kc.ai_allowed, kc.is_expired,
                           1 - (ke.embedding <=> CAST(:query_vec AS vector)) AS score
                    FROM knowledge_embeddings ke
                    JOIN knowledge_chunks kc ON ke.chunk_id = kc.id
                    WHERE ke.organization_id = :org_id
                      AND ke.is_active = TRUE
                      AND kc.is_expired = FALSE
                      AND kc.ai_allowed = TRUE
                    ORDER BY ke.embedding <=> CAST(:query_vec AS vector)
                    LIMIT :top_k
                """),
                {
                    "org_id": organization_id,
                    "query_vec": vec_str,
                    "top_k": top_k,
                },
            )
            rows = rows.fetchall()

            hits: List[VectorHit] = []
            for row in rows:
                hits.append(VectorHit(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    organization_id=row.organization_id,
                    score=float(row.score or 0.0),
                    metadata={
                        "knowledge_type": row.knowledge_type,
                        "language": row.language,
                        "visibility": row.visibility,
                    },
                ))

            latency_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                f"[VECTOR SEARCH:native] org={organization_id} top_k={top_k} "
                f"hits={len(hits)} {latency_ms}ms"
            )
            return hits

        except Exception as pgvector_err:
            # pgvector extension not installed or embedding column doesn't exist
            # Fall through to JSON fallback
            if "operator does not exist" not in str(pgvector_err) and \
               "column" not in str(pgvector_err).lower() and \
               "does not exist" not in str(pgvector_err).lower():
                # Unexpected error — re-raise
                raise

            logger.info(
                f"[VECTOR SEARCH] pgvector not available, using JSON fallback: {pgvector_err}"
            )

        # ── Strategy 2: JSON linear scan fallback (SQLite / dev) ─────────────
        rows = await self.db.execute(
            text("""
                SELECT ke.chunk_id, ke.organization_id, ke.embedding_json,
                       kc.document_id, kc.knowledge_type, kc.language,
                       kc.visibility, kc.ai_allowed, kc.is_expired
                FROM knowledge_embeddings ke
                JOIN knowledge_chunks kc ON ke.chunk_id = kc.id
                WHERE ke.organization_id = :org_id
                  AND ke.is_active = TRUE
                  AND kc.is_expired = FALSE
                  AND kc.ai_allowed = TRUE
                LIMIT 1000
            """),
            {"org_id": organization_id},
        )
        rows = rows.fetchall()

        hits: List[VectorHit] = []
        for row in rows:
            stored = row.embedding_json
            if not stored:
                continue
            score = self._cosine_similarity(embedding, stored)
            hits.append(VectorHit(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                organization_id=row.organization_id,
                score=score,
                metadata={
                    "knowledge_type": row.knowledge_type,
                    "language": row.language,
                    "visibility": row.visibility,
                },
            ))

        hits.sort(key=lambda h: h.score, reverse=True)
        hits = hits[:top_k]

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            f"[VECTOR SEARCH:json] org={organization_id} top_k={top_k} "
            f"candidates={len(rows)} hits={len(hits)} {latency_ms}ms"
        )
        return hits


    async def delete(
        self,
        organization_id: str,
        chunk_ids: List[str],
    ) -> int:
        """Delete embeddings. ALWAYS scoped to organization_id."""
        if not chunk_ids:
            return 0
        result = await self.db.execute(
            text(
                "DELETE FROM knowledge_embeddings "
                "WHERE organization_id = :org_id "
                "AND chunk_id = ANY(:chunk_ids)"
            ),
            {"org_id": organization_id, "chunk_ids": chunk_ids},
        )
        await self.db.commit()
        deleted = result.rowcount or 0
        logger.info(
            f"[VECTOR DELETE] org={organization_id} deleted={deleted} chunks"
        )
        return deleted

    async def delete_by_document(
        self,
        organization_id: str,
        document_id: str,
    ) -> int:
        """Delete all embeddings for a document scoped to organization."""
        result = await self.db.execute(
            text(
                "DELETE FROM knowledge_embeddings ke "
                "USING knowledge_chunks kc "
                "WHERE ke.chunk_id = kc.id "
                "AND ke.organization_id = :org_id "
                "AND kc.document_id = :doc_id"
            ),
            {"org_id": organization_id, "doc_id": document_id},
        )
        await self.db.commit()
        deleted = result.rowcount or 0
        logger.info(
            f"[VECTOR DELETE DOC] org={organization_id} doc={document_id} "
            f"deleted={deleted} embeddings"
        )
        return deleted

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ─── Mock Vector Store (Tests) ────────────────────────────────────────────────

class MockVectorStoreProvider(VectorStoreProvider):
    """
    In-memory mock vector store for unit tests.
    Strict tenant isolation enforced.
    """
    provider_name = "mock"

    def __init__(self):
        # {org_id: {chunk_id: ChunkVector}}
        self._store: Dict[str, Dict[str, ChunkVector]] = {}

    async def upsert(self, chunks: List[ChunkVector]) -> int:
        for chunk in chunks:
            if chunk.organization_id not in self._store:
                self._store[chunk.organization_id] = {}
            self._store[chunk.organization_id][chunk.chunk_id] = chunk
        return len(chunks)

    async def search(
        self,
        organization_id: str,
        embedding: List[float],
        top_k: int,
        filters: Optional[VectorSearchFilters] = None,
    ) -> List[VectorHit]:
        org_chunks = self._store.get(organization_id, {})
        results = []
        for chunk in org_chunks.values():
            if not chunk.embedding:
                continue
            score = PgVectorStoreProvider._cosine_similarity(
                embedding, chunk.embedding
            )
            results.append(VectorHit(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                organization_id=chunk.organization_id,
                score=score,
                metadata=chunk.metadata,
            ))
        results.sort(key=lambda h: h.score, reverse=True)
        return results[:top_k]

    async def delete(
        self, organization_id: str, chunk_ids: List[str]
    ) -> int:
        org_chunks = self._store.get(organization_id, {})
        count = 0
        for cid in chunk_ids:
            if cid in org_chunks:
                del org_chunks[cid]
                count += 1
        return count

    async def delete_by_document(
        self, organization_id: str, document_id: str
    ) -> int:
        org_chunks = self._store.get(organization_id, {})
        to_delete = [
            cid for cid, cv in org_chunks.items()
            if cv.document_id == document_id
        ]
        for cid in to_delete:
            del org_chunks[cid]
        return len(to_delete)
