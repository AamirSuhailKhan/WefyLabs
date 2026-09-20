"""
Part 3 — Matching Intelligence Facade
======================================
Canonical service boundary for Lead ↔ Property Matching, Shortlist Management,
Customer Interactions, and Qualification Orchestration.
Ready for direct consumption by Part 4 AI Sales Agent tools and Copilot.
"""
from app.modules.matching_intelligence.service import MatchingIntelligenceFacade

__all__ = ["MatchingIntelligenceFacade"]
