"""
Manual Review Service — manages the manual review queue for ambiguous duplicate candidates.
Reviewer sees: lead vs identity, AI explanation, similarity breakdown, recommendation.
Reviewer decisions are stored as ML ground truth labels.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.identity_models import ManualReview, DuplicateCandidate

logger = logging.getLogger(__name__)


class ReviewService:
    """
    Manages the manual review queue.

    Queue Workflow:
    1. Identity resolution creates ManualReview when confidence is 85-94%
    2. Reviewer fetches pending reviews via list_pending()
    3. Reviewer submits decision via submit_decision()
    4. Decision is stored as ML ground truth
    5. System executes merge or marks as ignored
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_review(
        self,
        candidate: DuplicateCandidate,
        ai_explanation: str,
        organization_id: str,
        assigned_to: Optional[str] = None,
        priority: str = "normal",
    ) -> ManualReview:
        """Create a new manual review queue item."""
        review = ManualReview(
            candidate_id=candidate.id,
            organization_id=organization_id,
            lead_id=candidate.lead_id,
            candidate_identity_id=candidate.candidate_identity_id,
            ai_confidence=candidate.overall_confidence,
            ai_recommendation=self._get_recommendation(candidate.overall_confidence),
            ai_explanation=ai_explanation,
            similarity_breakdown={
                "per_field_scores": candidate.per_field_scores,
                "matched_fields": candidate.matched_fields,
                "algorithms_used": candidate.algorithms_used,
                "weights_used": candidate.weights_used,
                "reason": candidate.reason,
            },
            status="pending",
            priority=priority,
            assigned_to=assigned_to,
        )
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(review)

        logger.info(
            f"[REVIEW_SERVICE] Created review {review.id} for lead {candidate.lead_id} "
            f"vs identity {candidate.candidate_identity_id} (confidence={candidate.overall_confidence:.1%})"
        )
        return review

    async def submit_decision(
        self,
        review_id: str,
        reviewer_id: str,
        decision: str,  # merge | ignore | defer
        reviewer_notes: Optional[str] = None,
        reviewer_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Submit a reviewer decision. Stores as ML ground truth label.
        Returns the updated review and next action to take.
        """
        result = await self.db.execute(select(ManualReview).where(ManualReview.id == review_id))
        review = result.scalar_one_or_none()

        if not review:
            raise ValueError(f"ManualReview {review_id} not found")
        if review.status != "pending":
            raise ValueError(f"Review {review_id} is already {review.status}")

        if decision not in ("merge", "ignore", "defer"):
            raise ValueError(f"Invalid decision: {decision}. Must be merge | ignore | defer")

        # Store as ML ground truth
        review.reviewer_id = reviewer_id
        review.reviewer_decision = decision
        review.reviewer_confidence = reviewer_confidence
        review.reviewer_notes = reviewer_notes
        review.status = "completed" if decision != "defer" else "deferred"
        review.reviewed_at = datetime.now(timezone.utc)

        # Update the DuplicateCandidate status
        cand_result = await self.db.execute(
            select(DuplicateCandidate).where(DuplicateCandidate.id == review.candidate_id)
        )
        candidate = cand_result.scalar_one_or_none()
        if candidate:
            candidate.status = "merged" if decision == "merge" else "ignored"
            candidate.processed_at = datetime.now(timezone.utc)

        await self.db.commit()

        logger.info(f"[REVIEW_SERVICE] Review {review_id} decided: {decision} by {reviewer_id}")

        return {
            "review_id": review_id,
            "decision": decision,
            "next_action": "execute_merge" if decision == "merge" else "close",
            "candidate_id": review.candidate_id,
            "lead_id": review.lead_id,
            "candidate_identity_id": review.candidate_identity_id,
        }

    async def list_pending(
        self,
        organization_id: str,
        assigned_to: Optional[str] = None,
        limit: int = 50,
    ) -> List[ManualReview]:
        """List pending manual reviews for an organization."""
        stmt = (
            select(ManualReview)
            .where(
                ManualReview.organization_id == organization_id,
                ManualReview.status == "pending",
            )
            .order_by(ManualReview.created_at.asc())
            .limit(limit)
        )
        if assigned_to:
            stmt = stmt.where(ManualReview.assigned_to == assigned_to)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def _get_recommendation(confidence: float) -> str:
        if confidence >= 0.93:
            return "merge"
        elif confidence >= 0.88:
            return "merge"
        else:
            return "defer"
