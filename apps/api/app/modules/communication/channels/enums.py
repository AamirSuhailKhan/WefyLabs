"""
Part 12 — Canonical Communication Vocabulary
============================================
One canonical, provider-independent vocabulary for the Communication Hub.

IMPORTANT: Enum values do NOT activate a channel. A channel is only live when
its provider is configured AND the channel is enabled in settings. Adding a
value here (e.g. WHATSAPP) must never be treated as "the channel works".
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class Channel(str, Enum):
    """Canonical channel vocabulary shared across adapters, domain services and UI."""

    WEB = "web"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    VOICE = "voice"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    API = "api"
    OTHER = "other"

    @classmethod
    def normalize(cls, value: Optional[str]) -> "Channel":
        """Best-effort normalization of a channel string from any source.

        Accepts the canonical values, the legacy ad-hoc strings used across the
        repository (``webchat``, ``in_app``, ``whatsapp_cloud``) and returns the
        canonical :class:`Channel`. Unknown values fall back to ``OTHER``.
        """
        if value is None:
            return cls.OTHER
        raw = str(value).strip().lower()
        aliases = {
            "web": cls.WEB,
            "webchat": cls.WEB,
            "web_chat": cls.WEB,
            "in_app": cls.WEB,
            "inapp": cls.WEB,
            "app": cls.WEB,
            "email": cls.EMAIL,
            "smtp": cls.EMAIL,
            "sms": cls.SMS,
            "twilio": cls.SMS,
            "whatsapp": cls.WHATSAPP,
            "whatsapp_cloud": cls.WHATSAPP,
            "wa": cls.WHATSAPP,
            "telegram": cls.TELEGRAM,
            "voice": cls.VOICE,
            "call": cls.VOICE,
            "instagram": cls.INSTAGRAM,
            "facebook": cls.FACEBOOK,
            "messenger": cls.FACEBOOK,
            "api": cls.API,
            "other": cls.OTHER,
            "internal_note": cls.OTHER,
        }
        return aliases.get(raw, cls.OTHER)


# Channels that are implemented today. Anything else is explicitly FUTURE and
# must remain disabled until a dedicated part implements it.
IMPLEMENTED_CHANNELS = frozenset({Channel.WEB, Channel.EMAIL, Channel.SMS})
# Channels that exist in the codebase but are disabled by strict safety policy.
POLICY_DISABLED_CHANNELS = frozenset({Channel.WHATSAPP})
# Channels that are not implemented at all yet.
FUTURE_CHANNELS = frozenset({Channel.VOICE, Channel.INSTAGRAM, Channel.FACEBOOK})


class ChannelEnablementState(str, Enum):
    """Truthful operational state of a channel.

    Derived from configuration + provider readiness. Never inferred from the
    mere existence of an adapter class.
    """

    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    CONFIGURED = "CONFIGURED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    STAGING = "STAGING"
    ERROR = "ERROR"


class ChannelDirection(str, Enum):
    """Message direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageActorType(str, Enum):
    """Who authored a message. Canonical, channel-agnostic."""

    CUSTOMER = "CUSTOMER"
    HUMAN = "HUMAN"
    AI_AGENT = "AI_AGENT"
    AUTOMATION = "AUTOMATION"
    SYSTEM = "SYSTEM"


class MessageDeliveryState(str, Enum):
    """Canonical delivery lifecycle. Only use states a provider actually supports."""

    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class ConversationControlMode(str, Enum):
    """Who currently owns a conversation (mirrors ConversationControl.control_mode)."""

    AI = "ai"
    HUMAN = "human"
    PAUSED = "paused"
    BOT = "bot"


__all__ = [
    "Channel",
    "ChannelEnablementState",
    "ChannelDirection",
    "MessageActorType",
    "MessageDeliveryState",
    "ConversationControlMode",
    "IMPLEMENTED_CHANNELS",
    "POLICY_DISABLED_CHANNELS",
    "FUTURE_CHANNELS",
]
