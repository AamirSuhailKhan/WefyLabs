import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class SubscribeRequest(BaseModel):
    plan_id: str = Field(..., description="Plan ID e.g. starter_monthly, starter_annual, pro_monthly, pro_annual")
    broker_id: Optional[uuid.UUID] = Field(None, description="Optional broker ID override")

class SubscribeResponse(BaseModel):
    subscription_id: uuid.UUID
    razorpay_subscription_id: str
    short_url: str
    amount: int  # in paise
    currency: str = "INR"

class SubscriptionStatusResponse(BaseModel):
    subscription_status: str
    subscription_plan: Optional[str] = None
    trial_ends_at: datetime
    trial_days_remaining: int
    razorpay_customer_id: Optional[str] = None
    razorpay_subscription_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
