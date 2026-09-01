"""
Indexing Service
================
Orchestrates incremental and full reindex operations.
Event-driven: triggered via DomainEvent → Celery task → IndexingService.
Tracks indexing state in SearchIndexMetadata table.
"""
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_models import SearchIndexMetadata
from app.modules.search.providers.search_providers import PostgreSQLSearchProvider
from app.modules.indexing.adapters.document_adapters import get_adapter

logger = logging.getLogger(__name__)


class IndexingService:
    """
    Entity indexing orchestration service.
    Writes indexing metadata, coordinates with ISearchProvider.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.provider = PostgreSQLSearchProvider(db)

    async def index_entity(
        self,
        entity_type: str,
        entity_id: str,
        organization_id: str,
        entity_data: any,
        force: bool = False,
    ) -> bool:
        """
        Index a single entity.
        Skips if document hash matches stored hash (no change since last index).
        """
        adapter = get_adapter(entity_type)
        if not adapter:
            logger.warning(f"[INDEXING] No adapter for entity_type '{entity_type}'")
            return False

        document = adapter.to_document(entity_data, organization_id)
        new_hash = document.get("document_hash", "")

        # Check existing metadata
        existing = await self._get_metadata(entity_type, entity_id)
        if existing and not force and existing.document_hash == new_hash:
            logger.debug(f"[INDEXING] Skip '{entity_type}/{entity_id}' — hash unchanged")
            return True

        try:
            success = await self.provider.index_document(document)
            await self._upsert_metadata(
                entity_type=entity_type,
                entity_id=entity_id,
                organization_id=organization_id,
                document_hash=new_hash,
                status="indexed" if success else "failed",
            )
            logger.info(f"[INDEXING] Indexed '{entity_type}/{entity_id}' success={success}")
            return success
        except Exception as exc:
            logger.error(f"[INDEXING] Failed to index '{entity_type}/{entity_id}': {exc}")
            await self._upsert_metadata(
                entity_type=entity_type,
                entity_id=entity_id,
                organization_id=organization_id,
                document_hash=new_hash,
                status="failed",
                error_message=str(exc),
            )
            return False

    async def deindex_entity(self, entity_type: str, entity_id: str) -> bool:
        """Remove an entity from the search index."""
        try:
            success = await self.provider.deindex_document(entity_type, entity_id)
            await self._upsert_metadata(
                entity_type=entity_type,
                entity_id=entity_id,
                organization_id="",
                document_hash="",
                status="deindexed",
            )
            return success
        except Exception as exc:
            logger.error(f"[INDEXING] Failed to deindex '{entity_type}/{entity_id}': {exc}")
            return False

    async def reindex_all(self, entity_type: Optional[str] = None, organization_id: Optional[str] = None) -> dict:
        """Mark all matching index metadata as stale to trigger re-indexing."""
        conditions = [SearchIndexMetadata.index_status != "deindexed"]
        if entity_type:
            conditions.append(SearchIndexMetadata.entity_type == entity_type)
        if organization_id:
            conditions.append(SearchIndexMetadata.organization_id == organization_id)

        from sqlalchemy import and_
        stmt = (
            update(SearchIndexMetadata)
            .where(and_(*conditions))
            .values(index_status="stale", updated_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        count = result.rowcount
        logger.info(f"[REINDEX] Marked {count} documents as stale for reindex. type={entity_type}, org={organization_id}")
        return {"marked_stale": count, "entity_type": entity_type}

    async def get_index_health(self) -> dict:
        """Return indexing statistics per entity type."""
        from sqlalchemy import func
        stmt = select(
            SearchIndexMetadata.entity_type,
            SearchIndexMetadata.index_status,
            func.count().label("count")
        ).group_by(SearchIndexMetadata.entity_type, SearchIndexMetadata.index_status)

        result = await self.db.execute(stmt)
        rows = result.fetchall()

        stats: dict = {}
        for entity_type, status, count in rows:
            if entity_type not in stats:
                stats[entity_type] = {}
            stats[entity_type][status] = count

        provider_health = await self.provider.health()
        return {"index_stats": stats, "provider": provider_health}

    async def _get_metadata(self, entity_type: str, entity_id: str) -> Optional[SearchIndexMetadata]:
        stmt = select(SearchIndexMetadata).where(
            SearchIndexMetadata.entity_type == entity_type,
            SearchIndexMetadata.entity_id == entity_id,
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def _upsert_metadata(
        self, entity_type: str, entity_id: str, organization_id: str,
        document_hash: str, status: str, error_message: Optional[str] = None
    ) -> None:
        existing = await self._get_metadata(entity_type, entity_id)
        now = datetime.now(timezone.utc)

        if existing:
            existing.index_status = status
            existing.document_hash = document_hash
            existing.indexed_at = now if status == "indexed" else existing.indexed_at
            existing.error_message = error_message
            existing.updated_at = now
            if status == "failed":
                existing.retry_count = (existing.retry_count or 0) + 1
        else:
            meta = SearchIndexMetadata(
                organization_id=organization_id,
                entity_type=entity_type,
                entity_id=entity_id,
                index_status=status,
                document_hash=document_hash,
                indexed_at=now if status == "indexed" else None,
                error_message=error_message,
            )
            self.db.add(meta)
        await self.db.flush()
