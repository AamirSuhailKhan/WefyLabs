"""
Part 21.2A — Tenant Property Inventory Matcher
================================================
Matches extracted prospect requirements against verified PropertyListing inventory
owned strictly and exclusively by the current tenant (organization_id / broker_id).
Guarantees:
- Zero cross-tenant inventory leakage.
- Zero fabricated properties or fake prices.
- Transparent matching rationale and requirement compatibility breakdown.
"""
import uuid
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.property_models import PropertyListing
from app.modules.prospect_intelligence.dto.prospect_intelligence_dto import (
    StrictLLMProspectExtractionDTO, MatchedPropertyDTO
)

logger = logging.getLogger(__name__)


class TenantPropertyMatcher:
    """
    Tenant-isolated real estate inventory matcher.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def match_tenant_properties(
        self,
        organization_id: str,
        extraction: StrictLLMProspectExtractionDTO,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Queries only properties matching organization_id and scores compatibility.
        """
        # Base query strictly enforcing tenant isolation via broker_id
        broker_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) and len(organization_id) == 36 else organization_id
        stmt = select(PropertyListing).where(
            and_(
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None)
            )
        )

        result = await self.db.execute(stmt)
        listings = result.scalars().all()

        if not listings:
            return []

        matched_results: List[Dict[str, Any]] = []

        for prop in listings:
            score, matched_reqs, unmatched_reqs, reason = self._score_property(prop, extraction)
            if score >= 0.40:
                matched_results.append({
                    "property_id": str(prop.id),
                    "title": prop.title or f"{prop.property_type.title()} in {prop.city}",
                    "property_type": prop.property_type,
                    "city": prop.city,
                    "price": float(prop.price) if prop.price else None,
                    "currency_code": getattr(prop, "currency_code", "AED") or "AED",
                    "match_score": round(score, 2),
                    "matched_requirements": matched_reqs,
                    "unmatched_requirements": unmatched_reqs,
                    "confidence": 1.0,
                    "reason": reason,
                })

        # Sort by match_score descending
        matched_results.sort(key=lambda m: m["match_score"], reverse=True)
        return matched_results[:limit]

    def _score_property(
        self, prop: PropertyListing, extraction: StrictLLMProspectExtractionDTO
    ) -> tuple[float, List[str], List[str], str]:
        """Calculates property match score against prospect requirements."""
        matched_reqs: List[str] = []
        unmatched_reqs: List[str] = []
        score = 0.50  # Base availability score

        # 1. Location match
        prop_city = (prop.city or "").lower()
        prop_loc = (prop.location or "").lower()
        req_loc = (extraction.location or "").lower()
        req_areas = [a.lower() for a in extraction.preferred_areas]

        if req_loc and (req_loc in prop_city or req_loc in prop_loc):
            matched_reqs.append(f"Location match: {prop.city}")
            score += 0.20
        elif any(area in prop_loc or area in prop_city for area in req_areas):
            matched_reqs.append(f"Preferred area match: {prop.location or prop.city}")
            score += 0.20
        elif req_loc:
            unmatched_reqs.append(f"Different location ({prop.city} vs {extraction.location})")

        # 2. Property type / Bedrooms match
        if extraction.property_type and prop.property_type:
            if extraction.property_type.lower() in prop.property_type.lower():
                matched_reqs.append(f"Property type match: {prop.property_type}")
                score += 0.15
            else:
                unmatched_reqs.append(f"Type mismatch ({prop.property_type} vs {extraction.property_type})")

        if extraction.bedrooms is not None and getattr(prop, "bedrooms", None) is not None:
            if prop.bedrooms == extraction.bedrooms:
                matched_reqs.append(f"Bedroom count exact match: {prop.bedrooms} BHK")
                score += 0.15
            elif abs(prop.bedrooms - extraction.bedrooms) == 1:
                matched_reqs.append(f"Bedroom count close match: {prop.bedrooms} BHK")
                score += 0.05
            else:
                unmatched_reqs.append(f"Bedroom mismatch ({prop.bedrooms} vs {extraction.bedrooms})")

        # 3. Budget match
        if prop.price and extraction.budget_max:
            if prop.price <= extraction.budget_max * 1.1:
                matched_reqs.append(f"Within budget: {prop.price:,.0f} {getattr(prop, 'currency_code', '')}")
                score += 0.15
            else:
                unmatched_reqs.append(f"Exceeds budget ceiling ({prop.price:,.0f} vs {extraction.budget_max:,.0f})")

        final_score = min(1.0, max(0.0, score))
        summary_reason = f"Matched {len(matched_reqs)} criteria: {', '.join(matched_reqs[:2])}" if matched_reqs else "General inventory match"

        return final_score, matched_reqs, unmatched_reqs, summary_reason
