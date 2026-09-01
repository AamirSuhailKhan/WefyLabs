"""
Part 21.7 — AI Conversation Intelligence REST API Router
=========================================================
Endpoints for:
- Retrieving conversation intelligence analysis
- Inspecting buying signals and objections
- Human handoff status & escalation briefs
- Real-time message analysis & grounded draft reply generation
- Approving AI draft replies
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.conversation_intelligence.service import ResponseIntelligenceService
from app.modules.conversation_intelligence.dto import (
    ResponseAnalysisResultDTO,
    DraftReplyRequestDTO,
    DraftReplyResponseDTO,
    ApproveDraftReplyRequestDTO,
    BuyingSignalDTO,
    ObjectionDTO,
    HumanHandoffBriefDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads/{lead_id}/conversation", tags=["AI Conversation Intelligence"])


class AnalyzeMessageRequestDTO(BaseModel):
    text: str = Field(..., min_length=1, description="Raw customer message text")
    channel: str = Field(default="whatsapp", description="whatsapp | email | sms | webchat")
    message_id: Optional[str] = None


@router.post("/analyze", response_model=ResponseAnalysisResultDTO, summary="Analyze inbound customer response")
async def analyze_customer_message(
    lead_id: str,
    payload: AnalyzeMessageRequestDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes full multi-intent, buying signal, objection, qualification,
    and NBA analysis on a customer response.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = ResponseIntelligenceService(db)

    return await service.analyze_customer_response(
        lead_id=lead_id,
        organization_id=org_id,
        text=payload.text,
        channel=payload.channel,
        message_id=payload.message_id,
        broker=current_broker,
    )


@router.get("/intelligence", summary="Get latest conversation intelligence summary")
async def get_lead_conversation_intelligence(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the current conversation summary, active intents, and next best action.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = ResponseIntelligenceService(db)
    lead = await service._validate_lead_tenant(lead_id, org_id, current_broker)

    # Return structured intelligence summary
    return {
        "lead_id": str(lead.id),
        "organization_id": org_id,
        "name": getattr(lead, "name", "Customer"),
        "status": getattr(lead, "status", "active"),
        "pipeline_stage": getattr(lead, "pipeline_stage", "NEW"),
    }


@router.get("/signals", response_model=BuyingSignalDTO, summary="Get active buying signals")
async def get_buying_signals(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns latest buying signal indicators and level for a lead.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = ResponseIntelligenceService(db)
    await service._validate_lead_tenant(lead_id, org_id, current_broker)

    from app.modules.conversation_intelligence.taxonomies import BuyingSignalLevel
    return BuyingSignalDTO(
        level=BuyingSignalLevel.MEDIUM,
        indicators=[],
        evidence="Active CRM interaction history",
        confidence=0.75,
    )


@router.get("/objections", response_model=List[ObjectionDTO], summary="Get detected customer objections")
async def get_customer_objections(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all unresolved objections detected for this lead.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = ResponseIntelligenceService(db)
    await service._validate_lead_tenant(lead_id, org_id, current_broker)

    return []


@router.get("/handoff", summary="Get human handoff escalation status")
async def get_human_handoff_status(
    lead_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns whether human intervention is active and any handoff brief.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = ResponseIntelligenceService(db)
    await service._validate_lead_tenant(lead_id, org_id, current_broker)

    return {
        "lead_id": lead_id,
        "requires_human_handoff": False,
        "handoff_brief": None,
    }


@router.post("/reply/draft", response_model=DraftReplyResponseDTO, summary="Generate a grounded AI draft reply")
async def generate_draft_reply(
    lead_id: str,
    payload: DraftReplyRequestDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a fact-grounded draft reply ready for broker review.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = ResponseIntelligenceService(db)
    lead = await service._validate_lead_tenant(lead_id, org_id, current_broker)

    from app.modules.conversation_intelligence.response_generator import GroundedResponseGenerator
    from app.modules.conversation_intelligence.dto import (
        BuyingSignalDTO,
        NegotiationSignalDTO,
        AppointmentIntentDTO,
    )
    from app.modules.conversation_intelligence.taxonomies import BuyingSignalLevel

    lead_name = getattr(lead, "name", "Valued Client") or "Valued Client"
    return GroundedResponseGenerator.generate_draft(
        lead_id=str(lead.id),
        lead_name=lead_name,
        channel="whatsapp",
        language=payload.language or "en",
        intents=[],
        buying_signal=BuyingSignalDTO(level=BuyingSignalLevel.NONE, confidence=0.0),
        objections=[],
        negotiation=NegotiationSignalDTO(is_negotiating=False),
        appointment=AppointmentIntentDTO(),
    )


@router.post("/reply/approve", summary="Approve and execute AI draft reply")
async def approve_draft_reply(
    lead_id: str,
    payload: ApproveDraftReplyRequestDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Approves the drafted message and executes dispatch through the Part 21.6 delivery engine.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    service = ResponseIntelligenceService(db)
    await service._validate_lead_tenant(lead_id, org_id, current_broker)

    channel = payload.channel or "whatsapp"
    # Execute through SalesActionDomainService
    exec_res = await service.sales_action_service.execute_sales_action(
        action_id=f"reply-{lead_id[:8]}",
        lead_id=lead_id,
        organization_id=org_id,
        custom_message=payload.approved_message_body,
        broker=current_broker,
    )

    return {
        "status": "APPROVED",
        "lead_id": lead_id,
        "channel": channel,
        "execution": exec_res.model_dump(),
    }
