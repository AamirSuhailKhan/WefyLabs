"""
Volume 2 PART 2 — Lead Enrichment Lifecycle Events
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LeadEnrichmentStarted(BaseModel):
    event_id: str
    lead_id: str
    organization_id: str
    trigger_source: str = "LeadNormalized"
    timestamp: str = Field(default_factory=_now_iso)


class LeadEnriched(BaseModel):
    event_id: str
    lead_id: str
    organization_id: str
    quality_tier: str # hot | warm | cold | unqualified
    quality_score: float # 0 - 100
    overall_confidence: float # 0.0 - 1.0
    field_completion_rate: float
    execution_time_ms: float
    timestamp: str = Field(default_factory=_now_iso)


class LeadEnrichmentFailed(BaseModel):
    event_id: str
    lead_id: str
    organization_id: str
    error_message: str
    retry_count: int = 0
    timestamp: str = Field(default_factory=_now_iso)


class ConfidenceUpdated(BaseModel):
    event_id: str
    lead_id: str
    organization_id: str
    field_name: str
    new_confidence: float
    source_type: str
    timestamp: str = Field(default_factory=_now_iso)


class ProfileUpdated(BaseModel):
    event_id: str
    lead_id: str
    organization_id: str
    modified_fields: List[str]
    timestamp: str = Field(default_factory=_now_iso)
