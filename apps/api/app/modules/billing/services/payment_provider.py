"""
WefyLabs Canonical Payment Provider Abstraction
================================================
Provider-agnostic interface decoupling core billing services from external payment gateways.
- Standardizes provider customer creation, order creation, capture, refunds, and webhooks.
- Normalizes gateway error responses into unified internal exceptions.
- RazorpayAdapter converges directly onto RazorpayProductionService.
"""
from __future__ import annotations

import abc
import uuid
from typing import Dict, Any, Optional
from decimal import Decimal
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.modules.billing.services.razorpay_service import RazorpayProductionService
from app.modules.billing.dto.payment_dto import (
    CreatePaymentOrderRequest,
    CreatePaymentOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    CreateRefundRequest,
    CreateRefundResponse,
)


class PaymentProviderError(Exception):
    """Normalized payment provider exception."""
    def __init__(self, code: str, message: str, provider: str = "RAZORPAY"):
        self.code = code
        self.message = message
        self.provider = provider
        super().__init__(f"[{provider}] {code}: {message}")


class PaymentProvider(abc.ABC):
    """Abstract payment provider gateway interface."""

    @abc.abstractmethod
    async def create_order(
        self,
        broker: Broker,
        plan_id: str,
        idempotency_key: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None
    ) -> CreatePaymentOrderResponse:
        pass

    @abc.abstractmethod
    async def verify_and_capture(
        self,
        broker: Broker,
        order_id: str,
        payment_id: str,
        signature: str,
        client_ip: Optional[str] = None
    ) -> VerifyPaymentResponse:
        pass

    @abc.abstractmethod
    async def create_refund(
        self,
        broker: Broker,
        payment_id: str,
        amount_paise: Optional[int] = None,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> CreateRefundResponse:
        pass


class RazorpayAdapter(PaymentProvider):
    """
    Production Razorpay implementation converging directly on RazorpayProductionService.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.service = RazorpayProductionService(db)

    async def create_order(
        self,
        broker: Broker,
        plan_id: str,
        idempotency_key: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None
    ) -> CreatePaymentOrderResponse:
        req = CreatePaymentOrderRequest(
            plan_id=plan_id,
            idempotency_key=idempotency_key,
            notes=notes,
        )
        return await self.service.create_payment_order(broker, req, client_ip)

    async def verify_and_capture(
        self,
        broker: Broker,
        order_id: str,
        payment_id: str,
        signature: str,
        client_ip: Optional[str] = None
    ) -> VerifyPaymentResponse:
        req = VerifyPaymentRequest(
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
        )
        return await self.service.finalize_payment(broker, req, client_ip)

    async def create_refund(
        self,
        broker: Broker,
        payment_id: str,
        amount_paise: Optional[int] = None,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> CreateRefundResponse:
        req = CreateRefundRequest(
            razorpay_payment_id=payment_id,
            amount_paise=amount_paise,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        return await self.service.create_refund(broker, req, client_ip)
