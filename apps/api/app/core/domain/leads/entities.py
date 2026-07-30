import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class LeadScoreCategory(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    UNQUALIFIED = "unqualified"
    PENDING = "pending"
    SPAM = "spam"

class LeadStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"
    SPAM = "spam"

class PipelineStageEnum(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    VIEWING = "viewing"
    NEGOTIATING = "negotiating"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

@dataclass
class LeadScoreValueObject:
    score: LeadScoreCategory
    confidence: float
    reasoning: str
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class LeadEntity:
    """Pure Domain Entity representing a Real Estate Lead."""
    id: uuid.UUID
    broker_id: uuid.UUID
    phone: str
    name: Optional[str] = "New Lead"
    source: str = "manual"
    score: LeadScoreCategory = LeadScoreCategory.PENDING
    score_confidence: float = 0.0
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    preferred_locations: List[str] = field(default_factory=list)
    timeline: Optional[str] = None
    loan_status: Optional[str] = None
    status: LeadStatus = LeadStatus.PENDING
    pipeline_stage: PipelineStageEnum = PipelineStageEnum.NEW
    notes: List[Dict[str, Any]] = field(default_factory=list)
    last_message_at: Optional[datetime] = None
    qualified_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_as_qualified(self, score_val: LeadScoreValueObject) -> None:
        self.score = score_val.score
        self.score_confidence = score_val.confidence
        self.status = LeadStatus.QUALIFIED if score_val.score in (LeadScoreCategory.HOT, LeadScoreCategory.WARM) else LeadStatus.ACTIVE
        self.qualified_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def advance_stage(self, new_stage: PipelineStageEnum) -> None:
        self.pipeline_stage = new_stage
        self.updated_at = datetime.now(timezone.utc)
