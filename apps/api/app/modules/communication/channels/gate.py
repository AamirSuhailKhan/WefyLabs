"""
Part 12 — Outbound Send Gate
============================
The single place where "may we send on this channel right now?" is decided.

Every outbound path (API, AI workforce, follow-up engine, appointment engine,
Revenue Autopilot) must pass through this gate before dispatching. It fails
closed: an unknown or disabled channel can never send.
"""
from __future__ import annotations

from typing import Iterable, Optional, Union

from app.modules.communication.channels.enums import (
    Channel,
    ChannelEnablementState,
)
from app.modules.communication.channels.status import (
    ChannelStatus,
    ChannelStatusService,
)


class ChannelNotSendableError(Exception):
    """Raised when an outbound send is attempted on an unavailable channel.

    Carries a machine-readable ``state`` so callers can map it to an HTTP 409
    without leaking provider internals.
    """

    def __init__(self, channel: str, state: ChannelEnablementState, reason: Optional[str] = None):
        self.channel = channel
        self.state = state
        self.reason = reason or f"Channel '{channel}' is not available for sending ({state.value})."
        super().__init__(self.reason)

    def to_dict(self) -> dict:
        return {"error": "channel_not_sendable", "channel": self.channel, "state": self.state.value, "reason": self.reason}


async def resolve_available_channel(
    candidates: Iterable[Union[str, Channel]],
    status_service: Optional[ChannelStatusService] = None,
) -> Optional[Channel]:
    """Return the first candidate channel whose state is ``ENABLED``.

    ``candidates`` is an ordered preference list (canonical values, ``Channel``
    members or legacy strings). Disabled / not-configured / future channels are
    skipped. Returns ``None`` when no candidate is currently sendable — callers
    must then treat the action as having no available channel rather than
    silently picking a disabled one.
    """
    service = status_service or ChannelStatusService()
    seen = set()
    for candidate in candidates:
        canonical = candidate if isinstance(candidate, Channel) else Channel.normalize(candidate)
        if canonical in seen:
            continue
        seen.add(canonical)
        status = await service.get_status(canonical)
        if status.state == ChannelEnablementState.ENABLED:
            return canonical
    return None


async def ensure_channel_sendable(
    channel: Union[str, Channel],
    status_service: Optional[ChannelStatusService] = None,
) -> ChannelStatus:
    """Validate that a channel is ENABLED, else raise :class:`ChannelNotSendableError`.

    Returns the resolved :class:`ChannelStatus` so callers can reuse provider
    metadata without a second lookup.
    """
    canonical = channel if isinstance(channel, Channel) else Channel.normalize(channel)
    service = status_service or ChannelStatusService()
    status = await service.get_status(canonical)
    if status.state != ChannelEnablementState.ENABLED:
        raise ChannelNotSendableError(canonical.value, status.state, status.reason)
    return status


__all__ = ["ChannelNotSendableError", "ensure_channel_sendable", "resolve_available_channel"]
