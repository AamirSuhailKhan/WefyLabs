from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


# ─── Search Query DTOs ────────────────────────────────────────────────────────

class GlobalSearchQueryDTO(BaseModel):
    """Input DTO for global cross-entity search."""
    q: str = Field(..., min_length=1, max_length=500)
    entity_types: Optional[List[str]] = None          # None = all types
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    # Common filters
    status: Optional[str] = None
    score: Optional[str] = None
    pipeline_stage: Optional[str] = None
    city: Optional[str] = None
    property_type: Optional[str] = None
    assigned_to: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    organization_id: Optional[str] = None


class EntitySearchDTO(BaseModel):
    """Entity-scoped search DTO with full filter set."""
    q: str = Field(default="", max_length=500)
    entity_type: str = "lead"
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    filters: Dict[str, Any] = Field(default_factory=dict)
    sort_by: Optional[str] = None
    sort_order: str = "desc"


class AutocompleteQueryDTO(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=100)
    entity_types: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=50)


class FacetQueryDTO(BaseModel):
    q: str = Field(default="")
    entity_type: str = "lead"
    fields: List[str] = Field(default_factory=lambda: ["status", "score", "pipeline_stage"])
    filters: Optional[Dict[str, Any]] = None


# ─── Search Result DTOs ───────────────────────────────────────────────────────

class SearchHitDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    display_title: str
    display_subtitle: Optional[str] = None
    score: float
    organization_id: str
    highlights: Dict[str, str] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class SearchGroupDTO(BaseModel):
    entity_type: str
    label: str
    hits: List[SearchHitDTO]
    total: int


class GlobalSearchResponseDTO(BaseModel):
    query: str
    groups: List[SearchGroupDTO]
    total: int
    page: int
    limit: int
    took_ms: int
    provider: str


class AutocompleteResponseDTO(BaseModel):
    suggestions: List[Dict[str, str]]
    query: str
    took_ms: int


class FacetResponseDTO(BaseModel):
    entity_type: str
    facets: Dict[str, List[Dict[str, Any]]]
    took_ms: int


# ─── Saved Search DTOs ────────────────────────────────────────────────────────

class SavedSearchCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    entity_type: str = "lead"
    query: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    sorting: Dict[str, Any] = Field(default_factory=dict)
    columns: List[str] = Field(default_factory=list)
    view_mode: str = "list"
    is_shared: bool = False
    share_scope: str = "personal"
    description: Optional[str] = None


class SavedSearchResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    entity_type: str
    query: Optional[str] = None
    filters: Dict[str, Any]
    sorting: Dict[str, Any]
    view_mode: str
    is_shared: bool
    share_scope: str
    run_count: int
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ─── Indexing DTOs ────────────────────────────────────────────────────────────

class IndexRequestDTO(BaseModel):
    entity_type: str
    entity_id: str
    organization_id: str
    priority: str = "normal"      # normal | high | low


class ReindexRequestDTO(BaseModel):
    entity_type: Optional[str] = None    # None = full system reindex
    organization_id: Optional[str] = None
    force: bool = False                  # Force reindex even if hash matches
