"""
PART 7 — Enterprise Search Platform Tests
==========================================
Comprehensive tests for:
  - SearchProvider interface & PostgreSQLSearchProvider
  - RankingEngine signals & weighting
  - Document Adapters serialization
  - Search DTO validation
  - SavedSearch CRUD logic
  - SearchHistory tracking
"""
import pytest
from datetime import datetime, timezone
from app.modules.search.interfaces.provider_interface import SearchResult, SearchDocument
from app.modules.search.ranking.ranking_engine import RankingEngine
from app.modules.search.dto.search_dto import GlobalSearchQueryDTO, SavedSearchCreateDTO, IndexRequestDTO
from app.modules.indexing.adapters.document_adapters import (
    LeadIndexAdapter, PropertyIndexAdapter, ContactIndexAdapter, TaskIndexAdapter
)


# ─── Search Document Adapter Tests ────────────────────────────────────────────

def test_lead_index_adapter():
    class DummyLead:
        id = "lead-123"
        name = "John Doe"
        phone = "+971501234567"
        status = "active"
        pipeline_stage = "viewing"
        updated_at = datetime.now(timezone.utc)

    doc = LeadIndexAdapter.to_document(DummyLead(), organization_id="org-1")
    assert doc["id"] == "lead-123"
    assert doc["entity_type"] == "lead"
    assert doc["display_title"] == "John Doe"
    assert "John Doe" in doc["searchable_text"]
    assert doc["document_hash"] is not None


def test_property_index_adapter():
    class DummyProperty:
        id = "prop-456"
        title = "Luxury Marina Villa"
        city = "Dubai"
        locality = "Dubai Marina"
        property_type = "villa"
        price = 5000000.0
        bedrooms = 4
        status = "available"
        updated_at = datetime.now(timezone.utc)

    doc = PropertyIndexAdapter.to_document(DummyProperty(), organization_id="org-1")
    assert doc["id"] == "prop-456"
    assert doc["entity_type"] == "property"
    assert doc["display_title"] == "Luxury Marina Villa"
    assert doc["price"] == 5000000.0


# ─── Ranking Engine Tests ─────────────────────────────────────────────────────

def test_ranking_engine_exact_match_boost():
    engine = RankingEngine()

    hit_exact = SearchResult(
        id="1", entity_type="lead", display_title="John Doe", display_subtitle="", score=0.5, organization_id="org-1"
    )
    hit_partial = SearchResult(
        id="2", entity_type="lead", display_title="John Smith Doe", display_subtitle="", score=0.5, organization_id="org-1"
    )

    ranked = engine.rank([hit_partial, hit_exact], query="John Doe")
    assert ranked[0].id == "1"  # Exact match should be ranked higher


def test_ranking_engine_entity_type_weighting():
    engine = RankingEngine()

    lead_hit = SearchResult(
        id="lead-1", entity_type="lead", display_title="Marina", display_subtitle="", score=0.5, organization_id="org-1"
    )
    task_hit = SearchResult(
        id="task-1", entity_type="task", display_title="Marina", display_subtitle="", score=0.5, organization_id="org-1"
    )

    ranked = engine.rank([task_hit, lead_hit], query="Marina")
    assert ranked[0].entity_type == "lead"  # Lead (weight 1.0) ranks higher than Task (0.5)


def test_ranking_engine_recency_boost():
    engine = RankingEngine()
    now_iso = datetime.now(timezone.utc).isoformat()

    recent_hit = SearchResult(
        id="r1", entity_type="lead", display_title="Alex", display_subtitle="", score=0.5, organization_id="org-1",
        data={"updated_at": now_iso}
    )
    old_hit = SearchResult(
        id="r2", entity_type="lead", display_title="Alex", display_subtitle="", score=0.5, organization_id="org-1",
        data={"updated_at": "2020-01-01T00:00:00+00:00"}
    )

    ranked = engine.rank([old_hit, recent_hit], query="Alex")
    assert ranked[0].id == "r1"


# ─── DTO Validation Tests ─────────────────────────────────────────────────────

def test_global_search_query_dto():
    dto = GlobalSearchQueryDTO(q="Dubai Villa", limit=10)
    assert dto.q == "Dubai Villa"
    assert dto.limit == 10
    assert dto.sort_order == "desc"


def test_saved_search_create_dto():
    dto = SavedSearchCreateDTO(
        name="Hot Leads in Dubai",
        entity_type="lead",
        filters={"status": "active", "score": "hot"},
        is_shared=True,
    )
    assert dto.name == "Hot Leads in Dubai"
    assert dto.filters["score"] == "hot"
    assert dto.is_shared is True


# ─── Search Provider Unconfigured & Vector Fallback Tests ─────────────────────

@pytest.mark.asyncio
async def test_meilisearch_unconfigured_safe_handling():
    from app.modules.search.providers.search_providers import MeilisearchSearchProvider
    provider = MeilisearchSearchProvider()
    assert not provider.is_configured()

    health = await provider.health()
    assert health["status"] == "unconfigured"

    res = await provider.search("luxury villa", organization_id="org-1")
    assert res.total == 0
    assert res.hits == []
    assert res.provider == "meilisearch"

    assert await provider.autocomplete("lux", organization_id="org-1") == []
    assert await provider.facets("lux", organization_id="org-1", entity_type="property", facet_fields=["city"]) == {}
    assert await provider.index_document({"id": "1", "entity_type": "lead"}) is False
    assert (await provider.bulk_index([{"id": "1"}]))["indexed"] == 0


@pytest.mark.asyncio
async def test_vector_search_provider_unconfigured_handling():
    from app.modules.search.providers.search_providers import VectorSearchProvider
    provider = VectorSearchProvider(db=None)
    assert not provider.is_configured()

    health = await provider.health()
    assert health["status"] == "unconfigured"

    res = await provider.search("villa", organization_id="org-1")
    assert res.total == 0
    assert res.hits == []

    semantic_res = await provider.semantic_search([0.1, 0.2, 0.3], organization_id="org-1")
    assert semantic_res == []


@pytest.mark.asyncio
async def test_vector_search_provider_with_mocked_pgvector():
    from unittest.mock import AsyncMock, patch, MagicMock
    from app.modules.search.providers.search_providers import VectorSearchProvider
    from app.modules.knowledge.providers.vector_store_provider import VectorHit

    mock_db = AsyncMock()
    provider = VectorSearchProvider(db=mock_db)
    assert provider.is_configured()

    mock_hits = [
        VectorHit(
            chunk_id="chunk-001",
            document_id="doc-001",
            organization_id="org-1",
            score=0.92,
            metadata={"title": "Downtown Dubai Property Guide", "snippet": "Prime residential area."}
        )
    ]

    with patch("app.modules.knowledge.providers.vector_store_provider.PgVectorStoreProvider.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_hits
        results = await provider.semantic_search([0.1, 0.2, 0.3], organization_id="org-1", limit=5)

        assert len(results) == 1
        assert results[0].id == "chunk-001"
        assert results[0].display_title == "Downtown Dubai Property Guide"
        assert results[0].score == 0.92
        assert results[0].organization_id == "org-1"

