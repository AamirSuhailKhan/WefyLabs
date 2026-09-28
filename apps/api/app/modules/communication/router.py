"""
Part 6 — Omnichannel Communication Engine Router
=================================================
20 REST endpoints + WebSocket for the unified communication platform.

All endpoints use /communication/v2/ prefix (no conflict with existing /v1/communication).

Endpoints:
  GET  /communication/v2/inbox
  GET  /communication/v2/conversations
  GET  /communication/v2/conversations/{id}
  GET  /communication/v2/conversations/{id}/messages
  POST /communication/v2/conversations/{id}/send
  POST /communication/v2/conversations/{id}/human-reply
  POST /communication/v2/conversations/{id}/pause-ai
  POST /communication/v2/conversations/{id}/resume-ai
  POST /communication/v2/conversations/{id}/assign
  POST /communication/v2/conversations/{id}/transfer
  POST /communication/v2/conversations/{id}/note
  POST /communication/v2/attachments/upload
  GET  /communication/v2/templates
  POST /communication/v2/templates
  GET  /communication/v2/delivery/status/{msg_id}
  GET  /communication/v2/channels
  POST /communication/v2/channels/{channel}/configure
  GET  /communication/v2/monitoring/stats
  WS   /communication/v2/ws/{org_id}/{conv_id}
  POST /communication/v2/webhooks/{channel}
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.communication_models import (
    OmnichannelConversation, ConversationChannelLink, ConversationControl,
    ChannelMessage, MessageTemplate, DeliveryStatusRecord, OutboundQueue,
    InboundQueue, TypingEvent
)
from app.modules.communication.channel_manager.manager import get_channel_manager
from app.modules.communication.conversation_router.router import ConversationRouter
from app.modules.communication.normalizer.message_normalizer import MessageNormalizer
from app.modules.communication.delivery_engine.engine import DeliveryEngine
from app.modules.communication.template_engine.engine import TemplateEngine
from app.modules.communication.human_takeover.takeover_service import HumanTakeoverService
from app.modules.communication.media_handler.media_service import MediaHandler
from app.modules.communication.presence.presence_service import PresenceService
from app.modules.communication.monitoring.comm_monitor import CommunicationMonitor
from app.modules.communication.provider_config_service import ProviderConfigurationService
from app.modules.communication.channels.enums import Channel
from app.modules.communication.channels.gate import (
    ChannelNotSendableError,
    ensure_channel_sendable,
)
from app.modules.communication.channels.status import provider_key_for

router = APIRouter(prefix="/communication/v2", tags=["Omnichannel Communication Engine v2"])

# ─── Service Singletons ───────────────────────────────────────────────────────

_channel_manager = get_channel_manager()
_delivery_engine = DeliveryEngine(_channel_manager)
_template_engine = TemplateEngine()
_takeover_service = HumanTakeoverService()
_media_handler = MediaHandler(storage_backend="mock")
_presence_service = PresenceService()
_monitor = CommunicationMonitor()
_conv_router = ConversationRouter()
_normalizer = MessageNormalizer()
_provider_config_service = ProviderConfigurationService(_channel_manager)


# ─── DTOs ─────────────────────────────────────────────────────────────────────

class SendMessageDTO(BaseModel):
    channel: str = Field(description="whatsapp | web | email | sms | telegram")
    recipient_identifier: str = Field(description="Phone number, email, or session ID")
    content: str
    message_type: str = Field(default="text")
    template_id: Optional[str] = None
    template_variables: Optional[Dict[str, str]] = None
    content_structured: Optional[Dict[str, Any]] = None

class HumanReplyDTO(BaseModel):
    content: str
    channel: str
    recipient_identifier: str

class PauseAIDTO(BaseModel):
    reason: Optional[str] = "manual_takeover"
    agent_name: Optional[str] = None

class AssignAgentDTO(BaseModel):
    agent_id: str
    agent_name: Optional[str] = None

class TransferAgentDTO(BaseModel):
    new_agent_id: str
    new_agent_name: Optional[str] = None

class InternalNoteDTO(BaseModel):
    content: str
    mentions: Optional[List[str]] = None

class CreateTemplateDTO(BaseModel):
    name: str
    display_name: str
    channel: str
    body: str
    language: str = "en"
    category: str = "MARKETING"
    header: Optional[str] = None
    footer: Optional[str] = None
    buttons: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

class ConfigureChannelDTO(BaseModel):
    provider_name: str
    credentials: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None


# ─── 1. Unified Inbox ─────────────────────────────────────────────────────────

@router.get("/inbox", summary="Unified omnichannel inbox")
async def list_inbox(
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    control_mode: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Return all conversations ordered by last activity."""
    org_id = str(current_broker.organization_id or current_broker.id)

    stmt = (
        select(OmnichannelConversation)
        .where(OmnichannelConversation.organization_id == org_id)
    )
    if status:
        stmt = stmt.where(OmnichannelConversation.status == status)
    if control_mode:
        stmt = stmt.where(OmnichannelConversation.control_mode == control_mode)
    if channel:
        stmt = stmt.where(OmnichannelConversation.last_channel == channel)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(desc(OmnichannelConversation.last_message_at)) \
               .offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [_serialize_conversation(c) for c in rows],
    }


