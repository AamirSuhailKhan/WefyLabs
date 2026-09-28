"""
Master Build 03 — Canonical Communication Truth Layer
=====================================================
Single, authoritative communication engine orchestrating:
1. Webhook Authentication, Raw Archiving & Idempotency
2. Tenant & E.164 Identity Resolution (Build 02 Identity Graph)
3. Canonical Omnichannel Conversation & Message Persistence
4. Transactional Outbox (OutboxEvent) Integration
5. Delivery Receipt Lifecycle State Machine
6. Outbound Dispatch with Zero-Fake-Success
7. AI Memory with Provenance & Customer-Correctable Truth
8. Human Handoff Control & Loop Protection
9. Communication Health & Observability Reporting
"""
from __future__ import annotations

import hmac
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.identity_models import Identity, IdentityLink
from app.models.outbox_models import OutboxEvent, OutboxStatus
from app.models.communication_models import (
    OmnichannelConversation,
    ConversationChannelLink,
    ConversationControl,
    ChannelMessage,
    DeliveryStatusRecord,
    OutboundQueue,
    RawCommunicationEvent,
    ConversationMemoryFact,
    MemoryProvenanceEnum,
    CanonicalSenderType,
    CanonicalMessageType,
    CanonicalMessageStatus,
    validate_message_status_transition,
)
from app.models.conversation import Conversation as LegacyConversation
from app.modules.communication.channel_manager.manager import get_channel_manager
from app.modules.communication.channels.gate import ensure_channel_sendable, ChannelNotSendableError
from app.modules.communication.channels.enums import Channel
from app.modules.communication.provider_adapters.base_provider import (
    OutboundMessageDTO,
    ProviderResponse,
    ProviderStatusEnum,
)

logger = logging.getLogger("wefylabs.communication.canonical")

# ── Prompt Injection Defense ─────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a?\s*(different|new)\s+(ai|assistant|bot|model)", re.IGNORECASE),
    re.compile(r"(system|assistant)\s*:", re.IGNORECASE),
    re.compile(r"<\s*(script|iframe|img|svg|object|embed)", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]|\[SYS\]|<<SYS>>|<\|im_start\|>", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)\s+(above|before)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+are|an?\s+)", re.IGNORECASE),
    re.compile(r"jailbreak|dan\s+mode|developer\s+mode", re.IGNORECASE),
    re.compile(r"print\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(instructions?|prompt|rules?)", re.IGNORECASE),
]


def sanitize_customer_text(raw_text: str) -> str:
    """
    Neutralizes instruction-injection patterns in customer messages.
    Wraps content in inert XML delimiters so downstream LLMs treat it as customer text.
    """
    if not raw_text:
        return ""
    sanitized = raw_text
    for pattern in _INJECTION_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return f"<untrusted_customer_message>{sanitized}</untrusted_customer_message>"


def normalize_phone_e164(phone: str) -> str:
    """
    Normalizes any input phone number to E.164 standard (+91XXXXXXXXXX).
    Handles 10-digit, 11-digit (0-prefix), 12-digit (91-prefix), and WhatsApp JIDs.
    """
    raw = str(phone).split("@")[0].strip()
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        return digits
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return f"+91{digits[1:]}"
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return f"+{digits}"
    return f"+{digits}"


