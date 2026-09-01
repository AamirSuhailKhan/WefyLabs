"""
Enterprise Search Service
=========================
The single public API consumed by all BeetleLabs modules:
  - CRM Controllers
  - AI Lead Discovery
  - RAG Pipeline
  - Analytics Engine
  - Recommendation Engine

Never call a search provider directly. Always use SearchService.
Never import SQLAlchemy models in AI/Analytics modules — call this service.
"""
import time
import math
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.search.interfaces.provider_interface import ISearchProvider
from app.modules.search.providers.search_providers import PostgreSQLSearchProvider
from app.modules.search.dto.search_dto import (
    GlobalSearchQueryDTO, EntitySearchDTO, AutocompleteQueryDTO, FacetQueryDTO,
    SearchHitDTO, SearchGroupDTO, GlobalSearchResponseDTO,
    AutocompleteResponseDTO, FacetResponseDTO,
)
from app.modules.search.ranking.ranking_engine import RankingEngine
from app.infrastructure.cache.query_cache import AsyncQueryCacheService, CacheTTL
from app.models.search_models import SearchHistory

logger = logging.getLogger(__name__)

# Entity type display labels for grouped results
ENTITY_LABELS: Dict[str, str] = {
    "lead": "Leads",
    "property": "Properties",
    "contact": "Contacts",
    "task": "Tasks",
    "meeting": "Meetings",
    "organization": "Organizations",
    "user": "Users",
    "note": "Notes",
}

# Canonical entity type display order in global search
ENTITY_ORDER = ["lead", "contact", "property", "task", "meeting", "organization", "user", "note"]


class SearchService:
    """
    Enterprise Search Orchestration Service.
    Orchestrates: provider → ranking → cache → history → audit.
    """

    def __init__(self, db: AsyncSession, provider: Optional[ISearchProvider] = None):
        self.db = db
        # Default to PostgreSQL provider; swap at DI layer for Meilisearch/OpenSearch
        self.provider: ISearchProvider = provider or PostgreSQLSearchProvider(db)
        self.ranking = RankingEngine()

    # ── Global Search ─────────────────────────────────────────────────────────

    async def global_search(
        self, dto: GlobalSearchQueryDTO, user_id: str
    ) -> GlobalSearchResponseDTO:
        start = time.time()
        cache_key = f"gsearch:{dto.organization_id}:{dto.q}:{dto.entity_types}:{dto.page}"
        cached = AsyncQueryCacheService.get(cache_key)
        if cached:
            logger.debug(f"[SEARCH CACHE HIT] '{dto.q}'")
            return GlobalSearchResponseDTO(**cached)

        # Build filter map
        filters: Dict[str, Any] = {}
        if dto.status: filters["status"] = dto.status
        if dto.score: filters["score"] = dto.score
        if dto.pipeline_stage: filters["pipeline_stage"] = dto.pipeline_stage
        if dto.city: filters["city"] = dto.city
        if dto.property_type: filters["property_type"] = dto.property_type

        provider_result = await self.provider.search(
            query=dto.q,
            organization_id=dto.organization_id or "",
            entity_types=dto.entity_types,
            filters=filters,
            page=dto.page,
            limit=dto.limit,
            sort_by=dto.sort_by,
            sort_order=dto.sort_order,
        )

        # Apply ranking engine
        ranked_hits = self.ranking.rank(provider_result.hits, dto.q)

        # Group results by entity type in canonical order
        groups_map: Dict[str, List[SearchHitDTO]] = {}
        for hit in ranked_hits:
            if hit.entity_type not in groups_map:
                groups_map[hit.entity_type] = []
            groups_map[hit.entity_type].append(SearchHitDTO(**hit.to_dict()))

        groups = [
            SearchGroupDTO(
                entity_type=et,
                label=ENTITY_LABELS.get(et, et.title()),
                hits=groups_map[et],
                total=len(groups_map[et]),
            )
            for et in ENTITY_ORDER
            if et in groups_map
        ]

        took_ms = int((time.time() - start) * 1000)
        response = GlobalSearchResponseDTO(
            query=dto.q,
            groups=groups,
            total=provider_result.total,
            page=dto.page,
            limit=dto.limit,
            took_ms=took_ms,
            provider=self.provider.provider_name,
        )

        # Cache result
        AsyncQueryCacheService.set(cache_key, response.model_dump(), ttl_seconds=CacheTTL.SEARCH_RESULTS)

        # Record search history (non-blocking)
        await self._record_history(
            user_id=user_id,
            organization_id=dto.organization_id or "",
            query=dto.q,
            entity_types=dto.entity_types or [],
            filters=filters,
            result_count=provider_result.total,
            latency_ms=took_ms,
        )

        logger.info(f"[SEARCH] '{dto.q}' → {provider_result.total} hits | {took_ms}ms | provider={self.provider.provider_name}")
        return response

    # ── Autocomplete ──────────────────────────────────────────────────────────

    async def autocomplete(self, dto: AutocompleteQueryDTO, organization_id: str) -> AutocompleteResponseDTO:
        start = time.time()
        cache_key = f"ac:{organization_id}:{dto.prefix}:{dto.entity_types}"
        cached = AsyncQueryCacheService.get(cache_key)
        if cached:
            return AutocompleteResponseDTO(**cached)

        suggestions = await self.provider.autocomplete(
            prefix=dto.prefix,
            organization_id=organization_id,
            entity_types=dto.entity_types,
            limit=dto.limit,
        )
        took_ms = int((time.time() - start) * 1000)
        response = AutocompleteResponseDTO(
            suggestions=suggestions, query=dto.prefix, took_ms=took_ms
        )
        AsyncQueryCacheService.set(cache_key, response.model_dump(), ttl_seconds=CacheTTL.AUTOCOMPLETE)
        return response

    # ── Facets ────────────────────────────────────────────────────────────────

    async def get_facets(self, dto: FacetQueryDTO, organization_id: str) -> FacetResponseDTO:
        start = time.time()
        cache_key = f"facets:{organization_id}:{dto.entity_type}:{dto.q}"
        cached = AsyncQueryCacheService.get(cache_key)
        if cached:
            return FacetResponseDTO(**cached)

        facet_data = await self.provider.facets(
            query=dto.q,
            organization_id=organization_id,
            entity_type=dto.entity_type,
            facet_fields=dto.fields,
            filters=dto.filters,
        )
        took_ms = int((time.time() - start) * 1000)
        response = FacetResponseDTO(entity_type=dto.entity_type, facets=facet_data, took_ms=took_ms)
        AsyncQueryCacheService.set(cache_key, response.model_dump(), ttl_seconds=CacheTTL.FACETS)
        return response

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self) -> Dict[str, Any]:
        provider_health = await self.provider.health()
        return {"search_service": "healthy", "provider": provider_health}

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _record_history(
        self, user_id: str, organization_id: str, query: str,
        entity_types: List[str], filters: Dict, result_count: int, latency_ms: int
    ) -> None:
        try:
            entry = SearchHistory(
                organization_id=organization_id,
                user_id=user_id,
                query=query,
                entity_types=entity_types,
                filters_applied=filters,
                result_count=result_count,
                latency_ms=latency_ms,
                was_successful=result_count >= 0,
                search_provider=self.provider.provider_name,
            )
            self.db.add(entry)
            await self.db.flush()
        except Exception as exc:
            logger.warning(f"[SEARCH HISTORY] Failed to record: {exc}")
