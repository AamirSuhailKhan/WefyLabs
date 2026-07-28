from datetime import datetime
from typing import Optional, List
import uuid
from pydantic import BaseModel, ConfigDict, Field

class SubscriptionBase(BaseModel):
    razorpay_payment_id: Optional[str] = Field(None, max_length=255)
    razorpay_subscription_id: Optional[str] = Field(None, max_length=255)
    amount: int = Field(..., description="Amount in paise")
    currency: str = Field("INR", max_length=3)
    status: str = Field("created", max_length=20)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class SubscriptionCreate(SubscriptionBase):
    broker_id: uuid.UUID

class SubscriptionUpdate(BaseModel):
    razorpay_payment_id: Optional[str] = Field(None, max_length=255)
    razorpay_subscription_id: Optional[str] = Field(None, max_length=255)
    amount: Optional[int] = None
    currency: Optional[str] = Field(None, max_length=3)
    status: Optional[str] = Field(None, max_length=20)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class SubscriptionResponse(SubscriptionBase):
    id: uuid.UUID
    broker_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SubscriptionListResponse(BaseModel):
    items: List[SubscriptionResponse]
    total: int
    page: int
    page_size: int
    pages: int
