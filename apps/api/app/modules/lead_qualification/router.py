"""
Part 21.4.1 — AI Lead Qualification REST API Router
===================================================
Endpoints:
    GET    /api/v1/leads/{lead_id}/qualification                   # Fetch evaluated qualification snapshot
    GET    /api/v1/leads/{lead_id}/qualification/facts             # Fetch qualification facts & evidence
    GET    /api/v1/leads/{lead_id}/qualification/conflicts         # Fetch evidence conflicts
    GET    /api/v1/leads/{lead_id}/qualification/history           # Fetch immutable audit history
    GET    /api/v1/qualification/policies                          # List active requirement policies
    POST   /api/v1/leads/{lead_id}/qualification/facts             # Record a qualification fact
    POST   /api/v1/leads/{lead_id}/qualification/conflicts/{id}/resolve # Resolve an evidence conflict
    POST   /api/v1/leads/{lead_id}/qualification/override          # Authorized human review override
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.qualification_models import QualificationAuditActorType
from app.modules.lead_qualification.service import LeadQualificationDomainService
from app.modules.lead_qualification.dto import (
    QualificationSnapshotDTO,
    QualificationFactDTO,
    QualificationFactCreateDTO,
    QualificationConflictDTO,
    QualificationConflictResolveDTO,
    QualificationAuditEventDTO,
    QualificationPolicyDTO,
    QualificationHumanOverrideDTO,
    QualificationExtractRequestDTO,
    QualificationExtractionSummaryDTO,
    QualificationEvaluationResultDTO,
    QualificationMissingInfoDTO,
    QualificationConversationStartDTO,
    QualificationConversationMessageDTO,
    QualificationConversationResponseDTO,
    QualificationConversationStateDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Lead Qualification Engine"])


def _get_org_id(broker: Broker) -> str:
    """Resolve organization identifier from current authenticated broker."""
    return getattr(broker, "organization_id", None) or str(broker.id)


@router.get(
    "/api/v1/leads/{lead_id}/qualification",
    response_model=QualificationSnapshotDTO,
    summary="Get Evaluated Lead Qualification Snapshot",
)
async def get_lead_qualification_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Retrieves the deterministically evaluated qualification snapshot for a CRM lead."""
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.get_lead_qualification_snapshot(
        organization_id=org_id, lead_id=lead_id, broker=current_broker
    )


