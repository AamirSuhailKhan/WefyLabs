"""
Part 12 — Canonical Channel Layer
=================================
Provider-independent channel vocabulary, truthful status derivation and the
outbound send gate used by the Communication Hub.
"""
from app.modules.communication.channels.enums import (
    Channel,
    ChannelDirection,
    ChannelEnablementState,
    ConversationControlMode,
    MessageActorType,
    MessageDeliveryState,
    FUTURE_CHANNELS,
    IMPLEMENTED_CHANNELS,
    POLICY_DISABLED_CHANNELS,
)
from app.modules.communication.channels.gate import (
    ChannelNotSendableError,
    ensure_channel_sendable,
    resolve_available_channel,
)
from app.modules.communication.channels.status import (
    ChannelStatus,
    ChannelStatusService,
)

__all__ = [
    "Channel",
    "ChannelDirection",
    "ChannelEnablementState",
    "ConversationControlMode",
    "MessageActorType",
    "MessageDeliveryState",
    "FUTURE_CHANNELS",
    "IMPLEMENTED_CHANNELS",
    "POLICY_DISABLED_CHANNELS",
    "ChannelNotSendableError",
    "ensure_channel_sendable",
    "resolve_available_channel",
    "ChannelStatus",
    "ChannelStatusService",
]
