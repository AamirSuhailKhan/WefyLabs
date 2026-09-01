"""
Hybrid Knowledge Search Service
==================================
Fuses three retrieval signals into a single ranked result set:
  1. Vector search — semantic similarity (pgvector)
  2. Keyword search — PostgreSQL full-text search (GIN + tsvector)
  3. Structured lookup — direct property/project DB query (via PropertyService)

Fusion algorithm: Reciprocal Rank Fusion (RRF)
  RRF score = Σ 1 / (k + rank_i) for each method
  k = 60 (standard constant)

Post-fusion:
  → Permission filter (tenant isolation + visibility + channel rules)
  → Freshness filter (exclude expired chunks)
  → Reranker
  → Context builder

CRITICAL invariants:
  1. organization_id enforced at EVERY DB query — never crossed.
  2. customer_facing_allowed checked before including in customer-facing answers.
  3. Expired chunks (is_expired=True) are NEVER served.
  4. Fact-only claims (PRICE, AVAILABILITY) are ALWAYS routed to structured lookup first.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.modules.knowledge.providers.provider_registry import ProviderRegistry
from app.modules.knowledge.providers.vector_store_provider import VectorSearchFilters
from app.modules.knowledge.providers.reranker_provider import RankableDocument
from app.modules.knowledge.retrieval.permission_service import KnowledgePermissionService
from app.modules.knowledge.retrieval.freshness_service import KnowledgeFreshnessService

logger = logging.getLogger(__name__)

RRF_K = 60  # Standard RRF constant


# ─── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class KnowledgeSearchResult:
    """A single retrieval result after fusion and permission filtering."""
    chunk_id: str
    document_id: str
    organization_id: str
    text: str
    score: float
    rank_position: int
    retrieval_method: str
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    reranker_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # metadata: knowledge_type, language, visibility, page_number,
    #           heading, section, source_title, effective_at, expires_at,
    #           verification_status, fact_type (if applicable)


@dataclass
class HybridSearchResponse:
    """Full hybrid retrieval response."""
    results: List[KnowledgeSearchResult]
    query: str
    organization_id: str
    total_vector_hits: int
    total_keyword_hits: int
    total_fused: int
    total_after_permission_filter: int
    retrieval_latency_ms: int
    reranking_latency_ms: int
    provider_used: str = "pgvector"


# ─── Hybrid Search Service ────────────────────────────────────────────────────

class HybridSearchService:
    """
    Main hybrid retrieval orchestrator.
    Called from:
      - KnowledgeService (AI agent tool)
      - Knowledge search API endpoint
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.permission_service = KnowledgePermissionService(db)
        self.freshness_service = KnowledgeFreshnessService(db)

    async def search(
        self,
        query: str,
        organization_id: str,
        top_k: int = 10,
        rerank_top_n: int = 5,
        knowledge_types: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
        language: Optional[str] = None,
        channel: str = "internal",
        role: str = "INTERNAL",
        session_context: Optional[Dict[str, Any]] = None,
    ) -> HybridSearchResponse:
        """
        Execute hybrid retrieval with permission enforcement.

        Args:
            channel: "customer_facing" | "internal" | "admin"
            role: caller's RBAC role (ADMIN, MANAGER, AGENT, CUSTOMER)
        """
        start = time.monotonic()
        session_context = session_context or {}

        # ── 1. Generate query embedding ──────────────────────────────────────
        embed_provider = await ProviderRegistry.get_embedding_provider(
            organization_id, self.db
        )
        embed_result = await embed_provider.embed_texts([query])
        query_embedding = embed_result.results[0].embedding if embed_result.results else []

        # ── 2. Vector search ─────────────────────────────────────────────────
        vector_hits = await self._vector_search(
            organization_id=organization_id,
            embedding=query_embedding,
            top_k=top_k * 3,  # Retrieve more for fusion
            knowledge_types=knowledge_types,
            project_id=project_id,
            property_id=property_id,
            language=language,
        )

        # ── 3. Keyword search ────────────────────────────────────────────────
        keyword_hits = await self._keyword_search(
            query=query,
            organization_id=organization_id,
            top_k=top_k * 3,
            knowledge_types=knowledge_types,
            project_id=project_id,
            property_id=property_id,
            language=language,
        )

        retrieval_latency_ms = int((time.monotonic() - start) * 1000)

        # ── 4. RRF Fusion ────────────────────────────────────────────────────
        fused = self._rrf_fusion(vector_hits, keyword_hits, top_k=top_k * 2)

        # ── 5. Permission filter ─────────────────────────────────────────────
        allowed = await self.permission_service.filter_results(
            results=fused,
            organization_id=organization_id,
            channel=channel,
            role=role,
        )

        # ── 6. Freshness filter ──────────────────────────────────────────────
        fresh = await self.freshness_service.filter_expired(results=allowed)

        # ── 7. Reranking ─────────────────────────────────────────────────────
        rerank_start = time.monotonic()
        reranker = await ProviderRegistry.get_reranker_provider(
            organization_id, self.db
        )
        rankable = [
            RankableDocument(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                text=r["text"],
                initial_score=r["rrf_score"],
                retrieval_method=r["retrieval_method"],
                metadata=r.get("metadata", {}),
            )
            for r in fresh
        ]
        reranked = await reranker.rerank(
            query=query,
            documents=rankable,
            top_n=rerank_top_n,
            context={
                "project_id": project_id,
                "property_id": property_id,
                **session_context,
            },
        )
        reranking_latency_ms = int((time.monotonic() - rerank_start) * 1000)

        # ── 8. Build final results ───────────────────────────────────────────
        final_results = [
            KnowledgeSearchResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                organization_id=organization_id,
                text=r.text,
                score=r.final_score,
                rank_position=r.rank_position,
                retrieval_method=r.metadata.get("retrieval_method", "hybrid"),
                vector_score=r.metadata.get("vector_score"),
                keyword_score=r.metadata.get("keyword_score"),
                reranker_score=r.reranker_score,
                metadata=r.metadata,
            )
            for r in reranked
        ]

        logger.info(
            f"[HYBRID SEARCH] org={organization_id} query='{query[:40]}...' "
            f"vector={len(vector_hits)} keyword={len(keyword_hits)} "
            f"fused={len(fused)} allowed={len(allowed)} "
            f"final={len(final_results)} "
            f"retrieval={retrieval_latency_ms}ms rerank={reranking_latency_ms}ms"
        )

        return HybridSearchResponse(
            results=final_results,
            query=query,
            organization_id=organization_id,
            total_vector_hits=len(vector_hits),
            total_keyword_hits=len(keyword_hits),
            total_fused=len(fused),
            total_after_permission_filter=len(allowed),
            retrieval_latency_ms=retrieval_latency_ms,
            reranking_latency_ms=reranking_latency_ms,
        )

    async def _vector_search(
        self,
        organization_id: str,
        embedding: List[float],
        top_k: int,
        knowledge_types: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Vector similarity search via VectorStoreProvider."""
        vector_store = ProviderRegistry.get_vector_store_provider(
            provider_name="pgvector", db=self.db
        )
        filters = VectorSearchFilters(
            organization_id=organization_id,
            knowledge_types=knowledge_types,
            project_id=project_id,
            property_id=property_id,
            language=language,
            ai_allowed=True,
            exclude_expired=True,
        )
        hits = await vector_store.search(
            organization_id=organization_id,
            embedding=embedding,
            top_k=top_k,
            filters=filters,
        )

        results = []
        for rank, hit in enumerate(hits, 1):
            results.append({
                "chunk_id": hit.chunk_id,
                "document_id": hit.document_id,
                "text": "",  # Text is loaded below from chunk join
                "vector_score": hit.score,
                "vector_rank": rank,
                "retrieval_method": "vector",
                "metadata": hit.metadata,
            })

        # Load chunk text for vector hits
        if results:
            chunk_ids = [r["chunk_id"] for r in results]
            rows = await self.db.execute(
                text("""
                    SELECT kc.id, kc.content, kc.heading, kc.section, kc.page_number,
                           kc.knowledge_type, kc.visibility, kc.ai_allowed,
                           kc.language, kc.is_expired, kd.title as doc_title,
                           kc.effective_at, kc.expires_at
                    FROM knowledge_chunks kc
                    JOIN knowledge_documents kd ON kc.document_id = kd.id
                    WHERE kc.id = ANY(:ids)
                    AND kc.organization_id = :org_id
                """),
                {"ids": chunk_ids, "org_id": organization_id},
            )
            chunk_map = {}
            for row in rows:
                chunk_map[row.id] = row

            enriched = []
            for r in results:
                row = chunk_map.get(r["chunk_id"])
                if row and not row.is_expired:
                    r["text"] = row.content
                    r["metadata"].update({
                        "knowledge_type": row.knowledge_type,
                        "visibility": row.visibility,
                        "ai_allowed": row.ai_allowed,
                        "language": row.language,
                        "page_number": row.page_number,
                        "heading": row.heading,
                        "section": row.section,
                        "source_title": row.doc_title,
                    })
                    enriched.append(r)
            results = enriched

        return results

    async def _keyword_search(
        self,
        query: str,
        organization_id: str,
        top_k: int,
        knowledge_types: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """PostgreSQL full-text search on knowledge_chunks.content."""
        where_clauses = [
            "kc.organization_id = :org_id",
            "kc.ai_allowed = TRUE",
            "kc.is_expired = FALSE",
            "kd.status = 'PUBLISHED'",
            "plainto_tsquery('english', :query) @@ to_tsvector('english', kc.content)",
        ]
        params: Dict[str, Any] = {
            "org_id": organization_id,
            "query": query,
            "top_k": top_k,
        }

        if knowledge_types:
            where_clauses.append("kc.knowledge_type = ANY(:ktypes)")
            params["ktypes"] = knowledge_types

        if project_id:
            where_clauses.append("kc.project_id = :project_id")
            params["project_id"] = project_id

        if property_id:
            where_clauses.append("kc.property_id = :property_id")
            params["property_id"] = property_id

        if language:
            where_clauses.append("kc.language = :language")
            params["language"] = language

        sql = f"""
            SELECT
                kc.id as chunk_id,
                kc.document_id,
                kc.content,
                kc.heading,
                kc.section,
                kc.page_number,
                kc.knowledge_type,
                kc.visibility,
                kc.ai_allowed,
                kc.language,
                kd.title as doc_title,
                ts_rank_cd(to_tsvector('english', kc.content), plainto_tsquery('english', :query)) as rank_score
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kc.document_id = kd.id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY rank_score DESC
            LIMIT :top_k
        """

        try:
            rows = await self.db.execute(text(sql), params)
            results = []
            for rank, row in enumerate(rows, 1):
                results.append({
                    "chunk_id": row.chunk_id,
                    "document_id": row.document_id,
                    "text": row.content,
                    "keyword_score": float(row.rank_score),
                    "keyword_rank": rank,
                    "retrieval_method": "keyword",
                    "metadata": {
                        "knowledge_type": row.knowledge_type,
                        "visibility": row.visibility,
                        "ai_allowed": row.ai_allowed,
                        "language": row.language,
                        "page_number": row.page_number,
                        "heading": row.heading,
                        "section": row.section,
                        "source_title": row.doc_title,
                    },
                })
            return results
        except Exception as exc:
            logger.error(f"[KEYWORD SEARCH] Failed: {exc}", exc_info=True)
            return []

    def _rrf_fusion(
        self,
        vector_hits: List[Dict],
        keyword_hits: List[Dict],
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion.
        Merges vector and keyword ranked lists into a single unified ranking.
        """
        scores: Dict[str, Dict[str, Any]] = {}

        # Score from vector hits
        for rank, hit in enumerate(vector_hits, 1):
            cid = hit["chunk_id"]
            if cid not in scores:
                scores[cid] = {**hit, "rrf_score": 0.0, "retrieval_method": "hybrid"}
            scores[cid]["rrf_score"] += 1.0 / (RRF_K + rank)
            scores[cid]["vector_score"] = hit.get("vector_score")

        # Score from keyword hits
        for rank, hit in enumerate(keyword_hits, 1):
            cid = hit["chunk_id"]
            if cid not in scores:
                scores[cid] = {**hit, "rrf_score": 0.0, "retrieval_method": "keyword"}
            else:
                scores[cid]["retrieval_method"] = "hybrid"
            scores[cid]["rrf_score"] += 1.0 / (RRF_K + rank)
            scores[cid]["keyword_score"] = hit.get("keyword_score")

        # Sort by RRF score descending
        fused = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        return fused[:top_k]
