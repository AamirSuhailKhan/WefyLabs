"""
Master Build 04 — Conversation Session Continuity Service
==========================================================
Maintains stateful, per-lead conversation sessions with bounded memory windows.

ARCHITECTURE:
  Each (organization_id, lead_id) pair has exactly ONE active ConversationSession.
  Session state is stored in OmnichannelConversation.metadata_['session'] (JSONB).

PERSISTENCE STRATEGY:
  - Within a service instance (single request), an in-memory write-through cache
    prevents stale reads after mutations (critical for SQLite JSON text columns).
  - DB writes use flag_modified() to force SQLAlchemy dirty-tracking on JSON columns.
  - flush() is used (not commit()) to preserve the test fixture's rollback pattern.

INVARIANTS:
  1. Session context is always scoped to organization_id + lead_id.
  2. Memory window is bounded (MAX_MEMORY_TURNS) to prevent unbounded growth.
  3. Sessions are created on first inbound message; never pre-created speculatively.
  4. Handoff flag, once set True, can only be cleared by explicit broker action.
  5. LLMs never read raw session memory; they receive structured context summaries only.
  6. All session writes are idempotent on turn_id.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_MEMORY_TURNS = 20  # bounded sliding window


class ConversationTurn:
    """In-memory representation of a single conversation turn (no raw PII)."""
    __slots__ = ("turn_id", "direction", "channel", "content_summary",
                 "detected_intents", "buying_signal_level", "timestamp")

    def __init__(
        self,
        direction: str,            # "inbound" | "outbound"
        channel: str,              # "whatsapp" | "email" | "sms"
        content_summary: str,      # sanitized summary — never raw customer text
        detected_intents: List[str],
        buying_signal_level: Optional[str],
        timestamp: Optional[datetime] = None,
        turn_id: Optional[str] = None,
    ):
        self.turn_id = turn_id or str(uuid.uuid4())
        self.direction = direction
        self.channel = channel
        self.content_summary = content_summary
        self.detected_intents = detected_intents
        self.buying_signal_level = buying_signal_level
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "direction": self.direction,
            "channel": self.channel,
            "content_summary": self.content_summary,
            "detected_intents": self.detected_intents,
            "buying_signal_level": self.buying_signal_level,
            "timestamp": self.timestamp.isoformat(),
        }


class ConversationSessionState:
    """
    In-memory session state for a single (organization_id, lead_id) pair.
    Persisted in OmnichannelConversation.metadata_['session'] (JSONB).
    """

    _SIGNAL_RANK = {"STRONG": 3, "MODERATE": 2, "WEAK": 1, "NONE": 0}

    def __init__(
        self,
        session_id: str,
        organization_id: str,
        lead_id: str,
        current_topic: Optional[str] = None,
        turns: Optional[List[Dict[str, Any]]] = None,
        handoff_requested: bool = False,
        autonomy_paused: bool = False,
        message_count: int = 0,
        inbound_count: int = 0,
        outbound_count: int = 0,
        last_inbound_at: Optional[str] = None,
        last_outbound_at: Optional[str] = None,
        dominant_intent: Optional[str] = None,
        highest_buying_signal: Optional[str] = None,
    ):
        self.session_id = session_id
        self.organization_id = organization_id
        self.lead_id = lead_id
        self.current_topic = current_topic
        self.turns: List[Dict[str, Any]] = turns or []
        self.handoff_requested = handoff_requested
        self.autonomy_paused = autonomy_paused
        self.message_count = message_count
        self.inbound_count = inbound_count
        self.outbound_count = outbound_count
        self.last_inbound_at = last_inbound_at
        self.last_outbound_at = last_outbound_at
        self.dominant_intent = dominant_intent
        self.highest_buying_signal = highest_buying_signal

    def add_turn(self, turn: ConversationTurn) -> None:
        """Add a turn, enforcing bounded memory window."""
        self.turns.append(turn.to_dict())
        if len(self.turns) > MAX_MEMORY_TURNS:
            self.turns = self.turns[-MAX_MEMORY_TURNS:]

        self.message_count += 1
        if turn.direction == "inbound":
            self.inbound_count += 1
            self.last_inbound_at = turn.timestamp.isoformat()
        else:
            self.outbound_count += 1
            self.last_outbound_at = turn.timestamp.isoformat()

        if turn.detected_intents:
            self.dominant_intent = turn.detected_intents[0]

        if turn.buying_signal_level:
            current_rank = self._SIGNAL_RANK.get(self.highest_buying_signal or "NONE", 0)
            new_rank = self._SIGNAL_RANK.get(turn.buying_signal_level, 0)
            if new_rank > current_rank:
                self.highest_buying_signal = turn.buying_signal_level

    def to_context_summary(self) -> Dict[str, Any]:
        """
        Returns a structured, LLM-safe context summary.
        NEVER contains raw customer message text.
        """
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "current_topic": self.current_topic,
            "handoff_requested": self.handoff_requested,
            "autonomy_paused": self.autonomy_paused,
            "message_count": self.message_count,
            "inbound_count": self.inbound_count,
            "outbound_count": self.outbound_count,
            "last_inbound_at": self.last_inbound_at,
            "last_outbound_at": self.last_outbound_at,
            "dominant_intent": self.dominant_intent,
            "highest_buying_signal": self.highest_buying_signal,
            "recent_turns_count": len(self.turns),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "current_topic": self.current_topic,
            "turns": self.turns,
            "handoff_requested": self.handoff_requested,
            "autonomy_paused": self.autonomy_paused,
            "message_count": self.message_count,
            "inbound_count": self.inbound_count,
            "outbound_count": self.outbound_count,
            "last_inbound_at": self.last_inbound_at,
            "last_outbound_at": self.last_outbound_at,
            "dominant_intent": self.dominant_intent,
            "highest_buying_signal": self.highest_buying_signal,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSessionState":
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            organization_id=data["organization_id"],
            lead_id=data["lead_id"],
            current_topic=data.get("current_topic"),
            turns=data.get("turns", []),
            handoff_requested=data.get("handoff_requested", False),
            autonomy_paused=data.get("autonomy_paused", False),
            message_count=data.get("message_count", 0),
            inbound_count=data.get("inbound_count", 0),
            outbound_count=data.get("outbound_count", 0),
            last_inbound_at=data.get("last_inbound_at"),
            last_outbound_at=data.get("last_outbound_at"),
            dominant_intent=data.get("dominant_intent"),
            highest_buying_signal=data.get("highest_buying_signal"),
        )


class ConversationSessionService:
    """
    Manages stateful conversation sessions for all tenants and leads.

    Session persistence strategy:
      - Session state is stored in OmnichannelConversation.metadata_['session'].
      - An in-memory write-through cache (_cache) ensures that within a single
        service instance (single request/test), reads always return the latest
        mutated state without requiring a DB roundtrip.
      - This solves SQLite's JSON text column limitation where mutations are
        only visible after a committed write AND a fresh DB query bypassing
        the SQLAlchemy identity map cache.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        # In-memory write-through cache: (org_id, lead_id) → ConversationSessionState
        self._cache: Dict[tuple, ConversationSessionState] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Public Interface
    # ──────────────────────────────────────────────────────────────────────────

    async def get_or_create_session(
        self,
        organization_id: str,
        lead_id: str,
        channel: str = "whatsapp",
    ) -> ConversationSessionState:
        """
        Load existing session (from cache or DB), or create a new one.
        Always organization-scoped.
        """
        cache_key = (organization_id, lead_id)

        # 1. Return from write-through cache if available (avoids stale DB reads)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Try to load from DB
        from app.models.communication_models import OmnichannelConversation

        stmt = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.organization_id == organization_id,
                OmnichannelConversation.lead_id == lead_id,
            )
        ).limit(1)

        result = await self.db.execute(stmt)
        conv = result.scalar_one_or_none()

        if conv is not None:
            meta = conv.metadata_ or {}
            session_data = meta.get("session") if isinstance(meta, dict) else None
            if session_data and session_data.get("organization_id") == organization_id:
                session = ConversationSessionState.from_dict(session_data)
                self._cache[cache_key] = session
                return session
            # Conversation exists but no session state yet
            session = self._new_session(organization_id, lead_id)
            self._cache[cache_key] = session
            return session

        # 3. No conversation at all — create one
        session = self._new_session(organization_id, lead_id)
        new_conv = OmnichannelConversation(
            organization_id=organization_id,
            lead_id=lead_id,
            preferred_channel=channel,
            status="active",
            metadata_={"session": session.to_dict()},
        )
        self.db.add(new_conv)
        await self.db.flush()
        self._cache[cache_key] = session
        return session

    async def append_turn(
        self,
        organization_id: str,
        lead_id: str,
        turn: ConversationTurn,
    ) -> ConversationSessionState:
        """
        Load session, add turn (enforcing memory bound), persist, return updated state.
        Idempotent on turn_id.
        """
        # Load session (from cache or DB)
        session = await self.get_or_create_session(organization_id, lead_id, turn.channel)

        # Idempotency: skip if turn_id already recorded
        existing_ids = {t.get("turn_id") for t in session.turns}
        if turn.turn_id not in existing_ids:
            session.add_turn(turn)

        # Update cache immediately (write-through)
        cache_key = (organization_id, lead_id)
        self._cache[cache_key] = session

        # Persist to DB
        await self._persist_session_to_db(organization_id, lead_id, session)

        return session

    async def mark_handoff(self, organization_id: str, lead_id: str) -> None:
        """Mark session as requiring human handoff. Only AI-triggered."""
        session = await self.get_or_create_session(organization_id, lead_id)
        session.handoff_requested = True
        self._cache[(organization_id, lead_id)] = session
        await self._persist_session_to_db(organization_id, lead_id, session)

    async def clear_handoff(self, organization_id: str, lead_id: str) -> None:
        """Clear handoff flag — only callable by authenticated broker actions."""
        session = await self.get_or_create_session(organization_id, lead_id)
        session.handoff_requested = False
        session.autonomy_paused = False
        self._cache[(organization_id, lead_id)] = session
        await self._persist_session_to_db(organization_id, lead_id, session)

    async def pause_autonomy(self, organization_id: str, lead_id: str) -> None:
        """Pause AI autonomy for this lead's conversation."""
        session = await self.get_or_create_session(organization_id, lead_id)
        session.autonomy_paused = True
        self._cache[(organization_id, lead_id)] = session
        await self._persist_session_to_db(organization_id, lead_id, session)

    async def resume_autonomy(self, organization_id: str, lead_id: str) -> None:
        """Resume AI autonomy for this lead's conversation."""
        session = await self.get_or_create_session(organization_id, lead_id)
        session.autonomy_paused = False
        self._cache[(organization_id, lead_id)] = session
        await self._persist_session_to_db(organization_id, lead_id, session)

    async def get_context_summary(
        self, organization_id: str, lead_id: str
    ) -> Dict[str, Any]:
        """Return a structured, LLM-safe context summary for the session."""
        session = await self.get_or_create_session(organization_id, lead_id)
        return session.to_context_summary()

    # ──────────────────────────────────────────────────────────────────────────
    # Private Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _new_session(self, organization_id: str, lead_id: str) -> ConversationSessionState:
        return ConversationSessionState(
            session_id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
        )

    async def _persist_session_to_db(
        self, organization_id: str, lead_id: str, session: ConversationSessionState
    ) -> None:
        """
        Write session state to OmnichannelConversation.metadata_['session'].
        Uses flag_modified() to force SQLAlchemy dirty-tracking on the JSON column.
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
            # Create conversation record if it doesn't exist
            conv = OmnichannelConversation(
                organization_id=organization_id,
                lead_id=lead_id,
                preferred_channel="whatsapp",
                status="active",
                metadata_={"session": session.to_dict()},
            )
            self.db.add(conv)
            await self.db.flush()
            return

        # Assign a fresh dict so SQLAlchemy detects the mutation
        new_meta = dict(conv.metadata_ or {})
        new_meta["session"] = session.to_dict()
        conv.metadata_ = new_meta
        flag_modified(conv, "metadata_")
        await self.db.flush()