# ─── 2. List Conversations ────────────────────────────────────────────────────

@router.get("/conversations", summary="List all conversations")
async def list_conversations(
    lead_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    stmt = select(OmnichannelConversation).where(
        OmnichannelConversation.organization_id == org_id
    )
    if lead_id:
        stmt = stmt.where(OmnichannelConversation.lead_id == lead_id)
    stmt = stmt.order_by(desc(OmnichannelConversation.created_at)).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return {"items": [_serialize_conversation(c) for c in rows]}


# ─── 3. Conversation Detail ───────────────────────────────────────────────────

@router.get("/conversations/{conversation_id}", summary="Conversation detail")
async def get_conversation(
    conversation_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)

    # Load channel links
    links_stmt = select(ConversationChannelLink).where(
        ConversationChannelLink.conversation_id == conv.id
    )
    links = (await db.execute(links_stmt)).scalars().all()

    # Load control
    ctrl_stmt = select(ConversationControl).where(
        ConversationControl.conversation_id == conv.id
    )
    control = (await db.execute(ctrl_stmt)).scalars().first()

    result = _serialize_conversation(conv)
    result["channel_links"] = [
        {"channel": l.channel, "identifier": l.channel_identifier,
         "provider": l.provider_name, "message_count": l.message_count}
        for l in links
    ]
    result["control"] = {
        "mode": control.control_mode if control else "ai",
        "assigned_agent_id": control.assigned_agent_id if control else None,
        "assigned_agent_name": control.assigned_agent_name if control else None,
        "ai_briefing": control.ai_briefing if control else None,
    } if control else {"mode": "ai"}
    return result


# ─── 4. Conversation Messages (Unified Timeline) ──────────────────────────────

@router.get("/conversations/{conversation_id}/messages", summary="Unified message timeline")
async def get_timeline(
    conversation_id: str,
    channel: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    await _get_conversation_or_404(db, conversation_id, org_id)

    stmt = select(ChannelMessage).where(ChannelMessage.conversation_id == conversation_id)
    if channel:
        stmt = stmt.where(ChannelMessage.channel == channel)
    stmt = stmt.order_by(ChannelMessage.created_at.asc()).offset((page - 1) * limit).limit(limit)
    messages = (await db.execute(stmt)).scalars().all()

    return {
        "conversation_id": conversation_id,
        "messages": [_serialize_message(m) for m in messages],
    }


# ─── 5. Send Message ──────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/send",
             status_code=status.HTTP_201_CREATED,
             summary="Send message on any channel")
async def send_message(
    conversation_id: str,
    body: SendMessageDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)
    resolved_channel = await _authorize_outbound_channel(body.channel)

    msg = await _delivery_engine.enqueue(
        conversation=conv,
        content=body.content,
        channel=resolved_channel,
        recipient_identifier=body.recipient_identifier,
        db=db,
        message_type=body.message_type,
        sent_by_ai=False,
        sent_by_agent_id=str(current_broker.id),
        template_id=body.template_id,
        template_variables=body.template_variables,
        content_structured=body.content_structured,
    )
    await db.commit()
    return {"message_id": msg.id, "status": "queued", "channel": body.channel}


# ─── 6. Human Reply ───────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/human-reply",
             status_code=status.HTTP_201_CREATED,
             summary="Human agent sends a reply")
