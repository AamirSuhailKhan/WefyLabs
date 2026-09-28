"""
Master Build 04 — WhatsApp Inbound Message Pipeline
====================================================
Production-grade pipeline for processing inbound WhatsApp messages end-to-end.

PIPELINE STAGES:
  1. NORMALIZE   — Sender phone normalized to E.164
  2. DEDUPLICATE — Idempotency on WhatsApp message_id fingerprint
  3. ROUTE       — Lead resolved from normalized phone within tenant scope
  4. SANITIZE    — Prompt-injection defense on message content
  5. ANALYZE     — Deterministic intent/signal detection (no LLM for routing)
  6. SESSION     — Turn appended to bounded session memory
  7. HANDOFF_CHECK — Check if human takeover is active
  8. DISPATCH    — CUSTOMER_MESSAGE_RECEIVED event → autonomous loop

INVARIANTS:
  1. Tenant scope is ALWAYS from the webhook credential config, never from body.
  2. Lead lookup is by normalized E.164 phone within broker scope.
  3. Unknown senders → HUMAN_REVIEW path (never fail silently).
  4. Message text NEVER becomes an LLM instruction verbatim.
  5. All stages are individually timed for latency observability.
"""
from __future__ import annotations

import re
import uuid
import time
import logging
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead

logger = logging.getLogger(__name__)

# ── Prompt injection patterns ─────────────────────────────────────────────────
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


def sanitize_inbound_text(raw_text: str) -> str:
    """
    Neutralize prompt injection patterns in inbound message text.
    Wrapped in inert XML delimiters so any remaining text cannot escape context.
    """
    sanitized = raw_text
    for pattern in _INJECTION_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return f"<untrusted_customer_message>{sanitized}</untrusted_customer_message>"


def compute_message_fingerprint(
    broker_id: str, sender_phone: str, whatsapp_message_id: str
) -> str:
    """Deterministic deduplication fingerprint for an inbound message."""
    raw = f"{broker_id}::{sender_phone}::{whatsapp_message_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize_phone_e164(phone: str) -> str:
    """
    Normalize to E.164 format.
    Handles Indian 10-digit, 11-digit (0-prefix), 12-digit (91-prefix), WhatsApp identifiers.
    """
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+"):
        return digits
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return f"+91{digits[1:]}"
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return f"+{digits}"
    return f"+{digits}"


# ── Pipeline Result DTO ───────────────────────────────────────────────────────

class InboundPipelineResultDTO:
    """Complete result of processing one inbound WhatsApp message."""
    __slots__ = (
        "pipeline_id", "broker_id", "lead_id", "whatsapp_message_id",
        "fingerprint", "stage_reached", "success", "duplicate_suppressed",
        "lead_unknown", "handoff_required", "draft_reply_queued",
        "analysis_result", "session_context", "error_message",
        "stage_timings_ms", "total_elapsed_ms",
    )

    def __init__(self, broker_id: str, whatsapp_message_id: str, fingerprint: str):
        self.pipeline_id = str(uuid.uuid4())
        self.broker_id = broker_id
        self.whatsapp_message_id = whatsapp_message_id
        self.fingerprint = fingerprint
        self.lead_id: Optional[str] = None
        self.stage_reached: str = "START"
        self.success: bool = False
        self.duplicate_suppressed: bool = False
        self.lead_unknown: bool = False
        self.handoff_required: bool = False
        self.draft_reply_queued: bool = False
        self.analysis_result: Optional[Dict[str, Any]] = None
        self.session_context: Optional[Dict[str, Any]] = None
        self.error_message: Optional[str] = None
        self.stage_timings_ms: Dict[str, float] = {}
        self.total_elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "broker_id": self.broker_id,
            "lead_id": self.lead_id,
            "whatsapp_message_id": self.whatsapp_message_id,
            "fingerprint": self.fingerprint[:16] + "...",
            "stage_reached": self.stage_reached,
            "success": self.success,
            "duplicate_suppressed": self.duplicate_suppressed,
            "lead_unknown": self.lead_unknown,
            "handoff_required": self.handoff_required,
            "draft_reply_queued": self.draft_reply_queued,
            "analysis_result": self.analysis_result,
            "session_context": self.session_context,
            "error_message": self.error_message,
            "stage_timings_ms": self.stage_timings_ms,
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
        }


