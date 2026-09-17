import logging
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.dependencies import get_db, get_current_broker, get_optional_broker
from app.models.broker import Broker
from app.models.audit_log import AuditLog
from app.models.copilot_models import CopilotConversation, CopilotMessage
from app.services.copilot_orchestrator import CopilotOrchestratorService
from app.modules.copilot.engine.copilot_agent import CopilotAgentEngine
from app.common.redis.rate_limiter import check_rate_limit

logger = logging.getLogger("beetlelabs.copilot.router")

router = APIRouter(prefix="/copilot", tags=["AI Copilot Operating System"])


# ─── Pydantic Request Schemas ──────────────────────────────────────────────────

class CopilotQueryRequest(BaseModel):
    query: str
    route_path: str = "/dashboard"
    active_entity_id: Optional[str] = None
    conversation_id: Optional[str] = None
    history: Optional[List[dict]] = None
    confirmed_action: Optional[dict] = None


class CopilotActionRequest(BaseModel):
    action_type: str
    target_id: Optional[str] = None
    payload: Optional[dict] = None


class ActionConfirmRequest(BaseModel):
    confirmation_token: str
    tool_name: str
    arguments: Optional[dict] = None
    conversation_id: Optional[str] = None


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"
    route_context: Optional[str] = "/dashboard"


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


# ─── Copilot Conversation Endpoints ───────────────────────────────────────────

