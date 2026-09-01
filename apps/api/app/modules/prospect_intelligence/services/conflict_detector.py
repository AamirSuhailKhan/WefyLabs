"""
Part 21.2A — Preference Conflict & Supersession Engine
======================================================
Detects shifts in prospect preferences across conversation turns (e.g. 2BHK -> 4BHK, 1.5M -> 2.0M AED)
and logs supersession history without destructive loss of earlier observations.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class ConflictDetector:
    """
    Compares previous prospect intelligence profile against latest extraction.
    """

    @classmethod
    def detect_conflicts(
        cls,
        existing_profile: Optional[Any],
        new_extraction: Any,
    ) -> List[Dict[str, Any]]:
        """
        Returns list of conflict/supersession events.
        """
        conflicts: List[Dict[str, Any]] = []
        if not existing_profile:
            return conflicts

        # Retain existing historical conflicts
        if hasattr(existing_profile, "conflicts") and existing_profile.conflicts:
            conflicts.extend(existing_profile.conflicts)

        # 1. Check Property Type / Bedrooms conflict
        prev_req = getattr(existing_profile, "property_requirements", {}) or {}
        prev_bedrooms = prev_req.get("bedrooms")
        new_bedrooms = getattr(new_extraction, "bedrooms", None)
        if prev_bedrooms is not None and new_bedrooms is not None and prev_bedrooms != new_bedrooms:
            conflicts.append({
                "field": "bedrooms",
                "previous_value": prev_bedrooms,
                "new_value": new_bedrooms,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "supersession_status": "SUPERSEDED_BY_RECENT_CONVERSATION",
                "rationale": f"Prospect updated bedroom requirement from {prev_bedrooms} to {new_bedrooms}."
            })

        # 2. Check Location conflict
        prev_loc = prev_req.get("location")
        new_loc = getattr(new_extraction, "location", None)
        if prev_loc and new_loc and prev_loc.lower() != new_loc.lower():
            conflicts.append({
                "field": "location",
                "previous_value": prev_loc,
                "new_value": new_loc,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "supersession_status": "SUPERSEDED_BY_RECENT_CONVERSATION",
                "rationale": f"Prospect updated location focus from {prev_loc} to {new_loc}."
            })

        # 3. Check Budget conflict
        prev_budget = getattr(existing_profile, "budget", {}) or {}
        prev_b_max = prev_budget.get("budget_max")
        new_b_max = getattr(new_extraction, "budget_max", None)
        if prev_b_max and new_b_max and abs(float(prev_b_max) - float(new_b_max)) > 1000:
            conflicts.append({
                "field": "budget_max",
                "previous_value": prev_b_max,
                "new_value": new_b_max,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "supersession_status": "SUPERSEDED_BY_RECENT_CONVERSATION",
                "rationale": f"Prospect updated budget ceiling from {prev_b_max} to {new_b_max}."
            })

        # 4. Check Financing conflict
        prev_fin = getattr(existing_profile, "financing", "UNKNOWN")
        new_fin = getattr(new_extraction, "financing", "UNKNOWN")
        if prev_fin != "UNKNOWN" and new_fin != "UNKNOWN" and prev_fin != new_fin:
            conflicts.append({
                "field": "financing",
                "previous_value": prev_fin,
                "new_value": new_fin,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "supersession_status": "SUPERSEDED_BY_RECENT_CONVERSATION",
                "rationale": f"Prospect updated financing preference from {prev_fin} to {new_fin}."
            })

        return conflicts
