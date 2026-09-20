"""
Volume 2 PART 5 — Autonomous AI Sales Agent REST + WebSocket API Router
========================================================================
12 Production Endpoints:
- POST   /ai-agent/v1/message               (REST: Inbound omni-channel messaging, rate-limited)
- WS     /ai-agent/v1/ws/chat/{org}/{lead}  (WebSocket: Real-time streaming web chat)
- GET    /ai-agent/v1/sessions/{session_id}
- GET    /ai-agent/v1/sessions/{session_id}/history
- GET    /ai-agent/v1/sessions/{session_id}/qualification
- POST   /ai-agent/v1/sessions/{session_id}/escalate
- POST   /ai-agent/v1/sessions/{session_id}/human-reply (Human agent sends reply back)
- GET    /ai-agent/v1/escalations
- GET    /ai-agent/v1/decisions
- GET    /ai-agent/v1/tools/executions
- POST   /ai-agent/v1/prompts
- GET    /ai-agent/v1/monitoring/stats
- GET    /ai-agent/v1/llm/usage
- GET    /ai-agent/v1/channels               (List supported channels + config)
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.agent_models import (
    AgentSession, ConversationState, QualificationProfile, Escalation,
    DecisionRecord, ToolExecution, PromptVersion, LLMUsage, AgentConfiguration
)
from app.modules.ai_agent.conversation_manager.manager import (
    ConversationManager, IncomingMessage, OutgoingMessage
)
from app.modules.ai_agent.monitoring.tracker import AgentMonitoringTracker
from app.modules.ai_agent.websocket_handler import (
    websocket_chat_handler, check_rate_limit, ws_manager
)
from app.modules.ai_agent.channel_gateway.gateway import ChannelGateway

router = APIRouter(prefix="/ai-agent/v1", tags=["Autonomous AI Sales Agent"])
manager = ConversationManager()
tracker = AgentMonitoringTracker()
gateway = ChannelGateway()


# ─── Pydantic DTO Schemas ────────────────────────────────────────────────────

class MessageRequestDTO(BaseModel):
    lead_id: str
    organization_id: str
    channel: str = Field(default="web", description="whatsapp | telegram | web | email")
    content: str
    sender_phone: Optional[str] = None
    sender_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageResponseDTO(BaseModel):
    session_id: str
    lead_id: str
    content: str
    channel: str
    turn_index: int
    current_state: str
    decision_type: str
    escalated: bool
    escalation_id: Optional[str] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    safety_violations: Optional[List[str]] = None
    was_blocked: bool


class ForceEscalateDTO(BaseModel):
    reason: str = Field(default="manual_escalation")
    priority: str = Field(default="medium")
    notes: Optional[str] = None


class HumanReplyDTO(BaseModel):
    """Human agent sends a message into an escalated conversation."""
    content: str
    agent_name: Optional[str] = None
    resolve_escalation: bool = False
    resolution_notes: Optional[str] = None


class CreatePromptVersionDTO(BaseModel):
    prompt_key: str = Field(default="sales_agent_v1")
    organization_id: Optional[str] = None
    system_template: str
    notes: Optional[str] = None


# ─── 1. POST /message (rate-limited) ────────────────────────────────────────

@router.post("/message", response_model=MessageResponseDTO)
async def process_inbound_message(
    dto: MessageRequestDTO,
    db: AsyncSession = Depends(get_db)
):
    """
    Process an inbound message from any channel through the autonomous AI Sales Agent.
    Rate limited: 100 msg/min per organization, 30 msg/min per lead.
    """
    check_rate_limit(dto.organization_id, dto.lead_id)

    incoming = IncomingMessage(
        lead_id=dto.lead_id,
        organization_id=dto.organization_id,
        channel=dto.channel,
        content=dto.content,
        sender_phone=dto.sender_phone,
        sender_name=dto.sender_name,
        metadata=dto.metadata
    )
    try:
        outgoing: OutgoingMessage = await manager.process(db, incoming)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversation access denied") from exc
    return MessageResponseDTO(
        session_id=outgoing.session_id,
        lead_id=outgoing.lead_id,
        content=outgoing.content,
        channel=outgoing.channel,
        turn_index=outgoing.turn_index,
        current_state=outgoing.current_state,
        decision_type=outgoing.decision_type,
        escalated=outgoing.escalated,
        escalation_id=outgoing.escalation_id,
        tool_results=outgoing.tool_results,
        safety_violations=outgoing.safety_violations,
        was_blocked=outgoing.was_blocked
    )


# ─── 2. WebSocket /ws/chat/{organization_id}/{lead_id} ──────────────────────

@router.websocket("/ws/chat/{organization_id}/{lead_id}")
async def websocket_chat(
    websocket: WebSocket,
    organization_id: str,
    lead_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time WebSocket chat endpoint.
    Streams agent response tokens as they are generated.
    Sends tool_start/tool_end events for live UI status indicators.
    Reconnect-safe: restores session from DB automatically.
    """
    await websocket_chat_handler(websocket, organization_id, lead_id, db)


# ─── 3. GET /sessions/{session_id} ──────────────────────────────────────────

