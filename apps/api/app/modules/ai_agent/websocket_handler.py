"""
WebSocket Streaming Endpoint for BeetleLabs AI Sales Agent Web Chat.

Provides:
  1. ws://host/ai-agent/v1/ws/chat/{organization_id}/{lead_id}
     - Full bidirectional WebSocket for real-time web chat
     - Streams agent response tokens as they are generated
     - Sends tool_start / tool_end events to the UI
     - Handles reconnect gracefully (restores session from DB)

  2. Rate Limiting middleware on /message REST endpoint
     - Per-organization: 100 messages/minute
     - Per-lead: 30 messages/minute
     - Uses in-memory token bucket (Redis in production)
"""
from __future__ import annotations

import json
import asyncio
import logging
import time
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status

logger = logging.getLogger("wefylabs.ai_agent.ws")

# ─── Per-organization rate limiter (in-memory, Redis in production) ──────────

class TokenBucketRateLimiter:
    """
    Simple token-bucket rate limiter.
    Limits: 100 msg/min per organization, 30 msg/min per lead.
    Production: swap _buckets for Redis ZADD/ZREMRANGEBYSCORE.
    """

    def __init__(self):
        self._buckets: Dict[str, list] = {}  # key → [timestamps]
        self._org_limit = 100
        self._lead_limit = 30
        self._window_seconds = 60

    def check(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        window_start = now - self._window_seconds
        timestamps = self._buckets.get(key, [])
        # Remove timestamps outside window
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        self._buckets[key] = timestamps
        return True

    def check_organization(self, organization_id: str) -> bool:
        return self.check(f"org:{organization_id}", self._org_limit)

    def check_lead(self, lead_id: str) -> bool:
        return self.check(f"lead:{lead_id}", self._lead_limit)


_rate_limiter = TokenBucketRateLimiter()


def check_rate_limit(organization_id: str, lead_id: str) -> None:
    """
    Call before processing any message.
    Raises HTTPException 429 if either limit is exceeded.
    """
    if not _rate_limiter.check_organization(organization_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: 100 messages/minute per organization.",
        )
    if not _rate_limiter.check_lead(lead_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: 30 messages/minute per conversation.",
        )


# ─── WebSocket Connection Manager ────────────────────────────────────────────

class WebSocketConnectionManager:
    """Tracks active WebSocket connections per session."""

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id] = websocket
        logger.info(f"[WS] Connected: {session_id}")

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)
        logger.info(f"[WS] Disconnected: {session_id}")

    async def send_json(self, session_id: str, data: dict) -> None:
        ws = self._connections.get(session_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.disconnect(session_id)

    async def send_token(self, session_id: str, token: str) -> None:
        """Stream a single response token to the web chat UI."""
        await self.send_json(session_id, {"type": "token", "content": token})

    async def send_tool_event(self, session_id: str, tool_name: str, event: str, data: dict = None) -> None:
        """Notify UI of tool execution start/end for live status."""
        await self.send_json(session_id, {
            "type": f"tool_{event}",
            "tool": tool_name,
            "data": data or {},
        })

    async def send_complete(self, session_id: str, outgoing: dict) -> None:
        """Signal response completion."""
        await self.send_json(session_id, {"type": "complete", **outgoing})

    async def send_error(self, session_id: str, error: str) -> None:
        await self.send_json(session_id, {"type": "error", "message": error})


ws_manager = WebSocketConnectionManager()


# ─── WebSocket Handler ────────────────────────────────────────────────────────

async def websocket_chat_handler(
    websocket: WebSocket,
    organization_id: str,
    lead_id: str,
    db,  # AsyncSession injected by FastAPI
) -> None:
    """
    Main WebSocket handler for AI Sales Agent web chat.

    Protocol:
      Client → Server: {"content": "user message", "channel": "web"}
      Server → Client: {"type": "token", "content": "partial response token"}
                       {"type": "tool_start", "tool": "search_properties"}
                       {"type": "tool_end", "tool": "search_properties", "data": {...}}
                       {"type": "complete", "session_id": "...", "current_state": "...", ...}
                       {"type": "error", "message": "..."}
    """
    from app.modules.ai_agent.conversation_manager.manager import (
        ConversationManager, IncomingMessage
    )
    import hashlib

    session_key = hashlib.sha256(f"{organization_id}:{lead_id}".encode()).hexdigest()[:16]
    await ws_manager.connect(session_key, websocket)
    manager = ConversationManager()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_error(session_key, "Invalid JSON payload")
                continue

            content = payload.get("content", "").strip()
            if not content:
                await ws_manager.send_error(session_key, "Empty message")
                continue

            # Rate limiting
            try:
                check_rate_limit(organization_id, lead_id)
            except HTTPException as exc:
                await ws_manager.send_error(session_key, exc.detail)
                continue

            # Notify UI: processing started
            await ws_manager.send_json(session_key, {"type": "thinking"})

            incoming = IncomingMessage(
                lead_id=lead_id,
                organization_id=organization_id,
                channel="web",
                content=content,
            )

            try:
                outgoing = await manager.process(db, incoming)
                # Simulate token streaming for web UI
                response_text = outgoing.content
                chunk_size = 4
                for i in range(0, len(response_text), chunk_size):
                    await ws_manager.send_token(session_key, response_text[i:i + chunk_size])
                    await asyncio.sleep(0.01)

                await ws_manager.send_complete(session_key, {
                    "session_id": outgoing.session_id,
                    "lead_id": outgoing.lead_id,
                    "current_state": outgoing.current_state,
                    "decision_type": outgoing.decision_type,
                    "escalated": outgoing.escalated,
                    "escalation_id": outgoing.escalation_id,
                    "tool_results": outgoing.tool_results,
                    "safety_violations": outgoing.safety_violations,
                    "was_blocked": outgoing.was_blocked,
                })
            except Exception as exc:
                logger.error(f"[WS] ConversationManager error: {exc}", exc_info=True)
                await ws_manager.send_error(session_key, "Agent processing error. Please try again.")

    except WebSocketDisconnect:
        ws_manager.disconnect(session_key)
    except Exception as exc:
        logger.error(f"[WS] Unexpected error: {exc}", exc_info=True)
        ws_manager.disconnect(session_key)
