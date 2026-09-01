import logging
from typing import Optional, List
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_models import SearchHistory

logger = logging.getLogger(__name__)


class SearchHistoryService:
    """Manages user search history: recent queries, popular queries, deletion."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_recent(self, user_id: str, organization_id: str, limit: int = 10) -> List[dict]:
        stmt = (
            select(SearchHistory)
            .where(SearchHistory.user_id == user_id, SearchHistory.organization_id == organization_id)
            .order_by(SearchHistory.created_at.desc())
            .limit(limit)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return [
            {
                "id": i.id,
                "query": i.query,
                "entity_types": i.entity_types,
                "result_count": i.result_count,
                "latency_ms": i.latency_ms,
                "created_at": i.created_at,
            }
            for i in items
        ]

    async def get_popular(self, organization_id: str, limit: int = 10) -> List[dict]:
        """Return top queries by frequency within the org."""
        stmt = (
            select(SearchHistory.query, func.count().label("count"))
            .where(SearchHistory.organization_id == organization_id, SearchHistory.was_successful == True)
            .group_by(SearchHistory.query)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).fetchall()
        return [{"query": r[0], "count": r[1]} for r in rows]

    async def delete_entry(self, history_id: str, user_id: str) -> bool:
        stmt = (
            delete(SearchHistory)
            .where(SearchHistory.id == history_id, SearchHistory.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def clear_history(self, user_id: str, organization_id: str) -> int:
        stmt = delete(SearchHistory).where(
            SearchHistory.user_id == user_id,
            SearchHistory.organization_id == organization_id,
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
