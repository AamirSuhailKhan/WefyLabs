"""
BeetleLabs Payment & Billing DTOs
=================================
Pydantic V2 schemas for Razorpay order generation, signature verification,
refund processing, webhook payloads, and payment history queries.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class CreatePaymentOrderRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plan_id: str = Field(..., description="Plan identifier from server catalog (e.g. starter_monthly, pro_monthly)")
    idempotency_key: Optional[str] = Field(None, description="Client-generated unique key to prevent duplicate orders")
    notes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Safe metadata tags")


class CreatePaymentOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    razorpay_order_id: str
    key_id: str = Field(..., description="Public Razorpay Key ID (safe for frontend)")
    amount: int = Field(..., description="Authoritative order amount in paise")
    currency: str = "INR"
    plan_id: str
    plan_name: str
    status: str
    created_at: datetime


class VerifyPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    razorpay_order_id: str = Field(..., description="Razorpay order ID returned by order creation")
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID returned by Checkout")
    razorpay_signature: str = Field(..., description="HMAC-SHA256 signature returned by Checkout")


class VerifyPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    status: str
    order_id: uuid.UUID
    transaction_id: uuid.UUID
    razorpay_payment_id: str
    razorpay_order_id: str
    amount: int
    currency: str
    plan_id: str
    message: str


class CreateRefundRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    razorpay_payment_id: str = Field(..., description="Razorpay payment ID to refund")
    amount: Optional[int] = Field(None, ge=100, description="Amount in paise to refund (None for full refund)")
    reason: Optional[str] = Field(None, description="Merchant reason for refund")
    idempotency_key: Optional[str] = Field(None, description="Unique key to prevent duplicate refund execution")


class CreateRefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    refund_id: uuid.UUID
    razorpay_refund_id: str
    razorpay_payment_id: str
    amount: int
    currency: str
    status: str
    created_at: datetime
    message: str


class PaymentTransactionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: Optional[uuid.UUID] = None
    razorpay_payment_id: str
    razorpay_order_id: Optional[str] = None
    amount: int
    currency: str
    status: str
    method: Optional[str] = None
    bank: Optional[str] = None
    wallet: Optional[str] = None
    vpa: Optional[str] = None
    captured_at: Optional[datetime] = None
    created_at: datetime


class PaymentRefundDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    razorpay_refund_id: str
    razorpay_payment_id: str
    amount: int
    currency: str
    status: str
    reason: Optional[str] = None
    created_at: datetime


class PaymentOrderDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    razorpay_order_id: str
    plan_id: str
    amount: int
    currency: str
    status: str
    created_at: datetime
    transactions: List[PaymentTransactionDTO] = []
    refunds: List[PaymentRefundDTO] = []


class PaymentHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    orders: List[PaymentOrderDTO]
    total_orders: int
    total_spent_paise: int


class ReconcileOrderResponse(BaseModel):
    order_id: str
    razorpay_order_id: str
    db_status: str
    provider_status: str
    reconciled: bool
    action_taken: str


class EmergencyPauseRequest(BaseModel):
    enabled: bool = Field(..., description="True to activate emergency pause, False to resume")
    reason: Optional[str] = Field(None, description="Administrative justification")


class EmergencyPauseResponse(BaseModel):
    emergency_pause_active: bool
    message: str
    timestamp: datetime


class PlanInfoDTO(BaseModel):
    plan_id: str
    name: str
    amount_paise: int
    amount_inr: float
    period: str
    plan_type: str
    price_usd: int
    features: List[str] = []
