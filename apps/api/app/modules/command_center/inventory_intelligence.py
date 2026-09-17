"""
Part 30 — Real-Estate Inventory Intelligence & Supply/Demand Gap Engine
=======================================================================
Deterministic supply & demand analysis aggregating internal CRM data:
- Correlates verified Lead demand preferences against available Property listings
- Produces internal Demand Heatmap (Top Localities, BHK, Budget Bands, Types)
- Identifies acute inventory gaps (high lead demand vs low inventory supply)
- Strict Principle: Never presents internal CRM statistics as market-wide data.
"""
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional
import re

from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.modules.command_center.dto import (
    DemandHeatmapDTO,
    InventoryGapItemDTO,
    InventoryOpportunityDTO
)
from app.modules.property_recommendation.requirement_normalizer import (
    normalize_property_type,
    extract_bedrooms_from_text,
    parse_indian_budget
)


class InventoryIntelligenceEngine:
    """
    Computes grounded supply-demand dynamics and actionable inventory gaps
    using exclusively verified organization data.
    """

    @classmethod
    def compute_demand_heatmap(
        cls,
        leads: List[Lead],
        properties: List[PropertyListing]
    ) -> DemandHeatmapDTO:
        """
        Aggregates active buyer preferences to construct the internal CRM demand heatmap.
        """
        location_counts = Counter()
        bhk_counts = Counter()
        budget_band_counts = Counter({
            "Under ₹50L": 0,
            "₹50L – ₹1 Cr": 0,
            "₹1 Cr – ₹2 Cr": 0,
            "Above ₹2 Cr": 0
        })
        type_counts = Counter()

        for lead in leads:
            # 1. Locations
            locs = lead.preferred_locations or []
            for loc in locs:
                if loc and len(loc.strip()) > 1:
                    location_counts[loc.strip().title()] += 1

            # 2. BHK
            bhk = None
            if lead.property_type:
                bhk = extract_bedrooms_from_text(lead.property_type)
            if bhk:
                bhk_counts[f"{bhk} BHK"] += 1

            # 3. Budget Bands
            b_max = float(lead.budget_max or 0)
            if b_max > 0:
                if b_max < 5_000_000:
                    budget_band_counts["Under ₹50L"] += 1
                elif b_max <= 10_000_000:
                    budget_band_counts["₹50L – ₹1 Cr"] += 1
                elif b_max <= 20_000_000:
                    budget_band_counts["₹1 Cr – ₹2 Cr"] += 1
                else:
                    budget_band_counts["Above ₹2 Cr"] += 1

            # 4. Property Types
            if lead.property_type:
                norm_pt = normalize_property_type(lead.property_type)
                if norm_pt:
                    type_counts[norm_pt.title()] += 1

        # Format Top items
        top_locs = [
            {"location": loc, "active_leads": count, "count": count}
            for loc, count in location_counts.most_common(5)
        ]
        top_bhk_list = [
            {"bhk": bhk, "active_leads": count, "count": count}
            for bhk, count in bhk_counts.most_common(5)
        ]
        top_budgets = [
            {"band": band, "active_leads": count, "count": count}
            for band, count in budget_band_counts.items() if count > 0
        ]
        top_types = [
            {"property_type": pt, "active_leads": count, "count": count}
            for pt, count in type_counts.most_common(5)
        ]

        return DemandHeatmapDTO(
            top_locations=top_locs,
            top_bhk=top_bhk_list,
            top_budget_ranges=top_budgets,
            top_property_types=top_types,
            disclaimer="Demand aggregated exclusively from your verified CRM leads (internal intelligence only)"
        )

    @classmethod
    def identify_inventory_gaps(
        cls,
        leads: List[Lead],
        properties: List[PropertyListing]
    ) -> List[InventoryGapItemDTO]:
        """
        Compares lead requirements against available inventory by locality, BHK, and type.
        Identifies segments where demand significantly outstrips available supply.
        """
        # Map available properties: key -> count
        # key format: (locality_lower, bhk)
        supply_map = defaultdict(int)
        for p in properties:
            if (p.status or "").lower() == "available":
                loc = (p.locality or p.city or "").lower().strip()
                bhk = p.bedrooms or 0
                supply_map[(loc, bhk)] += 1

        # Map lead demand: key -> list of lead IDs
        demand_map = defaultdict(list)
        for lead in leads:
            bhk = extract_bedrooms_from_text(lead.property_type) or 0
            locs = lead.preferred_locations or []
            if not locs:
                # Add under general city/unspecified
                demand_map[("unspecified", bhk)].append(lead.id)
            for loc in locs:
                cleaned_loc = loc.lower().strip()
                if cleaned_loc:
                    demand_map[(cleaned_loc, bhk)].append(lead.id)

        gaps: List[InventoryGapItemDTO] = []

        for (loc, bhk), lead_ids in demand_map.items():
            if loc == "unspecified" or len(lead_ids) < 2:
                continue

            demand_count = len(lead_ids)
            if bhk > 0:
                supply_count = supply_map.get((loc, bhk), 0)
            else:
                supply_count = sum(cnt for (l, _), cnt in supply_map.items() if l == loc)
            deficit = demand_count - supply_count

            if deficit > 0:
                severity = "HIGH" if (deficit >= 3 or supply_count == 0) else "MEDIUM"
                bhk_label = f"{bhk} BHK" if bhk > 0 else "Residential"
                loc_label = loc.title()
                label = f"{bhk_label} in {loc_label}"

                rec = (
                    f"Acquire or source {bhk_label} inventory in {loc_label} "
                    f"to serve {deficit} unmet active buyer leads in your CRM."
                )

                gap_item = InventoryGapItemDTO(
                    segment_label=label,
                    property_type="Apartment",
                    locality=loc_label,
                    bhk=bhk if bhk > 0 else None,
                    demand_lead_count=demand_count,
                    supply_property_count=supply_count,
                    gap_deficit=deficit,
                    gap_severity=severity,
                    actionable_recommendation=rec
                )
                gaps.append(gap_item)

        # Sort gaps by largest deficit first
        gaps.sort(key=lambda g: (-g.gap_deficit, g.segment_label))
        return gaps[:10]

    @classmethod
    def identify_new_inventory_opportunities(
        cls,
        properties: List[PropertyListing],
        leads: List[Lead],
        days_threshold: int = 14
    ) -> List[InventoryOpportunityDTO]:
        """
        Highlights freshly added properties and identifies immediate potential matching buyers.
        """
        opportunities: List[InventoryOpportunityDTO] = []
        available_props = [p for p in properties if (p.status or "").lower() == "available"]

        # Sort by creation date descending
        recent_props = sorted(
            available_props,
            key=lambda x: x.created_at or x.updated_at or datetime.min,
            reverse=True
        )[:8]

        for p in recent_props:
            matching_leads_count = 0
            strong_matches_count = 0

            p_price = float(p.price or 0)
            p_loc = (p.locality or "").lower()
            p_beds = p.bedrooms or 0

            for l in leads:
                l_budget_max = float(l.budget_max or 0)
                l_locs = [loc.lower() for loc in (l.preferred_locations or [])]
                l_beds = extract_bedrooms_from_text(l.property_type)

                # Basic compatibility checks
                budget_compat = (l_budget_max == 0 or p_price <= (l_budget_max * 1.15))
                loc_compat = any(loc in p_loc or p_loc in loc for loc in l_locs) if l_locs else True
                bhk_compat = (l_beds is None or l_beds == p_beds)

                if budget_compat and loc_compat:
                    matching_leads_count += 1
                    if bhk_compat and p_price <= l_budget_max:
                        strong_matches_count += 1

            opp = InventoryOpportunityDTO(
                property_id=str(p.id),
                property_code=p.property_code,
                title=p.title,
                price=p.price,
                locality=p.locality,
                city=p.city,
                bedrooms=p.bedrooms,
                property_type=p.property_type or "apartment",
                status=p.status or "available",
                created_at=p.created_at.isoformat() if p.created_at else "",
                potential_leads_count=matching_leads_count,
                strong_matches_count=strong_matches_count
            )
            opportunities.append(opp)

        return opportunities
