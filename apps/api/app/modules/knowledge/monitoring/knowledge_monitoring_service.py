"""
Knowledge Intelligence Platform — Monitoring Service
======================================================
Collects and exposes operational metrics for the knowledge engine.

Metrics tracked:
  - Document counts by status
  - Processing pipeline health (pending, running, failed jobs)
  - Embedding cost (tokens, estimated USD)
  - Retrieval volume and latency
  - Conflict counts (open, resolved)
  - Freshness violations
  - Cache hit rates (if Redis metrics available)

Design:
  - All queries are read-only and tenant-isolated.
  - Used by the /knowledge/health endpoint.
  - Can be extended to emit Prometheus metrics.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class DocumentStatusSummary:
    """Count of documents in each lifecycle state."""
    total: int = 0
    uploaded: int = 0
    processing: int = 0
    parsed: int = 0
    extracted: int = 0
    indexing: int = 0
    indexed: int = 0
    published: int = 0
    failed: int = 0
    archived: int = 0
    expired: int = 0
    deleted: int = 0


@dataclass
class PipelineHealthSummary:
    """State of the background processing pipeline."""
    pending_jobs: int = 0
    running_jobs: int = 0
    failed_jobs: int = 0
    completed_jobs_24h: int = 0
    avg_processing_time_seconds: float = 0.0


@dataclass
class RetrievalMetricsSummary:
    """Knowledge retrieval performance metrics."""
    total_queries_24h: int = 0
    avg_retrieval_latency_ms: float = 0.0
    avg_reranking_latency_ms: float = 0.0
    total_chunks_indexed: int = 0
    open_conflicts: int = 0
    resolved_conflicts: int = 0
    freshness_violations: int = 0


@dataclass
class CostSummary:
    """AI cost tracking for the knowledge engine."""
    total_embedding_tokens: int = 0
    total_embedding_cost_usd: float = 0.0
    total_queries: int = 0
    estimated_monthly_cost_usd: float = 0.0


@dataclass
class KnowledgeHealthReport:
    """Full health report for a knowledge engine tenant."""
    organization_id: Optional[str]
    status: str                         # "healthy" | "degraded" | "critical"
    documents: DocumentStatusSummary
    pipeline: PipelineHealthSummary
    retrieval: RetrievalMetricsSummary
    costs: CostSummary
    embedding_provider: str
    vector_store_provider: str
    ocr_provider: str
    checked_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "organization_id": self.organization_id,
            "embedding_provider": self.embedding_provider,
            "vector_store_provider": self.vector_store_provider,
            "ocr_provider": self.ocr_provider,
            "checked_at": self.checked_at,
            "documents": {
                "total": self.documents.total,
                "published": self.documents.published,
                "processing": self.documents.processing,
                "failed": self.documents.failed,
                "expired": self.documents.expired,
                "indexed": self.documents.indexed,
            },
            "pipeline": {
                "pending_jobs": self.pipeline.pending_jobs,
                "running_jobs": self.pipeline.running_jobs,
                "failed_jobs": self.pipeline.failed_jobs,
                "completed_jobs_24h": self.pipeline.completed_jobs_24h,
            },
            "retrieval": {
                "total_queries_24h": self.retrieval.total_queries_24h,
                "avg_retrieval_latency_ms": round(self.retrieval.avg_retrieval_latency_ms, 1),
                "total_chunks_indexed": self.retrieval.total_chunks_indexed,
                "open_conflicts": self.retrieval.open_conflicts,
                "freshness_violations": self.retrieval.freshness_violations,
            },
            "costs": {
                "total_embedding_tokens": self.costs.total_embedding_tokens,
                "total_embedding_cost_usd": round(self.costs.total_embedding_cost_usd, 4),
                "estimated_monthly_cost_usd": round(self.costs.estimated_monthly_cost_usd, 2),
            },
        }


class KnowledgeMonitoringService:
    """
    Collects health and metrics for the Knowledge Intelligence Platform.
    All queries are scoped by organization_id for tenant isolation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_health_report(
        self,
        organization_id: Optional[str] = None,
    ) -> KnowledgeHealthReport:
        """
        Collect a full health report for an organization's knowledge engine.
        If organization_id is None, returns platform-wide metrics (admin only).
        """
        try:
            docs = await self._get_document_summary(organization_id)
        except Exception as exc:
            logger.error(f"[MONITOR] Document summary failed: {exc}")
            docs = DocumentStatusSummary()

        try:
            pipeline = await self._get_pipeline_health(organization_id)
        except Exception as exc:
            logger.error(f"[MONITOR] Pipeline health failed: {exc}")
            pipeline = PipelineHealthSummary()

        try:
            retrieval = await self._get_retrieval_metrics(organization_id)
        except Exception as exc:
            logger.error(f"[MONITOR] Retrieval metrics failed: {exc}")
            retrieval = RetrievalMetricsSummary()

        try:
            costs = await self._get_cost_summary(organization_id)
        except Exception as exc:
            logger.error(f"[MONITOR] Cost summary failed: {exc}")
            costs = CostSummary()

        # Determine overall health status
        status = "healthy"
        if docs.failed > 5 or pipeline.failed_jobs > 10:
            status = "degraded"
        if docs.failed > 20 or pipeline.running_jobs > 50:
            status = "critical"

        import os
        return KnowledgeHealthReport(
            organization_id=organization_id,
            status=status,
            documents=docs,
            pipeline=pipeline,
            retrieval=retrieval,
            costs=costs,
            embedding_provider=os.getenv("KNOWLEDGE_EMBEDDING_PROVIDER", "openai"),
            vector_store_provider=os.getenv("KNOWLEDGE_VECTOR_STORE_PROVIDER", "pgvector"),
            ocr_provider=os.getenv("KNOWLEDGE_OCR_PROVIDER", "mock"),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _get_document_summary(
        self, organization_id: Optional[str]
    ) -> DocumentStatusSummary:
        """Count documents per lifecycle status."""
        org_filter = "AND organization_id = :org_id" if organization_id else ""
        params = {"org_id": organization_id} if organization_id else {}

        result = await self.db.execute(
            text(f"""
                SELECT status, COUNT(*) as cnt
                FROM knowledge_documents
                WHERE 1=1 {org_filter}
                GROUP BY status
            """),
            params,
        )
        rows = result.fetchall()

        summary = DocumentStatusSummary()
        for row in rows:
            status_key = row.status.lower() if row.status else "unknown"
            count = row.cnt or 0
            summary.total += count
            if hasattr(summary, status_key):
                setattr(summary, status_key, count)

        return summary

    async def _get_pipeline_health(
        self, organization_id: Optional[str]
    ) -> PipelineHealthSummary:
        """Check state of the background processing pipeline."""
        org_filter = "AND organization_id = :org_id" if organization_id else ""
        params = {"org_id": organization_id} if organization_id else {}
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        result = await self.db.execute(
            text(f"""
                SELECT status, COUNT(*) as cnt
                FROM knowledge_processing_jobs
                WHERE 1=1 {org_filter}
                GROUP BY status
            """),
            params,
        )
        rows = result.fetchall()

        completed_params = {"since": since}
        if organization_id:
            completed_params["org_id"] = organization_id

        completed_result = await self.db.execute(
            text(f"""
                SELECT COUNT(*) as cnt
                FROM knowledge_processing_jobs
                WHERE status = 'completed'
                  AND completed_at >= :since
                  {org_filter}
            """),
            completed_params,
        )
        completed_row = completed_result.fetchone()

        summary = PipelineHealthSummary(
            completed_jobs_24h=completed_row.cnt if completed_row else 0,
        )
        for row in rows:
            if row.status == "pending":
                summary.pending_jobs = row.cnt
            elif row.status == "running":
                summary.running_jobs = row.cnt
            elif row.status == "failed":
                summary.failed_jobs = row.cnt

        return summary

    async def _get_retrieval_metrics(
        self, organization_id: Optional[str]
    ) -> RetrievalMetricsSummary:
        """Collect retrieval volume and quality metrics."""
        org_filter = "AND organization_id = :org_id" if organization_id else ""
        params = {"org_id": organization_id} if organization_id else {}
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        q_params = {"since": since}
        if organization_id:
            q_params["org_id"] = organization_id

        q_result = await self.db.execute(
            text(f"""
                SELECT COUNT(*) as cnt,
                       AVG(retrieval_latency_ms) as avg_latency
                FROM knowledge_queries
                WHERE created_at >= :since {org_filter}
            """),
            q_params,
        )
        q_row = q_result.fetchone()

        chunk_result = await self.db.execute(
            text(f"""
                SELECT COUNT(*) as cnt
                FROM knowledge_chunks
                WHERE is_expired = FALSE {org_filter}
            """),
            params,
        )
        chunk_row = chunk_result.fetchone()

        conflict_result = await self.db.execute(
            text(f"""
                SELECT
                  SUM(CASE WHEN resolution_status = 'OPEN' THEN 1 ELSE 0 END) as open_cnt,
                  SUM(CASE WHEN resolution_status = 'RESOLVED' THEN 1 ELSE 0 END) as resolved_cnt
                FROM knowledge_conflicts
                WHERE 1=1 {org_filter}
            """),
            params,
        )
        conflict_row = conflict_result.fetchone()

        now_str = datetime.now(timezone.utc).isoformat()
        fresh_params = {"now": now_str}
        if organization_id:
            fresh_params["org_id"] = organization_id

        fresh_result = await self.db.execute(
            text(f"""
                SELECT COUNT(*) as cnt
                FROM knowledge_documents
                WHERE status = 'PUBLISHED'
                  AND expires_at IS NOT NULL
                  AND expires_at < :now
                  {org_filter}
            """),
            fresh_params,
        )
        fresh_row = fresh_result.fetchone()

        return RetrievalMetricsSummary(
            total_queries_24h=q_row.cnt if q_row else 0,
            avg_retrieval_latency_ms=float(q_row.avg_latency or 0.0) if q_row else 0.0,
            total_chunks_indexed=chunk_row.cnt if chunk_row else 0,
            open_conflicts=conflict_row.open_cnt if conflict_row and conflict_row.open_cnt else 0,
            resolved_conflicts=conflict_row.resolved_cnt if conflict_row and conflict_row.resolved_cnt else 0,
            freshness_violations=fresh_row.cnt if fresh_row else 0,
        )

    async def _get_cost_summary(
        self, organization_id: Optional[str]
    ) -> CostSummary:
        """Estimate AI costs from tracked token usage."""
        org_filter = "AND organization_id = :org_id" if organization_id else ""
        params = {"org_id": organization_id} if organization_id else {}

        result = await self.db.execute(
            text(f"""
                SELECT
                  COALESCE(SUM(total_tokens), 0) as total_tokens,
                  COALESCE(SUM(cost_usd), 0) as total_cost,
                  COUNT(*) as total_queries
                FROM knowledge_queries
                WHERE 1=1 {org_filter}
            """),
            params,
        )
        row = result.fetchone()

        total_tokens = int(row.total_tokens or 0) if row else 0
        total_cost = float(row.total_cost or 0.0) if row else 0.0
        total_queries = int(row.total_queries or 0) if row else 0
        estimated_monthly = total_cost * 30 if total_cost > 0 else 0.0

        return CostSummary(
            total_embedding_tokens=total_tokens,
            total_embedding_cost_usd=total_cost,
            total_queries=total_queries,
            estimated_monthly_cost_usd=estimated_monthly,
        )

    async def get_document_processing_errors(
        self,
        organization_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return recently failed documents with error details."""
        result = await self.db.execute(
            text("""
                SELECT id, title, file_name, processing_error, updated_at
                FROM knowledge_documents
                WHERE organization_id = :org_id
                  AND status = 'FAILED'
                ORDER BY updated_at DESC
                LIMIT :limit
            """),
            {"org_id": organization_id, "limit": limit},
        )
        rows = result.fetchall()
        return [
            {
                "document_id": row.id,
                "title": row.title,
                "file_name": row.file_name,
                "error": row.processing_error,
                "failed_at": str(row.updated_at),
            }
            for row in rows
        ]
