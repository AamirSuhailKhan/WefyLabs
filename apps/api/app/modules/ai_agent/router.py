"""
Volume 2 PART 5 — Autonomous AI Sales Agent REST + WebSocket API Router

P0 Security Hardening (applied):
- ALL endpoints require authenticated principal via get_current_tenant.
- organization_id is ALWAYS derived from the JWT principal — never from the request body (IDOR fix).
- Destructive/control endpoints (execute-action, pause, resume, handoff, prompts, escalate) require MANAGER+.
- WebSocket chat accepts optional bearer token query param for browser clients.
- Tenant scoping enforced on all DB queries.

12 Production Endpoints:
- POST   /ai-agent/v1/message               (REST: Inbound omni-channel messaging, rate-limited)
- WS     /ai-agent/v1/ws/chat/{org}/{lead}  (WebSocket: Real-time streaming web chat)
- GET    /ai-agent/v1/sessions/{session_id}
- GET    /ai-agent/v1/sessions/{session_id}/history
- GET    /ai-agent/v1/sessions/{session_id}/qualification
- POST   /ai-agent/v1/sessions/{session_id}/escalate          [MANAGER+]
- POST   /ai-agent/v1/sessions/{session_id}/human-reply       [MANAGER+]
- GET    /ai-agent/v1/escalations
- GET    /ai-agent/v1/decisions
- GET    /ai-agent/v1/tools/executions
- POST   /ai-agent/v1/prompts                                  [MANAGER+]
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
from app.dependencies import get_current_tenant, get_current_broker, TenantContext
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

_MANAGER_ROLES = {"OWNER", "ADMIN", "MANAGER"}


def _require_manager(tenant: TenantContext) -> None:
    """Raise 403 if the caller does not hold a manager-level role."""
    if not tenant.role or tenant.role.upper() not in _MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or higher role required for this operation."
        )


async def _get_session_for_tenant(session_id: str, tenant: TenantContext, db: AsyncSession) -> AgentSession:
    """Resolve AgentSession and enforce tenant ownership."""
    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AgentSession not found")
    if str(session.organization_id) != tenant.organization_id:
        # Return 404 not 403 to avoid enumeration
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AgentSession not found")
    return session


# ─── Pydantic DTO Schemas ────────────────────────────────────────────────────

class MessageRequestDTO(BaseModel):
    lead_id: str
    channel: str = Field(default="web", description="whatsapp | telegram | web | email")
    content: str
    sender_phone: Optional[str] = None
    sender_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    # organization_id removed — derived from JWT principal


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
    system_template: str
    notes: Optional[str] = None
    # organization_id removed — derived from JWT principal


# ─── 1. POST /message (rate-limited) ────────────────────────────────────────

@router.post("/message", response_model=MessageResponseDTO)
async def process_inbound_message(
    dto: MessageRequestDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Process an inbound message from any channel through the autonomous AI Sales Agent.
    Rate limited: 100 msg/min per organization, 30 msg/min per lead.
    Organization context derived from authenticated JWT principal.
    """
    check_rate_limit(tenant.organization_id, dto.lead_id)

    incoming = IncomingMessage(
        lead_id=dto.lead_id,
        organization_id=tenant.organization_id,  # Server-side only
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
    token: Optional[str] = Query(default=None, description="Bearer token for browser WS auth"),
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time WebSocket chat endpoint.
    Authenticates via ?token=<jwt> query parameter (standard for browser WS).
    Validates that organization_id in path matches the authenticated principal's tenant.
    """
    # Validate token before accepting connection
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    from fastapi.security import HTTPAuthorizationCredentials
    from app.dependencies import get_current_broker
    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        broker = await get_current_broker(credentials=creds, db=db)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Validate that the caller's memberships include this organization
    from sqlalchemy import select as sa_select
    from app.models.organization import OrganizationMember
    result = await db.execute(
        sa_select(OrganizationMember.organization_id).where(
            OrganizationMember.broker_id == broker.id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    if not result.scalar_one_or_none():
        await websocket.close(code=4003, reason="Organization access denied")
        return

    await websocket_chat_handler(websocket, organization_id, lead_id, db)


# ─── 3. GET /sessions/{session_id} ──────────────────────────────────────────

@router.get("/sessions/{session_id}")
async def get_session_status(
    session_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve session state, FSM position, buyer profile, and turn count. Tenant-scoped."""
    return await _get_session_for_tenant(session_id, tenant, db)


# ─── 4. GET /sessions/{session_id}/history ──────────────────────────────────

@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = Query(50, le=200),
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Full conversation turn history. Validates tenant ownership of session."""
    await _get_session_for_tenant(session_id, tenant, db)

    result = await db.execute(
        select(ConversationState)
        .where(ConversationState.session_id == session_id)
        .order_by(ConversationState.turn_index)
        .limit(limit)
    )
    return result.scalars().all()


# ─── 5. GET /sessions/{session_id}/qualification ────────────────────────────

@router.get("/sessions/{session_id}/qualification")
async def get_session_qualification(
    session_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Live buyer qualification profile with completion percentage. Tenant-scoped."""
    await _get_session_for_tenant(session_id, tenant, db)

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
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Manually override: force human handoff for an active session. MANAGER+ required."""
    _require_manager(tenant)
    session = await _get_session_for_tenant(session_id, tenant, db)

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
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Human agent sends a message back into an escalated conversation. MANAGER+ required.
    If resolve_escalation=True, closes the escalation and re-enables the AI.
    """
    _require_manager(tenant)

    from datetime import datetime, timezone
    from sqlalchemy import update

    session = await _get_session_for_tenant(session_id, tenant, db)

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
        session.escalated = False
        session.current_state = "follow_up"

    await db.commit()

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
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """List pending/active human handoff briefings for the broker dashboard. Tenant-scoped."""
    query = select(Escalation).where(Escalation.organization_id == tenant.organization_id)
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
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Full AI decision reasoning chain — auditable by managers. Tenant-scoped."""
    await _get_session_for_tenant(session_id, tenant, db)

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
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Tool execution audit log with source verification flags. Tenant-scoped."""
    await _get_session_for_tenant(session_id, tenant, db)

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
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new versioned system prompt template for A/B testing and rollback. MANAGER+ required."""
    _require_manager(tenant)

    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(PromptVersion)
        .where(
            PromptVersion.prompt_key == dto.prompt_key,
            PromptVersion.organization_id == tenant.organization_id,
            PromptVersion.is_active == True,
        )
        .values(is_active=False)
    )

    pv = PromptVersion(
        prompt_key=dto.prompt_key,
        organization_id=tenant.organization_id,  # Server-side only
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
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Real-time performance metrics — conversion, escalation, cost, and SLA compliance."""
    return await tracker.get_summary_stats(db, tenant.organization_id)


# ─── 13. GET /llm/usage ─────────────────────────────────────────────────────

@router.get("/llm/usage")
async def get_llm_usage_dashboard(
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Token usage and USD financial cost breakdown per provider and model. Tenant-scoped."""
    result = await db.execute(
        select(LLMUsage)
        .where(LLMUsage.organization_id == tenant.organization_id)
        .order_by(desc(LLMUsage.created_at))
        .limit(100)
    )
    records = result.scalars().all()
    total_cost = sum(r.cost_usd for r in records)
    total_tokens = sum(r.total_tokens for r in records)
    return {
        "organization_id": tenant.organization_id,
        "sample_count": len(records),
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "records": records,
    }


# ─── 14. GET /channels ───────────────────────────────────────────────────────

@router.get("/channels")
async def list_supported_channels(
    tenant: TenantContext = Depends(get_current_tenant),
):
    """List all supported channels and their capabilities. Requires authentication."""
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
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get buyer's shortlisted properties for this session. Tenant-scoped."""
    session = await _get_session_for_tenant(session_id, tenant, db)

    from app.modules.ai_agent.tool_executor.services import ShortlistService
    svc = ShortlistService(db)
    return await svc.get(
        lead_id=session.lead_id,
        organization_id=tenant.organization_id,
        status_filter=status_filter,
    )


@router.post("/sessions/{session_id}/shortlist")
async def add_to_session_shortlist(
    session_id: str,
    dto: AddShortlistDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Add or update a property in the buyer's shortlist. Tenant-scoped."""
    session = await _get_session_for_tenant(session_id, tenant, db)

    from app.modules.ai_agent.tool_executor.services import ShortlistService
    svc = ShortlistService(db)
    data = await svc.add(
        lead_id=session.lead_id,
        property_id=dto.property_id,
        status=dto.status,
        organization_id=tenant.organization_id,
        notes=dto.notes,
    )
    await db.commit()
    return data


# ─── 16. GET /sessions/{session_id}/comparison ───────────────────────────────

@router.get("/sessions/{session_id}/comparison")
async def compare_session_properties(
    session_id: str,
    property_ids: List[str] = Query(...),
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple properties side-by-side with verified data. Tenant-scoped."""
    session = await _get_session_for_tenant(session_id, tenant, db)

    from app.modules.ai_agent.tool_executor.services import ComparisonService
    svc = ComparisonService(db)
    return await svc.compare(
        property_ids=property_ids[:4],  # Hard limit: 4 max
        organization_id=tenant.organization_id,
    )


# ─── 17. GET /slots/{organization_id} ────────────────────────────────────────

@router.get("/slots/{organization_id}")
async def get_viewing_slots(
    organization_id: str,
    property_id: Optional[str] = Query(None),
    days_ahead: int = Query(7, le=30),
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get available property viewing time slots. Enforces path org_id matches authenticated tenant."""
    if organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access denied.")

    from app.modules.ai_agent.tool_executor.services import CalendarSlotService
    svc = CalendarSlotService(db)
    return await svc.get_available_slots(
        organization_id=tenant.organization_id,
        property_id=property_id,
        days_ahead=days_ahead,
    )


# ─── Master Build 06 — Canonical Sales Agent Endpoints ───────────────────────

class AgentTurnRequestDTO(BaseModel):
    lead_id: str
    conversation_id: str
    customer_message: str
    actor_id: Optional[str] = "ai_agent"
    current_facts: Optional[Dict[str, Any]] = None
    is_human_active: bool = False
    is_paused: bool = False
    # organization_id removed — derived from JWT principal


class ProposeActionRequestDTO(BaseModel):
    lead_id: str
    customer_message: str
    qualification_facts: Optional[Dict[str, Any]] = None
    missing_fields: Optional[List[str]] = None
    is_human_active: bool = False
    is_paused: bool = False
    # organization_id removed — derived from JWT principal


class ExecuteActionRequestDTO(BaseModel):
    actor_id: str
    action_type: str
    parameters: Dict[str, Any]
    authorization_token: Optional[str] = None
    risk_tier: str = "MEDIUM"
    # organization_id removed — derived from JWT principal


class HandoffRequestDTO(BaseModel):
    conversation_id: str
    lead_id: str
    reason: str
    actor_id: Optional[str] = None
    # organization_id removed — derived from JWT principal


class PauseResumeRequestDTO(BaseModel):
    conversation_id: str
    reason: Optional[str] = "Human takeover requested"
    actor_id: Optional[str] = None
    # organization_id removed — derived from JWT principal


@router.post("/agent/turn")
async def execute_agent_turn(
    dto: AgentTurnRequestDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Executes a single governed sales turn using canonical SalesAgent. Tenant-scoped."""
    from app.modules.ai_agent.sales_agent import SalesAgent
    agent = SalesAgent(db)
    return await agent.process_turn(
        organization_id=tenant.organization_id,
        lead_id=dto.lead_id,
        conversation_id=dto.conversation_id,
        customer_message=dto.customer_message,
        actor_id=dto.actor_id or "ai_agent",
        current_facts=dto.current_facts,
        is_human_active=dto.is_human_active,
        is_paused=dto.is_paused,
    )


@router.post("/agent/propose-action")
async def propose_next_action(
    dto: ProposeActionRequestDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Evaluates Next Best Action and returns structured proposal without execution."""
    from app.modules.ai_agent.sales_agent import SalesAgent
    agent = SalesAgent(db)
    proposal = agent.propose_action(
        organization_id=tenant.organization_id,
        lead_id=dto.lead_id,
        customer_message=dto.customer_message,
        qualification_facts=dto.qualification_facts or {},
        missing_fields=dto.missing_fields,
        is_human_active=dto.is_human_active,
        is_paused=dto.is_paused,
    )
    return proposal.to_dict()


@router.post("/agent/execute-action")
async def execute_governed_action(
    dto: ExecuteActionRequestDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Executes an authorized action with single-use token verification. MANAGER+ required."""
    _require_manager(tenant)

    from app.modules.ai_agent.sales_agent import SalesAgent
    from app.modules.ai_agent.action_policy import ProposedActionDTO, NextBestActionType, ActionRiskTier
    agent = SalesAgent(db)
    try:
        action_type_enum = NextBestActionType(dto.action_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action_type: {dto.action_type}")

    try:
        risk_enum = ActionRiskTier(dto.risk_tier.upper())
    except ValueError:
        risk_enum = ActionRiskTier.MEDIUM

    proposal = ProposedActionDTO(
        action_type=action_type_enum,
        reason=dto.parameters.get("reason", "API requested action"),
        risk_tier=risk_enum,
        requires_authorization=True if dto.authorization_token else False,
        parameters=dto.parameters,
    )

    result = await agent.execute_authorized_action(
        organization_id=tenant.organization_id,
        actor_id=dto.actor_id,
        proposal=proposal,
        parameters=dto.parameters,
        authorization_token=dto.authorization_token,
    )
    return result.to_dict()


@router.post("/agent/handoff")
async def request_agent_handoff(
    dto: HandoffRequestDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Triggers human escalation and pauses AI autonomous outreach. MANAGER+ required."""
    _require_manager(tenant)

    from app.modules.ai_agent.sales_agent import SalesAgent
    agent = SalesAgent(db)
    return await agent.handoff(
        organization_id=tenant.organization_id,
        conversation_id=dto.conversation_id,
        lead_id=dto.lead_id,
        reason=dto.reason,
        actor_id=dto.actor_id,
    )


@router.post("/agent/pause")
async def pause_agent(
    dto: PauseResumeRequestDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Pauses autonomous AI activity on a conversation. MANAGER+ required."""
    _require_manager(tenant)

    from app.modules.ai_agent.sales_agent import SalesAgent
    agent = SalesAgent(db)
    return await agent.pause(
        organization_id=tenant.organization_id,
        conversation_id=dto.conversation_id,
        reason=dto.reason or "Human takeover",
        actor_id=dto.actor_id,
    )


@router.post("/agent/resume")
async def resume_agent(
    dto: PauseResumeRequestDTO,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Resumes autonomous AI activity after human control is released. MANAGER+ required."""
    _require_manager(tenant)

    from app.modules.ai_agent.sales_agent import SalesAgent
    agent = SalesAgent(db)
    return await agent.resume(
        organization_id=tenant.organization_id,
        conversation_id=dto.conversation_id,
        actor_id=dto.actor_id,
    )


@router.get("/agent/state")
async def get_agent_state(
    conversation_id: str = Query(...),
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Returns conversation state, control mode, and active agent status. Tenant-scoped."""
    from app.models.communication_models import OmnichannelConversation, ConversationControl
    res = await db.execute(
        select(OmnichannelConversation).where(
            OmnichannelConversation.id == conversation_id,
            OmnichannelConversation.organization_id == tenant.organization_id,  # Tenant-scoped
        )
    )
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    ctrl_res = await db.execute(
        select(ConversationControl).where(
            ConversationControl.conversation_id == conversation_id,
        )
    )
    ctrl = ctrl_res.scalar_one_or_none()
    control_mode = ctrl.control_mode if ctrl else "ai"
    return {
        "organization_id": tenant.organization_id,
        "conversation_id": conversation_id,
        "control_mode": control_mode,
        "status": conv.status,
        "is_ai_active": control_mode == "ai" and conv.status in ("active", "open"),
    }


@router.get("/agent/trace")
async def get_agent_traces(
    trace_id: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Retrieves immutable agent traces for debugging and governance. Tenant-scoped."""
    from app.modules.ai_agent.agent_trace import AgentTraceRecorder
    if trace_id:
        trace = AgentTraceRecorder.get_trace_by_id(trace_id)
        if not trace or trace.organization_id != tenant.organization_id:
            raise HTTPException(status_code=404, detail="Trace not found")
        return trace.to_dict()
    traces = AgentTraceRecorder.get_traces_for_org(tenant.organization_id)
    return [t.to_dict() for t in traces]