@router.get(
    "/api/v1/leads/{lead_id}/qualification/facts",
    response_model=List[QualificationFactDTO],
    summary="Get Lead Qualification Facts & Evidence",
)
async def get_lead_facts_endpoint(
    lead_id: str,
    include_superseded: bool = Query(False, description="Include superseded/historical facts"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Retrieves all atomic qualification facts and evidence records for a lead."""
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.get_lead_facts(
        organization_id=org_id,
        lead_id=lead_id,
        include_superseded=include_superseded,
        broker=current_broker,
    )


@router.get(
    "/api/v1/leads/{lead_id}/qualification/conflicts",
    response_model=List[QualificationConflictDTO],
    summary="Get Lead Qualification Conflicts",
)
async def get_lead_conflicts_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Retrieves all detected evidence contradictions and their resolution states."""
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.get_lead_conflicts(
        organization_id=org_id, lead_id=lead_id, broker=current_broker
    )


@router.get(
    "/api/v1/leads/{lead_id}/qualification/history",
    response_model=List[QualificationAuditEventDTO],
    summary="Get Lead Qualification Audit Trail",
)
async def get_lead_qualification_history_endpoint(
    lead_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Retrieves the chronological audit event trail for a lead's qualification lifecycle."""
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.get_lead_audit_history(
        organization_id=org_id, lead_id=lead_id, limit=limit, broker=current_broker
    )


@router.get(
    "/api/v1/qualification/policies",
    response_model=List[QualificationPolicyDTO],
    summary="List Qualification Requirement Policies",
)
async def list_qualification_policies_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Lists active qualification criteria and requirement policies for the organization."""
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.list_policies(organization_id=org_id)


@router.post(
    "/api/v1/leads/{lead_id}/qualification/facts",
    response_model=QualificationFactDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Record a Qualification Fact",
)
async def record_fact_endpoint(
    lead_id: str,
    dto: QualificationFactCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Records a new atomic qualification fact with provenance."""
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.record_fact(
        organization_id=org_id,
        lead_id=lead_id,
        dto=dto,
        actor_type=QualificationAuditActorType.HUMAN,
        actor_id=str(current_broker.id),
        broker=current_broker,
    )


@router.post(
    "/api/v1/leads/{lead_id}/qualification/conflicts/{conflict_id}/resolve",
    response_model=QualificationConflictDTO,
    summary="Resolve Evidence Conflict",
)
async def resolve_conflict_endpoint(
    lead_id: str,
    conflict_id: str,
    dto: QualificationConflictResolveDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Resolves an open qualification evidence conflict."""
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.resolve_conflict(
        organization_id=org_id,
        lead_id=lead_id,
        conflict_id=conflict_id,
        dto=dto,
        actor_id=str(current_broker.id),
        broker=current_broker,
    )


@router.post(
    "/api/v1/leads/{lead_id}/qualification/override",
    response_model=QualificationSnapshotDTO,
    summary="Authorized Human Review Override",
)
async def apply_human_override_endpoint(
    lead_id: str,
    dto: QualificationHumanOverrideDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Applies an authorized human override to lead qualification state.
    Enforces RBAC and creates an immutable audit entry.
    """
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    actor_role = getattr(current_broker, "role", "broker")
    return await svc.apply_human_override(
        organization_id=org_id,
        lead_id=lead_id,
        dto=dto,
        actor_id=str(current_broker.id),
        actor_role=actor_role,
        broker=current_broker,
    )


@router.post(
    "/api/v1/leads/{lead_id}/qualification/extract",
    response_model=QualificationExtractionSummaryDTO,
    summary="Extract Qualification Facts from Conversations",
)
async def extract_lead_qualification_endpoint(
    lead_id: str,
    payload: QualificationExtractRequestDTO = QualificationExtractRequestDTO(),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Triggers AI / Heuristic qualification fact extraction from real lead conversation messages.
    Extracts structured facts with calibrated confidence, provenance, and conflict detection.
    The AI proposes facts; qualification state is evaluated deterministically by the policy engine.
    """
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.extract_and_ingest_from_lead_conversations(
        organization_id=org_id,
        lead_id=lead_id,
        message_id=payload.message_id,
        include_full_history=payload.include_full_history,
        actor_id=str(current_broker.id),
        broker=current_broker,
    )


@router.post(
    "/api/v1/leads/{lead_id}/qualification/evaluate",
    response_model=QualificationEvaluationResultDTO,
    summary="Deterministically Evaluate Lead Qualification Policy",
)
async def evaluate_lead_qualification_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Deterministically evaluates active qualification facts and conflicts against policy rules.
    Computes completeness, confidence, missing information, next best question, updates snapshot,
    and returns full decision result. Never accepts state from client.
    """
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.evaluate_lead_qualification(
        organization_id=org_id,
        lead_id=lead_id,
        actor_id=str(current_broker.id),
        broker=current_broker,
    )


@router.get(
    "/api/v1/leads/{lead_id}/qualification/missing",
    response_model=QualificationMissingInfoDTO,
    summary="Get Missing Qualification Fields and Question Prompts",
)
async def get_missing_qualification_info_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Retrieves the prioritized missing qualification requirements for a lead
    along with deterministic question templates for sales agents or AI copilot.
    """
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.get_missing_qualification_info(
        organization_id=org_id,
        lead_id=lead_id,
        broker=current_broker,
    )


# ─── Part 21.4.4 Qualification Conversation Endpoints ────────────────────────

@router.post(
    "/api/v1/leads/{lead_id}/qualification/conversation/start",
    response_model=QualificationConversationResponseDTO,
    summary="Start or Resume Lead Qualification Conversation",
)
async def start_qualification_conversation_endpoint(
    lead_id: str,
    payload: QualificationConversationStartDTO = QualificationConversationStartDTO(),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Initiates or resumes multi-turn qualification conversation.
    Evaluates current facts, determines the highest priority missing field,
    and returns a structured conversational question or terminal state.
    """
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.start_qualification_conversation(
        organization_id=org_id,
        lead_id=lead_id,
        start_dto=payload,
        broker=current_broker,
    )


@router.post(
    "/api/v1/leads/{lead_id}/qualification/conversation/message",
    response_model=QualificationConversationResponseDTO,
    summary="Process Customer Response in Qualification Conversation",
)
async def process_qualification_conversation_message_endpoint(
    lead_id: str,
    payload: QualificationConversationMessageDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Processes an inbound customer response in the qualification conversation:
    - Extracts structured facts with provenance (Part 21.4.2).
    - Checks for explicit human handoff triggers.
    - Re-evaluates deterministic policy state (Part 21.4.3).
    - Returns updated state, matched properties (if requested), and next question.
    """
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.process_customer_qualification_message(
        organization_id=org_id,
        lead_id=lead_id,
        msg_dto=payload,
        broker=current_broker,
    )


@router.get(
    "/api/v1/leads/{lead_id}/qualification/conversation/state",
    response_model=QualificationConversationStateDTO,
    summary="Get Active Qualification Conversation State",
)
async def get_qualification_conversation_state_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Retrieves the current qualification conversation state, history turns,
    fatigue attempt counters, missing requirements, and human handoff indicators.
    """
    svc = LeadQualificationDomainService(db)
    org_id = _get_org_id(current_broker)
    return await svc.get_qualification_conversation_state(
        organization_id=org_id,
        lead_id=lead_id,
        broker=current_broker,
    )