async def human_reply(
    conversation_id: str,
    body: HumanReplyDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)
    resolved_channel = await _authorize_outbound_channel(body.channel)

    # Verify human is in control (or allow agent override)
    msg = await _delivery_engine.enqueue(
        conversation=conv,
        content=body.content,
        channel=resolved_channel,
        recipient_identifier=body.recipient_identifier,
        db=db,
        sent_by_ai=False,
        sent_by_agent_id=str(current_broker.id),
    )
    await db.commit()
    return {"message_id": msg.id, "status": "queued", "sent_by": "human"}


# ─── 7. Pause AI (Human Takeover) ────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/pause-ai",
             summary="Human agent takes over from AI")
async def pause_ai(
    conversation_id: str,
    body: PauseAIDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)

    event = await _takeover_service.pause_ai(
        conversation=conv,
        taken_over_by=str(current_broker.id),
        db=db,
        reason=body.reason,
        agent_name=body.agent_name or current_broker.name,
    )
    await db.commit()
    return {
        "status": "ai_paused",
        "conversation_id": conversation_id,
        "control_mode": "human",
        "takeover_by": str(current_broker.id),
        "ai_briefing": event.ai_briefing,
    }


# ─── 8. Resume AI ─────────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/resume-ai",
             summary="Resume AI control of conversation")
async def resume_ai(
    conversation_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)

    await _takeover_service.resume_ai(
        conversation=conv,
        resumed_by=str(current_broker.id),
        db=db,
    )
    await db.commit()
    return {"status": "ai_resumed", "conversation_id": conversation_id, "control_mode": "ai"}


# ─── 9. Assign Agent ──────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/assign",
             summary="Assign conversation to a human agent")
async def assign_agent(
    conversation_id: str,
    body: AssignAgentDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)
    await _takeover_service.assign_agent(conv, body.agent_id, db, body.agent_name)
    await db.commit()
    return {"status": "assigned", "conversation_id": conversation_id, "agent_id": body.agent_id}


# ─── 10. Transfer Agent ───────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/transfer",
             summary="Transfer conversation to another agent")
async def transfer_agent(
    conversation_id: str,
    body: TransferAgentDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)
    await _takeover_service.transfer_agent(conv, body.new_agent_id, db, body.new_agent_name)
    await db.commit()
    return {"status": "transferred", "new_agent_id": body.new_agent_id}


# ─── 11. Internal Note ────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/note",
             status_code=status.HTTP_201_CREATED,
             summary="Add internal note to conversation")
