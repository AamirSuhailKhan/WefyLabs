"""
Master Build 04 — Conversation Analytics Service
=================================================
Provides queryable, tenant-scoped conversation performance metrics.

CAPABILITIES:
  1. Per-tenant aggregate metrics (messages sent/received, handoffs, response rate)
  2. Per-lead conversation summary (session state, buying signal, turn count)
  3. Channel breakdown (WhatsApp vs Email vs SMS)
  4. Buying signal distribution (STRONG, MODERATE, WEAK, NONE)
  5. Hot-lead surfacing by buying signal threshold

INVARIANTS:
  1. All queries ALWAYS filter by organization_id — never cross-tenant.
  2. No PII returned in aggregate metrics — only counts and percentages.
  3. All counts come from verified DB state — never from LLM estimates.
  4. Time windows are always explicit; defaults to last 30 days if unspecified.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ConversationMetricsDTO:
    """Tenant-level aggregate conversation metrics over a time window."""

    def __init__(
        self,
        organization_id: str,
        window_days: int,
        total_conversations: int,
        active_conversations: int,
        handoff_conversations: int,
        total_inbound_messages: int,
        total_outbound_messages: int,
        unique_leads_engaged: int,
        sessions_with_viewing_request: int,
        sessions_with_strong_signal: int,
        sessions_with_opt_out: int,
        channel_breakdown: Dict[str, int],
        buying_signal_distribution: Dict[str, int],
        computed_at: Optional[datetime] = None,
    ):
        self.organization_id = organization_id
        self.window_days = window_days
        self.total_conversations = total_conversations
        self.active_conversations = active_conversations
        self.handoff_conversations = handoff_conversations
        self.total_inbound_messages = total_inbound_messages
        self.total_outbound_messages = total_outbound_messages
        self.unique_leads_engaged = unique_leads_engaged
        self.sessions_with_viewing_request = sessions_with_viewing_request
        self.sessions_with_strong_signal = sessions_with_strong_signal
        self.sessions_with_opt_out = sessions_with_opt_out
        self.channel_breakdown = channel_breakdown
        self.buying_signal_distribution = buying_signal_distribution
        self.computed_at = computed_at or datetime.now(timezone.utc)

        # Derived rates (safe division)
        self.handoff_rate = (
            round(handoff_conversations / total_conversations * 100, 2)
            if total_conversations > 0 else 0.0
        )
        self.strong_signal_rate = (
            round(sessions_with_strong_signal / total_conversations * 100, 2)
            if total_conversations > 0 else 0.0
        )
        self.response_rate = (
            round(total_outbound_messages / max(total_inbound_messages, 1) * 100, 2)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "window_days": self.window_days,
            "total_conversations": self.total_conversations,
            "active_conversations": self.active_conversations,
            "handoff_conversations": self.handoff_conversations,
            "total_inbound_messages": self.total_inbound_messages,
            "total_outbound_messages": self.total_outbound_messages,
            "unique_leads_engaged": self.unique_leads_engaged,
            "sessions_with_viewing_request": self.sessions_with_viewing_request,
            "sessions_with_strong_signal": self.sessions_with_strong_signal,
            "sessions_with_opt_out": self.sessions_with_opt_out,
            "channel_breakdown": self.channel_breakdown,
            "buying_signal_distribution": self.buying_signal_distribution,
            "handoff_rate_pct": self.handoff_rate,
            "strong_signal_rate_pct": self.strong_signal_rate,
            "response_rate_pct": self.response_rate,
            "computed_at": self.computed_at.isoformat(),
        }


class LeadConversationSummaryDTO:
    """Per-lead conversation summary from session state."""

    def __init__(
        self,
        organization_id: str,
        lead_id: str,
        session_id: Optional[str],
        current_topic: Optional[str],
        message_count: int,
        inbound_count: int,
        outbound_count: int,
        dominant_intent: Optional[str],
        highest_buying_signal: Optional[str],
        handoff_requested: bool,
        autonomy_paused: bool,
        last_inbound_at: Optional[str],
        last_outbound_at: Optional[str],
    ):
        self.organization_id = organization_id
        self.lead_id = lead_id
        self.session_id = session_id
        self.current_topic = current_topic
        self.message_count = message_count
        self.inbound_count = inbound_count
        self.outbound_count = outbound_count
        self.dominant_intent = dominant_intent
        self.highest_buying_signal = highest_buying_signal
        self.handoff_requested = handoff_requested
        self.autonomy_paused = autonomy_paused
        self.last_inbound_at = last_inbound_at
        self.last_outbound_at = last_outbound_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "session_id": self.session_id,
            "current_topic": self.current_topic,
            "message_count": self.message_count,
            "inbound_count": self.inbound_count,
            "outbound_count": self.outbound_count,
            "dominant_intent": self.dominant_intent,
            "highest_buying_signal": self.highest_buying_signal,
            "handoff_requested": self.handoff_requested,
            "autonomy_paused": self.autonomy_paused,
            "last_inbound_at": self.last_inbound_at,
            "last_outbound_at": self.last_outbound_at,
        }


class ConversationAnalyticsService:
    """
    Queryable, tenant-scoped conversation analytics engine.

    Aggregates over OmnichannelConversation records (scoped by organization_id)
    and their JSONB session state stored in metadata_['session'].
    """

    _SIGNAL_RANK = {"STRONG": 3, "MODERATE": 2, "WEAK": 1, "NONE": 0}

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tenant_metrics(
        self,
        organization_id: str,
        window_days: int = 30,
    ) -> ConversationMetricsDTO:
        """
        Compute aggregate conversation metrics for a tenant over the last `window_days`.
        Always enforces tenant isolation via organization_id.
        """
        from app.models.communication_models import OmnichannelConversation

        window_start = datetime.now(timezone.utc) - timedelta(days=window_days)

        stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.organization_id == organization_id,
                OmnichannelConversation.created_at >= window_start,
            )
        )

        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        total = len(conversations)
        active_count = 0
        handoff_count = 0
        total_inbound = 0
        total_outbound = 0
        unique_leads: set[str] = set()
        viewing_request_count = 0
        strong_signal_count = 0
        opt_out_count = 0
        channel_counts: Dict[str, int] = {}
        signal_counts: Dict[str, int] = {"STRONG": 0, "MODERATE": 0, "WEAK": 0, "NONE": 0}

        for conv in conversations:
            if conv.lead_id:
                unique_leads.add(str(conv.lead_id))

            # Channel breakdown — use preferred_channel
            channel = getattr(conv, "preferred_channel", "unknown") or "unknown"
            channel_counts[channel] = channel_counts.get(channel, 0) + 1

            # Active status
            if getattr(conv, "status", "active") == "active":
                active_count += 1

            # Session state from metadata_
            meta = conv.metadata_ or {}
            session = meta.get("session", {}) if isinstance(meta, dict) else {}

            if session:
                if session.get("handoff_requested", False):
                    handoff_count += 1

                total_inbound += session.get("inbound_count", 0) or 0
                total_outbound += session.get("outbound_count", 0) or 0

                sig = session.get("highest_buying_signal", "NONE") or "NONE"
                if sig in signal_counts:
                    signal_counts[sig] += 1
                if sig == "STRONG":
                    strong_signal_count += 1

                intent = session.get("dominant_intent") or ""
                if "VIEWING_REQUEST" in intent:
                    viewing_request_count += 1
                if "OPT_OUT" in intent:
                    opt_out_count += 1

        return ConversationMetricsDTO(
            organization_id=organization_id,
            window_days=window_days,
            total_conversations=total,
            active_conversations=active_count,
            handoff_conversations=handoff_count,
            total_inbound_messages=total_inbound,
            total_outbound_messages=total_outbound,
            unique_leads_engaged=len(unique_leads),
            sessions_with_viewing_request=viewing_request_count,
            sessions_with_strong_signal=strong_signal_count,
            sessions_with_opt_out=opt_out_count,
            channel_breakdown=channel_counts,
            buying_signal_distribution=signal_counts,
        )

    async def get_lead_conversation_summary(
        self,
        organization_id: str,
        lead_id: str,
    ) -> Optional[LeadConversationSummaryDTO]:
        """
        Return the conversation summary for a specific lead within a tenant.
        Returns None if no conversation exists.
        """
        from app.models.communication_models import OmnichannelConversation

        stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.organization_id == organization_id,
                OmnichannelConversation.lead_id == lead_id,
            )
        ).limit(1)

        result = await self.db.execute(stmt)
        conv = result.scalar_one_or_none()

        if conv is None:
            return None

        meta = conv.metadata_ or {}
        session = meta.get("session", {}) if isinstance(meta, dict) else {}

        return LeadConversationSummaryDTO(
            organization_id=organization_id,
            lead_id=lead_id,
            session_id=session.get("session_id"),
            current_topic=session.get("current_topic"),
            message_count=session.get("message_count", 0) or 0,
            inbound_count=session.get("inbound_count", 0) or 0,
            outbound_count=session.get("outbound_count", 0) or 0,
            dominant_intent=session.get("dominant_intent"),
            highest_buying_signal=session.get("highest_buying_signal"),
            handoff_requested=session.get("handoff_requested", False),
            autonomy_paused=session.get("autonomy_paused", False),
            last_inbound_at=session.get("last_inbound_at"),
            last_outbound_at=session.get("last_outbound_at"),
        )

    async def get_hot_leads(
        self,
        organization_id: str,
        signal_threshold: str = "STRONG",
        limit: int = 50,
    ) -> List[LeadConversationSummaryDTO]:
        """
        Return leads with buying signal at or above threshold, sorted by recency.
        Used by broker dashboard to surface highest-priority conversations.
        """
        from app.models.communication_models import OmnichannelConversation

        threshold_rank = self._SIGNAL_RANK.get(signal_threshold, 3)

        stmt = select(OmnichannelConversation).where(
            OmnichannelConversation.organization_id == organization_id,
        ).order_by(OmnichannelConversation.updated_at.desc()).limit(500)

        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        hot_leads: List[LeadConversationSummaryDTO] = []
        for conv in conversations:
            meta = conv.metadata_ or {}
            session = meta.get("session", {}) if isinstance(meta, dict) else {}
            if not session:
                continue

            sig = session.get("highest_buying_signal", "NONE") or "NONE"
            if self._SIGNAL_RANK.get(sig, 0) >= threshold_rank:
                hot_leads.append(LeadConversationSummaryDTO(
                    organization_id=organization_id,
                    lead_id=str(conv.lead_id) if conv.lead_id else "unknown",
                    session_id=session.get("session_id"),
                    current_topic=session.get("current_topic"),
                    message_count=session.get("message_count", 0) or 0,
                    inbound_count=session.get("inbound_count", 0) or 0,
                    outbound_count=session.get("outbound_count", 0) or 0,
                    dominant_intent=session.get("dominant_intent"),
                    highest_buying_signal=sig,
                    handoff_requested=session.get("handoff_requested", False),
                    autonomy_paused=session.get("autonomy_paused", False),
                    last_inbound_at=session.get("last_inbound_at"),
                    last_outbound_at=session.get("last_outbound_at"),
                ))
                if len(hot_leads) >= limit:
                    break

        return hot_leads
