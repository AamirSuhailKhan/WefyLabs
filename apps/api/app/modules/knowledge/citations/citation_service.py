"""
Citation Service
==================
Persists knowledge citations for every AI answer to the database.

Every answer that uses retrieved knowledge must:
  1. Record which chunks were cited (KnowledgeCitation records)
  2. Update the retrieval records (was_cited=True)
  3. Log the query for observability and evaluation

This enables:
  - Auditability ("show me what knowledge the AI used")
  - Evaluation (precision/recall)
  - Feedback loop (which chunks are most cited)
  - Compliance (traceable AI outputs)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.models.knowledge_models import KnowledgeCitation, KnowledgeQuery, KnowledgeRetrieval

logger = logging.getLogger(__name__)


class CitationService:
    """
    Records citations and query telemetry to the database.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_query(
        self,
        organization_id: str,
        query_text: str,
        session_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        channel: Optional[str] = None,
        intent: Optional[str] = None,
        filters_applied: Optional[Dict] = None,
        knowledge_types: Optional[List[str]] = None,
        retrieval_stats: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a knowledge query and its retrieval telemetry.
        Returns the query_id for linking citations.
        """
        retrieval_stats = retrieval_stats or {}
        query_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        query = KnowledgeQuery(
            id=query_id,
            organization_id=organization_id,
            session_id=session_id,
            lead_id=lead_id,
            channel=channel,
            query_text=query_text[:2000],
            query_language=retrieval_stats.get("query_language", "en"),
            intent=intent,
            entities_extracted=retrieval_stats.get("entities", {}),
            filters_applied=filters_applied or {},
            knowledge_types_queried=knowledge_types or [],
            top_k=retrieval_stats.get("top_k", 10),
            vector_hits=retrieval_stats.get("vector_hits", 0),
            keyword_hits=retrieval_stats.get("keyword_hits", 0),
            reranked_hits=retrieval_stats.get("reranked_hits", 0),
            context_chunks_used=retrieval_stats.get("context_chunks_used", 0),
            retrieval_latency_ms=retrieval_stats.get("retrieval_latency_ms"),
            reranking_latency_ms=retrieval_stats.get("reranking_latency_ms"),
            llm_latency_ms=retrieval_stats.get("llm_latency_ms"),
            total_latency_ms=retrieval_stats.get("total_latency_ms"),
            embedding_tokens=retrieval_stats.get("embedding_tokens", 0),
            context_tokens=retrieval_stats.get("context_tokens", 0),
            llm_tokens_input=retrieval_stats.get("llm_tokens_input", 0),
            llm_tokens_output=retrieval_stats.get("llm_tokens_output", 0),
            answer_confidence=retrieval_stats.get("answer_confidence"),
            grounding_passed=retrieval_stats.get("grounding_passed"),
            had_citation=retrieval_stats.get("had_citation", False),
            hallucination_flagged=retrieval_stats.get("hallucination_flagged", False),
            created_at=now,
        )
        self.db.add(query)
        await self.db.commit()
        return query_id

    async def record_citations(
        self,
        query_id: str,
        organization_id: str,
        citations: List[Any],  # List of KnowledgeCitation dataclass instances
    ) -> int:
        """
        Persist citation records for an answered query.
        Returns count of citations saved.
        """
        now = datetime.now(timezone.utc)
        count = 0

        for citation in citations:
            db_citation = KnowledgeCitation(
                id=str(uuid.uuid4()),
                query_id=query_id,
                organization_id=organization_id,
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                page_number=citation.page_number,
                section=citation.section,
                heading=citation.heading,
                cited_text=citation.cited_text,
                source_display_name=citation.source_title,
                citation_index=citation.citation_index,
                created_at=now,
            )
            self.db.add(db_citation)
            count += 1

        # Mark retrieval records as cited
        if citations:
            chunk_ids = [c.chunk_id for c in citations if c.chunk_id]
            if chunk_ids:
                await self.db.execute(
                    update(KnowledgeRetrieval)
                    .where(
                        KnowledgeRetrieval.query_id == query_id,
                        KnowledgeRetrieval.chunk_id.in_(chunk_ids),
                    )
                    .values(was_cited=True, was_used_in_context=True)
                )

        await self.db.commit()
        logger.info(
            f"[CITATIONS] query={query_id} recorded {count} citations"
        )
        return count

    async def record_retrieval_results(
        self,
        query_id: str,
        organization_id: str,
        results: List[Dict[str, Any]],
    ) -> None:
        """Record all retrieval candidates (not just cited ones) for evaluation."""
        now = datetime.now(timezone.utc)
        for rank, result in enumerate(results, 1):
            retrieval = KnowledgeRetrieval(
                id=str(uuid.uuid4()),
                query_id=query_id,
                chunk_id=result.get("chunk_id", ""),
                document_id=result.get("document_id", ""),
                organization_id=organization_id,
                retrieval_method=result.get("retrieval_method", "hybrid"),
                rank_position=rank,
                vector_score=result.get("vector_score"),
                keyword_score=result.get("keyword_score"),
                reranker_score=result.get("reranker_score"),
                final_score=result.get("score"),
                was_used_in_context=False,
                was_cited=False,
                created_at=now,
            )
            self.db.add(retrieval)
        await self.db.commit()
