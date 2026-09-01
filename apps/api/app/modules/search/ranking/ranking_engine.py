"""
Search Ranking Engine
=====================
Configurable multi-signal ranking for search results.
Ranking order (highest priority first):
  1. Exact match on display_title
  2. Prefix match
  3. Provider similarity score (fuzzy)
  4. Entity type weight
  5. Lead score boost (hot > warm > cold)
  6. Recent activity boost
"""
import logging
from typing import List, Dict
from datetime import datetime, timezone
from app.modules.search.interfaces.provider_interface import SearchResult

logger = logging.getLogger(__name__)

# Entity base weights — configurable per organization via SearchRanking table
DEFAULT_ENTITY_WEIGHTS: Dict[str, float] = {
    "lead": 1.0,
    "contact": 0.9,
    "property": 0.8,
    "meeting": 0.6,
    "task": 0.5,
    "note": 0.4,
    "organization": 0.7,
    "user": 0.6,
}

# Lead score boosts
LEAD_SCORE_BOOSTS: Dict[str, float] = {
    "hot": 0.4,
    "warm": 0.2,
    "cold": 0.0,
    "pending": 0.0,
    "unqualified": -0.1,
}


class RankingEngine:
    """
    Multi-signal ranking engine for search results.
    Stateless — safe to instantiate per request.
    """

    def rank(self, hits: List[SearchResult], query: str) -> List[SearchResult]:
        """Apply all ranking signals and return sorted results."""
        q_lower = query.strip().lower()
        for hit in hits:
            hit.score = self._compute_score(hit, q_lower)

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def _compute_score(self, hit: SearchResult, query: str) -> float:
        score = hit.score  # Start with provider-computed similarity score

        title_lower = (hit.display_title or "").strip().lower()

        # Signal 1: Exact title match
        if title_lower == query:
            score += 2.0

        # Signal 2: Prefix match
        elif title_lower.startswith(query):
            score += 0.8

        # Signal 3: Contains query
        elif query in title_lower:
            score += 0.4

        # Signal 4: Entity type base weight
        entity_weight = DEFAULT_ENTITY_WEIGHTS.get(hit.entity_type, 0.5)
        score *= entity_weight

        # Signal 5: Lead score boost
        if hit.entity_type == "lead":
            lead_score = hit.data.get("score", "pending")
            score += LEAD_SCORE_BOOSTS.get(lead_score, 0.0)

        # Signal 6: Recency boost — prefer recently updated entities
        score += self._recency_boost(hit.data.get("updated_at"))

        return round(score, 4)

    def _recency_boost(self, updated_at_str: any) -> float:
        """Boost entities updated in the last 7 days."""
        if not updated_at_str:
            return 0.0
        try:
            if isinstance(updated_at_str, str):
                # Parse ISO format
                dt = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            elif isinstance(updated_at_str, datetime):
                dt = updated_at_str
            else:
                return 0.0

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            days_ago = (datetime.now(timezone.utc) - dt).days
            if days_ago <= 1:
                return 0.3
            elif days_ago <= 7:
                return 0.15
            elif days_ago <= 30:
                return 0.05
        except Exception:
            pass
        return 0.0
