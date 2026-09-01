"""
Candidate Property Retrieval Service
====================================
Queries authoritative PropertyListing DB and Search Service for available inventory.
Never retrieves from stale vector embeddings alone.
"""

import logging
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile
from app.modules.recommendation.scoring.FX_converter import FXConverter

logger = logging.getLogger(__name__)

class CandidateRetrievalService:
    """
    Multi-stage inventory query engine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fx_converter = FXConverter()

    async def retrieve_candidates(
        self,
        buyer_profile: BuyerProfile,
        limit: int = 50,
        filter_overpriced: bool = False,
    ) -> List[PropertyListing]:
        """
        Queries database for available property listings matching candidate criteria.
        """
        b_uuid = (
            uuid.UUID(buyer_profile.broker_id)
            if isinstance(buyer_profile.broker_id, str) and len(buyer_profile.broker_id) == 36
            else buyer_profile.broker_id
        )

        conditions = [
            PropertyListing.deleted_at.is_(None),
            PropertyListing.status == "available"
        ]
        if b_uuid:
            conditions.append(PropertyListing.broker_id == b_uuid)

        stmt = (
            select(PropertyListing)
            .where(and_(*conditions))
            .order_by(PropertyListing.created_at.desc())
            .limit(limit * 2)
        )

        result = await self.db.execute(stmt)
        listings = list(result.scalars().all())

        # Optional AVM overpriced filter
        if filter_overpriced:
            listings = [p for p in listings if not getattr(p, "is_overpriced", False)]

        logger.info(f"[CANDIDATE_RETRIEVAL] Retrieved {len(listings)} candidate listings.")
        return listings[:limit]

