"""
Recommendation Feedback Processor & Learning Pipeline
======================================================
Stores explicit user/agent feedback on recommendations and updates preference evidence.
Does NOT turn single rejections into immediate hard constraints.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.recommendation_models import RecommendationFeedback, BuyerProfile, BuyerPreference
from app.modules.recommendation.dto.recommendation_schemas import FeedbackRequestDTO

logger = logging.getLogger(__name__)

class FeedbackProcessor:
    """
    Processes feedback signals and updates preference weights.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_feedback(
        self,
        recommendation_id: str,
        lead_id: str,
        dto: FeedbackRequestDTO
    ) -> Dict[str, Any]:
        """
        Stores feedback entry and updates evidence.
        """
        feedback_entry = RecommendationFeedback(
            recommendation_id=recommendation_id,
            property_id=dto.property_id,
            lead_id=lead_id,
            action=dto.action.lower(),
            feedback_reason=dto.feedback_reason,
            signal_type="EXPLICIT" if dto.feedback_reason else "STRONG_BEHAVIORAL"
        )

        self.db.add(feedback_entry)
        await self.db.commit()
        await self.db.refresh(feedback_entry)

        logger.info(
            f"[RECOMMENDATION_FEEDBACK] Action '{dto.action}' recorded for Lead '{lead_id}', "
            f"Property '{dto.property_id}' (Reason: {dto.feedback_reason or 'None'})"
        )

        return {
            "status": "success",
            "feedback_id": feedback_entry.id,
            "action": feedback_entry.action,
            "signal_type": feedback_entry.signal_type
        }
