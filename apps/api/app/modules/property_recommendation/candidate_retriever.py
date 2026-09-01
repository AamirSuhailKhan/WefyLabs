"""
Part 21.3 — Candidate Property Retrieval Service
=================================================
Queries authoritative PropertyListing database strictly scoped to the authenticated tenant.
Guarantees:
- Zero cross-tenant inventory leakage.
- Zero synthetic / mock property generation.
- Real-time availability enforcement.
"""
import uuid
import hashlib
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.property_models import PropertyListing
from app.modules.property_recommendation.dto import NormalizedRequirementsDTO
from app.modules.global_.currencies.money import Money

logger = logging.getLogger(__name__)


def compute_inventory_hash(listings: List[PropertyListing]) -> str:
    """Computes a deterministic hash of candidate listings to detect price or availability changes."""
    hasher = hashlib.sha256()
    for p in sorted(listings, key=lambda x: str(x.id)):
        hasher.update(str(p.id).encode("utf-8"))
        hasher.update(str(p.price).encode("utf-8"))
        hasher.update(str(p.status).encode("utf-8"))
        hasher.update(str(getattr(p, "updated_at", "")).encode("utf-8"))
    return hasher.hexdigest()[:16]


class CandidateRetrievalService:
    """
    Tenant-isolated property candidate retrieval engine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve_candidates(
        self,
        organization_id: str,
        requirements: NormalizedRequirementsDTO,
        limit: int = 50,
        filter_overpriced: bool = False,
    ) -> Tuple[List[PropertyListing], str]:
        """
        Retrieves active property candidates from the tenant's database inventory.
        Returns: (candidate_listings, inventory_hash)
        """
        # Convert organization_id / broker_id to UUID if valid 36-char string
        broker_uuid = (
            uuid.UUID(organization_id)
            if isinstance(organization_id, str) and len(organization_id) == 36
            else organization_id
        )

        conditions = [
            PropertyListing.broker_id == broker_uuid,
            PropertyListing.deleted_at.is_(None),
            PropertyListing.status.in_(["available", "active", "ready"]),
        ]

        # Transaction intent filter (BUY prospects shouldn't receive rental-only inventory)
        intent = requirements.transaction_intent.upper()
        if intent in ("BUY", "INVEST"):
            conditions.append(PropertyListing.transaction_category.in_(["resale", "offplan_developer", "sale", "new"]))
        elif intent in ("RENT", "LEASE"):
            conditions.append(PropertyListing.transaction_category.in_(["rent", "lease", "rental"]))

        stmt = (
            select(PropertyListing)
            .where(and_(*conditions))
            .order_by(PropertyListing.created_at.desc())
            .limit(limit * 3)
        )

        result = await self.db.execute(stmt)
        listings = list(result.scalars().all())

        # If zero candidates match exact transaction filter, relax transaction filter within tenant scope
        if not listings:
            fallback_stmt = (
                select(PropertyListing)
                .where(
                    and_(
                        PropertyListing.broker_id == broker_uuid,
                        PropertyListing.deleted_at.is_(None),
                        PropertyListing.status.in_(["available", "active", "ready"]),
                    )
                )
                .order_by(PropertyListing.created_at.desc())
                .limit(limit * 3)
            )
            fallback_res = await self.db.execute(fallback_stmt)
            listings = list(fallback_res.scalars().all())

        # Optional AVM overpriced filter
        if filter_overpriced:
            listings = [p for p in listings if not getattr(p, "is_overpriced", False)]

        inv_hash = compute_inventory_hash(listings)
        logger.info(
            f"[CANDIDATE_RETRIEVAL] Retrieved {len(listings)} tenant candidates for org '{organization_id}' "
            f"(inv_hash: {inv_hash}). Zero mock data."
        )

        return listings[:limit], inv_hash
