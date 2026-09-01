"""
Enterprise Search Controller
============================
All search endpoints. This is the ONLY entry point for search — no module
may bypass this controller to query the database for search purposes.

Endpoints:
  GET  /v1/search                        - Global cross-entity search
  GET  /v1/search/leads                  - Lead-scoped search
  GET  /v1/search/properties             - Property search
  GET  /v1/search/contacts               - Contact search
  GET  /v1/search/autocomplete           - Autocomplete suggestions
  GET  /v1/search/facets                 - Facet aggregations
  GET  /v1/search/health                 - Search platform health
  POST /v1/search/reindex                - Full/partial system reindex
  POST /v1/search/reindex/{entity_type}  - Entity-type reindex
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.search.service.search_service import SearchService
from app.modules.search.dto.search_dto import (
    GlobalSearchQueryDTO, AutocompleteQueryDTO, FacetQueryDTO, ReindexRequestDTO
)
from app.modules.indexing.service.indexing_service import IndexingService

router = APIRouter(prefix="/v1/search", tags=["Enterprise Search Platform"])


@router.get("", response_model=APIResponse, summary="Global Cross-Entity Search")
async def global_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    entity_types: Optional[str] = Query(None, description="Comma-separated entity types: lead,property,contact"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    score: Optional[str] = None,
    pipeline_stage: Optional[str] = None,
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Global search across Leads, Properties, Contacts, Tasks, Meetings.
    Returns grouped results ordered by relevance score.
    """
    parsed_types = [t.strip() for t in entity_types.split(",")] if entity_types else None
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))

    dto = GlobalSearchQueryDTO(
        q=q,
        entity_types=parsed_types,
        page=page,
        limit=limit,
        status=status,
        score=score,
        pipeline_stage=pipeline_stage,
        city=city,
        property_type=property_type,
        sort_by=sort_by,
        sort_order=sort_order,
        organization_id=org_id,
    )
    service = SearchService(db)
    result = await service.global_search(dto, user_id=str(current_broker.id))
    return create_success_response(
        data=result.model_dump(),
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/leads", response_model=APIResponse, summary="Lead-Scoped Search")
async def search_leads(
    request: Request,
    q: str = Query(default="", max_length=500),
    status: Optional[str] = None,
    score: Optional[str] = None,
    pipeline_stage: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    dto = GlobalSearchQueryDTO(
        q=q or " ",
        entity_types=["lead"],
        page=page,
        limit=limit,
        status=status,
        score=score,
        pipeline_stage=pipeline_stage,
        organization_id=org_id,
    )
    service = SearchService(db)
    result = await service.global_search(dto, user_id=str(current_broker.id))
    leads_group = next((g for g in result.groups if g.entity_type == "lead"), None)
    return create_success_response(
        data=leads_group.hits if leads_group else [],
        meta={"total": leads_group.total if leads_group else 0, "page": page, "limit": limit},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/properties", response_model=APIResponse, summary="Property-Scoped Search")
async def search_properties(
    request: Request,
    q: str = Query(default="", max_length=500),
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    dto = GlobalSearchQueryDTO(
        q=q or " ",
        entity_types=["property"],
        page=page,
        limit=limit,
        city=city,
        property_type=property_type,
        organization_id=org_id,
    )
    service = SearchService(db)
    result = await service.global_search(dto, user_id=str(current_broker.id))
    props_group = next((g for g in result.groups if g.entity_type == "property"), None)
    return create_success_response(
        data=props_group.hits if props_group else [],
        meta={"total": props_group.total if props_group else 0, "page": page, "limit": limit},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/contacts", response_model=APIResponse, summary="Contact-Scoped Search")
async def search_contacts(
    request: Request,
    q: str = Query(default="", max_length=500),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    dto = GlobalSearchQueryDTO(
        q=q or " ",
        entity_types=["contact"],
        page=page,
        limit=limit,
        organization_id=org_id,
    )
    service = SearchService(db)
    result = await service.global_search(dto, user_id=str(current_broker.id))
    group = next((g for g in result.groups if g.entity_type == "contact"), None)
    return create_success_response(
        data=group.hits if group else [],
        meta={"total": group.total if group else 0, "page": page, "limit": limit},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/autocomplete", response_model=APIResponse, summary="Autocomplete Suggestions")
async def autocomplete(
    request: Request,
    prefix: str = Query(..., min_length=1, max_length=100),
    entity_types: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Sub-100ms autocomplete for names, emails, titles, phone numbers."""
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    parsed_types = [t.strip() for t in entity_types.split(",")] if entity_types else None
    dto = AutocompleteQueryDTO(prefix=prefix, entity_types=parsed_types, limit=limit)
    service = SearchService(db)
    result = await service.autocomplete(dto, organization_id=org_id)
    return create_success_response(
        data=result.model_dump(),
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/facets", response_model=APIResponse, summary="Dynamic Facet Aggregations")
async def get_facets(
    request: Request,
    q: str = Query(default=""),
    entity_type: str = Query(default="lead"),
    fields: str = Query(default="status,score,pipeline_stage"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Generate dynamic facet counts for filters UI."""
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    dto = FacetQueryDTO(q=q, entity_type=entity_type, fields=[f.strip() for f in fields.split(",")])
    service = SearchService(db)
    result = await service.get_facets(dto, organization_id=org_id)
    return create_success_response(
        data=result.model_dump(),
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.get("/health", response_model=APIResponse, summary="Search Platform Health")
async def search_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    service = SearchService(db)
    indexing_service = IndexingService(db)
    search_status = await service.health()
    index_health = await indexing_service.get_index_health()
    return create_success_response(
        data={**search_status, "index_health": index_health},
        request_id=getattr(request.state, "correlation_id", ""),
    )


@router.post("/reindex", response_model=APIResponse, summary="Trigger Full/Partial Reindex")
async def trigger_reindex(
    dto: ReindexRequestDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Admin endpoint: marks documents as stale to trigger background re-indexing."""
    indexing_service = IndexingService(db)
    result = await indexing_service.reindex_all(
        entity_type=dto.entity_type,
        organization_id=dto.organization_id,
    )
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))


@router.post("/reindex/{entity_type}", response_model=APIResponse, summary="Reindex by Entity Type")
async def trigger_entity_reindex(
    entity_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    indexing_service = IndexingService(db)
    result = await indexing_service.reindex_all(entity_type=entity_type, organization_id=org_id)
    return create_success_response(data=result, request_id=getattr(request.state, "correlation_id", ""))
