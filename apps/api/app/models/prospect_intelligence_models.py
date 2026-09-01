"""
Part 21.2A — AI Prospect Intelligence Engine Models
=====================================================
SQLAlchemy 2.0 models for comprehensive, evidence-grounded prospect intelligence:
- Identity & Language
- Multi-dimensional Prospect Type & Transaction Intent
- Granular Property Requirements & Amenities
- Budget with Currency & Confidence
- Timeline, Financing, Purpose & Urgency
- 11 Field-Level Confidences (0.00 – 1.00)
- Provenance (Field -> Source Record mapping)
- Missing Information & Ranked Next Best Questions
- Verified Tenant-Scoped Property Matches
- Grounded Sales Intelligence Brief & Next Best Action
- Preference Conflict & Supersession History
"""
import uuid
import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float,
    JSON, Index, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")

def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ─── Enums ────────────────────────────────────────────────────────────────────

class ProspectType(str, enum.Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    RENTER = "RENTER"
    LANDLORD = "LANDLORD"
    INVESTOR = "INVESTOR"
    END_USER = "END_USER"
    DEVELOPER = "DEVELOPER"
    BROKER = "BROKER"
    UNKNOWN = "UNKNOWN"


class TransactionIntent(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    RENT = "RENT"
    LEASE = "LEASE"
    INVEST = "INVEST"
    INQUIRE = "INQUIRE"
    UNKNOWN = "UNKNOWN"


class TimelineCategory(str, enum.Enum):
    IMMEDIATE = "IMMEDIATE"
    ZERO_TO_THREE_MONTHS = "0_3_MONTHS"
    THREE_TO_SIX_MONTHS = "3_6_MONTHS"
    SIX_TO_TWELVE_MONTHS = "6_12_MONTHS"
    TWELVE_PLUS_MONTHS = "12_PLUS_MONTHS"
    UNKNOWN = "UNKNOWN"


class FinancingType(str, enum.Enum):
    CASH = "CASH"
    MORTGAGE = "MORTGAGE"
    FINANCING_REQUIRED = "FINANCING_REQUIRED"
    UNKNOWN = "UNKNOWN"


class PurposeCategory(str, enum.Enum):
    END_USE = "END_USE"
    INVESTMENT = "INVESTMENT"
    SECOND_HOME = "SECOND_HOME"
    RELOCATION = "RELOCATION"
    RENTAL_YIELD = "RENTAL_YIELD"
    UNKNOWN = "UNKNOWN"


class UrgencyLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class SalesReadiness(str, enum.Enum):
    NOT_READY = "NOT_READY"
    NEEDS_QUALIFICATION = "NEEDS_QUALIFICATION"
    SALES_READY = "SALES_READY"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class IntelligenceStatus(str, enum.Enum):
    ANALYZING = "ANALYZING"
    READY = "READY"
    FAILED = "FAILED"
    STALE = "STALE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class NextBestActionType(str, enum.Enum):
    SEND_PROPERTY_OPTIONS = "SEND_PROPERTY_OPTIONS"
    ASK_BUDGET = "ASK_BUDGET"
    ASK_TIMELINE = "ASK_TIMELINE"
    ASK_FINANCING = "ASK_FINANCING"
    OFFER_VIEWING = "OFFER_VIEWING"
    CALL_LEAD = "CALL_LEAD"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    WAIT_FOR_RESPONSE = "WAIT_FOR_RESPONSE"
    NO_ACTION = "NO_ACTION"


# ─── Models ───────────────────────────────────────────────────────────────────

class ProspectIntelligence(Base):
    """
    Unified AI Prospect Intelligence Profile.
    Persists structured, evidence-grounded insights for a single CRM lead.
    """
    __tablename__ = "prospect_intelligence_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(30), default=IntelligenceStatus.READY.value, nullable=False, index=True
    )
    intelligence_version: Mapped[str] = mapped_column(
        String(50), default="v1.0-real-estate-prospect", nullable=False
    )
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Identity & Language
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    # Intent & Roles
    prospect_types: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    transaction_intent: Mapped[str] = mapped_column(
        String(30), default=TransactionIntent.UNKNOWN.value, nullable=False, index=True
    )

    # Property Requirements
    property_requirements: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    # Budget & Financials
    budget: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )

    # Timeline, Financing, Purpose, Urgency
    timeline: Mapped[str] = mapped_column(
        String(30), default=TimelineCategory.UNKNOWN.value, nullable=False
    )
    financing: Mapped[str] = mapped_column(
        String(30), default=FinancingType.UNKNOWN.value, nullable=False
    )
    purpose: Mapped[str] = mapped_column(
        String(30), default=PurposeCategory.UNKNOWN.value, nullable=False
    )
    urgency: Mapped[str] = mapped_column(
        String(30), default=UrgencyLevel.UNKNOWN.value, nullable=False
    )

    # 11 Field-Level Confidences (0.00 – 1.00)
    confidences: Mapped[Dict[str, float]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discovery_relevance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)

    # Sales Readiness
    sales_readiness: Mapped[str] = mapped_column(
        String(30), default=SalesReadiness.NOT_READY.value, nullable=False, index=True
    )

    # Missing Information Engine
    missing_information: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    next_best_questions: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)

    # Verified Tenant Property Matches
    matched_properties: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)

    # Sales Intelligence Brief & Next Best Action
    sales_brief: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    next_best_action: Mapped[str] = mapped_column(
        String(50), default=NextBestActionType.NO_ACTION.value, nullable=False
    )
    next_best_action_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Field Provenance (Field -> Evidence Record)
    provenance: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Conflict / Supersession History
    conflicts: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)

    # Human Corrections / Overrides
    human_overrides: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Model & Execution Metadata
    model_provider: Mapped[str] = mapped_column(String(50), default="gemini", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="gemini-3.5-flash", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_prospect_intel_org_lead", "organization_id", "lead_id"),
        Index("ix_prospect_intel_org_readiness", "organization_id", "sales_readiness"),
        Index("ix_prospect_intel_org_intent", "organization_id", "transaction_intent"),
    )


class ProspectIntelligenceHistory(Base):
    """
    Immutable audit history log of prospect intelligence evaluations.
    Preserves historical analysis snapshots and preference shifts.
    """
    __tablename__ = "prospect_intelligence_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False)
    reason_for_change: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_prospect_hist_lead_created", "lead_id", "created_at"),
    )
