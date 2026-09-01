"""
Reranker Provider Abstraction
==============================
Reranking improves retrieval precision by re-scoring retrieved chunks
against the original query using a cross-encoder or rule-based model.

Implementations:
  ScoreBoostRerankerProvider — rule-based (default, no external API)
  CohereRerankerProvider     — Cohere Rerank API
  CrossEncoderProvider       — local cross-encoder (sentence-transformers)

Ranking factors (configurable per org):
  - Semantic similarity to query
  - Keyword relevance
  - Entity match (project, property, developer)
  - Source authority (source priority rank)
  - Document freshness (recency)
  - Verification status (VERIFIED > UNVERIFIED)
  - Permission level
  - Conversation context match
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class RankableDocument:
    """A retrieved chunk or result ready for reranking."""
    chunk_id: str
    document_id: str
    text: str
    initial_score: float        # Score from retrieval (vector or keyword)
    retrieval_method: str       # "vector" | "keyword" | "hybrid" | "structured"
    metadata: Dict[str, Any] = field(default_factory=dict)
    # metadata: knowledge_type, language, verification_status, source_priority_rank,
    #           freshness_days, project_id, property_id, effective_at, expires_at


@dataclass
class RankedDocument:
    """A reranked result."""
    chunk_id: str
    document_id: str
    text: str
    initial_score: float
    reranker_score: float
    final_score: float          # Combined/weighted final score
    rank_position: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    rerank_reason: str = ""


# ─── Abstract Interface ────────────────────────────────────────────────────────

class RerankerProvider(ABC):
    """
    Abstract reranker interface.
    Input: query + list of ranked documents.
    Output: re-sorted list of RankedDocument.
    """
    provider_name: str = "abstract"

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[RankableDocument],
        top_n: int = 5,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[RankedDocument]:
        """
        Rerank documents for the query.
        Returns at most top_n results, sorted by final_score descending.
        context may contain: project_id, lead_id, channel, conversation_id.
        """
        ...


# ─── Score Boost Reranker (Default, No API needed) ───────────────────────────

class ScoreBoostRerankerProvider(RerankerProvider):
    """
    Rule-based reranker — no external API required.
    Applies configurable boosts based on:
      - Keyword match in text
      - Verification status
      - Source authority rank
      - Document freshness
      - Entity (project/property) match
      - Knowledge type priority

    Default reranker when no Cohere/CrossEncoder is configured.
    """
    provider_name = "score_boost"

    # Knowledge type priority boosts (higher = more important for real estate)
    _TYPE_BOOSTS: Dict[str, float] = {
        "PRICE": 1.5,
        "PAYMENT_PLAN": 1.4,
        "AVAILABILITY": 1.4,
        "FLOOR_PLAN": 1.2,
        "PROJECT": 1.1,
        "AMENITY": 1.1,
        "LOCATION": 1.0,
        "FAQ": 1.0,
        "POLICY": 0.9,
        "LEGAL": 0.8,
        "MARKETING": 0.7,
        "OTHER": 0.6,
    }

    async def rerank(
        self,
        query: str,
        documents: List[RankableDocument],
        top_n: int = 5,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[RankedDocument]:
        context = context or {}
        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))

        ranked: List[RankedDocument] = []

        for doc in documents:
            score = doc.initial_score

            # ── 1. Keyword overlap boost
            text_tokens = set(re.findall(r"\w+", doc.text.lower()))
            overlap = len(query_tokens & text_tokens)
            keyword_boost = min(overlap / max(len(query_tokens), 1) * 0.3, 0.3)
            score += keyword_boost

            # ── 2. Verification status boost
            verification = doc.metadata.get("verification_status", "UNVERIFIED")
            if verification == "VERIFIED":
                score += 0.2
            elif verification == "UNVERIFIED":
                score -= 0.05

            # ── 3. Source authority boost (lower rank number = higher authority)
            authority_rank = doc.metadata.get("source_priority_rank", 50)
            authority_boost = max(0, (100 - authority_rank) / 100 * 0.15)
            score += authority_boost

            # ── 4. Freshness boost (prefer recent documents)
            freshness_days = doc.metadata.get("freshness_days", 90)
            if freshness_days < 7:
                score += 0.15
            elif freshness_days < 30:
                score += 0.10
            elif freshness_days < 90:
                score += 0.05
            elif freshness_days > 365:
                score -= 0.10

            # ── 5. Entity match boost (project or property)
            context_project_id = context.get("project_id")
            context_property_id = context.get("property_id")
            doc_project_id = doc.metadata.get("project_id")
            doc_property_id = doc.metadata.get("property_id")

            if context_project_id and doc_project_id == context_project_id:
                score += 0.25
            if context_property_id and doc_property_id == context_property_id:
                score += 0.20

            # ── 6. Knowledge type priority
            knowledge_type = doc.metadata.get("knowledge_type", "OTHER")
            type_boost = self._TYPE_BOOSTS.get(knowledge_type, 0.6)
            score *= type_boost

            # ── 7. Retrieval method confidence
            if doc.retrieval_method == "hybrid":
                score += 0.05
            elif doc.retrieval_method == "structured":
                score += 0.15  # Structured data is more reliable

            ranked.append(RankedDocument(
                chunk_id=doc.chunk_id,
                document_id=doc.document_id,
                text=doc.text,
                initial_score=doc.initial_score,
                reranker_score=score,
                final_score=round(score, 4),
                rank_position=0,  # will be set after sort
                metadata=doc.metadata,
                rerank_reason=f"boost:keyword={keyword_boost:.2f},authority={authority_boost:.2f}",
            ))

        # Sort by final score descending
        ranked.sort(key=lambda r: r.final_score, reverse=True)
        ranked = ranked[:top_n]

        # Assign rank positions
        for i, r in enumerate(ranked):
            r.rank_position = i + 1

        logger.info(
            f"[RERANKER:ScoreBoost] query='{query[:40]}...' "
            f"input={len(documents)} output={len(ranked)}"
        )
        return ranked


# ─── Cohere Reranker (Production) ─────────────────────────────────────────────

class CohereRerankerProvider(RerankerProvider):
    """
    Cohere Rerank API provider.
    Requires: cohere Python SDK + API key.
    """
    provider_name = "cohere"
    _DEFAULT_MODEL = "rerank-english-v3.0"

    def __init__(self, api_key: str, model: Optional[str] = None):
        self._api_key = api_key
        self._model = model or self._DEFAULT_MODEL

    async def rerank(
        self,
        query: str,
        documents: List[RankableDocument],
        top_n: int = 5,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[RankedDocument]:
        try:
            import cohere
            import asyncio

            client = cohere.Client(self._api_key)
            texts = [d.text[:2000] for d in documents]  # Cohere limit

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.rerank(
                    model=self._model,
                    query=query,
                    documents=texts,
                    top_n=top_n,
                ),
            )

            ranked: List[RankedDocument] = []
            for result in response.results:
                original = documents[result.index]
                ranked.append(RankedDocument(
                    chunk_id=original.chunk_id,
                    document_id=original.document_id,
                    text=original.text,
                    initial_score=original.initial_score,
                    reranker_score=result.relevance_score,
                    final_score=round(result.relevance_score, 4),
                    rank_position=len(ranked) + 1,
                    metadata=original.metadata,
                ))

            logger.info(
                f"[RERANKER:Cohere] query='{query[:40]}' "
                f"input={len(documents)} output={len(ranked)}"
            )
            return ranked

        except ImportError:
            logger.warning("[RERANKER:Cohere] cohere SDK not installed, falling back to ScoreBoost")
            return await ScoreBoostRerankerProvider().rerank(query, documents, top_n, context)
        except Exception as exc:
            logger.error(f"[RERANKER:Cohere] Error: {exc}", exc_info=True)
            return await ScoreBoostRerankerProvider().rerank(query, documents, top_n, context)


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_reranker_provider(
    provider_name: str = "score_boost",
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> RerankerProvider:
    """Resolve reranker by name from KnowledgeProvider config."""
    if provider_name == "cohere":
        if not api_key:
            logger.warning("[RERANKER FACTORY] Cohere api_key missing, using ScoreBoost")
            return ScoreBoostRerankerProvider()
        return CohereRerankerProvider(api_key=api_key)
    return ScoreBoostRerankerProvider()
