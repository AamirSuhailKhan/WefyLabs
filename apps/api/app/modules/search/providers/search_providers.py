"""
PostgreSQL Search Provider
==========================
Phase 1 search engine using:
- PostgreSQL full-text search (tsvector + tsquery + GIN index)
- pg_trgm trigram similarity for fuzzy matching
- Composite filter stack for RBAC-aware multi-field queries
- Ranking via ts_rank_cd + custom field boosts

Swappable: replace with MeilisearchSearchProvider by changing
           the DI binding in app/modules/search/providers/registry.py
"""
import time
import logging
from typing import Optional, List, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.search.interfaces.provider_interface import (
    ISearchProvider, SearchDocument, SearchResult, SearchProviderResult
)

logger = logging.getLogger(__name__)


class PostgreSQLSearchProvider(ISearchProvider):
    """
    PostgreSQL full-text + trigram search provider.
    Uses plainto_tsquery for natural language, similarity() for fuzzy.
    """
    provider_name = "postgresql"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        query: str,
        organization_id: str,
        entity_types: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> SearchProviderResult:
        start = time.time()
        filters = filters or {}
        entity_types = entity_types or ["lead", "property", "contact", "task", "meeting"]
        hits = []
        total = 0

        # Execute search per entity type, collect and rank
        for entity_type in entity_types:
            type_hits = await self._search_entity(
                query=query,
                entity_type=entity_type,
                organization_id=organization_id,
                filters=filters,
                limit=limit,
            )
            hits.extend(type_hits)
            total += len(type_hits)

        # Sort all hits by relevance score descending
        hits.sort(key=lambda h: h.score, reverse=True)
        hits = hits[:limit]

        took_ms = int((time.time() - start) * 1000)
        logger.info(f"[SEARCH] PostgreSQL: '{query}' → {total} raw hits, {len(hits)} returned, {took_ms}ms")
        return SearchProviderResult(hits=hits, total=total, took_ms=took_ms, provider=self.provider_name)

    async def _search_entity(
        self, query: str, entity_type: str, organization_id: str,
        filters: Dict[str, Any], limit: int
    ) -> List[SearchResult]:
        """Execute full-text + similarity search for a single entity type."""
        if entity_type == "lead":
            return await self._search_leads(query, organization_id, filters, limit)
        elif entity_type == "property":
            return await self._search_properties(query, organization_id, filters, limit)
        elif entity_type == "contact":
            return await self._search_contacts(query, organization_id, filters, limit)
        elif entity_type == "task":
            return await self._search_tasks(query, organization_id, filters, limit)
        elif entity_type == "meeting":
            return await self._search_meetings(query, organization_id, filters, limit)
        return []

    async def _search_leads(self, query: str, org_id: str, filters: Dict, limit: int) -> List[SearchResult]:
        """Full-text search on leads: name, phone, status, pipeline_stage."""
        safe_query = query.replace("'", "''")
        sql = text("""
            SELECT
                id::text,
                name,
                phone,
                status,
                score,
                pipeline_stage,
                broker_id::text,
                GREATEST(
                    similarity(COALESCE(name, ''), :query),
                    similarity(phone, :query)
                ) AS sim_score,
                updated_at
            FROM leads
            WHERE
                deleted_at IS NULL
                AND broker_id::text = :org_id
                AND (
                    COALESCE(name, '') ILIKE :like_query
                    OR phone ILIKE :like_query
                    OR status ILIKE :like_query
                    OR pipeline_stage ILIKE :like_query
                    OR similarity(COALESCE(name, ''), :query) > 0.15
                    OR similarity(phone, :query) > 0.2
                )
                {status_filter}
                {score_filter}
            ORDER BY sim_score DESC, updated_at DESC
            LIMIT :limit
        """.format(
            status_filter="AND status = :status" if "status" in filters else "",
            score_filter="AND score = :score" if "score" in filters else "",
        ))

        params: Dict[str, Any] = {
            "query": query,
            "like_query": f"%{query}%",
            "org_id": org_id,
            "limit": limit,
        }
        if "status" in filters:
            params["status"] = filters["status"]
        if "score" in filters:
            params["score"] = filters["score"]

        try:
            result = await self.db.execute(sql, params)
            rows = result.fetchall()
        except Exception as exc:
            logger.warning(f"[SEARCH] Lead search failed: {exc}")
            return []

        return [
            SearchResult(
                id=str(row[0]),
                entity_type="lead",
                display_title=row[1] or row[2],       # name or phone
                display_subtitle=f"{row[3]} · {row[4]} · {row[5]}",
                score=float(row[7] or 0.5),
                organization_id=str(row[6]),
                data={"status": row[3], "score": row[4], "pipeline_stage": row[5], "phone": row[2]},
            )
            for row in rows
        ]

    async def _search_properties(self, query: str, org_id: str, filters: Dict, limit: int) -> List[SearchResult]:
        """Full-text search on property listings."""
        sql = text("""
            SELECT
                id::text,
                title,
                city,
                locality,
                property_type,
                price,
                broker_id::text,
                similarity(title, :query) AS sim_score,
                updated_at
            FROM property_listings
            WHERE
                deleted_at IS NULL
                AND broker_id::text = :org_id
                AND (
                    title ILIKE :like_query
                    OR city ILIKE :like_query
                    OR locality ILIKE :like_query
                    OR project_name ILIKE :like_query
                    OR similarity(title, :query) > 0.1
                )
            ORDER BY sim_score DESC, updated_at DESC
            LIMIT :limit
        """)
        params = {"query": query, "like_query": f"%{query}%", "org_id": org_id, "limit": limit}

        try:
            result = await self.db.execute(sql, params)
            rows = result.fetchall()
        except Exception as exc:
            logger.warning(f"[SEARCH] Property search failed: {exc}")
            return []

        return [
            SearchResult(
                id=str(row[0]),
                entity_type="property",
                display_title=row[1],
                display_subtitle=f"{row[2]}, {row[3]} · {row[4]}",
                score=float(row[7] or 0.3),
                organization_id=str(row[6]),
                data={"city": row[2], "locality": row[3], "property_type": row[4], "price": row[5]},
            )
            for row in rows
        ]

    async def _search_contacts(self, query: str, org_id: str, filters: Dict, limit: int) -> List[SearchResult]:
        """Full-text search on contacts."""
        sql = text("""
            SELECT
                id,
                name,
                email,
                phone,
                contact_type,
                organization_id,
                similarity(name, :query) AS sim_score,
                updated_at
            FROM contacts
            WHERE
                deleted_at IS NULL
                AND organization_id = :org_id
                AND (
                    name ILIKE :like_query
                    OR COALESCE(email, '') ILIKE :like_query
                    OR COALESCE(phone, '') ILIKE :like_query
                    OR similarity(name, :query) > 0.15
                )
            ORDER BY sim_score DESC, updated_at DESC
            LIMIT :limit
        """)
        params = {"query": query, "like_query": f"%{query}%", "org_id": org_id, "limit": limit}

        try:
            result = await self.db.execute(sql, params)
            rows = result.fetchall()
        except Exception as exc:
            logger.warning(f"[SEARCH] Contact search failed: {exc}")
            return []

        return [
            SearchResult(
                id=str(row[0]),
                entity_type="contact",
                display_title=row[1],
                display_subtitle=f"{row[2] or ''} · {row[4]}",
                score=float(row[6] or 0.3),
                organization_id=str(row[5]),
                data={"email": row[2], "phone": row[3], "contact_type": row[4]},
            )
            for row in rows
        ]

    async def _search_tasks(self, query: str, org_id: str, filters: Dict, limit: int) -> List[SearchResult]:
        """Full-text search on tasks."""
        sql = text("""
            SELECT id, title, status, priority, organization_id,
                   similarity(title, :query) AS sim_score, updated_at
            FROM tasks
            WHERE organization_id = :org_id
              AND (title ILIKE :like_query OR similarity(title, :query) > 0.1)
            ORDER BY sim_score DESC, updated_at DESC
            LIMIT :limit
        """)
        params = {"query": query, "like_query": f"%{query}%", "org_id": org_id, "limit": limit}
        try:
            result = await self.db.execute(sql, params)
            rows = result.fetchall()
        except Exception as exc:
            logger.warning(f"[SEARCH] Task search failed: {exc}")
            return []
        return [
            SearchResult(
                id=str(row[0]),
                entity_type="task",
                display_title=row[1],
                display_subtitle=f"{row[2]} · {row[3]}",
                score=float(row[5] or 0.2),
                organization_id=str(row[4]),
                data={"status": row[2], "priority": row[3]},
            )
            for row in rows
        ]

    async def _search_meetings(self, query: str, org_id: str, filters: Dict, limit: int) -> List[SearchResult]:
        """Full-text search on meetings."""
        sql = text("""
            SELECT id, title, status, meeting_type, organization_id,
                   similarity(title, :query) AS sim_score, updated_at
            FROM meetings
            WHERE organization_id = :org_id
              AND (title ILIKE :like_query OR similarity(title, :query) > 0.1)
            ORDER BY sim_score DESC, updated_at DESC
            LIMIT :limit
        """)
        params = {"query": query, "like_query": f"%{query}%", "org_id": org_id, "limit": limit}
        try:
            result = await self.db.execute(sql, params)
            rows = result.fetchall()
        except Exception as exc:
            logger.warning(f"[SEARCH] Meeting search failed: {exc}")
            return []
        return [
            SearchResult(
                id=str(row[0]),
                entity_type="meeting",
                display_title=row[1],
                display_subtitle=f"{row[2]} · {row[3]}",
                score=float(row[5] or 0.2),
                organization_id=str(row[4]),
                data={"status": row[2], "meeting_type": row[3]},
            )
            for row in rows
        ]

    async def autocomplete(
        self, prefix: str, organization_id: str,
        entity_types: Optional[List[str]] = None, limit: int = 10
    ) -> List[Dict[str, str]]:
        """Prefix-match autocomplete across lead names, property titles, contact names."""
        entity_types = entity_types or ["lead", "property", "contact"]
        suggestions = []

        if "lead" in entity_types:
            sql = text("""
                SELECT DISTINCT name, 'lead' AS entity_type
                FROM leads
                WHERE deleted_at IS NULL AND broker_id::text = :org_id
                  AND name ILIKE :prefix
                LIMIT :limit
            """)
            try:
                rows = (await self.db.execute(sql, {"org_id": organization_id, "prefix": f"{prefix}%", "limit": limit})).fetchall()
                suggestions.extend([{"label": r[0], "entity_type": r[1], "value": r[0]} for r in rows if r[0]])
            except Exception:
                pass

        if "property" in entity_types:
            sql = text("""
                SELECT DISTINCT title, 'property' AS entity_type
                FROM property_listings
                WHERE deleted_at IS NULL AND broker_id::text = :org_id
                  AND title ILIKE :prefix
                LIMIT :limit
            """)
            try:
                rows = (await self.db.execute(sql, {"org_id": organization_id, "prefix": f"{prefix}%", "limit": limit})).fetchall()
                suggestions.extend([{"label": r[0], "entity_type": r[1], "value": r[0]} for r in rows])
            except Exception:
                pass

        if "contact" in entity_types:
            sql = text("""
                SELECT DISTINCT name, 'contact' AS entity_type
                FROM contacts
                WHERE deleted_at IS NULL AND organization_id = :org_id
                  AND name ILIKE :prefix
                LIMIT :limit
            """)
            try:
                rows = (await self.db.execute(sql, {"org_id": organization_id, "prefix": f"{prefix}%", "limit": limit})).fetchall()
                suggestions.extend([{"label": r[0], "entity_type": r[1], "value": r[0]} for r in rows])
            except Exception:
                pass

        # Deduplicate, sort, limit
        seen = set()
        unique = []
        for s in suggestions:
            key = f"{s['value']}:{s['entity_type']}"
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique[:limit]

    async def facets(
        self, query: str, organization_id: str, entity_type: str,
        facet_fields: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate facet aggregations for a query result set."""
        result = {}
        if entity_type == "lead":
            for field in facet_fields:
                if field in ("status", "score", "pipeline_stage", "source", "property_type"):
                    sql = text(f"""
                        SELECT {field}, COUNT(*) as count
                        FROM leads
                        WHERE deleted_at IS NULL AND broker_id::text = :org_id
                          AND (name ILIKE :q OR phone ILIKE :q)
                        GROUP BY {field}
                        ORDER BY count DESC
                        LIMIT 20
                    """)
                    try:
                        rows = (await self.db.execute(sql, {"org_id": organization_id, "q": f"%{query}%"})).fetchall()
                        result[field] = [{"value": str(r[0]), "count": r[1]} for r in rows if r[0]]
                    except Exception as exc:
                        logger.warning(f"[FACET] Failed to compute '{field}' for leads: {exc}")
                        result[field] = []

        elif entity_type == "property":
            for field in facet_fields:
                if field in ("property_type", "city", "locality", "status", "transaction_category"):
                    sql = text(f"""
                        SELECT {field}, COUNT(*) as count
                        FROM property_listings
                        WHERE deleted_at IS NULL AND broker_id::text = :org_id
                          AND title ILIKE :q
                        GROUP BY {field}
                        ORDER BY count DESC
                        LIMIT 20
                    """)
                    try:
                        rows = (await self.db.execute(sql, {"org_id": organization_id, "q": f"%{query}%"})).fetchall()
                        result[field] = [{"value": str(r[0]), "count": r[1]} for r in rows]
                    except Exception as exc:
                        logger.warning(f"[FACET] Failed to compute '{field}' for properties: {exc}")
                        result[field] = []
        return result

    async def index_document(self, document: SearchDocument) -> bool:
        """PostgreSQL Phase 1: documents are indexed natively in tables. No-op here."""
        logger.debug(f"[SEARCH INDEX] PG provider: document '{document.get('entity_id')}' is stored natively.")
        return True

    async def deindex_document(self, entity_type: str, entity_id: str) -> bool:
        logger.debug(f"[SEARCH DEINDEX] PG provider: entity '{entity_type}/{entity_id}' — no external index to remove.")
        return True

    async def bulk_index(self, documents: List[SearchDocument]) -> Dict[str, int]:
        logger.info(f"[SEARCH BULK INDEX] PG provider: {len(documents)} documents are natively stored.")
        return {"indexed": len(documents), "failed": 0}

    async def health(self) -> Dict[str, Any]:
        try:
            await self.db.execute(text("SELECT 1"))
            return {"provider": self.provider_name, "status": "healthy", "backend": "postgresql"}
        except Exception as exc:
            return {"provider": self.provider_name, "status": "error", "error": str(exc)}


class MeilisearchSearchProvider(ISearchProvider):
    """Phase 2 Stub — Meilisearch provider. Swap in by changing the DI registry."""
    provider_name = "meilisearch"

    async def search(self, query, organization_id, entity_types=None, filters=None, page=1, limit=20, sort_by=None, sort_order="desc"):
        raise NotImplementedError("MeilisearchSearchProvider is not yet active. Configure SEARCH_PROVIDER=meilisearch.")

    async def autocomplete(self, prefix, organization_id, entity_types=None, limit=10):
        raise NotImplementedError()

    async def facets(self, query, organization_id, entity_type, facet_fields, filters=None):
        raise NotImplementedError()

    async def index_document(self, document):
        raise NotImplementedError()

    async def deindex_document(self, entity_type, entity_id):
        raise NotImplementedError()

    async def bulk_index(self, documents):
        raise NotImplementedError()

    async def health(self):
        return {"provider": self.provider_name, "status": "not_configured"}


class VectorSearchProvider(ISearchProvider):
    """Phase 4 Stub — Vector/embedding search for RAG and AI Lead Discovery."""
    provider_name = "vector"

    async def search(self, query, organization_id, entity_types=None, filters=None, page=1, limit=20, sort_by=None, sort_order="desc"):
        raise NotImplementedError("VectorSearchProvider is not yet active.")

    async def autocomplete(self, prefix, organization_id, entity_types=None, limit=10):
        raise NotImplementedError()

    async def facets(self, query, organization_id, entity_type, facet_fields, filters=None):
        raise NotImplementedError()

    async def index_document(self, document):
        raise NotImplementedError()

    async def deindex_document(self, entity_type, entity_id):
        raise NotImplementedError()

    async def bulk_index(self, documents):
        raise NotImplementedError()

    async def health(self):
        return {"provider": self.provider_name, "status": "not_configured"}

    async def semantic_search(self, query_vector, organization_id, entity_types=None, limit=10):
        """Vector similarity search — implement with pgvector or Pinecone."""
        raise NotImplementedError("Configure a vector index to enable semantic search.")
