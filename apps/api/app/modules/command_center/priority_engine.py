"""
Part 30 — AI Real-Estate Agent Daily Command Center Priority Engine
===================================================================
Deterministic, non-hallucinatory priority scoring engine.
Evaluates operational facts:
- First-contact SLA breaches & impending expiries
- Overdue follow-ups and due duration
- Proximity of site visits and client meetings (within 2-4 hours)
- Hot lead stagnation and high-intent absence of follow-ups
- High-score (90+) property matches for active prospects
- Unrecorded site visit outcomes
- Stale lead re-engagement triggers
- New inventory opportunities
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set
import uuid

from app.modules.command_center.dto import PriorityItemDTO


class CommandCenterPriorityEngine:
    """
    Deterministic operational prioritization engine.
    Calculates normalized scores (0-100) and assigns actionable directives.
    """

    @classmethod
    def evaluate_item_priority(
        cls,
        category: str,
        due_at: Optional[datetime] = None,
        overdue_minutes: Optional[int] = None,
        is_hot_lead: bool = False,
        match_score: Optional[float] = None,
        days_inactive: int = 0,
        meeting_type: Optional[str] = None,
        now: Optional[datetime] = None
    ) -> tuple[str, float]:
        """
        Determines (priority_label, priority_score) based strictly on verified operational criteria.
        Returns: ('CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW', score: float).
        """
        ref_now = now or datetime.now(timezone.utc)

        # 1. First Contact SLA
        if category == "first_contact":
            if overdue_minutes and overdue_minutes > 0:
                # Critical breach
                score = min(100.0, 95.0 + min(overdue_minutes / 10.0, 5.0))
                return "CRITICAL", score
            else:
                # Impending SLA
                mins_left = abs(overdue_minutes) if overdue_minutes else 15
                if mins_left <= 10:
                    return "HIGH", 92.0
                return "HIGH", 85.0

        # 2. Meetings & Site Visits Proximity
        if category in ("site_visit", "meeting"):
            if due_at:
                diff_mins = (due_at - ref_now).total_seconds() / 60.0
                if 0 <= diff_mins <= 120:
                    # Starting within 2 hours
                    return "HIGH", 91.0
                elif 0 <= diff_mins <= 240:
                    # Starting within 4 hours
                    return "HIGH", 82.0
                elif diff_mins < 0:
                    # Past meeting needing outcome
                    return "MEDIUM", 72.0
            return "MEDIUM", 65.0

        # 3. Overdue Follow-ups
        if category == "overdue_followup":
            days_overdue = (overdue_minutes or 0) / 1440.0
            if days_overdue >= 5:
                return "CRITICAL", 94.0
            elif days_overdue >= 2:
                return "HIGH", 88.0
            elif days_overdue >= 1 or is_hot_lead:
                return "HIGH", 84.0
            return "MEDIUM", 74.0

        # 4. Hot Leads Needing Touchpoint
        if category == "hot_lead":
            if match_score and match_score >= 90.0:
                return "HIGH", 87.0
            if days_inactive >= 3:
                return "HIGH", 83.0
            return "MEDIUM", 70.0

        # 5. Strong Property Matches
        if category == "strong_match":
            if match_score and match_score >= 95.0:
                return "HIGH", 86.0
            elif match_score and match_score >= 88.0:
                return "HIGH", 80.0
            return "MEDIUM", 68.0

        # 6. Stale Leads
        if category == "stale_lead":
            if is_hot_lead:
                return "HIGH", 78.0
            if days_inactive >= 30:
                return "MEDIUM", 64.0
            return "MEDIUM", 58.0

        # 7. New Inventory Opportunity
        if category == "inventory_opportunity":
            return "MEDIUM", 55.0

        # 8. Follow-up Due Today
        if category == "followup_due":
            return "MEDIUM", 60.0

        # Default general task
        return "LOW", 40.0

    @classmethod
    def rank_and_filter_priorities(
        cls,
        items: List[PriorityItemDTO],
        dismissed_keys: Optional[Set[str]] = None,
        limit: int = 50
    ) -> List[PriorityItemDTO]:
        """
        Filters out dismissed / snoozed items and orders deterministically by priority score descending.
        """
        active_dismissals = dismissed_keys or set()
        eligible = [it for it in items if it.item_key not in active_dismissals]

        # Deterministic sort: highest priority score first, ties broken by due_at or id
        eligible.sort(
            key=lambda x: (
                -x.priority_score,
                x.due_at or "9999-12-31",
                x.id
            )
        )
        return eligible[:limit]
