"""
Part 21.6 — CommunicationProvider Abstract Base Class & Typed Contracts
========================================================================
Production-grade provider abstraction for WhatsApp Cloud API, Email (SMTP),
SMS Gateway, WebChat, and Telegram.

NON-NEGOTIABLE INVARIANTS:
1. Zero mock fallback in production paths.
2. If credentials are missing, returns CONFIGURATION_REQUIRED or PROVIDER_UNAVAILABLE.
3. Every delivery result is strictly typed and truthful.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ─── Enumerations ─────────────────────────────────────────────────────────────

class DeliveryStatusEnum(str, Enum):
    """Controlled, truthful delivery lifecycle statuses."""
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_FAILED = "AUTH_FAILED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class ProviderStatusEnum(str, Enum):
    """Operational health status of a provider configuration."""
    READY = "READY"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    DISABLED = "DISABLED"
    MAINTENANCE = "MAINTENANCE"


# ─── Capabilities & DTOs ──────────────────────────────────────────────────────

@dataclass
class CommunicationCapabilities:
    """Declared capabilities of a communication provider."""
    supports_text: bool = True
    supports_templates: bool = False
    supports_media: bool = False
    supports_typing_indicator: bool = False
    supports_read_receipts: bool = False
    supports_webhooks: bool = False
    max_text_length: int = 4096


@dataclass
class InboundMessageDTO:
    """Normalized inbound message — channel-agnostic."""
    provider_name: str
    channel: str                     # whatsapp | telegram | email | webchat | sms
    provider_message_id: str         # Provider-assigned ID
    idempotency_key: str             # Dedup key (typically provider_message_id hash)
    sender_identifier: str           # phone | email | telegram_id | session_id
    sender_name: str
    content: str
    message_type: str = "text"       # text | image | video | audio | document | location | sticker
    content_structured: Optional[Dict[str, Any]] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: Optional[str] = None
    phone_number_id: Optional[str] = None   # WhatsApp: which phone number received this


@dataclass
class OutboundMessageDTO:
    """Channel-agnostic outbound message passed to provider.send()."""
    message_id: str
    conversation_id: str
    organization_id: str
    channel: str
    provider_name: str
    recipient_identifier: str
    content: str
    message_type: str = "text"
    content_structured: Optional[Dict[str, Any]] = None   # buttons, lists, templates
    template_id: Optional[str] = None
    template_variables: Optional[Dict[str, str]] = None
    attachment_url: Optional[str] = None
    attachment_mime: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProviderResponse:
    """Result from provider.send() or provider.get_delivery_status()."""
    success: bool
    provider_message_id: Optional[str] = None
    status: str = "sent"                             # sent | failed | queued | config_required
    delivery_status: DeliveryStatusEnum = DeliveryStatusEnum.SENT
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    rate_limit_reset_seconds: Optional[int] = None
    raw_response: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None

    def __post_init__(self):
        # Normalize status string if delivery_status provided
        if isinstance(self.delivery_status, DeliveryStatusEnum):
            if not self.success and self.delivery_status in (
                DeliveryStatusEnum.CONFIGURATION_REQUIRED,
                DeliveryStatusEnum.AUTH_FAILED,
                DeliveryStatusEnum.PROVIDER_UNAVAILABLE,
                DeliveryStatusEnum.INVALID_RECIPIENT,
                DeliveryStatusEnum.RATE_LIMITED,
                DeliveryStatusEnum.FAILED,
            ):
                self.status = self.delivery_status.value.lower()


@dataclass
class ProviderDeliveryStatus:
    """Delivery status update from a provider callback or poll."""
    provider_message_id: str
    status: str                                      # sent | delivered | read | failed
    delivery_status: DeliveryStatusEnum = DeliveryStatusEnum.SENT
    provider_timestamp: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_event: Optional[Dict[str, Any]] = None


# ─── Abstract Base Class ──────────────────────────────────────────────────────

class CommunicationProvider(abc.ABC):
    """
    Abstract base for all communication channel providers.
    Every provider MUST implement all abstract methods.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name. e.g. 'meta_cloud', 'telegram', 'smtp'"""

    @property
    @abc.abstractmethod
    def channel(self) -> str:
        """Channel this provider handles. e.g. 'whatsapp', 'telegram', 'email'"""

    @property
    @abc.abstractmethod
    def supported_message_types(self) -> List[str]:
        """List of message types this provider can send."""

    @property
    def supports_typing_indicator(self) -> bool:
        """Whether this channel supports typing indicators."""
        return False

    @property
    def supports_read_receipts(self) -> bool:
        """Whether this channel supports read receipts."""
        return False

    @property
    def supports_media(self) -> bool:
        """Whether this channel supports media attachments."""
        return True

    def capabilities(self) -> CommunicationCapabilities:
        """Returns standard capability descriptor for this provider."""
        return CommunicationCapabilities(
            supports_text="text" in self.supported_message_types,
            supports_templates="template" in self.supported_message_types,
            supports_media=self.supports_media,
            supports_typing_indicator=self.supports_typing_indicator,
            supports_read_receipts=self.supports_read_receipts,
            supports_webhooks=True,
            max_text_length=4096,
        )

    @abc.abstractmethod
    async def verify_configuration(self) -> ProviderStatusEnum:
        """
        Validates provider configuration and connectivity without leaking secrets.
        Returns ProviderStatusEnum (READY, CONFIGURATION_REQUIRED, AUTHENTICATION_FAILED, DISABLED).
        """

    @abc.abstractmethod
    async def connect(self) -> None:
        """Initialize provider connection / verify credentials."""

    @abc.abstractmethod
    async def send(self, message: OutboundMessageDTO) -> ProviderResponse:
        """
        Send a message via this provider.
        Must be idempotent — calling twice with the same idempotency_key is safe.
        """

    @abc.abstractmethod
    async def receive(self, payload: Dict[str, Any]) -> InboundMessageDTO:
        """
        Parse and normalize a raw inbound webhook payload.
        Called by the ChannelGateway after signature verification.
        """

    @abc.abstractmethod
    async def upload_media(self, file_bytes: bytes, mime_type: str,
                           file_name: str) -> str:
        """Upload media to the provider's media server. Returns provider_media_id."""

    @abc.abstractmethod
    async def download_media(self, provider_media_id: str) -> bytes:
        """Download media from provider by media ID."""

    @abc.abstractmethod
    async def mark_read(self, provider_message_id: str) -> None:
        """Mark a message as read. No-op if provider doesn't support it."""

    @abc.abstractmethod
    async def send_typing(self, recipient_identifier: str) -> None:
        """Send typing indicator. No-op if not supported."""

    @abc.abstractmethod
    async def get_delivery_status(self, provider_message_id: str) -> ProviderDeliveryStatus:
        """Poll delivery status for a message. Used for providers without push callbacks."""

    @abc.abstractmethod
    async def verify_webhook_signature(self, raw_body: bytes,
                                       headers: Dict[str, str]) -> bool:
        """
        Verify that the inbound webhook is authentic.
        Must return True to proceed, False to reject.
        """

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Clean up any provider resources / connections."""

    def normalize_error(self, error_code: Optional[str], error_message: Optional[str]) -> Tuple[DeliveryStatusEnum, bool]:
        """
        Maps provider-specific error codes into (DeliveryStatusEnum, is_retryable).
        Default implementation provides standard heuristics.
        """
        err_str = f"{error_code or ''} {error_message or ''}".lower()
        if not error_code and not error_message:
            return DeliveryStatusEnum.FAILED, False
        if any(w in err_str for w in ("rate limit", "throttl", "429", "too many requests", "130429", "131047")):
            return DeliveryStatusEnum.RATE_LIMITED, True
        if any(w in err_str for w in ("auth", "token", "unauthorized", "401", "403", "190", "permission")):
            return DeliveryStatusEnum.AUTH_FAILED, False
        if any(w in err_str for w in ("invalid recipient", "invalid phone", "not a whatsapp user", "131026", "131051", "recipient")):
            return DeliveryStatusEnum.INVALID_RECIPIENT, False
        if any(w in err_str for w in ("timeout", "503", "502", "504", "unavailable", "connection refused", "temporary")):
            return DeliveryStatusEnum.PROVIDER_UNAVAILABLE, True
        if any(w in err_str for w in ("config", "missing credentials", "placeholder")):
            return DeliveryStatusEnum.CONFIGURATION_REQUIRED, False
        return DeliveryStatusEnum.FAILED, False
