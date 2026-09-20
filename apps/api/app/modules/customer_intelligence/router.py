"""
Canonical Customer Intelligence API Router
==========================================
Exposes canonical REST endpoints under /api/v1/customers for:
- Identity Resolution
- Customer Retrieval & Creation
- Structured Requirement Profile & Positive/Negative Preferences
- Conversation Creation & Retrieval
- Message Management with Canonical Sender Types
- 4-Tier Bounded Conversation Memory Retrieval
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.modules.customer_intelligence.service import CustomerIntelligenceService
from app.modules.customer_intelligence.schemas import (
    CustomerCreateDTO, CustomerResponse,
    IdentityResolutionRequest, IdentityResolutionResponse,
    RequirementProfileDTO, RequirementUpdateDTO,
    ConversationCreateDTO, ConversationResponse,
    MessageCreateDTO, MessageResponse,
    BoundedMemoryContextResponse
)

router = APIRouter(prefix="/customers", tags=["Customer Intelligence & Memory Foundation"])


# ─── 1. Identity Resolution Endpoint ─────────────────────────────────────────

@router.post("/resolve", response_model=IdentityResolutionResponse)
async def resolve_customer_identity(
    request: IdentityResolutionRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Deterministic identity resolution against existing tenant customers.
    Returns EXACT_MATCH, POSSIBLE_MATCH, or NO_MATCH.
    Prevents accidental merges across low-confidence candidates.
    """
    svc = CustomerIntelligenceService(db)
    return await svc.resolve_identity(str(current_broker.id), request)


# ─── 2. Customer Creation & Retrieval ────────────────────────────────────────

@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    dto: CustomerCreateDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Establishes a canonical customer identity record linked to tenant context.
    If an exact match on phone/email already exists, reuses the existing record.
    """
    svc = CustomerIntelligenceService(db)
    return await svc.create_customer(str(current_broker.id), dto, actor_id=str(current_broker.id))


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves canonical customer identity and CRM state."""
    svc = CustomerIntelligenceService(db)
    try:
        return await svc.get_customer(str(current_broker.id), customer_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found in this organization."
        )


# ─── 3. Requirement Profile & Preferences ────────────────────────────────────

@router.get("/{customer_id}/profile", response_model=RequirementProfileDTO)
async def get_customer_requirement_profile(
    customer_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the structured customer requirement profile, including positive
    and negative preferences, and the provenance origin for every field.
    """
    svc = CustomerIntelligenceService(db)
    try:
        return await svc.get_requirement_profile(str(current_broker.id), customer_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found."
        )


@router.patch("/{customer_id}/requirements", response_model=RequirementProfileDTO)
async def update_customer_requirements(
    customer_id: str,
    update_dto: RequirementUpdateDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Applies deterministic updates to customer requirements enforcing provenance rules:
    - Inferred AI observations CANNOT overwrite explicit customer statements.
    - Negative preferences are recorded as durable constraints.
    - Previous scalar values are superseded with full version audit trail.
    """
    svc = CustomerIntelligenceService(db)
    try:
        return await svc.update_requirements(
            str(current_broker.id),
            customer_id,
            update_dto,
            actor=str(current_broker.id)
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found."
        )


# ─── 4. Conversation Domain ──────────────────────────────────────────────────

@router.post("/{customer_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    customer_id: str,
    dto: ConversationCreateDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Creates a canonical conversation envelope for the customer."""
    svc = CustomerIntelligenceService(db)
    try:
        return await svc.create_conversation(str(current_broker.id), customer_id, dto)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found."
        )


@router.get("/{customer_id}/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    customer_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists all conversations for a customer within tenant scope."""
    svc = CustomerIntelligenceService(db)
    return await svc.get_conversations(str(current_broker.id), customer_id)


# ─── 5. Message Domain ───────────────────────────────────────────────────────

@router.post("/{customer_id}/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    customer_id: str,
    conversation_id: str,
    dto: MessageCreateDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a canonical message with sender_type (CUSTOMER, AI_AGENT, HUMAN_AGENT, SYSTEM).
    Redacts credentials and updates conversation metrics.
    """
    svc = CustomerIntelligenceService(db)
    try:
        return await svc.create_message(str(current_broker.id), customer_id, conversation_id, dto)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{customer_id}/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    customer_id: str,
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves paginated messages for a conversation."""
    svc = CustomerIntelligenceService(db)
    try:
        return await svc.get_messages(str(current_broker.id), customer_id, conversation_id, limit, offset)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─── 6. Bounded Memory Retrieval ─────────────────────────────────────────────

@router.get("/{customer_id}/memory", response_model=BoundedMemoryContextResponse)
async def get_bounded_memory(
    customer_id: str,
    conversation_id: Optional[str] = Query(None, description="Optional conversation UUID for session dialogue"),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the 4-tier bounded memory context:
    1. CURRENT_TURN: latest message turn
    2. CURRENT_SESSION: active dialogue window (last 6 messages)
    3. CUSTOMER_MEMORY: confirmed requirements, negative constraints, objections, property feedback
    4. CRM_MEMORY: pipeline stage, score, CRM metadata
    """
    svc = CustomerIntelligenceService(db)
    try:
        return await svc.get_bounded_memory(str(current_broker.id), customer_id, conversation_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
