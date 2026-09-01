import math
import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_models import SavedSearch
from app.modules.search.dto.search_dto import SavedSearchCreateDTO, SavedSearchResponseDTO
from app.infrastructure.cache.query_cache import AsyncQueryCacheService, CacheTTL

logger = logging.getLogger(__name__)


class SavedSearchService:
    """
    Saved Search CRUD Service.
    Supports personal, workspace, and org-level shared searches.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, dto: SavedSearchCreateDTO, user_id: str, organization_id: str,
        workspace_id: Optional[str] = None
    ) -> SavedSearchResponseDTO:
        saved = SavedSearch(
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            name=dto.name,
            description=dto.description,
            entity_type=dto.entity_type,
            query=dto.query,
            filters=dto.filters,
            sorting=dto.sorting,
            columns=dto.columns,
            view_mode=dto.view_mode,
            is_shared=dto.is_shared,
            share_scope=dto.share_scope,
        )
        self.db.add(saved)
        await self.db.commit()
        AsyncQueryCacheService.invalidate_tag(f"saved_search:{user_id}")
        logger.info(f"[SAVED SEARCH] Created '{dto.name}' for user={user_id}")
        return SavedSearchResponseDTO.model_validate(saved)

    async def list_for_user(
        self, user_id: str, organization_id: str, entity_type: Optional[str] = None
    ) -> List[SavedSearchResponseDTO]:
        cache_key = f"saved_search_list:{user_id}:{entity_type}"
        cached = AsyncQueryCacheService.get(cache_key)
        if cached:
            return [SavedSearchResponseDTO(**item) for item in cached]

        conditions = [
            # Own searches OR shared searches in the org
            (SavedSearch.user_id == user_id) |
            (
                (SavedSearch.organization_id == organization_id) &
                (SavedSearch.is_shared == True)
            )
        ]
        if entity_type:
            conditions.append(SavedSearch.entity_type == entity_type)

        stmt = select(SavedSearch).where(and_(*conditions)).order_by(SavedSearch.updated_at.desc())
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        dtos = [SavedSearchResponseDTO.model_validate(i) for i in items]
        AsyncQueryCacheService.set(cache_key, [d.model_dump() for d in dtos], ttl_seconds=CacheTTL.SAVED_SEARCHES)
        return dtos

    async def update(
        self, search_id: str, user_id: str, dto: SavedSearchCreateDTO
    ) -> Optional[SavedSearchResponseDTO]:
        stmt = select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user_id)
        item = (await self.db.execute(stmt)).scalars().first()
        if not item:
            return None
        item.name = dto.name
        item.query = dto.query
        item.filters = dto.filters
        item.sorting = dto.sorting
        item.columns = dto.columns
        item.view_mode = dto.view_mode
        item.is_shared = dto.is_shared
        item.share_scope = dto.share_scope
        item.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        AsyncQueryCacheService.invalidate_tag(f"saved_search:{user_id}")
        return SavedSearchResponseDTO.model_validate(item)

    async def delete(self, search_id: str, user_id: str) -> bool:
        stmt = select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user_id)
        item = (await self.db.execute(stmt)).scalars().first()
        if not item:
            return False
        await self.db.delete(item)
        await self.db.commit()
        AsyncQueryCacheService.invalidate_tag(f"saved_search:{user_id}")
        return True

    async def record_run(self, search_id: str) -> None:
        """Increment run count and update last_run_at on execution."""
        stmt = (
            update(SavedSearch)
            .where(SavedSearch.id == search_id)
            .values(run_count=SavedSearch.run_count + 1, last_run_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
        await self.db.commit()
