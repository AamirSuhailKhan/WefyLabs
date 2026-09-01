"""
Follow-Up Content Strategy Engine
=================================
Determines communication goal, value proposition, and contextual facts before message generation.
Ensures no empty 'just checking in' messages are sent unless meaningful customer value exists.
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead
from app.models.property_models import PropertyListing

logger = logging.getLogger(__name__)

class ContentStrategyEngine:
    """
    Formulates the strategic objective and context payload for outbound follow-ups.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_strategy_context(
        self,
        lead: Lead,
        reason_type: str,
        target_property_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gathers verified CRM and property facts for message drafting.
        """
        lead_name = lead.name or "there"
        location = lead.preferred_locations[0] if lead.preferred_locations else "prime location"
        prop_type = lead.property_type or "property"
        budget_str = f"{lead.budget_max:,.0f}" if lead.budget_max else "your target budget"

        property_data: Optional[Dict[str, Any]] = None
        grounded_facts: List[Dict[str, Any]] = []

        if target_property_id:
            stmt = select(PropertyListing).where(PropertyListing.id == target_property_id)
            res = await self.db.execute(stmt)
            prop = res.scalar_one_or_none()
            if prop:
                property_data = {
                    "property_id": str(prop.id),
                    "title": prop.title,
                    "price": prop.price,
                    "currency": prop.currency,
                    "bedrooms": prop.bedrooms,
                    "locality": prop.locality,
                    "city": prop.city,
                    "status": prop.status
                }
                grounded_facts.append({
                    "fact_type": "PROPERTY_LISTING",
                    "title": prop.title,
                    "price": f"{prop.price:,.0f} {prop.currency}",
                    "bedrooms": prop.bedrooms,
                    "location": f"{prop.locality}, {prop.city}"
                })

        return {
            "lead_name": lead_name,
            "property_type": prop_type,
            "preferred_location": location,
            "budget": budget_str,
            "reason_type": reason_type,
            "property": property_data,
            "grounded_facts": grounded_facts
        }