@router.get("/conversations")
async def list_copilot_conversations(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100)
):
    """Lists all persistent Copilot conversation sessions for the authenticated broker."""
    stmt = (
        select(CopilotConversation)
        .where(
            CopilotConversation.broker_id == current_broker.id,
            CopilotConversation.is_active.is_(True)
        )
        .order_by(desc(CopilotConversation.updated_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    convs = res.scalars().all()

    return [
        {
            "id": str(c.id),
            "title": c.title,
            "route_context": c.route_context,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        }
        for c in convs
    ]


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_copilot_conversation(
    req: CreateConversationRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Creates a fresh multi-turn Copilot conversation session."""
    org_id = getattr(current_broker, "organization_id", None) or str(current_broker.id)
    conv = CopilotConversation(
        id=uuid.uuid4(),
        organization_id=str(org_id),
        broker_id=current_broker.id,
        title=req.title or "New Conversation",
        route_context=req.route_context or "/dashboard",
        is_active=True
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return {
        "id": str(conv.id),
        "title": conv.title,
        "route_context": conv.route_context,
        "created_at": conv.created_at.isoformat()
    }


@router.get("/conversations/{conversation_id}")
async def get_copilot_conversation_messages(
    conversation_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves full message turn history for a persistent conversation session."""
    try:
        c_uuid = uuid.UUID(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")

    conv = await db.get(CopilotConversation, c_uuid)
    if not conv or conv.broker_id != current_broker.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    stmt_msgs = (
        select(CopilotMessage)
        .where(CopilotMessage.conversation_id == conv.id)
        .order_by(CopilotMessage.created_at.asc())
    )
    m_res = await db.execute(stmt_msgs)
    messages = m_res.scalars().all()

    return {
        "id": str(conv.id),
        "title": conv.title,
        "route_context": conv.route_context,
        "messages": [
            {
                "id": str(m.id),
                "sender": m.sender,
                "content": m.content,
                "reasoning": m.thought_reasoning,
                "tool_calls": m.tool_calls,
                "citations": [c.get("source") for c in (m.citations or []) if isinstance(c, dict)],
                "action_preview": m.action_preview,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }


@router.patch("/conversations/{conversation_id}")
async def rename_copilot_conversation(
    conversation_id: str,
    req: RenameConversationRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Renames an existing conversation title."""
    try:
        c_uuid = uuid.UUID(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")

    conv = await db.get(CopilotConversation, c_uuid)
    if not conv or conv.broker_id != current_broker.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv.title = req.title.strip()
    await db.commit()
    return {"id": str(conv.id), "title": conv.title}


@router.delete("/conversations/{conversation_id}")
async def delete_copilot_conversation(
    conversation_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Soft-deletes or purges a conversation session."""
    try:
        c_uuid = uuid.UUID(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format.")

    conv = await db.get(CopilotConversation, c_uuid)
    if not conv or conv.broker_id != current_broker.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    await db.delete(conv)
    await db.commit()
    return {"success": True, "message": "Conversation deleted."}


# ─── Query & Action Execution Endpoints ────────────────────────────────────────

@router.get("/suggested-actions")
async def get_copilot_suggested_actions(
    route_path: str = Query("/dashboard"),
    current_broker: Optional[Broker] = Depends(get_optional_broker)
):
    """Returns context-aware prompt action pills based on user route and live CRM state."""
    ctx_type = CopilotOrchestratorService.resolve_context_type(route_path)
    actions = CopilotOrchestratorService.get_suggested_actions(ctx_type)
    return {
        "route_path": route_path,
        "context_type": ctx_type.value,
        "suggested_actions": actions
    }


@router.post("/query")
async def execute_copilot_query_endpoint(
    req: CopilotQueryRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Executes a multi-turn, context-aware AI Copilot turn with tool calling & citations."""
    # ── Copilot rate limiting: 30 requests / minute / broker ─────────────────
    rate_key = f"broker:{current_broker.id}"
    if not check_rate_limit(rate_key, prefix="rl:copilot", limit=30, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many Copilot requests. Please wait a moment before trying again."
        )
    try:
        resp = await CopilotOrchestratorService.async_execute_copilot_query(
            db=db,
            broker=current_broker,
            query=req.query,
            route_path=req.route_path,
            conversation_id=req.conversation_id,
            history=req.history,
            active_entity_id=req.active_entity_id,
            confirmed_action=req.confirmed_action
        )
        return {
            "query": resp.query,
            "conversation_id": resp.conversation_id,
            "context_type": resp.context_type.value,
            "summary": resp.summary,
            "reasoning": resp.reasoning,
            "answer_markdown": resp.answer_markdown,
            "rich_cards": resp.rich_cards,
            "action_buttons": resp.action_buttons,
            "confidence_score": resp.confidence_score,
            "citations": resp.citations,
            "suggested_followups": resp.suggested_followups,
            "executed_tools": [
                {"tool_name": t.tool_name, "arguments": t.arguments} for t in resp.executed_tools
            ],
            "action_preview": resp.action_preview
        }
    except Exception as e:
        logger.error(f"[Copilot Execution Error]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Copilot Execution Error: {str(e)}")


@router.post("/actions/execute")
async def execute_copilot_action_endpoint(
    req: CopilotActionRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Executes a real CRM action triggered via 1-click Copilot action buttons."""
    res = await CopilotOrchestratorService.async_execute_crm_action(
        db=db,
        broker=current_broker,
        action_type=req.action_type,
        target_id=req.target_id,
        payload=req.payload or {}
    )
    # ── Audit log for write actions ──────────────────────────────────────────
    try:
        org_id = getattr(current_broker, "organization_id", None) or str(current_broker.id)
        audit = AuditLog(
            organization_id=org_id,
            actor_id=current_broker.id,
            actor_type="ai",
            action=f"copilot.action.{req.action_type.lower()}",
            resource_type="copilot_action",
            resource_id=req.target_id,
            changes={"action_type": req.action_type, "payload_keys": list((req.payload or {}).keys())},
        )
        db.add(audit)
        await db.commit()
    except Exception as audit_err:
        logger.warning(f"[Copilot Audit] Failed to write audit log: {audit_err}")
    return res


@router.post("/actions/confirm")
async def confirm_copilot_action_endpoint(
    req: ActionConfirmRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Confirms and securely executes a previewed high-risk / destructive action."""
    confirmed_payload = {
        "tool_name": req.tool_name,
        "arguments": req.arguments or {},
        "confirmation_token": req.confirmation_token
    }
    res = await CopilotOrchestratorService.async_execute_crm_action(
        db=db,
        broker=current_broker,
        action_type="CONFIRM_ACTION",
        payload=confirmed_payload
    )
    # ── Audit log confirmed write actions ────────────────────────────────────
    try:
        org_id = getattr(current_broker, "organization_id", None) or str(current_broker.id)
        audit = AuditLog(
            organization_id=org_id,
            actor_id=current_broker.id,
            actor_type="ai",
            action="copilot.action.confirmed",
            resource_type="copilot_action",
            resource_id=req.conversation_id,
            changes={"tool_name": req.tool_name, "argument_keys": list((req.arguments or {}).keys())},
        )
        db.add(audit)
        await db.commit()
    except Exception as audit_err:
        logger.warning(f"[Copilot Audit] Failed to write audit log: {audit_err}")
    return res
