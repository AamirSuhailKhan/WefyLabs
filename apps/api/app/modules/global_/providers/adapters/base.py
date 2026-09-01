"""
Provider Adapter Base Classes
==============================
All provider integrations (payment, WhatsApp, SMS, email, FX) must implement
the abstract adapter interfaces defined here.

Architecture Rules:
- Core services NEVER import provider SDKs directly
- All provider interaction flows through adapters
- Adapters are selected at runtime by ProviderRegistry
- Provider credentials are stored in vault — never in code or plaintext DB
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Any, Dict

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SHARED TYPES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProviderHealthStatus:
    is_healthy: bool
    status: str                    # HEALTHY | WARNING | DEGRADED | FAILED
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    provider_code: str = ""


@dataclass
class SendResult:
    success: bool
    provider_message_id: Optional[str]
    provider_code: str
    status: str                    # SENT | QUEUED | FAILED | RATE_LIMITED
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class DeliveryStatus:
    provider_message_id: str
    status: str                    # SENT | DELIVERED | READ | FAILED | UNKNOWN
    provider_code: str
    timestamp: Optional[str] = None


@dataclass
class MessageContent:
    text: Optional[str] = None
    template_name: Optional[str] = None
    template_params: Optional[Dict[str, str]] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None   # image | video | document | audio


# ─────────────────────────────────────────────────────────────────────────────
# BASE PROVIDER ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class BaseProviderAdapter(ABC):
    """Root abstract class for all provider adapters."""

    @property
    @abstractmethod
    def provider_code(self) -> str:
        """Unique lowercase provider identifier: 'razorpay', 'stripe', '360dialog'."""
        ...

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider category: PAYMENT | WHATSAPP | SMS | EMAIL | FX | CALENDAR."""
        ...

    @property
    def supported_country_codes(self) -> List[str]:
        """
        ISO Alpha-2 country codes where this provider is available.
        Empty list = globally available.
        """
        return []

    @abstractmethod
    async def health_check(self) -> ProviderHealthStatus:
        """Ping provider to verify connectivity and credentials."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT PROVIDER ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CustomerCreateResult:
    customer_id: str
    provider_code: str
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class SubscriptionCreateResult:
    subscription_id: str
    provider_subscription_id: str
    short_url: Optional[str]
    amount: str                    # Decimal string — NEVER float
    currency_code: str
    status: str
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class WebhookVerificationResult:
    is_valid: bool
    event_type: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class BasePaymentAdapter(BaseProviderAdapter):
    """Abstract interface for payment gateway providers."""

    @property
    def provider_type(self) -> str:
        return "PAYMENT"

    @abstractmethod
    async def create_customer(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CustomerCreateResult:
        """Create or retrieve a customer record in the payment gateway."""
        ...

    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        currency_code: str,
        amount_decimal: str,         # Decimal string — NEVER float
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SubscriptionCreateResult:
        """Create a recurring subscription."""
        ...

    @abstractmethod
    async def cancel_subscription(self, provider_subscription_id: str) -> bool:
        """Cancel a subscription."""
        ...

    @abstractmethod
    async def verify_webhook(
        self,
        payload_bytes: bytes,
        signature_header: str,
    ) -> WebhookVerificationResult:
        """Verify inbound webhook signature."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP PROVIDER ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class BaseWhatsAppAdapter(BaseProviderAdapter):
    """Abstract interface for WhatsApp BSP (Business Solution Provider) adapters."""

    @property
    def provider_type(self) -> str:
        return "WHATSAPP"

    @abstractmethod
    async def send_message(
        self,
        to_e164: str,              # E.164 format: "+971501234567"
        content: MessageContent,
    ) -> SendResult:
        """Send a WhatsApp message (text or media)."""
        ...

    @abstractmethod
    async def send_template(
        self,
        to_e164: str,
        template_name: str,
        language_code: str,        # "en" | "ar" | "hi"
        params: Optional[Dict[str, str]] = None,
    ) -> SendResult:
        """Send an approved WhatsApp template message."""
        ...

    @abstractmethod
    async def get_delivery_status(self, provider_message_id: str) -> DeliveryStatus:
        """Poll delivery status for a sent message."""
        ...

    @abstractmethod
    async def verify_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """Verify inbound webhook from WhatsApp provider."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# SMS PROVIDER ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class BaseSMSAdapter(BaseProviderAdapter):
    """Abstract interface for SMS providers."""

    @property
    def provider_type(self) -> str:
        return "SMS"

    @abstractmethod
    async def send_sms(
        self,
        to_e164: str,
        message: str,
        sender_id: Optional[str] = None,
    ) -> SendResult:
        ...

    @abstractmethod
    async def get_delivery_status(self, provider_message_id: str) -> DeliveryStatus:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL PROVIDER ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EmailSendResult:
    success: bool
    provider_message_id: Optional[str]
    provider_code: str
    status: str
    error_message: Optional[str] = None


class BaseEmailAdapter(BaseProviderAdapter):
    """Abstract interface for email providers."""

    @property
    def provider_type(self) -> str:
        return "EMAIL"

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_name: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmailSendResult:
        ...

    @abstractmethod
    async def send_template(
        self,
        to_email: str,
        template_id: str,
        template_data: Dict[str, Any],
    ) -> EmailSendResult:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# FX RATE PROVIDER ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

from decimal import Decimal
from datetime import date


@dataclass
class FXRateData:
    base_currency: str
    rates: Dict[str, Decimal]   # quote_currency → rate (Decimal)
    provider_code: str
    timestamp: str              # ISO8601 UTC


class BaseFXAdapter(BaseProviderAdapter):
    """Abstract interface for FX rate providers."""

    @property
    def provider_type(self) -> str:
        return "FX"

    @abstractmethod
    async def get_latest_rates(self, base_currency: str) -> FXRateData:
        """Fetch latest rates for all available currencies against base."""
        ...

    @abstractmethod
    async def get_rate(self, base_currency: str, quote_currency: str) -> Decimal:
        """Fetch a single pair rate."""
        ...

    @abstractmethod
    async def get_historical_rates(self, base_currency: str, historical_date: date) -> FXRateData:
        """Fetch historical rates for a specific date."""
        ...