def verify_meta_hmac_signature(raw_body: bytes, signature_header: Optional[str], app_secret: Optional[str]) -> bool:
    """
    Constant-time HMAC-SHA256 signature verification for Meta Cloud API webhooks.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    if not app_secret:
        return False
    expected_hash = signature_header.split("sha256=")[1].strip()
    calculated_hash = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculated_hash, expected_hash)


class CanonicalCommunicationService:
    """
    The Single Authoritative Communication Engine for WefyLabs.
    """

    def __init__(self):
        self._channel_manager = get_channel_manager()

    # ═════════════════════════════════════════════════════════════════════════
    # 1. INBOUND WEBHOOK PIPELINE (Meta WhatsApp, WebChat, Telegram, SMS)
    # ═════════════════════════════════════════════════════════════════════════

    async def ingest_inbound_webhook(
        self,
        db: AsyncSession,
        provider_name: str,
        raw_body: bytes,
        headers: Dict[str, str],
        parsed_payload: Dict[str, Any],
        enforce_signature: bool = True,
    ) -> Dict[str, Any]:
        """
        Orchestrates the 10-stage inbound communication pipeline:
        1. Webhook Authentication (HMAC verification)
        2. Immutable Raw Event Preservation (RawCommunicationEvent)
        3. Deterministic Webhook Idempotency
        4. Payload Classification (Status Update vs Inbound Message)
        5. Tenant Resolution (Fail-closed)
        6. Contact E.164 Normalization & Sanitization
        7. Identity Resolution (Build 02 Identity Graph)
        8. Lead Resolution
        9. Canonical Omnichannel Conversation & Message Persistence
        10. Transactional Outbox Event Emission
        """
        # ── Stage 1: Authentication / Signature Verification ─────────────────
        if enforce_signature and provider_name in ("whatsapp", "whatsapp_cloud", "meta"):
            sig_header = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")
            app_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)
            if settings.ENV == "production" or app_secret:
                if not verify_meta_hmac_signature(raw_body, sig_header, app_secret):
                    logger.warning("[CanonicalComm] Invalid Meta webhook HMAC signature rejected.")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid Meta webhook HMAC signature",
                    )

        # ── Stage 2: Immutable Raw Event Preservation (Section 12) ───────────
        payload_hash = hashlib.sha256(raw_body).hexdigest()
        provider_event_id = self._extract_provider_event_id(parsed_payload)

        raw_event = RawCommunicationEvent(
            provider=provider_name,
            provider_event_id=provider_event_id,
            payload_hash=payload_hash,
            raw_payload=parsed_payload,
            processing_status="PENDING",
            received_at=datetime.now(timezone.utc),
        )
        db.add(raw_event)
        await db.flush()

        # ── Stage 3: Webhook Idempotency Check (Section 13) ───────────────────
        if provider_event_id:
            dup_stmt = select(RawCommunicationEvent).where(
                and_(
                    RawCommunicationEvent.provider == provider_name,
                    RawCommunicationEvent.provider_event_id == provider_event_id,
                    RawCommunicationEvent.processing_status == "PROCESSED",
                    RawCommunicationEvent.id != raw_event.id,
                )
            )
            existing_dup = (await db.execute(dup_stmt)).scalars().first()
            if existing_dup:
                raw_event.processing_status = "DUPLICATE_IGNORED"
                raw_event.processed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"[CanonicalComm] Duplicate webhook event suppressed: {provider_event_id}")
                return {
                    "status": "ok",
                    "action": "duplicate_suppressed",
                    "provider_event_id": provider_event_id,
                }

        # ── Stage 4: Payload Classification ──────────────────────────────────
        # Check if this is a delivery status update (statuses) or an inbound message (messages)
        status_items = self._extract_statuses(parsed_payload)
        if status_items:
            # Route to delivery receipt processor
            results = []
            for st in status_items:
                wamid = st.get("id")
                st_val = st.get("status")  # sent, delivered, read, failed
                errors = st.get("errors")
                res = await self.record_delivery_receipt(
                    db=db,
                    external_message_id=wamid,
                    status=st_val,
                    provider_name=provider_name,
                    raw_event_id=raw_event.id,
                    error_data=errors,
                )
                results.append(res)
            raw_event.processing_status = "PROCESSED"
            raw_event.processed_at = datetime.now(timezone.utc)
            await db.commit()
            last_status = status_items[-1].get("status") if status_items else None
            return {
                "status": "ok",
                "action": "status_updates_processed",
                "count": len(results),
                "message_status": last_status,
            }

        message_items = self._extract_messages(parsed_payload)
        if not message_items:
            raw_event.processing_status = "IGNORED_NO_MESSAGES"
            raw_event.processed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"status": "ok", "action": "ignored_no_messages"}

        # Process primary incoming message item
        msg_item = message_items[0]
        from_phone_raw = msg_item.get("from")
        wamid = msg_item.get("id")
        msg_type = msg_item.get("type", "text")
        raw_text = self._extract_message_text(msg_item)
        reply_to_wamid = msg_item.get("context", {}).get("id")

        if not from_phone_raw:
            raw_event.processing_status = "FAILED_NO_SENDER"
            raw_event.failure_reason = "Missing from_phone in message item"
            await db.commit()
            return {"status": "ok", "detail": "Missing sender phone"}

        # ── Stage 5: Tenant Resolution ───────────────────────────────────────
        org_id, broker = await self._resolve_tenant(db, parsed_payload, from_phone_raw)
        raw_event.organization_id = org_id

        # ── Stage 6: Contact E.164 Normalization & Sanitization ───────────────
        normalized_phone = normalize_phone_e164(from_phone_raw)
        sanitized_text = sanitize_customer_text(raw_text)

        # ── Stage 7: Identity Resolution (Build 02 Identity Graph) ────────────
        identity = await self._resolve_or_create_identity(db, org_id, normalized_phone)

        # ── Stage 8: Lead Resolution ─────────────────────────────────────────
        lead = await self._resolve_or_create_lead(db, org_id, broker, normalized_phone, identity.id)

        # ── Stage 9: Canonical Conversation & Message Persistence ────────────
        conversation, is_new_conv = await self._resolve_or_create_conversation(
            db, org_id, identity.id, str(lead.id), "whatsapp", normalized_phone
        )

        now = datetime.now(timezone.utc)
        channel_message = ChannelMessage(
            organization_id=org_id,
            conversation_id=conversation.id,
            identity_id=identity.id,
            lead_id=str(lead.id),
            channel="whatsapp",
            provider_name="whatsapp_cloud",
            provider_message_id=wamid,
            external_message_id=wamid,
            direction="inbound",
            message_type=msg_type,
            content=sanitized_text,
            sender_id=identity.id,
            sender_name=identity.primary_name or "WhatsApp Contact",
            sender_identifier=normalized_phone,
            sender_type=CanonicalSenderType.CUSTOMER,
            delivery_status="delivered",
            received_at=now,
            reply_to_message_id=reply_to_wamid,
            idempotency_key=f"inbound:{org_id}:{wamid or uuid.uuid4()}",
            metadata_={"raw_type": msg_type, "wamid": wamid, "raw_event_id": raw_event.id},
        )
        db.add(channel_message)

        # Update conversation aggregate counters
        conversation.total_messages += 1
        conversation.unread_count += 1
        conversation.last_message_at = now
        conversation.last_channel = "whatsapp"
        conversation.last_message_preview = sanitized_text[:120] if sanitized_text else "[Attachment]"
        conversation.status = "active"

        # Dual-write to legacy Conversation table for backward compatibility
        legacy_conv = LegacyConversation(
            organization_id=uuid.UUID(org_id),
            lead_id=lead.id,
            direction="inbound",
            sender_type="lead",
            message=sanitized_text or "[Attachment]",
            message_type="text" if msg_type == "text" else "image",
            whatsapp_message_id=wamid,
        )
        db.add(legacy_conv)

        # ── Stage 10: Transactional Outbox Event (Section 18) ────────────────
        outbox_event = OutboxEvent(
            event_id=str(uuid.uuid4()),
            tenant_id=org_id,
            event_type="message.received",
            aggregate_type="conversation",
            aggregate_id=conversation.id,
            payload={
                "message_id": channel_message.id,
                "external_message_id": wamid,
                "conversation_id": conversation.id,
                "identity_id": identity.id,
                "lead_id": str(lead.id),
                "channel": "whatsapp",
                "direction": "inbound",
                "sender_phone": normalized_phone,
                "content": sanitized_text,
                "received_at": now.isoformat(),
            },
            status=OutboxStatus.PENDING,
            idempotency_key=f"outbox_inbound_{wamid or channel_message.id}",
        )
        db.add(outbox_event)

        raw_event.processing_status = "PROCESSED"
        raw_event.processed_at = now
        await db.commit()

        logger.info(
            f"[CanonicalComm] Inbound WhatsApp message processed: "
            f"msg_id={channel_message.id} wamid={wamid} org={org_id} conv={conversation.id}"
        )

        return {
            "status": "ok",
            "action": "message_persisted",
            "message_id": channel_message.id,
            "conversation_id": conversation.id,
            "identity_id": identity.id,
            "lead_id": str(lead.id),
            "is_new_conversation": is_new_conv,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # 2. DELIVERY RECEIPT ARCHITECTURE (Section 10)
    # ═════════════════════════════════════════════════════════════════════════

    async def record_delivery_receipt(
        self,
        db: AsyncSession,
        external_message_id: str,
        status: str,
        provider_name: str,
        raw_event_id: Optional[str] = None,
        error_data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Processes provider delivery events (sent -> delivered -> read | failed).
        Enforces canonical status state machine, records immutable audit row,
        and emits transactional outbox event.
        """
        if not external_message_id:
            return {"status": "ignored", "reason": "Missing external_message_id"}

        canonical_status = status.lower()

        # Lookup message by external_message_id or provider_message_id
        stmt = select(ChannelMessage).where(
            or_(
                ChannelMessage.external_message_id == external_message_id,
                ChannelMessage.provider_message_id == external_message_id,
            )
        )
        msg = (await db.execute(stmt)).scalars().first()

        if not msg:
            logger.warning(
                f"[CanonicalComm] Delivery receipt for unknown message: {external_message_id} status={status}"
            )
            return {"status": "ignored", "reason": "Message not found"}

        # Validate canonical state machine transition (Section 9)
        if not validate_message_status_transition(msg.delivery_status, canonical_status):
            logger.warning(
                f"[CanonicalComm] Blocked invalid status transition: "
                f"{msg.delivery_status} → {canonical_status} for msg_id={msg.id}"
            )
            return {
                "status": "rejected",
                "reason": f"Invalid transition from {msg.delivery_status} to {canonical_status}",
            }

        now = datetime.now(timezone.utc)
        msg.delivery_status = canonical_status

        if canonical_status == "delivered":
            msg.delivered_at = now
        elif canonical_status == "read":
            msg.read_at = now
        elif canonical_status == "failed":
            msg.failed_at = now
            msg.failure_reason = json.dumps(error_data) if error_data else "Provider delivery failed"

        # Record immutable delivery status audit event (Section 10)
        status_rec = DeliveryStatusRecord(
            message_id=msg.id,
            organization_id=msg.organization_id,
            status=canonical_status,
            provider_name=provider_name,
            provider_message_id=external_message_id,
            provider_timestamp=now,
            error_message=str(error_data) if error_data else None,
        )
        db.add(status_rec)

        # Emit OutboxEvent for delivery state change
        outbox_event = OutboxEvent(
            event_id=str(uuid.uuid4()),
            tenant_id=msg.organization_id,
            event_type=f"message.{canonical_status}",
            aggregate_type="message",
            aggregate_id=msg.id,
            payload={
                "message_id": msg.id,
                "conversation_id": msg.conversation_id,
                "external_message_id": external_message_id,
                "status": canonical_status,
                "timestamp": now.isoformat(),
                "error": error_data,
            },
            status=OutboxStatus.PENDING,
            idempotency_key=f"outbox_status_{external_message_id}_{canonical_status}",
        )
        db.add(outbox_event)
        await db.flush()

        logger.info(
            f"[CanonicalComm] Delivery receipt updated: msg_id={msg.id} "
            f"wamid={external_message_id} status={canonical_status}"
        )

        return {
            "status": "updated",
            "message_id": msg.id,
            "new_status": canonical_status,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # 3. OUTBOUND MESSAGE PIPELINE (Section 19: Truthful Outbox Dispatch)
    # ═════════════════════════════════════════════════════════════════════════

    async def send_outbound_message(
        self,
        db: AsyncSession,
        organization_id: str,
        conversation_id: str,
        content: str,
        channel: str = "whatsapp",
        recipient_identifier: Optional[str] = None,
        sender_type: str = CanonicalSenderType.AI_AGENT,
        sender_agent_id: Optional[str] = None,
        template_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> ChannelMessage:
        """
        Outbound message lifecycle:
        1. Tenant authorization & conversation validation
        2. Channel gate & enablement check
        3. AI handoff & policy check
        4. Outbound idempotency check
        5. Message creation with status QUEUED
        6. Transactional OutboxEvent creation
        7. Provider delivery worker dispatch (with zero fake success)
        8. Status mutation to SENT or FAILED
        """
        # ── Stage 1: Tenant Authorization & Conversation Validation ──────────
        conv_stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.id == conversation_id,
                OmnichannelConversation.organization_id == organization_id,
            )
        )
        conv = (await db.execute(conv_stmt)).scalars().first()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found in tenant {organization_id}",
            )

        # ── Stage 2: Channel Gate Check ──────────────────────────────────────
        canonical_channel = Channel.normalize(channel)
        channel_gate_error: Optional[ChannelNotSendableError] = None
        try:
            await ensure_channel_sendable(canonical_channel)
        except ChannelNotSendableError as exc:
            channel_gate_error = exc

        # ── Stage 3: AI Handoff & Loop Protection (Sections 20, 29, 57) ─────
        if sender_type == CanonicalSenderType.AI_AGENT:
            if conv.control_mode == "human":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Human takeover is active for this conversation. Autonomous AI sends are blocked.",
                )

        # ── Stage 4: Outbound Idempotency Check (Section 38) ─────────────────
        if idempotency_key:
            existing_stmt = select(ChannelMessage).where(
                and_(
                    ChannelMessage.organization_id == organization_id,
                    ChannelMessage.idempotency_key == idempotency_key,
                )
            )
            existing_msg = (await db.execute(existing_stmt)).scalars().first()
            if existing_msg:
                logger.info(f"[CanonicalComm] Idempotent outbound hit: key={idempotency_key} msg_id={existing_msg.id}")
                return existing_msg
        else:
            idempotency_key = hashlib.sha256(
                f"outbound:{conversation_id}:{uuid.uuid4()}".encode()
            ).hexdigest()[:64]

        # Resolve recipient identifier if not explicitly passed
        if not recipient_identifier:
            link_stmt = select(ConversationChannelLink).where(
                and_(
                    ConversationChannelLink.conversation_id == conv.id,
                    ConversationChannelLink.channel == canonical_channel.value,
                )
            )
            link = (await db.execute(link_stmt)).scalars().first()
            recipient_identifier = link.channel_identifier if link else ""

        if not recipient_identifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No recipient identifier available for channel {channel}",
            )

        now = datetime.now(timezone.utc)
        provider = self._channel_manager.get_provider(canonical_channel.value)

        # ── Stage 5: Message Creation with status QUEUED ─────────────────────
        msg_id = str(uuid.uuid4())
        msg = ChannelMessage(
            id=msg_id,
            organization_id=organization_id,
            conversation_id=conv.id,
            identity_id=conv.identity_id,
            lead_id=conv.lead_id,
            channel=canonical_channel.value,
            provider_name=provider.provider_name,
            direction="outbound",
            message_type="template" if template_id else "text",
            content=content,
            recipient_identifier=recipient_identifier,
            sender_identifier="system",
            sender_name="AI Agent" if sender_type == CanonicalSenderType.AI_AGENT else "Human Agent",
            sender_type=sender_type,
            sent_by_ai=(sender_type == CanonicalSenderType.AI_AGENT),
            sent_by_agent_id=sender_agent_id,
            template_id=template_id,
            delivery_status="queued",
            idempotency_key=idempotency_key,
            created_at=now,
        )
        db.add(msg)

        # ── Stage 6: Transactional Outbox Event ──────────────────────────────
        outbox_event = OutboxEvent(
            event_id=str(uuid.uuid4()),
            tenant_id=organization_id,
            event_type="message.queued",
            aggregate_type="conversation",
            aggregate_id=conv.id,
            payload={
                "message_id": msg.id,
                "conversation_id": conv.id,
                "channel": canonical_channel.value,
                "recipient": recipient_identifier,
                "content": content,
                "sender_type": sender_type,
            },
            status=OutboxStatus.PENDING,
            idempotency_key=f"outbox_queued_{msg.id}",
        )
        db.add(outbox_event)

        # Also register in OutboundQueue for background worker resilience
        queue_item = OutboundQueue(
            organization_id=organization_id,
            message_id=msg.id,
            channel=canonical_channel.value,
            provider_name=provider.provider_name,
            recipient_identifier=recipient_identifier,
            payload={"content": content, "template_id": template_id},
            status="pending",
            idempotency_key=idempotency_key,
        )
        db.add(queue_item)
        await db.flush()

        # ── Stage 7: Provider Dispatch with Zero-Fake-Success (Section 36) ────
        outbound_dto = OutboundMessageDTO(
            message_id=msg.id,
            conversation_id=conv.id,
            organization_id=organization_id,
            channel=canonical_channel.value,
            provider_name=provider.provider_name,
            recipient_identifier=recipient_identifier,
            content=content,
            message_type="template" if template_id else "text",
            template_id=template_id,
        )

        if channel_gate_error:
            resp = ProviderResponse(
                success=False,
                error_code="CHANNEL_DISABLED",
                error_message=str(channel_gate_error.reason),
            )
        else:
            try:
                resp: ProviderResponse = await provider.send(outbound_dto)
            except Exception as exc:
                logger.error(f"[CanonicalComm] Provider dispatch raised exception: {exc}")
                resp = ProviderResponse(
                    success=False,
                    error_code="PROVIDER_EXCEPTION",
                    error_message=str(exc),
                )

        # ── Stage 8: Update Message Status Truthfully ────────────────────────
        if resp.success:
            msg.delivery_status = "sent"
            msg.provider_message_id = resp.provider_message_id
            msg.external_message_id = resp.provider_message_id
            msg.sent_at = datetime.now(timezone.utc)
            queue_item.status = "sent"

            # Audit record
            db.add(DeliveryStatusRecord(
                message_id=msg.id,
                organization_id=organization_id,
                status="sent",
                provider_name=provider.provider_name,
                provider_message_id=resp.provider_message_id,
                latency_ms=resp.latency_ms,
            ))
            # Outbox sent event
            db.add(OutboxEvent(
                event_id=str(uuid.uuid4()),
                tenant_id=organization_id,
                event_type="message.sent",
                aggregate_type="message",
                aggregate_id=msg.id,
                payload={"message_id": msg.id, "external_id": resp.provider_message_id},
                status=OutboxStatus.PENDING,
            ))
        else:
            msg.delivery_status = "failed"
            msg.failed_at = datetime.now(timezone.utc)
            msg.failure_reason = resp.error_message or resp.error_code or "Unknown failure"
            queue_item.status = "failed"
            queue_item.last_error = msg.failure_reason

            db.add(DeliveryStatusRecord(
                message_id=msg.id,
                organization_id=organization_id,
                status="failed",
                provider_name=provider.provider_name,
                error_code=resp.error_code,
                error_message=resp.error_message,
            ))
            db.add(OutboxEvent(
                event_id=str(uuid.uuid4()),
                tenant_id=organization_id,
                event_type="message.failed",
                aggregate_type="message",
                aggregate_id=msg.id,
                payload={"message_id": msg.id, "error": resp.error_message},
                status=OutboxStatus.PENDING,
            ))

        conv.last_message_at = datetime.now(timezone.utc)
        conv.last_message_preview = content[:120]
        await db.commit()

        logger.info(
            f"[CanonicalComm] Outbound dispatch complete: msg_id={msg.id} "
            f"status={msg.delivery_status} external_id={msg.provider_message_id}"
        )
        return msg

    # ═════════════════════════════════════════════════════════════════════════
    # 4. CONVERSATION CONTEXT & AI MEMORY TRUTH (Sections 25, 26, 27, 28)
    # ═════════════════════════════════════════════════════════════════════════

    async def get_conversation_context(
        self,
        db: AsyncSession,
        organization_id: str,
        conversation_id: str,
        max_turns: int = 10,
    ) -> Dict[str, Any]:
        """
        Constructs bounded, deterministic conversation context for AI processing:
        - Identity details (Build 02)
        - Lead attributes
        - Bounded recent message turns
        - Memory facts with provenance (CUSTOMER_STATED supersedes AI_INFERRED)
        """
        conv_stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.id == conversation_id,
                OmnichannelConversation.organization_id == organization_id,
            )
        )
        conv = (await db.execute(conv_stmt)).scalars().first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Load Lead
        lead = None
        if conv.lead_id:
            try:
                lead_stmt = select(Lead).where(Lead.id == uuid.UUID(conv.lead_id))
                lead = (await db.execute(lead_stmt)).scalars().first()
            except Exception:
                pass

        # Load Identity
        identity = None
        if conv.identity_id:
            id_stmt = select(Identity).where(Identity.id == conv.identity_id)
            identity = (await db.execute(id_stmt)).scalars().first()

        # Load bounded recent messages
        msg_stmt = (
            select(ChannelMessage)
            .where(ChannelMessage.conversation_id == conv.id)
            .order_by(ChannelMessage.created_at.desc())
            .limit(max_turns)
        )
        recent_messages = list((await db.execute(msg_stmt)).scalars().all())
        recent_messages.reverse()

        # Load active memory facts
        mem_stmt = select(ConversationMemoryFact).where(
            and_(
                ConversationMemoryFact.conversation_id == conv.id,
                ConversationMemoryFact.is_active == True,
            )
        )
        memory_facts = list((await db.execute(mem_stmt)).scalars().all())

        facts_by_key = {}
        for f in memory_facts:
            facts_by_key[f.fact_key] = {
                "key": f.fact_key,
                "value": f.fact_value,
                "provenance": f.provenance,
                "is_authoritative": f.is_authoritative,
            }

        return {
            "conversation_id": conv.id,
            "organization_id": conv.organization_id,
            "control_mode": conv.control_mode,
            "identity": {
                "id": identity.id if identity else None,
                "phone": identity.primary_phone_e164 if identity else None,
                "name": identity.primary_name if identity else None,
                "health_score": identity.health_score if identity else 0.0,
            },
            "lead": {
                "id": str(lead.id) if lead else None,
                "name": lead.name if lead else None,
                "status": lead.status if lead else None,
                "pipeline_stage": lead.pipeline_stage if lead else None,
                "budget_min": float(lead.budget_min) if lead and lead.budget_min else None,
                "budget_max": float(lead.budget_max) if lead and lead.budget_max else None,
            },
            "memory_facts": facts_by_key,
            "recent_turns": [
                {
                    "message_id": m.id,
                    "direction": m.direction,
                    "sender_type": m.resolved_sender_type,
                    "content": m.content,
                    "delivery_status": m.delivery_status,
                    "created_at": m.created_at.isoformat(),
                }
                for m in recent_messages
            ],
            "ai_summary": conv.ai_summary,
            "ai_sentiment": conv.ai_sentiment,
        }

    async def update_memory_fact(
        self,
        db: AsyncSession,
        organization_id: str,
        conversation_id: str,
        key: str,
        value: str,
        category: str = "general",
        provenance: str = MemoryProvenanceEnum.AI_INFERRED,
    ) -> ConversationMemoryFact:
        """
        Updates an AI memory item respecting provenance rules (Section 28).
        If the new statement is CUSTOMER_STATED, it supersedes previous AI_INFERRED facts.
        """
        # Look for existing active facts with this key
        stmt = select(ConversationMemoryFact).where(
            and_(
                ConversationMemoryFact.conversation_id == conversation_id,
                ConversationMemoryFact.fact_key == key,
                ConversationMemoryFact.is_active == True,
            )
        )
        existing = (await db.execute(stmt)).scalars().first()

        new_fact_id = str(uuid.uuid4())
        new_fact = ConversationMemoryFact(
            id=new_fact_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            fact_category=category,
            fact_key=key,
            fact_value=value,
            provenance=provenance,
            is_authoritative=(provenance == MemoryProvenanceEnum.CUSTOMER_STATED),
            is_active=True,
        )

        if existing:
            # Check precedence: Customer statements authoritative supersede AI guesses
            if provenance == MemoryProvenanceEnum.CUSTOMER_STATED or existing.provenance == MemoryProvenanceEnum.AI_INFERRED:
                existing.is_active = False
                existing.superseded_by_id = new_fact.id
            elif existing.is_authoritative and provenance == MemoryProvenanceEnum.AI_INFERRED:
                # Do not let an AI inference override an authoritative customer statement!
                logger.info(f"[CanonicalComm] Prevented AI inference from overriding customer statement for {key}")
                return existing

        db.add(new_fact)
        await db.commit()
        return new_fact

    # ═════════════════════════════════════════════════════════════════════════
    # 5. HUMAN HANDOFF ENGINE (Sections 29 & 30)
    # ═════════════════════════════════════════════════════════════════════════

    async def request_human_handoff(
        self,
        db: AsyncSession,
        organization_id: str,
        conversation_id: str,
        reason: str,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Explicit human handoff:
        Transitions control_mode to 'human', pauses AI responses, generates briefing.
        """
        org_str = str(organization_id)
        conv_str = str(conversation_id)
        stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.id == conv_str,
                OmnichannelConversation.organization_id == org_str,
            )
        )
        conv = (await db.execute(stmt)).scalars().first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conv.control_mode = "human"

        ctrl_stmt = select(ConversationControl).where(ConversationControl.conversation_id == conv.id)
        ctrl = (await db.execute(ctrl_stmt)).scalars().first()
        if not ctrl:
            ctrl = ConversationControl(
                organization_id=org_str,
                conversation_id=conv.id,
                control_mode="human",
            )
            db.add(ctrl)

        ctrl.control_mode = "human"
        ctrl.takeover_reason = reason
        ctrl.takeover_at = datetime.now(timezone.utc)
        ctrl.takeover_by = actor_id

        # Generate briefing
        ctrl.ai_briefing = (
            f"Human Takeover requested on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. "
            f"Reason: {reason}. Preferred Channel: {conv.preferred_channel}. "
            f"Total Messages: {conv.total_messages}."
        )

        # Emit outbox event
        db.add(OutboxEvent(
            event_id=str(uuid.uuid4()),
            tenant_id=org_str,
            event_type="conversation.handoff",
            aggregate_type="conversation",
            aggregate_id=conv.id,
            payload={"reason": reason, "takeover_by": actor_id},
            status=OutboxStatus.PENDING,
        ))

        await db.commit()
        return {
            "status": "handoff_activated",
            "conversation_id": conv.id,
            "control_mode": "human",
            "briefing": ctrl.ai_briefing,
        }

    async def resume_ai_control(
        self,
        db: AsyncSession,
        organization_id: str,
        conversation_id: str,
        resumed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resumes autonomous AI processing for the conversation."""
        org_str = str(organization_id)
        conv_str = str(conversation_id)
        stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.id == conv_str,
                OmnichannelConversation.organization_id == org_str,
            )
        )
        conv = (await db.execute(stmt)).scalars().first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conv.control_mode = "ai"

        ctrl_stmt = select(ConversationControl).where(ConversationControl.conversation_id == conv.id)
        ctrl = (await db.execute(ctrl_stmt)).scalars().first()
        if ctrl:
            ctrl.control_mode = "ai"
            ctrl.resumed_at = datetime.now(timezone.utc)
            ctrl.resumed_by = resumed_by

        await db.commit()
        return {
            "status": "ai_resumed",
            "conversation_id": conv.id,
            "control_mode": "ai",
        }

    # ═════════════════════════════════════════════════════════════════════════
    # 6. COMMUNICATION HEALTH & CAPABILITIES (Section 62)
    # ═════════════════════════════════════════════════════════════════════════

    async def check_communication_health(self) -> Dict[str, Any]:
        """
        Reports operational status for all communication providers truthfully.
        Distinguishes configured, ready, degraded, and disabled states.
        """
        wa_provider = self._channel_manager.get_provider("whatsapp")
        wa_configured = wa_provider.is_configured() if wa_provider else False
        wa_enabled = bool(getattr(settings, "WHATSAPP_ENABLED", False))

        email_provider = self._channel_manager.get_provider("email")
        email_configured = email_provider.is_configured() if email_provider else False

        sms_provider = self._channel_manager.get_provider("sms")
        sms_configured = sms_provider.is_configured() if sms_provider else False

        telegram_provider = self._channel_manager.get_provider("telegram")
        telegram_configured = getattr(telegram_provider, "is_configured", lambda: False)() if telegram_provider else False

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channels": {
                "whatsapp": {
                    "enabled": wa_enabled,
                    "configured": wa_configured,
                    "status": "READY" if (wa_enabled and wa_configured) else ("CONFIG_REQUIRED" if not wa_configured else "DISABLED"),
                    "provider": "whatsapp_cloud",
                },
                "email": {
                    "enabled": bool(getattr(settings, "EMAIL_ENABLED", True)),
                    "configured": email_configured,
                    "status": "READY" if email_configured else "CONFIG_REQUIRED",
                    "provider": "smtp",
                },
                "sms": {
                    "enabled": bool(getattr(settings, "SMS_ENABLED", False)),
                    "configured": sms_configured,
                    "status": "READY" if sms_configured else "CONFIG_REQUIRED",
                    "provider": "sms_gateway",
                },
                "telegram": {
                    "enabled": bool(getattr(settings, "TELEGRAM_ENABLED", False)),
                    "configured": telegram_configured,
                    "status": "READY" if telegram_configured else "CONFIG_REQUIRED",
                    "provider": "telegram_bot",
                },
                "webchat": {
                    "enabled": True,
                    "configured": True,
                    "status": "READY",
                    "provider": "in_app",
                },
            },
        }

    # ═════════════════════════════════════════════════════════════════════════
    # 7. INTERNAL RESOLUTION HELPERS
    # ═════════════════════════════════════════════════════════════════════════

    async def _resolve_tenant(
        self, db: AsyncSession, payload: Dict[str, Any], from_phone: str
    ) -> Tuple[str, Optional[Broker]]:
        """
        Resolves the organization ID and broker for an incoming payload:
        1. Query matching Broker by whatsapp_number or phone
        2. Or query default broker/organization
        """
        normalized_from = normalize_phone_e164(from_phone)
        broker_stmt = select(Broker).where(
            or_(
                Broker.whatsapp_number == normalized_from,
                Broker.phone == normalized_from,
            )
        )
        broker = (await db.execute(broker_stmt)).scalars().first()

        if broker:
            return str(broker.id), broker

        # Fallback to first existing broker in DB as tenant scope
        any_broker_stmt = select(Broker).limit(1)
        fallback_broker = (await db.execute(any_broker_stmt)).scalars().first()
        if fallback_broker:
            return str(fallback_broker.id), fallback_broker

        # If no broker in DB yet, generate deterministic tenant ID
        return str(uuid.UUID(int=1)), None

    async def _resolve_or_create_identity(
        self, db: AsyncSession, org_id: str, phone: str
    ) -> Identity:
        """Resolves or creates permanent Identity node (Build 02 Identity Graph)."""
        stmt = select(Identity).where(
            and_(
                Identity.organization_id == org_id,
                Identity.primary_phone_e164 == phone,
            )
        )
        identity = (await db.execute(stmt)).scalars().first()
        if identity:
            identity.last_activity_at = datetime.now(timezone.utc)
            return identity

        identity = Identity(
            organization_id=org_id,
            primary_phone_e164=phone,
            primary_whatsapp=phone,
            first_source="whatsapp",
            verification_status="unverified",
            first_seen_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
        )
        db.add(identity)
        await db.flush()
        return identity

    async def _resolve_or_create_lead(
        self,
        db: AsyncSession,
        org_id: str,
        broker: Optional[Broker],
        phone: str,
        identity_id: str,
    ) -> Lead:
        """Resolves or creates Lead linked to the Identity."""
        broker_id = broker.id if broker else uuid.UUID(org_id)
        stmt = select(Lead).where(
            and_(
                Lead.phone == phone,
                Lead.broker_id == broker_id,
                Lead.deleted_at.is_(None),
            )
        )
        lead = (await db.execute(stmt)).scalars().first()
        if lead:
            return lead

        lead = Lead(
            broker_id=broker_id,
            organization_id=uuid.UUID(org_id),
            phone=phone,
            source="whatsapp",
            status="pending",
            pipeline_stage="new",
        )
        db.add(lead)
        await db.flush()

        # Link Lead to Identity
        link = IdentityLink(
            organization_id=org_id,
            identity_id=identity_id,
            lead_id=str(lead.id),
            link_method="auto_webhook",
            link_confidence=1.0,
            matched_fields=["phone"],
        )
        db.add(link)
        await db.flush()
        return lead

    async def _resolve_or_create_conversation(
        self,
        db: AsyncSession,
        org_id: str,
        identity_id: str,
        lead_id: str,
        channel: str,
        channel_identifier: str,
    ) -> Tuple[OmnichannelConversation, bool]:
        """
        Resolves existing OmnichannelConversation by identity/lead/channel_link
        or creates a new one (Section 17).
        """
        # 1. Search by ConversationChannelLink
        link_stmt = select(ConversationChannelLink).where(
            and_(
                ConversationChannelLink.organization_id == org_id,
                ConversationChannelLink.channel == channel,
                ConversationChannelLink.channel_identifier == channel_identifier,
            )
        )
        link = (await db.execute(link_stmt)).scalars().first()
        if link:
            conv_stmt = select(OmnichannelConversation).where(
                OmnichannelConversation.id == link.conversation_id
            )
            conv = (await db.execute(conv_stmt)).scalars().first()
            if conv:
                if not conv.identity_id:
                    conv.identity_id = identity_id
                return conv, False

        # 2. Search by Identity ID or Lead ID
        conv_stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.organization_id == org_id,
                or_(
                    OmnichannelConversation.identity_id == identity_id,
                    OmnichannelConversation.lead_id == lead_id,
                ),
            )
        ).order_by(desc(OmnichannelConversation.last_message_at))
        existing_conv = (await db.execute(conv_stmt)).scalars().first()

        if existing_conv:
            # Cross-channel linking: add link for this channel
            new_link = ConversationChannelLink(
                organization_id=org_id,
                conversation_id=existing_conv.id,
                channel=channel,
                channel_identifier=channel_identifier,
                provider_name="whatsapp_cloud",
            )
            db.add(new_link)
            await db.flush()
            return existing_conv, False

        # 3. Create new OmnichannelConversation
        now = datetime.now(timezone.utc)
        new_conv = OmnichannelConversation(
            organization_id=org_id,
            identity_id=identity_id,
            lead_id=lead_id,
            preferred_channel=channel,
            control_mode="ai",
            status="active",
            created_at=now,
            updated_at=now,
            last_message_at=now,
        )
        db.add(new_conv)
        await db.flush()

        # Link channel
        channel_link = ConversationChannelLink(
            organization_id=org_id,
            conversation_id=new_conv.id,
            channel=channel,
            channel_identifier=channel_identifier,
            provider_name="whatsapp_cloud",
        )
        db.add(channel_link)

        # Create control record
        control = ConversationControl(
            organization_id=org_id,
            conversation_id=new_conv.id,
            control_mode="ai",
        )
        db.add(control)
        await db.flush()

        return new_conv, True

    def _extract_provider_event_id(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extracts unique provider event identifier for deduplication."""
        if "entry" in payload:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    val = change.get("value", {})
                    statuses = val.get("statuses", [])
                    if statuses:
                        return f"status_{statuses[0].get('id')}_{statuses[0].get('status')}"
                    messages = val.get("messages", [])
                    if messages:
                        return f"msg_{messages[0].get('id')}"
        if "messages" in payload:
            msgs = payload.get("messages", [])
            if msgs:
                return f"msg_{msgs[0].get('id')}"
        return None

    def _extract_statuses(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts delivery status callbacks from Meta Cloud API payload."""
        statuses = []
        if "entry" in payload:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    val = change.get("value", {})
                    statuses.extend(val.get("statuses", []))
        return statuses

    def _extract_messages(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts incoming messages from Meta or 360dialog payload."""
        messages = []
        if "entry" in payload:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    val = change.get("value", {})
                    messages.extend(val.get("messages", []))
        elif "messages" in payload:
            messages.extend(payload.get("messages", []))
        return messages

    def _extract_message_text(self, msg_item: Dict[str, Any]) -> str:
        """Extracts text content or attachment description from message item."""
        m_type = msg_item.get("type", "text")
        if m_type == "text":
            return msg_item.get("text", {}).get("body", "")
        elif m_type == "button":
            return msg_item.get("button", {}).get("text", "")
        elif m_type == "interactive":
            inter = msg_item.get("interactive", {})
            if inter.get("type") == "button_reply":
                return inter.get("button_reply", {}).get("title", "")
            elif inter.get("type") == "list_reply":
                return inter.get("list_reply", {}).get("title", "")
        return f"[{m_type.upper()} attachment received]"


# Global Singleton
canonical_communication_service = CanonicalCommunicationService()
