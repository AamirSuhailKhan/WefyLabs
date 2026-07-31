import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class TransactionStage(str, Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPERTY_VISIT = "property_visit"
    OFFER = "offer"
    NEGOTIATION = "negotiation"
    BOOKING = "booking"
    DOCUMENTS = "documents"
    LOAN = "loan"
    LEGAL = "legal"
    REGISTRATION = "registration"
    CLOSING = "closing"
    COMMISSION = "commission"
    AFTER_SALES = "after_sales"

class DealRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH_RISK = "high_risk"
    CRITICAL_STALLED = "critical_stalled"

@dataclass
class PaymentInstallmentEntity:
    id: uuid.UUID
    name: str
    amount: float
    due_date: datetime
    is_paid: bool = False
    paid_at: Optional[datetime] = None

@dataclass
class DealMilestoneEntity:
    id: uuid.UUID
    stage: TransactionStage
    title: str
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None

@dataclass
class DealTransactionEntity:
    """Pure Domain Entity for a Real Estate Deal Transaction Lifecycle."""
    id: uuid.UUID
    broker_id: uuid.UUID
    lead_id: uuid.UUID
    property_id: uuid.UUID
    deal_name: str
    agreed_price: float
    currency: str
    current_stage: TransactionStage
    commission_percentage: float = 2.0
    estimated_commission_amount: float = 0.0
    risk_level: DealRiskLevel = DealRiskLevel.LOW
    closing_probability_pct: float = 85.0
    missing_documents: List[str] = field(default_factory=list)
    milestones: List[DealMilestoneEntity] = field(default_factory=list)
    installments: List[PaymentInstallmentEntity] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
