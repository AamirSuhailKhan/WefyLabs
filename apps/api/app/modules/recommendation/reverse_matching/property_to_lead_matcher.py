"""
Reverse Property-to-Lead Matcher Engine
=======================================
Calculates reverse suitability: Given a specific property listing, identifies the top qualified
buyer leads in the CRM who are most likely to purchase or book a viewing for this unit.
"""

import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile
from app.modules.recommendation.buyer_profile.profile_builder import BuyerProfileBuilder
from app.modules.recommendation.scoring.compatibility_scorer import CompatibilityScorer
from app.modules.recommendation.constraint_engine.hard_constraints import HardConstraintEngine

logger = logging.getLogger(__name__)

class ReversePropertyToLeadMatcher:
    """
    Inverse matching engine finding target buyer leads for property inventory.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.profile_builder = BuyerProfileBuilder(db)
        self.scorer = CompatibilityScorer()
        self.hard_constraints = HardConstraintEngine()

    async def match_leads_for_property(
        self,
        property_id: str,
        organization_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieves active lead profiles in the tenant org and ranks them by suitability for this property.
        """
        # Fetch target property
        import uuid as _uuid
        try:
            prop_pk = _uuid.UUID(str(property_id))
        except Exception:
            prop_pk = property_id

        stmt_prop = select(PropertyListing).where(PropertyListing.id == prop_pk)
        res_prop = await self.db.execute(stmt_prop)
        property_listing = res_prop.scalar_one_or_none()

        if not property_listing:
            raise ValueError(f"Property Listing ID '{property_id}' not found.")

        # Fetch active leads in organization
        stmt_leads = (
            select(Lead)
            .where(Lead.status.in_(["pending", "active", "qualified"]))
            .order_by(Lead.updated_at.desc())
            .limit(100)
        )
        res_leads = await self.db.execute(stmt_leads)
        active_leads = res_leads.scalars().all()

        results: List[Dict[str, Any]] = []

        for lead in active_leads:
            try:
                profile = await self.profile_builder.get_or_create_profile(
                    lead_id=str(lead.id),
                    organization_id=organization_id,
                    broker_id=str(lead.broker_id)
                )

                # Evaluate hard constraints against lead profile
                valid_props, _ = self.hard_constraints.filter_candidates([property_listing], profile)
                if not valid_props:
                    continue

                # Calculate match score
                score, breakdown = self.scorer.calculate_score(property_listing, profile)

                results.append({
                    "lead_id": str(lead.id),
                    "lead_name": lead.name or "New Buyer Lead",
                    "lead_phone": lead.phone,
                    "lead_score": lead.score,
                    "pipeline_stage": lead.pipeline_stage,
                    "match_score": score,
                    "budget_max": profile.max_budget,
                    "currency": profile.currency,
                    "score_breakdown": breakdown.model_dump()
                })
            except Exception as exc:
                logger.warning(f"[REVERSE_MATCHER] Error evaluating lead {lead.id}: {exc}")
                continue

        # Sort leads by match score descending
        sorted_results = sorted(results, key=lambda x: x["match_score"], reverse=True)[:limit]

        return {
            "property_id": property_id,
            "property_title": property_listing.title,
            "property_price": property_listing.price,
            "property_currency": property_listing.currency,
            "total_qualified_leads_evaluated": len(active_leads),
            "matching_leads_count": len(sorted_results),
            "matching_leads": sorted_results
        }