@router.get("/sessions/{session_id}")
async def get_session_status(session_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve session state, FSM position, buyer profile, and turn count."""
    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="AgentSession not found")
    return session


# ─── 4. GET /sessions/{session_id}/history ──────────────────────────────────

@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Full conversation turn history — customer messages + agent responses + FSM states."""
    result = await db.execute(
        select(ConversationState)
        .where(ConversationState.session_id == session_id)
        .order_by(ConversationState.turn_index)
        .limit(limit)
    )
    return result.scalars().all()


# ─── 5. GET /sessions/{session_id}/qualification ────────────────────────────

@router.get("/sessions/{session_id}/qualification")
async def get_session_qualification(session_id: str, db: AsyncSession = Depends(get_db)):
    """Live buyer qualification profile with completion percentage."""
    result = await db.execute(
        select(QualificationProfile).where(QualificationProfile.session_id == session_id)
    )
    qual = result.scalar_one_or_none()
    if not qual:
        raise HTTPException(status_code=404, detail="QualificationProfile not found")
    return qual


# ─── 6. POST /sessions/{session_id}/escalate ─────────────────────────────────

@router.post("/sessions/{session_id}/escalate")
async def force_session_escalation(
    session_id: str,
    dto: ForceEscalateDTO,
    db: AsyncSession = Depends(get_db)
):
    """Manually override: force human handoff for an active session."""
    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="AgentSession not found")

    ctx = await manager.context_builder.build(db, session)
    escalation = await manager.handoff_service.create_escalation(
        db=db, ctx=ctx, reason=dto.reason, priority=dto.priority, notes=dto.notes
    )
    session.escalated = True
    await db.commit()
    return escalation


# ─── 7. POST /sessions/{session_id}/human-reply ──────────────────────────────

@router.post("/sessions/{session_id}/human-reply")
async def human_agent_reply(
    session_id: str,
    dto: HumanReplyDTO,
    db: AsyncSession = Depends(get_db)
):
    """
    Human agent sends a message back into an escalated conversation.
    If resolve_escalation=True, closes the escalation and re-enables the AI.
    Broadcasts the reply to WebSocket if the lead has an active web chat connection.
    """
    from datetime import datetime, timezone
    from sqlalchemy import update

    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="AgentSession not found")

    # Log the human reply as a ConversationState turn
    turn_index = session.turn_count + 1
    human_turn = ConversationState(
        session_id=session_id,
        turn_index=turn_index,
        from_state=session.current_state,
        to_state=session.current_state,
        trigger="HUMAN_REPLY",
        transition_reason=f"Human agent: {dto.agent_name or 'Unknown'}",
        customer_message=None,
        agent_response=dto.content,
        metadata_json={"source": "human_agent", "agent_name": dto.agent_name},
    )
    db.add(human_turn)

    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(turn_count=turn_index, last_message_at=datetime.now(timezone.utc))
    )

    # Optionally resolve the escalation
    if dto.resolve_escalation:
        await db.execute(
            update(Escalation)
            .where(Escalation.session_id == session_id, Escalation.status == "pending")
            .values(
                status="resolved",
                resolved_at=datetime.now(timezone.utc),
                resolution_notes=dto.resolution_notes,
            )
        )
        # Re-enable AI for future messages
        session.escalated = False
        session.current_state = "follow_up"

    await db.commit()

    # Broadcast to WebSocket if connected
    import hashlib
    ws_key = hashlib.sha256(f"{session.organization_id}:{session.lead_id}".encode()).hexdigest()[:16]
    await ws_manager.send_json(ws_key, {
        "type": "human_message",
        "content": dto.content,
        "agent_name": dto.agent_name,
        "resolved": dto.resolve_escalation,
    })

    return {
        "session_id": session_id,
        "turn_index": turn_index,
        "human_reply_recorded": True,
        "escalation_resolved": dto.resolve_escalation,
    }


# ─── 8. GET /escalations ─────────────────────────────────────────────────────

