"""
Merge Simulator — Dry-run merge simulation without any DB writes.
Shows what WOULD happen if the merge were executed:
- Conflicting fields
- Fields that would be copied
- Affected lead count
- Estimated confidence impact
"""
from typing import Dict, Any, List, Optional
from .merge_executor import MERGEABLE_FIELDS


class MergeSimulator:
    """
    Simulates a merge without writing to the database.
    Returns a detailed simulation report for reviewer preview.
    """

    def simulate(
        self,
        source_data: Dict[str, Any],
        target_data: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Any]:
        """
        Simulate merge of source into target.

        Returns:
            {
                "would_conflict": [...],
                "would_merge": [...],
                "would_copy": [...],
                "merged_result_preview": {...},
                "affected_leads": int,
                "confidence": float,
                "can_auto_merge": bool,
                "simulation_warnings": [...],
            }
        """
        would_conflict = []
        would_merge = []
        would_copy = []
        merged_result = dict(target_data)
        warnings = []

        for field in MERGEABLE_FIELDS:
            source_val = source_data.get(field)
            target_val = target_data.get(field)

            if not target_val and source_val:
                merged_result[field] = source_val
                would_copy.append({
                    "field": field,
                    "from_source": source_val,
                    "action": "copy_to_target",
                })
            elif source_val and target_val and source_val != target_val:
                would_conflict.append({
                    "field": field,
                    "target_value": target_val,
                    "source_value": source_val,
                    "winner": "target",
                    "reason": "Target value preserved (existing data wins)",
                })
            elif source_val and target_val and source_val == target_val:
                would_merge.append(field)

        # Warnings
        if would_conflict:
            warnings.append(f"{len(would_conflict)} field conflict(s) will be recorded but NOT auto-resolved.")
        if confidence < 0.90:
            warnings.append(f"Confidence {confidence:.1%} is below 90% — consider manual review.")

        affected_leads = (target_data.get("lead_count") or 1) + (source_data.get("lead_count") or 1)

        return {
            "would_conflict": would_conflict,
            "would_merge": would_merge,
            "would_copy": would_copy,
            "merged_result_preview": merged_result,
            "affected_leads": affected_leads,
            "confidence": confidence,
            "can_auto_merge": confidence >= 0.95,
            "simulation_warnings": warnings,
            "conflict_count": len(would_conflict),
            "copy_count": len(would_copy),
        }
