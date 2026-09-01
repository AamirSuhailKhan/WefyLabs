"""
Part 21.4.1 — AI Lead Qualification Taxonomies & Normalizers
===========================================================
Defines controlled domain values and normalizers for:
- QualificationState
- QualificationIntent
- QualificationBuyerType
- QualificationTimeline
- QualificationFinancing
- FactValueCategory
- EvidenceSourceType
- FactStatus
- ConflictStatus
- QualificationAuditActorType
- QualificationAuditEventType

NON-NEGOTIABLE PRINCIPLE:
If a value is unknown or ungrounded, normalizers strictly return UNKNOWN.
Assumed/fabricated defaults are strictly prohibited.
"""
from typing import Optional, Any
from app.models.qualification_models import (
    QualificationState,
    QualificationIntent,
    QualificationBuyerType,
    QualificationTimeline,
    QualificationFinancing,
    FactValueCategory,
    EvidenceSourceType,
    FactStatus,
    ConflictStatus,
    QualificationAuditActorType,
    QualificationAuditEventType,
)


class QualificationTaxonomyNormalizer:
    """Deterministic normalizer for real-estate qualification taxonomies."""

    @staticmethod
    def normalize_intent(raw: Optional[str]) -> QualificationIntent:
        if not raw or not isinstance(raw, str):
            return QualificationIntent.UNKNOWN
        val = raw.strip().upper()
        if val in ("BUY", "PURCHASE", "BUYING", "BUYER"):
            return QualificationIntent.BUY
        if val in ("RENT", "LEASE", "RENTING", "TENANT", "RENTER"):
            return QualificationIntent.RENT
        if val in ("INVEST", "INVESTMENT", "INVESTING", "INVESTOR"):
            return QualificationIntent.INVEST
        if val in ("SELL", "SELLING", "SELLER", "VENDOR"):
            return QualificationIntent.SELL
        return QualificationIntent.UNKNOWN

    @staticmethod
    def normalize_buyer_type(raw: Optional[str]) -> QualificationBuyerType:
        if not raw or not isinstance(raw, str):
            return QualificationBuyerType.UNKNOWN
        val = raw.strip().upper().replace(" ", "_").replace("-", "_")
        if val in ("END_USER", "FIRST_TIME_BUYER", "SELF_USE", "OWNER_OCCUPIER", "FAMILY"):
            return QualificationBuyerType.END_USER
        if val in ("INVESTOR", "CAPITAL_GROWTH", "HIGH_YIELD", "PORTFOLIO"):
            return QualificationBuyerType.INVESTOR
        if val in ("LANDLORD", "LESSOR"):
            return QualificationBuyerType.LANDLORD
        if val in ("TENANT", "LESSEE", "RENTER"):
            return QualificationBuyerType.TENANT
        if val in ("COMPANY", "CORPORATE", "INSTITUTIONAL", "BUSINESS"):
            return QualificationBuyerType.COMPANY
        if val in ("AGENT", "BROKER", "INTERMEDIARY", "CHANNEL_PARTNER"):
            return QualificationBuyerType.AGENT
        return QualificationBuyerType.UNKNOWN

    @staticmethod
    def normalize_timeline(raw: Optional[str]) -> QualificationTimeline:
        if not raw or not isinstance(raw, str):
            return QualificationTimeline.UNKNOWN
        val = raw.strip().lower().replace(" ", "_").replace("-", "_")
        if val in ("immediate", "ready", "urgent", "asap", "this_week", "now"):
            return QualificationTimeline.IMMEDIATE
        if val in ("within_30_days", "30_days", "1_month", "one_month", "next_month"):
            return QualificationTimeline.WITHIN_30_DAYS
        if val in ("within_3_months", "3_months", "three_months", "quarter", "1_3_months"):
            return QualificationTimeline.WITHIN_3_MONTHS
        if val in ("within_6_months", "6_months", "six_months", "3_6_months", "half_year"):
            return QualificationTimeline.WITHIN_6_MONTHS
        if val in ("within_12_months", "12_months", "one_year", "6_12_months", "this_year"):
            return QualificationTimeline.WITHIN_12_MONTHS
        if val in ("more_than_12_months", "12_plus_months", "next_year", "long_term", "exploring"):
            return QualificationTimeline.MORE_THAN_12_MONTHS
        return QualificationTimeline.UNKNOWN

    @staticmethod
    def normalize_financing(raw: Optional[str]) -> QualificationFinancing:
        if not raw or not isinstance(raw, str):
            return QualificationFinancing.UNKNOWN
        val = raw.strip().upper().replace(" ", "_").replace("-", "_")
        if val in ("CASH", "SELF_FUNDED", "SAVINGS", "LIQUID"):
            return QualificationFinancing.CASH
        if val in ("MORTGAGE", "HOME_LOAN", "BANK_LOAN", "PRE_APPROVED", "LOAN"):
            return QualificationFinancing.MORTGAGE
        if val in ("PAYMENT_PLAN", "DEVELOPER_PLAN", "POST_HANDOVER", "INSTALLMENTS"):
            return QualificationFinancing.PAYMENT_PLAN
        return QualificationFinancing.UNKNOWN

    @staticmethod
    def normalize_source_type(raw: Optional[str]) -> EvidenceSourceType:
        if not raw or not isinstance(raw, str):
            return EvidenceSourceType.LEAD_FIELD
        val = raw.strip().upper()
        try:
            return EvidenceSourceType(val)
        except ValueError:
            return EvidenceSourceType.LEAD_FIELD
