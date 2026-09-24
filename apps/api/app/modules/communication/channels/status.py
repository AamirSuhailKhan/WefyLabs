"""
Part 12 — Channel Status Service
=================================
Single source of truth for "is this channel actually usable right now?".

The state is derived from two independent inputs and never from the mere
existence of an adapter class:

1. The channel enablement flag in settings (the kill switch).
2. The provider's own ``verify_configuration()`` readiness check.

This prevents the classic "adapter exists == channel is live" mistake.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config import settings
from app.modules.communication.channels.enums import (
    Channel,
    ChannelEnablementState,
    FUTURE_CHANNELS,
    IMPLEMENTED_CHANNELS,
)
from app.modules.communication.channel_manager.manager import (
    ChannelManager,
    get_channel_manager,
)
from app.modules.communication.provider_adapters.base_provider import (
    ProviderStatusEnum,
)

logger = logging.getLogger("wefylabs.communication.channels")


# Canonical channel → ChannelManager provider key. Only channels backed by a
# registered provider appear here.
_PROVIDER_KEY: Dict[Channel, str] = {
    Channel.WEB: "webchat",
    Channel.EMAIL: "email",
    Channel.SMS: "sms",
    Channel.WHATSAPP: "whatsapp",
    Channel.TELEGRAM: "telegram",
}

def provider_key_for(channel: "Channel") -> Optional[str]:
    """Return the ChannelManager provider key backing a canonical channel."""
    return _PROVIDER_KEY.get(channel)


# Canonical channel → settings enablement flag name.
_ENABLEMENT_FLAG: Dict[Channel, str] = {
    Channel.WEB: "WEBCHAT_ENABLED",
    Channel.EMAIL: "EMAIL_ENABLED",
    Channel.SMS: "SMS_ENABLED",
    Channel.WHATSAPP: "WHATSAPP_ENABLED",
    Channel.TELEGRAM: "TELEGRAM_ENABLED",
    Channel.VOICE: "VOICE_ENABLED",
    Channel.INSTAGRAM: "INSTAGRAM_ENABLED",
    Channel.FACEBOOK: "FACEBOOK_ENABLED",
}


@dataclass
class ChannelStatus:
    """Truthful, non-secret channel status report."""

    channel: str
    state: ChannelEnablementState
    enabled: bool
    configured: bool
    implemented: bool
    provider_name: Optional[str] = None
    reason: Optional[str] = None
    capabilities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "state": self.state.value,
            "enabled": self.enabled,
            "configured": self.configured,
            "implemented": self.implemented,
            "provider_name": self.provider_name,
            "reason": self.reason,
            "capabilities": self.capabilities,
        }


class ChannelStatusService:
    """Derives truthful per-channel status from config + provider readiness."""

    def __init__(self, channel_manager: Optional[ChannelManager] = None):
        self.channel_manager = channel_manager or get_channel_manager()

    # ─── Public API ───────────────────────────────────────────────────────────

    def is_enabled(self, channel: Channel) -> bool:
        """Return True only when the channel's kill switch is on."""
        flag_name = _ENABLEMENT_FLAG.get(channel)
        if not flag_name:
            # No flag means non-sendable (VOICE/API/OTHER/unknown).
            return channel is Channel.API
        return bool(getattr(settings, flag_name, False))

    async def get_status(self, channel: Channel) -> ChannelStatus:
        provider_key = _PROVIDER_KEY.get(channel)
        enabled = self.is_enabled(channel)
        implemented = channel in IMPLEMENTED_CHANNELS

        # Internal channels without a provider.
        if provider_key is None:
            if channel is Channel.API:
                return ChannelStatus(
                    channel=channel.value,
                    state=ChannelEnablementState.ENABLED,
                    enabled=True,
                    configured=True,
                    implemented=True,
                    reason="Internal API channel (no outbound provider).",
                )
            if channel in FUTURE_CHANNELS:
                return ChannelStatus(
                    channel=channel.value,
                    state=ChannelEnablementState.DISABLED,
                    enabled=enabled,
                    configured=False,
                    implemented=False,
                    reason="Channel is not implemented (future part).",
                )
            return ChannelStatus(
                channel=channel.value,
                state=ChannelEnablementState.DISABLED,
                enabled=enabled,
                configured=False,
                implemented=False,
                reason="Unknown or unsupported channel.",
            )

        # WhatsApp is intentionally held out of the Hub for Part 12.
        if channel is Channel.WHATSAPP:
            return ChannelStatus(
                channel=channel.value,
                state=ChannelEnablementState.DISABLED,
                enabled=False,
                configured=await self._provider_configured(provider_key),
                implemented=False,
                provider_name=self._provider_name(provider_key),
                reason=(
                    "WhatsApp is intentionally disabled. It is not exposed by the "
                    "Communication Hub and must not be activated in this part."
                ),
            )

        provider_name = self._provider_name(provider_key)
        if not enabled:
            return ChannelStatus(
                channel=channel.value,
                state=ChannelEnablementState.DISABLED,
                enabled=False,
                configured=await self._provider_configured(provider_key),
                implemented=implemented,
                provider_name=provider_name,
                reason="Channel disabled by configuration.",
            )

        if provider_name is None:
            return ChannelStatus(
                channel=channel.value,
                state=ChannelEnablementState.NOT_CONFIGURED,
                enabled=True,
                configured=False,
                implemented=implemented,
                reason="No provider is registered for this channel.",
            )

        provider_status, capabilities = await self._provider_readiness(provider_key)
        if provider_status == ProviderStatusEnum.READY:
            state = ChannelEnablementState.ENABLED
            configured = True
            reason = None
        elif provider_status == ProviderStatusEnum.AUTHENTICATION_FAILED:
            state = ChannelEnablementState.ERROR
            configured = False
            reason = "Provider authentication failed."
        elif provider_status == ProviderStatusEnum.DISABLED:
            state = ChannelEnablementState.DISABLED
            configured = False
            reason = "Provider reports itself disabled."
        elif provider_status == ProviderStatusEnum.MAINTENANCE:
            state = ChannelEnablementState.STAGING
            configured = False
            reason = "Provider is in maintenance."
        else:  # CONFIGURATION_REQUIRED
            state = ChannelEnablementState.NOT_CONFIGURED
            configured = False
            reason = "Provider credentials are not configured."

        return ChannelStatus(
            channel=channel.value,
            state=state,
            enabled=True,
            configured=configured,
            implemented=implemented,
            provider_name=provider_name,
            reason=reason,
            capabilities=capabilities,
        )

    async def get_all_status(self) -> List[ChannelStatus]:
        return [await self.get_status(ch) for ch in Channel]

    async def get_public_summary(self) -> Dict[str, Any]:
        """Non-secret summary suitable for the UI / health endpoints."""
        statuses = await self.get_all_status()
        return {
            "channels": {s.channel: s.to_dict() for s in statuses},
            "sendable_channels": [s.channel for s in statuses if s.state == ChannelEnablementState.ENABLED],
        }

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _provider_name(self, provider_key: str) -> Optional[str]:
        providers = self.channel_manager.get_all_providers(provider_key)
        return providers[0].provider_name if providers else None

    async def _provider_configured(self, provider_key: str) -> bool:
        providers = self.channel_manager.get_all_providers(provider_key)
        if not providers:
            return False
        for p in providers:
            is_conf = getattr(p, "is_configured", None)
            if callable(is_conf) and is_conf():
                return True
            try:
                if await p.verify_configuration() == ProviderStatusEnum.READY:
                    return True
            except Exception:  # pragma: no cover - defensive
                continue
        return False

    async def _provider_readiness(self, provider_key: str):
        providers = self.channel_manager.get_all_providers(provider_key)
        if not providers:
            return ProviderStatusEnum.CONFIGURATION_REQUIRED, {}
        provider = providers[0]
        try:
            status = await provider.verify_configuration()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[ChannelStatus] verify_configuration failed for %s: %s", provider_key, exc)
            return ProviderStatusEnum.CONFIGURATION_REQUIRED, {}
        caps = provider.capabilities()
        return status, {
            "supports_text": caps.supports_text,
            "supports_templates": caps.supports_templates,
            "supports_media": caps.supports_media,
            "supports_read_receipts": caps.supports_read_receipts,
        }


__all__ = ["ChannelStatus", "ChannelStatusService", "provider_key_for"]