# ── In-process Deduplication Store ───────────────────────────────────────────

class InboundMessageDeduplicator:
    """
    Bounded in-memory deduplication for inbound WhatsApp messages.
    Production deployment: replace with Redis SETNX + 24h TTL.
    """
    MAX_CACHE_SIZE = 10_000

    def __init__(self):
        self._seen: set[str] = set()

    def is_duplicate(self, fingerprint: str) -> bool:
        return fingerprint in self._seen

    def mark_seen(self, fingerprint: str) -> None:
        if len(self._seen) > self.MAX_CACHE_SIZE:
            self._seen.clear()
        self._seen.add(fingerprint)


# Singleton deduplicator (process-scoped; replace with Redis in production)
_global_deduplicator = InboundMessageDeduplicator()


# ── Main Pipeline Service ─────────────────────────────────────────────────────

class WhatsAppInboundPipeline:
    """
    Production WhatsApp inbound message processing pipeline.

    Usage:
        pipeline = WhatsAppInboundPipeline(db_session)
        result = await pipeline.process(
            broker_id="uuid-string",
            organization_id="uuid-string-or-none",
            sender_phone="+919876543210",
            whatsapp_message_id="wamid.xxx",
            raw_text="I'm interested in the 2BHK apartment",
        )
    """

    def __init__(self, db: AsyncSession, deduplicator: Optional[InboundMessageDeduplicator] = None):
        self.db = db
        self._dedup = deduplicator or _global_deduplicator

    async def process(
        self,
        broker_id: str,
        sender_phone: str,
        whatsapp_message_id: str,
        raw_text: str,
        organization_id: Optional[str] = None,
        channel_metadata: Optional[Dict[str, Any]] = None,
    ) -> InboundPipelineResultDTO:
        """
        Full pipeline execution.
        Each stage is timed individually. Failure at any stage short-circuits.
        """
        overall_start = time.perf_counter()
        fingerprint = compute_message_fingerprint(broker_id, sender_phone, whatsapp_message_id)
        result = InboundPipelineResultDTO(broker_id, whatsapp_message_id, fingerprint)

        try:
            # ── Stage 1: NORMALIZE ───────────────────────────────────────────
            t0 = time.perf_counter()
            normalized_phone = normalize_phone_e164(sender_phone)
            result.stage_reached = "NORMALIZE"
            result.stage_timings_ms["NORMALIZE"] = (time.perf_counter() - t0) * 1000

            # ── Stage 2: DEDUPLICATE ─────────────────────────────────────────
            t0 = time.perf_counter()
            if self._dedup.is_duplicate(fingerprint):
                result.duplicate_suppressed = True
                result.stage_reached = "DEDUPLICATE"
                result.success = True
                result.stage_timings_ms["DEDUPLICATE"] = (time.perf_counter() - t0) * 1000
                logger.info(f"[WA_PIPELINE] Duplicate suppressed: {fingerprint[:16]}...")
                return result
            self._dedup.mark_seen(fingerprint)
            result.stage_reached = "DEDUPLICATE"
            result.stage_timings_ms["DEDUPLICATE"] = (time.perf_counter() - t0) * 1000

            # ── Stage 3: ROUTE (lead resolution) ────────────────────────────
            t0 = time.perf_counter()
            lead = await self._resolve_lead(broker_id, normalized_phone)
            result.stage_reached = "ROUTE"
            result.stage_timings_ms["ROUTE"] = (time.perf_counter() - t0) * 1000

            if lead is None:
                result.lead_unknown = True
                result.handoff_required = True
                result.success = True  # pipeline succeeded, routes to human
                logger.warning(
                    f"[WA_PIPELINE] Unknown sender {normalized_phone[:7]}... → HUMAN_REVIEW"
                )
                return result

            result.lead_id = str(lead.id)
            # Use lead's organization_id if available, else broker_id for scoping
            effective_org_id = (
                str(lead.organization_id) if lead.organization_id else broker_id
            )

            # ── Stage 4: SANITIZE ────────────────────────────────────────────
            t0 = time.perf_counter()
            sanitized_text = sanitize_inbound_text(raw_text)
            result.stage_reached = "SANITIZE"
            result.stage_timings_ms["SANITIZE"] = (time.perf_counter() - t0) * 1000

            # ── Stage 5: ANALYZE ─────────────────────────────────────────────
            t0 = time.perf_counter()
            analysis = self._analyze_message(
                lead_id=str(lead.id),
                broker_id=broker_id,
                sanitized_text=sanitized_text,
            )
            result.analysis_result = analysis
            result.stage_reached = "ANALYZE"
            result.stage_timings_ms["ANALYZE"] = (time.perf_counter() - t0) * 1000

            # ── Stage 6: SESSION (append turn) ──────────────────────────────
            t0 = time.perf_counter()
            from app.modules.conversation_intelligence.session_service import (
                ConversationSessionService, ConversationTurn
            )
            session_svc = ConversationSessionService(self.db)
            turn = ConversationTurn(
                direction="inbound",
                channel="whatsapp",
                content_summary=analysis.get("content_summary", "customer message"),
                detected_intents=analysis.get("detected_intents", []),
                buying_signal_level=analysis.get("buying_signal_level"),
            )
            session = await session_svc.append_turn(effective_org_id, str(lead.id), turn)
            result.session_context = session.to_context_summary()
            result.stage_reached = "SESSION"
            result.stage_timings_ms["SESSION"] = (time.perf_counter() - t0) * 1000

            # ── Stage 7: HANDOFF CHECK ───────────────────────────────────────
            t0 = time.perf_counter()
            if session.handoff_requested or session.autonomy_paused:
                result.handoff_required = True
                result.success = True
                result.stage_reached = "HANDOFF_CHECK"
                result.stage_timings_ms["HANDOFF_CHECK"] = (time.perf_counter() - t0) * 1000
                logger.info(
                    f"[WA_PIPELINE] Session handoff/paused → HUMAN_REVIEW lead={result.lead_id[:8]}..."
                )
                return result

            if analysis.get("requires_human_handoff", False):
                result.handoff_required = True
                await session_svc.mark_handoff(effective_org_id, str(lead.id))
            result.stage_reached = "HANDOFF_CHECK"
            result.stage_timings_ms["HANDOFF_CHECK"] = (time.perf_counter() - t0) * 1000

            # ── Stage 8: AUTONOMOUS LOOP DISPATCH ───────────────────────────
            t0 = time.perf_counter()
            if not result.handoff_required:
                await self._dispatch_to_autonomous_loop(
                    broker_id=broker_id,
                    lead=lead,
                    analysis=analysis,
                    whatsapp_message_id=whatsapp_message_id,
                )
                result.draft_reply_queued = True
            result.stage_reached = "DISPATCH"
            result.stage_timings_ms["DISPATCH"] = (time.perf_counter() - t0) * 1000

            result.success = True

        except Exception as exc:
            logger.error(
                f"[WA_PIPELINE] Pipeline failed at stage={result.stage_reached}: {exc!r}"
            )
            result.error_message = f"Pipeline error at {result.stage_reached}: {type(exc).__name__}"
            result.success = False

        finally:
            result.total_elapsed_ms = (time.perf_counter() - overall_start) * 1000

        return result

    # ── Private Helpers ───────────────────────────────────────────────────────

    async def _resolve_lead(
        self, broker_id: str, normalized_phone: str
    ) -> Optional[Lead]:
        """
        Resolve lead from normalized E.164 phone within broker scope.
        Returns None if no matching lead (triggers HUMAN_REVIEW).
        """
        try:
            b_uuid = uuid.UUID(broker_id)
        except ValueError:
            return None

        stmt = select(Lead).where(
            and_(
                Lead.phone == normalized_phone,
                Lead.broker_id == b_uuid,
                Lead.deleted_at.is_(None),
            )
        ).limit(1)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _analyze_message(
        self,
        lead_id: str,
        broker_id: str,
        sanitized_text: str,
    ) -> Dict[str, Any]:
        """
        Deterministic keyword-based analysis of inbound message.
        Identifies primary intent WITHOUT calling an LLM.
        LLMs are only used downstream for response phrasing, never for routing decisions.
        """
        text_lower = sanitized_text.lower()

        intents = []
        buying_signal = "NONE"
        requires_handoff = False
        content_summary = "general inquiry"

        if any(kw in text_lower for kw in ["interested", "want to buy", "looking for", "inquiry", "tell me about"]):
            intents.append("PROPERTY_INQUIRY")
            buying_signal = "MODERATE"
            content_summary = "property inquiry"

        if any(kw in text_lower for kw in ["visit", "site visit", "viewing", "see the", "schedule a"]):
            intents.append("VIEWING_REQUEST")
            buying_signal = "STRONG"
            content_summary = "viewing request"

        if any(kw in text_lower for kw in ["price", "cost", "rate", "budget", "how much", "afford"]):
            intents.append("PRICE_INQUIRY")
            if buying_signal == "NONE":
                buying_signal = "WEAK"
            content_summary = "price inquiry"

        if any(kw in text_lower for kw in ["discount", "negotiate", "best price", "special offer"]):
            intents.append("NEGOTIATION")
            requires_handoff = True
            content_summary = "negotiation inquiry"

        if any(kw in text_lower for kw in ["stop", "unsubscribe", "opt out", "remove me", "don't contact"]):
            intents.append("OPT_OUT")
            requires_handoff = True
            content_summary = "opt-out request"

        if any(kw in text_lower for kw in ["human", "real person", "agent", "speak to someone", "call me"]):
            intents.append("HUMAN_AGENT_REQUEST")
            requires_handoff = True
            content_summary = "human agent request"

        if any(kw in text_lower for kw in ["brochure", "floor plan", "layout", "amenities"]):
            intents.append("DOCUMENT_REQUEST")
            content_summary = "document request"

        if not intents:
            intents.append("GENERAL_INQUIRY")

        return {
            "lead_id": lead_id,
            "broker_id": broker_id,
            "detected_intents": intents,
            "buying_signal_level": buying_signal,
            "requires_human_handoff": requires_handoff,
            "content_summary": content_summary,
            "analysis_method": "deterministic_keyword",  # LLMs never make routing decisions
        }

    async def _dispatch_to_autonomous_loop(
        self,
        broker_id: str,
        lead: Lead,
        analysis: Dict[str, Any],
        whatsapp_message_id: str,
    ) -> None:
        """
        Emit CUSTOMER_MESSAGE_RECEIVED event to the autonomous sales loop.
        The loop handles all guard chain, policy, and delivery decisions.
        """
        from app.modules.autonomous_loop.dto import SalesLoopEventDTO
        from app.modules.autonomous_loop.taxonomies import SalesLoopEventType, ActorType
        from app.modules.autonomous_loop.orchestrator import AutonomousSalesLoopService

        event = SalesLoopEventDTO(
            event_type=SalesLoopEventType.CUSTOMER_MESSAGE_RECEIVED,
            tenant_id=broker_id,
            lead_id=str(lead.id),
            broker_id=broker_id,
            actor_type=ActorType.WEBHOOK,
            actor_id=f"whatsapp::{whatsapp_message_id}",
            payload={
                "detected_intents": analysis.get("detected_intents", []),
                "buying_signal_level": analysis.get("buying_signal_level", "NONE"),
                "content_summary": analysis.get("content_summary"),
                "channel": "whatsapp",
                "whatsapp_message_id": whatsapp_message_id,
            },
            idempotency_key=f"wa_inbound::{whatsapp_message_id}",
            source="whatsapp_webhook",
        )

        orchestrator = AutonomousSalesLoopService(self.db)
        try:
            await orchestrator.process_event(event)
        except Exception as exc:
            # Log but don't fail the pipeline — message is already recorded
            logger.error(f"[WA_PIPELINE] Autonomous loop dispatch failed (non-fatal): {exc!r}")
