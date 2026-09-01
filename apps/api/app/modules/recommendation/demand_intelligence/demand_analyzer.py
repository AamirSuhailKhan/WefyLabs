"""
Property Demand & Unmet Demand Intelligence Engine
===================================================
Aggregates anonymized tenant-isolated buyer requirements to uncover market demand trends
and pinpoint unmet inventory gaps (e.g. high buyer demand vs low available inventory).
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile

logger = logging.getLogger(__name__)

class PropertyDemandAnalyzer:
    """
    Analyzes aggregated tenant buyer demand vs property inventory gaps.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_demand(self, organization_id: str) -> Dict[str, Any]:
        """
        Computes demand metrics by location, property type, and identifies unmet demand.
        """
        # Fetch active buyer profiles
        stmt_profiles = select(BuyerProfile).where(BuyerProfile.organization_id == organization_id)
        res_profiles = await self.db.execute(stmt_profiles)
        profiles = res_profiles.scalars().all()

        location_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        budget_ranges: Dict[str, int] = {"under_1m": 0, "1m_to_3m": 0, "above_3m": 0}

        for p in profiles:
            for loc in p.preferred_locations:
                location_counts[loc] = location_counts.get(loc, 0) + 1
            for pt in p.property_types:
                type_counts[pt] = type_counts.get(pt, 0) + 1

            if p.max_budget < 1000000:
                budget_ranges["under_1m"] += 1
            elif p.max_budget <= 3000000:
                budget_ranges["1m_to_3m"] += 1
            else:
                budget_ranges["above_3m"] += 1

        # Count actual available inventory
        stmt_inv = select(func.count(PropertyListing.id)).where(PropertyListing.status == "available")
        res_inv = await self.db.execute(stmt_inv)
        total_available_inventory = res_inv.scalar() or 0

        # Build top demand lists
        top_locations = [
            {"location": loc, "buyer_count": count}
            for loc, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        top_types = [
            {"property_type": pt, "buyer_count": count}
            for pt, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Calculate unmet demand gaps
        unmet_gaps = []
        for loc_info in top_locations:
            loc = loc_info["location"]
            demand_buyers = loc_info["buyer_count"]

            # Count inventory in this location
            stmt_loc_inv = select(func.count(PropertyListing.id)).where(
                and_(
                    PropertyListing.status == "available",
                    PropertyListing.locality.ilike(f"%{loc}%")
                )
            )
            res_loc_inv = await self.db.execute(stmt_loc_inv)
            avail_count = res_loc_inv.scalar() or 0

            if demand_buyers > avail_count:
                unmet_gaps.append({
                    "location": loc,
                    "qualified_buyer_demand": demand_buyers,
                    "available_units": avail_count,
                    "unmet_gap_ratio": round(demand_buyers / max(1, avail_count), 2),
                    "insight": f"{demand_buyers} qualified buyers are looking in '{loc}', but only {avail_count} matching units are available."
                })

        return {
            "organization_id": organization_id,
            "total_active_buyer_profiles": len(profiles),
            "total_available_inventory": total_available_inventory,
            "top_demanded_locations": top_locations,
            "top_demanded_property_types": top_types,
            "budget_demand_distribution": budget_ranges,
            "unmet_demand_gaps": unmet_gaps
        }