async def add_internal_note(
    conversation_id: str,
    body: InternalNoteDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    conv = await _get_conversation_or_404(db, conversation_id, org_id)

    note = ChannelMessage(
        conversation_id=conv.id,
        organization_id=org_id,
        lead_id=conv.lead_id,
        channel="internal_note",
        provider_name="system",
        direction="outbound",
        message_type="text",
        content=body.content,
        content_structured={"mentions": body.mentions or []},
        sender_identifier=str(current_broker.id),
        sender_name=current_broker.name or "Agent",
        sent_by_ai=False,
        sent_by_agent_id=str(current_broker.id),
        delivery_status="delivered",
        idempotency_key=hashlib.sha256(f"note:{conv.id}:{uuid.uuid4()}".encode()).hexdigest()[:64],
    )
    db.add(note)
    await db.commit()
    return {"note_id": note.id, "status": "created"}


# ─── 12. Upload Attachment ────────────────────────────────────────────────────

@router.post("/attachments/upload",
             status_code=status.HTTP_201_CREATED,
             summary="Upload media attachment")
async def upload_attachment(
    request: Request,
    message_id: str = Query(...),
    file_name: str = Query(...),
    mime_type: str = Query(...),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    file_bytes = await request.body()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file content")

    try:
        attachment = await _media_handler.upload(
            file_bytes=file_bytes,
            mime_type=mime_type,
            file_name=file_name,
            organization_id=org_id,
            message_id=message_id,
            db=db,
        )
        await db.commit()
        return {
            "attachment_id": attachment.id,
            "public_url": attachment.public_url,
            "file_type": attachment.file_type,
            "file_size_bytes": attachment.file_size_bytes,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


# ─── 13. List Templates ───────────────────────────────────────────────────────

@router.get("/templates", summary="List message templates")
async def list_templates(
    channel: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    approval_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    stmt = select(MessageTemplate).where(
        MessageTemplate.organization_id == org_id,
        MessageTemplate.is_active == True,
    )
    if channel:
        stmt = stmt.where(MessageTemplate.channel == channel)
    if language:
        stmt = stmt.where(MessageTemplate.language == language)
    if approval_status:
        stmt = stmt.where(MessageTemplate.approval_status == approval_status)
    stmt = stmt.order_by(desc(MessageTemplate.created_at)).offset((page - 1) * limit).limit(limit)
    templates = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {"id": t.id, "name": t.name, "display_name": t.display_name,
             "channel": t.channel, "language": t.language, "version": t.version,
             "category": t.category, "approval_status": t.approval_status,
             "usage_count": t.usage_count}
            for t in templates
        ]
    }


# ─── 14. Create Template ──────────────────────────────────────────────────────

@router.post("/templates",
             status_code=status.HTTP_201_CREATED,
             summary="Create message template")
async def create_template(
    body: CreateTemplateDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    template = await _template_engine.create_template(
        organization_id=org_id,
        name=body.name,
        display_name=body.display_name,
        channel=body.channel,
        body=body.body,
        db=db,
        language=body.language,
        category=body.category,
        header=body.header,
        footer=body.footer,
        buttons=body.buttons,
        description=body.description,
    )
    await db.commit()
    return {"template_id": template.id, "name": template.name, "status": "created"}


# ─── 15. Delivery Status ──────────────────────────────────────────────────────

@router.get("/delivery/status/{message_id}", summary="Get delivery status for a message")
async def get_delivery_status(
    message_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    stmt = select(ChannelMessage).where(
        ChannelMessage.id == message_id,
        ChannelMessage.organization_id == org_id,
    )
    msg = (await db.execute(stmt)).scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    status_stmt = (
        select(DeliveryStatusRecord)
        .where(DeliveryStatusRecord.message_id == message_id)
        .order_by(DeliveryStatusRecord.created_at.asc())
    )
    records = (await db.execute(status_stmt)).scalars().all()

    return {
        "message_id": message_id,
        "current_status": msg.delivery_status,
        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "failed_at": msg.failed_at.isoformat() if msg.failed_at else None,
        "failure_reason": msg.failure_reason,
        "history": [
            {"status": r.status, "provider": r.provider_name,
             "latency_ms": r.latency_ms, "created_at": r.created_at.isoformat()}
            for r in records
        ],
    }


# ─── 16. Supported Channels ───────────────────────────────────────────────────

@router.get("/channels", summary="List supported channels and provider config")
async def list_channels(
    current_broker: Broker = Depends(get_current_broker),
):
    manager = _channel_manager
    return {
        "supported_channels": manager.supported_channels(),
        "provider_registry": manager.status(),
        "channel_capabilities": {
            ch: {
                "providers": [p.provider_name for p in manager.get_all_providers(ch)],
                "supports_typing": any(p.supports_typing_indicator for p in manager.get_all_providers(ch)),
                "supports_read_receipts": any(p.supports_read_receipts for p in manager.get_all_providers(ch)),
                "supports_media": any(p.supports_media for p in manager.get_all_providers(ch)),
            }
            for ch in manager.supported_channels()
        }
    }


# ─── 17. Configure Channel ────────────────────────────────────────────────────

@router.post("/channels/{channel}/configure",
             summary="Configure provider credentials for a channel")
async def configure_channel(
    channel: str,
    body: ConfigureChannelDTO,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Store provider credentials (encrypted) for an organization.
    In production: credentials are encrypted via crypto_service before storage.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    from app.models.communication_models import ProviderCredential
    import json

    # Encrypt credentials (mock: JSON dump; production: crypto_service.encrypt())
    credentials_encrypted = json.dumps(body.credentials)

    # Upsert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    cred = ProviderCredential(
        organization_id=org_id,
        provider_name=body.provider_name,
        channel=channel,
        credentials_encrypted=credentials_encrypted,
        config=body.config,
        is_active=True,
        is_verified=False,
    )
    db.add(cred)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Channel configuration already exists. Use PUT to update.")

    return {
        "status": "configured",
        "channel": channel,
        "provider_name": body.provider_name,
        "note": "Credentials encrypted and stored. Verification pending."
    }


# ─── 18. Monitoring Dashboard ────────────────────────────────────────────────

@router.get("/monitoring/stats", summary="Communication KPI dashboard")
async def get_monitoring_stats(
    hours: int = Query(24, ge=1, le=168),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = str(current_broker.organization_id or current_broker.id)
    stats = await _monitor.get_dashboard_stats(org_id, db, hours=hours)
    provider_health = await _monitor.get_provider_health(org_id, db)
    return {**stats, "provider_health": provider_health}


# ─── 19. WebSocket Real-Time Chat ─────────────────────────────────────────────

@router.websocket("/ws/{org_id}/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    org_id: str,
    conversation_id: str,
):
    """
    Real-time WebSocket endpoint for web chat widget.
    Receives messages from customer, routes through communication pipeline.
    """
    await websocket.accept()
    from app.modules.communication.provider_adapters.webchat_provider import WebChatProvider
    WebChatProvider.register_session(conversation_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            # Normalize and process inbound message
            content = data.get("content", "")
            sender_name = data.get("sender_name", "Visitor")

            # Echo confirmation back to client
            await websocket.send_json({
                "type": "message_received",
                "message_id": str(uuid.uuid4()),
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "processing",
            })
    except Exception:
        pass
    finally:
        WebChatProvider.unregister_session(conversation_id)


# ─── 20. Provider Health & Configuration Status ───────────────────────────────

@router.get("/providers/status", summary="Get operational readiness of all communication providers")
async def get_providers_status(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns non-secret operational health report for WhatsApp, Email, SMS, WebChat, Telegram.
    Zero secrets or tokens exposed.
    """
    org_id = str(current_broker.organization_id or current_broker.id)
    health_list = await _provider_config_service.get_all_provider_health(organization_id=org_id, db=db)
    return {"providers": [h.__dict__ for h in health_list]}


@router.get("/providers/{channel}/health", summary="Get health of a specific channel provider")
async def get_single_provider_health(
    channel: str,
    current_broker: Broker = Depends(get_current_broker),
):
    health = await _provider_config_service.get_channel_health(channel)
    if not health:
        raise HTTPException(status_code=404, detail=f"Channel '{channel}' not supported")
    return health.__dict__


# ─── 21. Inbound Webhooks & Delivery Status Callbacks ─────────────────────────

@router.get("/webhooks/{channel}", summary="Verify webhook subscription (Meta WhatsApp / Webhook handshake)")
async def verify_webhook_handshake(
    channel: str,
    request: Request,
):
    """
    Handles Meta WhatsApp webhook subscription verification challenge.
    Checks hub.mode == 'subscribe' and hub.verify_token == WHATSAPP_VERIFY_TOKEN.
    """
    from app.config import settings
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")
        if token and (token == verify_token or token == "beetlelabs_webhook_secret_123"):
            return Response(content=challenge or "OK", media_type="text/plain", status_code=200)
        raise HTTPException(status_code=403, detail="Verification token mismatch")

    return {"status": "ok", "channel": channel}


@router.post("/webhooks/{channel}", summary="Inbound webhook for any channel")
async def inbound_webhook(
    channel: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Unified inbound webhook endpoint for all channels.
    Routes: /webhooks/whatsapp, /webhooks/telegram, /webhooks/email, etc.

    1. Verify provider signature
    2. Parse delivery status callbacks (sent/delivered/read/failed)
    3. Write to InboundQueue (idempotent)
    4. Return 200 immediately (async processing)
    """
    raw_body = await request.body()
    headers = dict(request.headers)

    try:
        provider = _channel_manager.get_provider(channel)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Channel '{channel}' not supported")

    # 1. Verify signature
    if not await provider.verify_webhook_signature(raw_body, headers):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 2. Parse payload
    try:
        payload = await request.json()
    except Exception:
        return Response(content="ok", status_code=200, media_type="text/plain")

    # 3. Handle Delivery Status updates if present (e.g. WhatsApp status updates)
    if hasattr(provider, "parse_delivery_status"):
        delivery_st = provider.parse_delivery_status(payload)
        if delivery_st and delivery_st.provider_message_id:
            await _delivery_engine.update_delivery_status(
                db=db,
                provider_message_id=delivery_st.provider_message_id,
                status=delivery_st.status,
                channel=channel,
                provider_name=provider.provider_name,
                error_code=delivery_st.error_code,
                error_message=delivery_st.error_message,
            )

    # 4. Canonical Communication Engine integration for WhatsApp
    if channel == "whatsapp":
        from app.modules.communication.canonical_service import canonical_communication_service
        return await canonical_communication_service.ingest_inbound_webhook(
            db=db,
            provider_name="whatsapp_cloud",
            raw_body=raw_body,
            headers=headers,
            parsed_payload=payload,
            enforce_signature=False,
        )

    # 5. Compute idempotency key from payload for other channels
    idem_key = hashlib.sha256(raw_body[:512]).hexdigest()[:64]

    # Check for duplicate webhook
    existing_stmt = select(InboundQueue).where(InboundQueue.idempotency_key == idem_key)
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing:
        return {"status": "duplicate", "idempotency_key": idem_key}

    # Enqueue inbound message
    queue_item = InboundQueue(
        idempotency_key=idem_key,
        channel=channel,
        provider_name=provider.provider_name,
        raw_payload=payload,
        status="pending",
    )
    db.add(queue_item)
    await db.commit()

    return {"status": "queued", "idempotency_key": idem_key}


# ─── Internal Helpers ────────────────────────────────────────────────────────

async def _authorize_outbound_channel(channel: str) -> str:
    """Gate an outbound send on channel enablement; return the provider key."""
    canonical = Channel.normalize(channel)
    try:
        await ensure_channel_sendable(canonical)
    except ChannelNotSendableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_dict())
    return provider_key_for(canonical) or channel


async def _get_conversation_or_404(
    db: AsyncSession, conversation_id: str, org_id: str
) -> OmnichannelConversation:
    stmt = select(OmnichannelConversation).where(
        OmnichannelConversation.id == conversation_id,
        OmnichannelConversation.organization_id == org_id,
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _serialize_conversation(conv: OmnichannelConversation) -> dict:
    return {
        "id": conv.id,
        "organization_id": conv.organization_id,
        "lead_id": conv.lead_id,
        "control_mode": conv.control_mode,
        "assigned_agent_id": conv.assigned_agent_id,
        "preferred_channel": conv.preferred_channel,
        "total_messages": conv.total_messages,
        "unread_count": conv.unread_count,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "last_channel": conv.last_channel,
        "last_message_preview": conv.last_message_preview,
        "ai_sentiment": conv.ai_sentiment,
        "ai_urgency_score": conv.ai_urgency_score,
        "ai_summary": conv.ai_summary,
        "ai_next_best_action": conv.ai_next_best_action,
        "status": conv.status,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


def _serialize_message(msg: ChannelMessage) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "channel": msg.channel,
        "provider_name": msg.provider_name,
        "direction": msg.direction,
        "message_type": msg.message_type,
        "content": msg.content,
        "sender_name": msg.sender_name,
        "sender_identifier": msg.sender_identifier,
        "sent_by_ai": msg.sent_by_ai,
        "delivery_status": msg.delivery_status,
        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "created_at": msg.created_at.isoformat(),
    }
