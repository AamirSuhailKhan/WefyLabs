"""
Channel Manager — Provider Registry
=======================================
Central registry of all communication providers.
ChannelManager maps (channel, provider_name) → CommunicationProvider instance.

Usage:
    manager = ChannelManager()
    manager.register(WhatsAppCloudProvider(...))
    provider = manager.get_provider("whatsapp", "meta_cloud")
    result = await provider.send(message)

Adding new channels = register new provider, zero other changes.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from app.modules.communication.provider_adapters.base_provider import CommunicationProvider

logger = logging.getLogger(__name__)


class ChannelManager:
    """
    Thread-safe provider registry.
    One singleton per application process (instantiated in router startup).
    Supports multiple providers per channel (e.g., primary + fallback).
    """

    def __init__(self):
        # Registry: channel → provider_name → CommunicationProvider
        self._providers: Dict[str, Dict[str, CommunicationProvider]] = {}
        # Default provider per channel
        self._defaults: Dict[str, str] = {}

    def register(self, provider: CommunicationProvider,
                 set_as_default: bool = True) -> None:
        """
        Register a provider for its channel.
        First registered provider becomes default unless set_as_default=False.
        """
        channel = provider.channel
        name = provider.provider_name

        if channel not in self._providers:
            self._providers[channel] = {}

        self._providers[channel][name] = provider
        if set_as_default or channel not in self._defaults:
            self._defaults[channel] = name

        logger.info(f"[ChannelManager] Registered provider={name} channel={channel} default={set_as_default}")

    def get_provider(self, channel: str,
                     provider_name: Optional[str] = None) -> CommunicationProvider:
        """
        Get provider for channel. Uses default if provider_name not specified.
        Raises ValueError if no provider registered for channel.
        """
        if channel not in self._providers or not self._providers[channel]:
            raise ValueError(f"No provider registered for channel: {channel}")

        if provider_name and provider_name in self._providers[channel]:
            return self._providers[channel][provider_name]

        # Use default
        default_name = self._defaults.get(channel)
        if default_name and default_name in self._providers[channel]:
            return self._providers[channel][default_name]

        # Fallback: first registered
        return next(iter(self._providers[channel].values()))

    def get_all_providers(self, channel: str) -> List[CommunicationProvider]:
        """Return all providers registered for a channel."""
        return list(self._providers.get(channel, {}).values())

    def supported_channels(self) -> List[str]:
        """Return list of all channels with at least one registered provider."""
        return [ch for ch, providers in self._providers.items() if providers]

    def is_channel_supported(self, channel: str) -> bool:
        return channel in self._providers and bool(self._providers[channel])

    async def connect_all(self) -> None:
        """Call connect() on all registered providers. Called on app startup."""
        for channel, providers in self._providers.items():
            for name, provider in providers.items():
                try:
                    await provider.connect()
                    logger.info(f"[ChannelManager] Connected provider={name} channel={channel}")
                except Exception as e:
                    logger.error(f"[ChannelManager] Failed to connect provider={name} channel={channel}: {e}")

    async def disconnect_all(self) -> None:
        """Call disconnect() on all providers. Called on app shutdown."""
        for channel, providers in self._providers.items():
            for name, provider in providers.items():
                try:
                    await provider.disconnect()
                except Exception as e:
                    logger.warning(f"[ChannelManager] Disconnect error provider={name}: {e}")

    def status(self) -> Dict:
        """Return registry status summary for health checks."""
        return {
            "channels": self.supported_channels(),
            "providers": {
                channel: list(providers.keys())
                for channel, providers in self._providers.items()
            },
            "defaults": self._defaults,
        }


# ─── Singleton factory ────────────────────────────────────────────────────────

_channel_manager_instance: Optional[ChannelManager] = None


def get_channel_manager() -> ChannelManager:
    """Return the application-level ChannelManager singleton."""
    global _channel_manager_instance
    if _channel_manager_instance is None:
        _channel_manager_instance = _build_default_channel_manager()
    return _channel_manager_instance


def _build_default_channel_manager() -> ChannelManager:
    """
    Build ChannelManager with real providers initialized from environment settings.
    When environment variables are missing, providers return CONFIGURATION_REQUIRED
    truthfully (never fake success).
    """
    from app.config import settings
    from app.modules.communication.provider_adapters.whatsapp_provider import WhatsAppCloudProvider
    from app.modules.communication.provider_adapters.telegram_provider import TelegramProvider
    from app.modules.communication.provider_adapters.email_smtp_provider import EmailSMTPProvider
    from app.modules.communication.provider_adapters.webchat_provider import WebChatProvider
    from app.modules.communication.provider_adapters.sms_provider import SMSGatewayProvider

    manager = ChannelManager()

    # WhatsApp Cloud API (Primary Meta Graph API)
    # STRICT SAFETY: WhatsApp is registered for status reporting only. The
    # adapter refuses to send unless WHATSAPP_ENABLED is explicitly true.
    manager.register(WhatsAppCloudProvider(
        access_token=getattr(settings, "WHATSAPP_ACCESS_TOKEN", None),
        phone_number_id=getattr(settings, "PHONE_NUMBER_ID", None),
        app_secret=getattr(settings, "WHATSAPP_APP_SECRET", None),
        business_account_id=getattr(settings, "WABA_ID", None),
        enabled=bool(getattr(settings, "WHATSAPP_ENABLED", False)),
    ))

    # Telegram Bot
    manager.register(TelegramProvider(
        bot_token=getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "",
        webhook_secret_token=getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or "",
    ))

    # Email SMTP (Sender Free via SMTP / Generic SMTP)
    manager.register(EmailSMTPProvider(
        smtp_host=getattr(settings, "SMTP_HOST", "") or "",
        smtp_port=int(getattr(settings, "SMTP_PORT", 587) or 587),
        smtp_user=getattr(settings, "SMTP_USER", "") or getattr(settings, "SMTP_USERNAME", "") or "",
        smtp_password=getattr(settings, "SMTP_PASSWORD", "") or "",
        from_email=getattr(settings, "SMTP_FROM_EMAIL", "") or getattr(settings, "EMAIL_FROM_ADDRESS", "") or "noreply@wefylabs.com",
        from_name=getattr(settings, "SMTP_FROM_NAME", "WefyLabs Real Estate") or "WefyLabs Real Estate",
        smtp_use_tls=bool(getattr(settings, "SMTP_USE_TLS", True)),
        smtp_use_ssl=bool(getattr(settings, "SMTP_USE_SSL", False)),
        smtp_security=getattr(settings, "SMTP_SECURITY", "STARTTLS"),
    ))

    # WebChat / In-App
    manager.register(WebChatProvider())

    # SMS Gateway (Twilio / Generic)
    manager.register(SMSGatewayProvider(
        account_sid=getattr(settings, "TWILIO_ACCOUNT_SID", None),
        auth_token=getattr(settings, "TWILIO_AUTH_TOKEN", None),
        from_number=getattr(settings, "TWILIO_FROM_NUMBER", None),
    ))

    return manager
