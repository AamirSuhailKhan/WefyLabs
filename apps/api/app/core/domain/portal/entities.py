import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class CustomerRole(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"
    INVESTOR = "investor"

@dataclass
class CustomerDealProgressEntity:
    deal_id: uuid.UUID
    property_title: str
    agreed_price: float
    current_stage: str
    booking_deposit_paid: bool
    loan_approval_status: str # approved | pending | in_review
    legal_noc_status: str # verified | pending
    estimated_registration_date: str
    completion_percentage: float

@dataclass
class CustomerPortalEntity:
    """Pure Domain Entity for Customer Self-Service Portal."""
    customer_id: uuid.UUID
    name: str
    email: str
    phone: str
    role: CustomerRole
    active_deal: Optional[CustomerDealProgressEntity] = None
    saved_properties_count: int = 0
    assigned_broker_name: str = "Aamir Khan"
    assigned_broker_phone: str = "+971 50 123 4567"
