"""
Search Provider Interface
=========================
ISearchProvider is the single abstraction that decouples ALL search callers
from the underlying search engine.

Phase 1:  PostgreSQLSearchProvider  (built now)
Phase 2:  MeilisearchSearchProvider (stub → plug in without service changes)
Phase 3:  OpenSearchSearchProvider  (stub)
Phase 4:  VectorSearchProvider      (stub — for RAG semantic search)

Any future module (RAG, AI Lead Discovery, Analytics) calls ISearchProvider
and never knows which engine is active.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class SearchDocument(dict):
    """
    Flat, serializable document sent to and returned from search providers.
    Fields are standardized across all entity types.
    """
    required_fields = ["id", "entity_type", "organization_id", "display_title", "updated_at"]


class SearchResult:
    """Represents a single search hit returned by a provider."""
    def __init__(
        self,
        id: str,
        entity_type: str,
        display_title: str,
        display_subtitle: Optional[str],
        score: float,
        organization_id: str,
        highlights: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.entity_type = entity_type
        self.display_title = display_title
        self.display_subtitle = display_subtitle
        self.score = score
        self.organization_id = organization_id
        self.highlights = highlights or {}
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "display_title": self.display_title,
            "display_subtitle": self.display_subtitle,
            "score": self.score,
            "organization_id": self.organization_id,
            "highlights": self.highlights,
            "data": self.data,
        }


class SearchProviderResult:
    """Batch result returned by a provider for a single query."""
    def __init__(
        self,
        hits: List[SearchResult],
        total: int,
        facets: Optional[Dict[str, Any]] = None,
        took_ms: int = 0,
        provider: str = "unknown",
    ):
        self.hits = hits
        self.total = total
        self.facets = facets or {}
        self.took_ms = took_ms
        self.provider = provider


class ISearchProvider(ABC):
    """
    Abstract Search Provider.
    Every search engine must implement this interface.
    Services depend only on this — never on concrete implementations.
    """
    provider_name: str = "base"

    # ── Core Search ───────────────────────────────────────────────────────────

    @abstractmethod
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
        """Perform a full-text search across specified entity types."""
        pass

    @abstractmethod
    async def autocomplete(
        self,
        prefix: str,
        organization_id: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Return autocomplete suggestions for a partial query."""
        pass

    @abstractmethod
    async def facets(
        self,
        query: str,
        organization_id: str,
        entity_type: str,
        facet_fields: List[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute facet aggregations for a query."""
        pass

    # ── Indexing ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def index_document(self, document: SearchDocument) -> bool:
        """Add or update a document in the search index."""
        pass

    @abstractmethod
    async def deindex_document(self, entity_type: str, entity_id: str) -> bool:
        """Remove a document from the search index."""
        pass

    @abstractmethod
    async def bulk_index(self, documents: List[SearchDocument]) -> Dict[str, int]:
        """Bulk index a batch of documents. Returns {indexed, failed}."""
        pass

    # ── Health ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """Return provider health status and index statistics."""
        pass

    # ── Semantic Search (Phase 4 extension point) ─────────────────────────────

    async def semantic_search(
        self,
        query_vector: List[float],
        organization_id: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> SearchProviderResult:
        """
        Vector similarity search for RAG and AI modules.
        Default: raises NotImplementedError (only VectorSearchProvider implements this).
        """
        raise NotImplementedError(
            f"Provider '{self.provider_name}' does not support semantic/vector search. "
            "Use VectorSearchProvider for RAG queries."
        )
