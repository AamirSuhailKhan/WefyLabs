"""
AI Memory & Customer Intelligence REST API Router
=================================================
Endpoints for:
- Retrieving Customer Memory Profiles & Scoped Views
- Generating Token-Budgeted AI Context Prompts
- Recording Verified Facts, Preferences & Constraints
- Extracting Memory Candidates from Dialogue
- Logging Objections and Property Rejection Codes
- GDPR/CCPA Privacy Deletion Requests
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.memory.service import AIMemoryService
from app.modules.memory.dto.memory_schemas import (
    RecordMemoryRequest, MemoryRecordResponse,
    ExtractMemoryRequest, ExtractMemoryResponse,
    MemoryContextResponse, ObjectionResponse,
    PropertyFeedbackResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/memory", tags=["AI Memory & Customer Intelligence"])

# ─── Memory Profile & Retrieval ────────────────────────────────────────────────

@router.get(
    "/{lead_id}",
    response_model=List[MemoryRecordResponse],
    summary="Get Lead Memory Profile"
)
async def get_lead_memories(
    lead_id: str,
    memory_type: Optional[str] = Query(None),
    only_active: bool = Query(True),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves all verified memories for a specific lead, scoped by tenant."""
    service = AIMemoryService(db)
    org_id = str(current_broker.organization_id or "org_default")
    types = [memory_type] if memory_type else None
    return await service.get_lead_memories(
        organization_id=org_id,
        lead_id=lead_id,
        memory_types=types,
        only_active=only_active
    )


@router.get(
    "/{lead_id}/context",
    response_model=MemoryContextResponse,
    summary="Get AI Prompt Context Block"
)
async def get_ai_context(
    lead_id: str,
    max_items: int = Query(10, ge=1, le=30),
    is_customer_facing: bool = Query(True),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Generates a compressed, token-budgeted prompt context block for AI Agent or Copilot."""
    service = AIMemoryService(db)
    org_id = str(current_broker.organization_id or "org_default")
    ctx_text = await service.get_ai_prompt_context(
        organization_id=org_id,
        lead_id=lead_id,
        max_items=max_items,
        is_customer_facing=is_customer_facing
    )
    records = await service.get_lead_memories(org_id, lead_id, only_active=True)
    return MemoryContextResponse(
        lead_id=lead_id,
        context_text=ctx_text,
        memories_count=len(records)
    )


# ─── Recording & Extraction ────────────────────────────────────────────────────

@router.post(
    "/{lead_id}/record",
    response_model=MemoryRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Verified Customer Memory"
)
async def record_memory(
    lead_id: str,
    req: RecordMemoryRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Records a verified memory item with contradiction checks and version archiving."""
    service = AIMemoryService(db)
    org_id = str(current_broker.organization_id or "org_default")
    actor = str(current_broker.email or current_broker.name or "agent")
    return await service.record_memory(
        organization_id=org_id,
        lead_id=lead_id,
        memory_type=req.memory_type,
        key=req.key,
        value_json=req.value_json,
        value_text=req.value_text,
        source_type=req.source_type,
        source_id=req.source_id,
        confidence=req.confidence,
        importance=req.importance,
        is_customer_safe=req.is_customer_safe,
        actor=actor
    )


@router.post(
    "/{lead_id}/extract",
    summary="Extract & Store Memories from Text"
)
async def extract_memories(
    lead_id: str,
    req: ExtractMemoryRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Parses text and records extracted facts/constraints."""
    service = AIMemoryService(db)
    org_id = str(current_broker.organization_id or "org_default")
    actor = str(current_broker.email or current_broker.name or "system")
    records = await service.extract_and_store_from_text(
        organization_id=org_id,
        lead_id=lead_id,
        text=req.text,
        is_customer_message=req.is_customer_message,
        actor=actor
    )
    return {
        "lead_id": lead_id,
        "extracted_count": len(records),
        "memories": [r.key for r in records]
    }


# ─── Objections & Property Feedback ────────────────────────────────────────────

@router.post(
    "/{lead_id}/objections",
    response_model=ObjectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log Customer Objection"
)
async def log_objection(
    lead_id: str,
    category: str = Query(..., description="PRICE | LOCATION | FINANCING | SIZE"),
    description: str = Query(...),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Logs a structured objection for sales tracking."""
    service = AIMemoryService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.record_objection(org_id, lead_id, category, description)


@router.post(
    "/{lead_id}/property-feedback",
    response_model=PropertyFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Property View or Rejection"
)
async def record_property_feedback(
    lead_id: str,
    property_id: str = Query(...),
    feedback_type: str = Query(..., description="VIEWED | SAVED | REJECTED | OFFERED"),
    rejection_reason_code: Optional[str] = Query(None, description="TOO_EXPENSIVE | WRONG_LOCATION | TOO_SMALL"),
    notes: Optional[str] = Query(None),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Records property feedback and rejection reason codes."""
    service = AIMemoryService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.record_property_feedback(
        organization_id=org_id,
        lead_id=lead_id,
        property_id=property_id,
        feedback_type=feedback_type,
        rejection_reason_code=rejection_reason_code,
        notes=notes
    )


# ─── Privacy & GDPR Deletion ───────────────────────────────────────────────────

@router.delete(
    "/{lead_id}",
    summary="GDPR/CCPA Lead Memory Purge"
)
async def purge_lead_memory(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Permanently purges all memory records for a lead."""
    service = AIMemoryService(db)
    org_id = str(current_broker.organization_id or "org_default")
    requester = str(current_broker.email or current_broker.name or "admin")
    del_req = await service.execute_lead_deletion(org_id, lead_id, requester)
    return {
        "status": "COMPLETED",
        "lead_id": lead_id,
        "purged_records_count": del_req.records_deleted_count,
        "completed_at": del_req.completed_at
    }
