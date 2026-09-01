"""
Knowledge Feedback Service
============================
Processes and persists quality feedback on knowledge retrieval answers.

Feedback types:
  POSITIVE             — answer was correct and helpful
  NEGATIVE             — answer was wrong or unhelpful
  HALLUCINATION        — AI made up information not in knowledge base
  OUTDATED             — information was stale/expired
  INCOMPLETE           — insufficient context was retrieved
  OFF_TOPIC            — retrieval returned irrelevant results

Feedback drives:
  1. Evaluation dashboards (precision / recall trends)
  2. Chunk ranking adjustments (flagged chunks get lower priority)
  3. Freshness alerts (OUTDATED feedback triggers staleness review)
  4. Conflict detection alerts (HALLUCINATION feedback triggers review)
  5. KnowledgeFeedbackReceived domain event

Persists to: KnowledgeFeedback model (existing DB table).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.knowledge_models import KnowledgeFeedback, KnowledgeChunk, KnowledgeDocument
from app.infrastructure.events.event_bus import event_bus, DomainEvent, ActorContext
from app.modules.knowledge.events.knowledge_events import KnowledgeEvents

logger = logging.getLogger(__name__)

# Feedback types that warrant immediate admin notification
_CRITICAL_TYPES = {"HALLUCINATION", "OUTDATED"}


class FeedbackService:
    """
    Records and processes knowledge quality feedback.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_feedback(
        self,
        organization_id: str,
        query_id: str,
        feedback_type: str,
        given_by: str,
        given_by_type: str = "broker",   # "broker" | "customer" | "system"
        notes: Optional[str] = None,
        document_ids_flagged: Optional[List[str]] = None,
        chunk_ids_flagged: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        answer_relevance_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Record feedback and trigger side effects:
          - Persist KnowledgeFeedback record
          - For OUTDATED: flag document freshness issue
          - For HALLUCINATION: flag chunks for review
          - Emit KnowledgeFeedbackReceived event
        """
        now = datetime.now(timezone.utc)
        feedback_id = str(uuid.uuid4())

        feedback = KnowledgeFeedback(
            id=feedback_id,
            organization_id=organization_id,
            query_id=query_id,
            session_id=session_id,
            lead_id=lead_id,
            given_by=given_by,
            given_by_type=given_by_type,
            feedback_type=feedback_type,
            notes=notes[:1000] if notes else None,
            document_ids_flagged=document_ids_flagged or [],
            chunk_ids_flagged=chunk_ids_flagged or [],
            answer_relevance_score=answer_relevance_score,
            created_at=now,
        )
        self.db.add(feedback)

        # Side effect: flag documents for review on critical feedback
        if feedback_type in _CRITICAL_TYPES and document_ids_flagged:
            await self._flag_documents_for_review(
                organization_id, document_ids_flagged, feedback_type
            )

        await self.db.commit()

        # Emit event
        await event_bus.publish(DomainEvent(
            event_type=KnowledgeEvents.FEEDBACK_RECEIVED,
            organization_id=organization_id,
            actor=ActorContext(user_id=given_by, actor_type=given_by_type),
            payload={
                "feedback_id": feedback_id,
                "query_id": query_id,
                "feedback_type": feedback_type,
                "documents_flagged": len(document_ids_flagged or []),
                "is_critical": feedback_type in _CRITICAL_TYPES,
            },
        ))

        logger.info(
            f"[FEEDBACK] org={organization_id} type={feedback_type} "
            f"query={query_id} by={given_by_type}:{given_by[:8]}..."
        )

        return {
            "feedback_id": feedback_id,
            "feedback_type": feedback_type,
            "critical": feedback_type in _CRITICAL_TYPES,
            "message": "Feedback recorded. Thank you.",
        }

    async def get_feedback_summary(
        self,
        organization_id: str,
    ) -> Dict[str, Any]:
        """
        Return feedback statistics for the organization.
        Used by admin dashboard.
        """
        total = await self.db.scalar(
            select(func.count(KnowledgeFeedback.id)).where(
                KnowledgeFeedback.organization_id == organization_id,
            )
        ) or 0

        # Count by type
        type_counts: Dict[str, int] = {}
        for feedback_type in [
            "POSITIVE", "NEGATIVE", "HALLUCINATION", "OUTDATED", "INCOMPLETE", "OFF_TOPIC"
        ]:
            count = await self.db.scalar(
                select(func.count(KnowledgeFeedback.id)).where(
                    KnowledgeFeedback.organization_id == organization_id,
                    KnowledgeFeedback.feedback_type == feedback_type,
                )
            ) or 0
            type_counts[feedback_type] = count

        positive = type_counts.get("POSITIVE", 0)
        satisfaction = round(positive / max(total, 1) * 100, 1)

        return {
            "total_feedback": total,
            "by_type": type_counts,
            "satisfaction_rate_pct": satisfaction,
            "hallucination_count": type_counts.get("HALLUCINATION", 0),
            "outdated_count": type_counts.get("OUTDATED", 0),
        }

    async def _flag_documents_for_review(
        self,
        organization_id: str,
        document_ids: List[str],
        reason: str,
    ) -> None:
        """Flag documents for admin review based on critical feedback."""
        if not document_ids:
            return
        for doc_id in document_ids:
            result = await self.db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == doc_id,
                    KnowledgeDocument.organization_id == organization_id,
                )
            )
            doc = result.scalars().first()
            if doc:
                doc.needs_review = True
                doc.review_reason = reason
                doc.updated_at = datetime.now(timezone.utc)
        logger.warning(
            f"[FEEDBACK] Flagged {len(document_ids)} documents for review: {reason}"
        )