@router.get("/escalations")
async def list_escalations(
    organization_id: str = Query(...),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List pending/active human handoff briefings for the broker dashboard."""
    query = select(Escalation).where(Escalation.organization_id == organization_id)
    if status_filter:
        query = query.where(Escalation.status == status_filter)
    if priority:
        query = query.where(Escalation.priority == priority)
    query = query.order_by(Escalation.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


# ─── 9. GET /decisions ──────────────────────────────────────────────────────

@router.get("/decisions")
async def audit_decisions(
    session_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Full AI decision reasoning chain — auditable by managers."""
    result = await db.execute(
        select(DecisionRecord)
        .where(DecisionRecord.session_id == session_id)
        .order_by(DecisionRecord.turn_index)
    )
    return result.scalars().all()


# ─── 10. GET /tools/executions ───────────────────────────────────────────────

@router.get("/tools/executions")
async def audit_tool_executions(
    session_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Tool execution audit log with source verification flags."""
    result = await db.execute(
        select(ToolExecution)
        .where(ToolExecution.session_id == session_id)
        .order_by(ToolExecution.turn_index)
    )
    return result.scalars().all()


# ─── 11. POST /prompts ────────────────────────────────────────────────────────

@router.post("/prompts")
async def create_prompt_version(
    dto: CreatePromptVersionDTO,
    db: AsyncSession = Depends(get_db)
):
    """Create a new versioned system prompt template for A/B testing and rollback."""
    # Deactivate previous version for this org+key
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(PromptVersion)
        .where(
            PromptVersion.prompt_key == dto.prompt_key,
            PromptVersion.organization_id == dto.organization_id,
            PromptVersion.is_active == True,
        )
        .values(is_active=False)
    )

    pv = PromptVersion(
        prompt_key=dto.prompt_key,
        organization_id=dto.organization_id,
        system_template=dto.system_template,
        notes=dto.notes,
        is_active=True,
    )
    db.add(pv)
    await db.commit()
    await db.refresh(pv)
    return pv


# ─── 12. GET /monitoring/stats ───────────────────────────────────────────────

@router.get("/monitoring/stats")
async def get_agent_kpi_stats(
    organization_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Real-time performance metrics — conversion, escalation, cost, and SLA compliance."""
    return await tracker.get_summary_stats(db, organization_id)


# ─── 13. GET /llm/usage ─────────────────────────────────────────────────────

@router.get("/llm/usage")
async def get_llm_usage_dashboard(
    organization_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Token usage and USD financial cost breakdown per provider and model."""
    result = await db.execute(
        select(LLMUsage)
        .where(LLMUsage.organization_id == organization_id)
        .order_by(desc(LLMUsage.created_at))
        .limit(100)
    )
    records = result.scalars().all()
    total_cost = sum(r.cost_usd for r in records)
    total_tokens = sum(r.total_tokens for r in records)
    return {
        "organization_id": organization_id,
        "sample_count": len(records),
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "records": records,
    }


# ─── 14. GET /channels ───────────────────────────────────────────────────────

@router.get("/channels")
async def list_supported_channels():
    """List all supported channels and their capabilities."""
    return {
        "supported_channels": [
            {"name": "web", "type": "REST + WebSocket", "streaming": True, "active": True},
            {"name": "whatsapp", "type": "WhatsApp Business API Webhook", "streaming": False, "active": True},
            {"name": "telegram", "type": "Telegram Bot API Webhook", "streaming": False, "active": True},
            {"name": "email", "type": "Email SMTP/IMAP", "streaming": False, "active": True},
            {"name": "voice", "type": "Voice STT/TTS (Future)", "streaming": True, "active": False},
            {"name": "sms", "type": "SMS Gateway (Future)", "streaming": False, "active": False},
            {"name": "instagram", "type": "Instagram DM (Future)", "streaming": False, "active": False},
        ],
        "note": "All active channels share the same ConversationManager engine.",
    }


# ─── 15. GET /sessions/{session_id}/shortlist ─────────────────────────────────

class AddShortlistDTO(BaseModel):
    property_id: str
    status: str = Field(default="shortlisted",
                        description="shortlisted | liked | rejected | visit_requested")
    notes: Optional[str] = None


@router.get("/sessions/{session_id}/shortlist")
async def get_session_shortlist(
    session_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    """Get buyer's shortlisted properties for this session."""
    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="AgentSession not found")

    from app.modules.ai_agent.tool_executor.services import ShortlistService
    svc = ShortlistService(db)
    return await svc.get(
        lead_id=session.lead_id,
        organization_id=session.organization_id,
        status_filter=status_filter,
    )


@router.post("/sessions/{session_id}/shortlist")
async def add_to_session_shortlist(
    session_id: str,
    dto: AddShortlistDTO,
    db: AsyncSession = Depends(get_db),
):
    """Add or update a property in the buyer's shortlist."""
    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="AgentSession not found")

    from app.modules.ai_agent.tool_executor.services import ShortlistService
    svc = ShortlistService(db)
    data = await svc.add(
        lead_id=session.lead_id,
        property_id=dto.property_id,
        status=dto.status,
        organization_id=session.organization_id,
        notes=dto.notes,
    )
    await db.commit()
    return data


# ─── 16. GET /sessions/{session_id}/comparison ───────────────────────────────

@router.get("/sessions/{session_id}/comparison")
async def compare_session_properties(
    session_id: str,
    property_ids: List[str] = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple properties side-by-side with verified data."""
    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="AgentSession not found")

    from app.modules.ai_agent.tool_executor.services import ComparisonService
    svc = ComparisonService(db)
    return await svc.compare(
        property_ids=property_ids[:4],  # Hard limit: 4 max
        organization_id=session.organization_id,
    )


# ─── 17. GET /slots/{organization_id} ────────────────────────────────────────

@router.get("/slots/{organization_id}")
async def get_viewing_slots(
    organization_id: str,
    property_id: Optional[str] = Query(None),
    days_ahead: int = Query(7, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Get available property viewing time slots (subject to calendar configuration)."""
    from app.modules.ai_agent.tool_executor.services import CalendarSlotService
    svc = CalendarSlotService(db)
    return await svc.get_available_slots(
        organization_id=organization_id,
        property_id=property_id,
        days_ahead=days_ahead,
    )
