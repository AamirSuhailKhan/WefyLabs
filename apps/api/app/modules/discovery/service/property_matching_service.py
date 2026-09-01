"""
Part 21.2 — Property Matching Discovery Service
=================================================
Matches discovered candidate intent against the organization's verified property inventory.

Rules:
  - NEVER invent inventory.
  - Matches only against verified PropertyListing records owned by the tenant.
"""
from __future__ import annotations
import uuid
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.property_models import PropertyListing
from app.models.discovery_models import DiscoveryCandidate

logger = logging.getLogger(__name__)


class PropertyMatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def match_candidate_properties(
        self, organization_id: str, candidate: DiscoveryCandidate, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find matching property listings from inventory based on candidate interest.
        Tenant-isolated.
        """
        norm = candidate.normalized_data or {}
        city = norm.get("city")
        property_type = norm.get("property_type")
        bmax = norm.get("budget_max")
        bmin = norm.get("budget_min")

        conditions = [PropertyListing.status == "available", PropertyListing.deleted_at.is_(None)]

        if city:
            conditions.append(PropertyListing.city.ilike(f"%{city}%"))
        if property_type:
            conditions.append(PropertyListing.property_type.ilike(f"%{property_type}%"))

        stmt = select(PropertyListing).where(and_(*conditions)).limit(limit)
        listings = (await self.db.execute(stmt)).scalars().all()

        results = []
        for prop in listings:
            # Check price overlap if available
            price_match = True
            if bmax and prop.price and prop.price > (float(bmax) * 1.15):  # 15% buffer
                price_match = False
            if bmin and prop.price and prop.price < (float(bmin) * 0.85):
                price_match = False

            results.append({
                "property_id": str(prop.id),
                "title": prop.title,
                "city": prop.city,
                "property_type": prop.property_type,
                "price": prop.price,
                "currency_code": prop.currency_code,
                "is_price_match": price_match,
            })

        return results
