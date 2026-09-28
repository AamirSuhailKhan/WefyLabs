"""
Canonical Property Intelligence API Router
==========================================
Exposes grounded property intelligence endpoints strictly enforcing tenant isolation:
- POST /api/v1/properties/intelligence/search
- GET  /api/v1/properties/intelligence/{property_id}/truth
- POST /api/v1/properties/intelligence/{property_id}/knowledge
- GET  /api/v1/properties/intelligence/{property_id}/availability
- POST /api/v1/properties/intelligence/classify-question
- POST /api/v1/properties/intelligence/{property_id}/detect-conflicts
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.modules.property_intelligence.service import PropertyIntelligenceService
from app.modules.property_intelligence.schemas import (
    PropertyTruthResponse,
    PropertySearchCriteria,
    PropertySearchResponse,
    PropertyKnowledgeQuery,
    PropertyKnowledgeResponse,
    ConflictDetectionResult,
    QuestionClassificationRequest,
    QuestionClassificationResponse,
)

router = APIRouter(prefix="/properties/intelligence", tags=["Canonical Property Intelligence"])


@router.post("/search", response_model=PropertySearchResponse)
async def search_property_inventory_endpoint(
    criteria: PropertySearchCriteria,
    actor_role: str = Query("customer", description="customer | broker | admin"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Deterministic 7-stage property search pipeline.
    Runs 100% without LLM/Gemini dependencies.
    """
    svc = PropertyIntelligenceService(db)
    return await svc.search_property_inventory(
        tenant_id=current_broker.id,
        criteria=criteria,
        actor_role=actor_role
    )


@router.get("/{property_id}/truth", response_model=PropertyTruthResponse)
async def get_property_truth_endpoint(
    property_id: str,
    actor_role: str = Query("customer", description="customer | broker | admin"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves verified property facts (Fact Pack) with explicit missing data semantics.
    Redacts internal broker details when actor_role is customer.
    """
    svc = PropertyIntelligenceService(db)
    return await svc.get_property_truth(
        tenant_id=current_broker.id,
        property_id=property_id,
        actor_role=actor_role
    )


@router.post("/{property_id}/knowledge", response_model=PropertyKnowledgeResponse)
async def retrieve_property_knowledge_endpoint(
    property_id: str,
    req: PropertyKnowledgeQuery,
    actor_role: str = Query("customer", description="customer | broker | admin"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves tenant-scoped approved property knowledge chunks and document excerpts.
    Wraps content in anti-prompt-injection delimiters.
    """
    svc = PropertyIntelligenceService(db)
    return await svc.retrieve_property_knowledge(
        tenant_id=current_broker.id,
        property_id=property_id,
        query=req.query,
        actor_role=actor_role,
        max_chunks=req.max_chunks
    )


@router.get("/{property_id}/availability")
async def check_property_availability_endpoint(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Live transactional availability lookup. Authoritative source of truth.
    """
    svc = PropertyIntelligenceService(db)
    return await svc.check_availability(
        tenant_id=current_broker.id,
        property_id=property_id
    )


@router.post("/classify-question", response_model=QuestionClassificationResponse)
async def classify_question_endpoint(
    req: QuestionClassificationRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Deterministic rule-based inquiry classifier (STRUCTURED_FACT, AVAILABILITY, KNOWLEDGE_FACT, etc.).
    """
    svc = PropertyIntelligenceService(db)
    return svc.classify_property_question(req.query)


from pydantic import BaseModel


class PropertyComparisonRequest(BaseModel):
    property_ids: List[str]
    actor_role: Optional[str] = "customer"


@router.post("/{property_id}/detect-conflicts", response_model=List[ConflictDetectionResult])
async def detect_conflicts_endpoint(
    property_id: str,
    payload: Dict[str, Any],
    source: str = Query("APPROVED_PROPERTY_DOCUMENT"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Compares incoming document claims against authoritative DB truth.
    Enforces source precedence hierarchy and flags discrepancies.
    """
    svc = PropertyIntelligenceService(db)
    return await svc.detect_conflicts(
        tenant_id=current_broker.id,
        property_id=property_id,
        incoming_data=payload,
        incoming_source=source
    )


@router.post("/compare")
async def compare_properties_endpoint(
    req: PropertyComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Deterministic side-by-side comparison of multiple properties.
    """
    svc = PropertyIntelligenceService(db)
    return await svc.compare_properties(
        tenant_id=current_broker.id,
        property_ids=req.property_ids,
        actor_role=req.actor_role or "customer"
    )


@router.get("/projects/{project_id}/summary")
async def get_project_summary_endpoint(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Authoritative project summary with towers and unit counts."""
    svc = PropertyIntelligenceService(db)
    return await svc.get_project_summary(
        tenant_id=current_broker.id,
        project_id=project_id
    )


@router.get("/units/{unit_id}/summary")
async def get_unit_summary_endpoint(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Authoritative unit summary with inventory status, pricing, and specs."""
    svc = PropertyIntelligenceService(db)
    return await svc.get_unit_summary(
        tenant_id=current_broker.id,
        unit_id=unit_id
    )

