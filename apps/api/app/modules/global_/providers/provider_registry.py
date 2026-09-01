"""
ProviderRegistry — Runtime Provider Adapter Selection
======================================================
Routes each organization + market + provider_type to the correct adapter instance.
Provider configuration is stored in the ProviderConfiguration table.
Credentials are referenced via secret_ref (vault/secrets manager).

Resolution:
1. Load ProviderConfiguration for org + market + type (priority ordered)
2. Instantiate the appropriate adapter
3. Return primary; if health check fails → secondary → fallback

NEVER select provider based on: if country == "IN": use razorpay
ALWAYS select based on: ProviderConfiguration database record.
"""
from __future__ import annotations

import logging
from typing import Optional, Type, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.global_models import ProviderConfiguration, ProviderHealth
from app.modules.global_.providers.adapters.base import (
    BasePaymentAdapter, BaseWhatsAppAdapter, BaseSMSAdapter, BaseEmailAdapter, BaseFXAdapter,
    ProviderHealthStatus,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT ADAPTERS
# ─────────────────────────────────────────────────────────────────────────────

class RazorpayAdapter(BasePaymentAdapter):
    """
    Razorpay payment gateway adapter.
    Available for: India (IN)
    """
    provider_code = "razorpay"
    supported_country_codes = ["IN"]

    def __init__(self, config: dict, secret_ref: str):
        self._config = config
        self._secret_ref = secret_ref   # Resolved at runtime from vault

    async def health_check(self) -> ProviderHealthStatus:
        try:
            # In production: ping Razorpay /health or test GET /plans
            return ProviderHealthStatus(is_healthy=True, status="HEALTHY", provider_code=self.provider_code)
        except Exception as e:
            return ProviderHealthStatus(is_healthy=False, status="FAILED", error_message=str(e), provider_code=self.provider_code)

    async def create_customer(self, name, email, phone=None, metadata=None):
        from app.modules.global_.providers.adapters.base import CustomerCreateResult
        # In production: call razorpay.Customer.create(...)
        raise NotImplementedError("Razorpay create_customer — integrate with razorpay-python SDK")

    async def create_subscription(self, customer_id, plan_id, currency_code, amount_decimal, metadata=None):
        raise NotImplementedError("Razorpay create_subscription — integrate with razorpay-python SDK")

    async def cancel_subscription(self, provider_subscription_id):
        raise NotImplementedError("Razorpay cancel_subscription — integrate with razorpay-python SDK")

    async def verify_webhook(self, payload_bytes, signature_header):
        from app.modules.global_.providers.adapters.base import WebhookVerificationResult
        raise NotImplementedError("Razorpay verify_webhook — integrate with razorpay-python SDK")


class StripeAdapter(BasePaymentAdapter):
    """
    Stripe payment gateway adapter.
    Available for: US, GB, AU, CA, SG, AE and global.
    """
    provider_code = "stripe"
    supported_country_codes = []  # Global

    def __init__(self, config: dict, secret_ref: str):
        self._config = config
        self._secret_ref = secret_ref

    async def health_check(self) -> ProviderHealthStatus:
        try:
            return ProviderHealthStatus(is_healthy=True, status="HEALTHY", provider_code=self.provider_code)
        except Exception as e:
            return ProviderHealthStatus(is_healthy=False, status="FAILED", error_message=str(e), provider_code=self.provider_code)

    async def create_customer(self, name, email, phone=None, metadata=None):
        raise NotImplementedError("Stripe create_customer — integrate with stripe-python SDK")

    async def create_subscription(self, customer_id, plan_id, currency_code, amount_decimal, metadata=None):
        raise NotImplementedError("Stripe create_subscription — integrate with stripe-python SDK")

    async def cancel_subscription(self, provider_subscription_id):
        raise NotImplementedError("Stripe cancel_subscription — integrate with stripe-python SDK")

    async def verify_webhook(self, payload_bytes, signature_header):
        raise NotImplementedError("Stripe verify_webhook — integrate with stripe-python SDK")


class TapAdapter(BasePaymentAdapter):
    """
    Tap Payments gateway adapter.
    Available for: AE, SA, QA, KW, OM, BH (GCC region).
    """
    provider_code = "tap"
    supported_country_codes = ["AE", "SA", "QA", "KW", "OM", "BH"]

    def __init__(self, config: dict, secret_ref: str):
        self._config = config
        self._secret_ref = secret_ref

    async def health_check(self) -> ProviderHealthStatus:
        try:
            return ProviderHealthStatus(is_healthy=True, status="HEALTHY", provider_code=self.provider_code)
        except Exception as e:
            return ProviderHealthStatus(is_healthy=False, status="FAILED", error_message=str(e), provider_code=self.provider_code)

    async def create_customer(self, name, email, phone=None, metadata=None):
        raise NotImplementedError("Tap create_customer — integrate with tap payments API")

    async def create_subscription(self, customer_id, plan_id, currency_code, amount_decimal, metadata=None):
        raise NotImplementedError("Tap create_subscription — integrate with tap payments API")

    async def cancel_subscription(self, provider_subscription_id):
        raise NotImplementedError("Tap cancel_subscription — integrate with tap payments API")

    async def verify_webhook(self, payload_bytes, signature_header):
        raise NotImplementedError("Tap verify_webhook — integrate with tap payments API")


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP ADAPTERS
# ─────────────────────────────────────────────────────────────────────────────

class Dialog360Adapter(BaseWhatsAppAdapter):
    """360Dialog WhatsApp Business Solution Provider."""
    provider_code = "360dialog"
    supported_country_codes = []  # Global

    def __init__(self, config: dict, secret_ref: str):
        self._config = config
        self._secret_ref = secret_ref
        self._api_base = config.get("api_base", "https://waba.360dialog.io/v1")

    async def health_check(self) -> ProviderHealthStatus:
        return ProviderHealthStatus(is_healthy=True, status="HEALTHY", provider_code=self.provider_code)

    async def send_message(self, to_e164, content):
        raise NotImplementedError("360dialog send_message — integrate with existing Dialog360 service")

    async def send_template(self, to_e164, template_name, language_code, params=None):
        raise NotImplementedError("360dialog send_template — integrate with existing Dialog360 service")

    async def get_delivery_status(self, provider_message_id):
        raise NotImplementedError("360dialog get_delivery_status")

    async def verify_webhook(self, payload, signature):
        raise NotImplementedError("360dialog verify_webhook")


class MetaDirectAdapter(BaseWhatsAppAdapter):
    """Meta Cloud API — direct WhatsApp Business Platform."""
    provider_code = "meta_direct"
    supported_country_codes = []  # Global

    def __init__(self, config: dict, secret_ref: str):
        self._config = config
        self._secret_ref = secret_ref
        self._phone_number_id = config.get("phone_number_id")

    async def health_check(self) -> ProviderHealthStatus:
        return ProviderHealthStatus(is_healthy=True, status="HEALTHY", provider_code=self.provider_code)

    async def send_message(self, to_e164, content):
        raise NotImplementedError("Meta direct send_message — integrate with existing Meta Cloud service")

    async def send_template(self, to_e164, template_name, language_code, params=None):
        raise NotImplementedError("Meta direct send_template")

    async def get_delivery_status(self, provider_message_id):
        raise NotImplementedError("Meta direct get_delivery_status")

    async def verify_webhook(self, payload, signature):
        raise NotImplementedError("Meta direct verify_webhook")


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

PAYMENT_ADAPTERS: Dict[str, Type[BasePaymentAdapter]] = {
    "razorpay": RazorpayAdapter,
    "stripe": StripeAdapter,
    "tap": TapAdapter,
}

WHATSAPP_ADAPTERS: Dict[str, Type[BaseWhatsAppAdapter]] = {
    "360dialog": Dialog360Adapter,
    "meta_direct": MetaDirectAdapter,
}


class ProviderRegistry:
    """
    Runtime provider adapter registry.
    Selects provider adapters based on ProviderConfiguration database records.
    NEVER selects based on if country_code == "IN": use razorpay.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_payment_adapter(
        self,
        organization_id: str,
        market_id: Optional[str] = None,
    ) -> Optional[BasePaymentAdapter]:
        """
        Get the primary payment adapter for an org+market.
        Falls back to secondary/fallback if primary health check fails.
        """
        configs = await self._load_provider_configs(organization_id, market_id, "PAYMENT")

        for config in configs:
            adapter_cls = PAYMENT_ADAPTERS.get(config.provider_code)
            if not adapter_cls:
                logger.warning(f"[ProviderRegistry] Unknown payment provider: {config.provider_code}")
                continue
            adapter = adapter_cls(
                config=config.config_json or {},
                secret_ref=config.secret_ref or "",
            )
            health = await adapter.health_check()
            if health.is_healthy:
                return adapter
            logger.warning(
                f"[ProviderRegistry] Payment provider {config.provider_code} is {health.status}. "
                f"Trying next priority."
            )

        logger.error(f"[ProviderRegistry] No healthy payment provider for org={organization_id} market={market_id}")
        return None

    async def get_whatsapp_adapter(
        self,
        organization_id: str,
        market_id: Optional[str] = None,
    ) -> Optional[BaseWhatsAppAdapter]:
        """Get the primary WhatsApp adapter for an org+market."""
        configs = await self._load_provider_configs(organization_id, market_id, "WHATSAPP")

        for config in configs:
            adapter_cls = WHATSAPP_ADAPTERS.get(config.provider_code)
            if not adapter_cls:
                continue
            adapter = adapter_cls(
                config=config.config_json or {},
                secret_ref=config.secret_ref or "",
            )
            health = await adapter.health_check()
            if health.is_healthy:
                return adapter
            logger.warning(f"[ProviderRegistry] WhatsApp provider {config.provider_code} unhealthy. Trying next.")

        return None

    async def _load_provider_configs(
        self,
        organization_id: str,
        market_id: Optional[str],
        provider_type: str,
    ) -> list[ProviderConfiguration]:
        """Load provider configs ordered by priority (1=primary, 2=secondary, 3=fallback)."""
        conditions = [
            ProviderConfiguration.organization_id == organization_id,
            ProviderConfiguration.provider_type == provider_type,
            ProviderConfiguration.is_active == True,
        ]
        if market_id:
            conditions.append(ProviderConfiguration.market_id == market_id)

        stmt = (
            select(ProviderConfiguration)
            .where(and_(*conditions))
            .order_by(ProviderConfiguration.priority)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
