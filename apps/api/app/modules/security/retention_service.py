"""
WefyLabs Enterprise Retention, Legal Hold & Controlled Deletion Engine
======================================================================
Build 11 Data Lifecycle & Compliance:
1. Retention Policy Registry:
   - Configurable retention periods across Leads, Conversations, Audit Logs, AI Traces, Exports, and Financials.
2. Legal Hold Mechanism:
   - Prevents deletion or automated purging of records subject to active legal/compliance holds.
   - Fail-closed: Attempting deletion of a record under Legal Hold returns HTTP 423 Locked.
3. Controlled Deletion Strategies:
   - SOFT_DELETE (flagged inactive)
   - ANONYMIZE (GDPR Article 17 Right-to-be-Forgotten; masks PII while preserving aggregate financial analytics)
   - HARD_DELETE (permanent purge when legally eligible)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Set, List
from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class RetentionDomain(str, Enum):
    LEADS = "leads"
    CONVERSATIONS = "conversations"
    AUDIT_LOGS = "audit_logs"
    AI_TRACES = "ai_traces"
    EXPORTS = "exports"
    FINANCIAL_RECORDS = "financial_records"


class DeletionStrategy(str, Enum):
    SOFT_DELETE = "SOFT_DELETE"
    ANONYMIZE = "ANONYMIZE"
    HARD_DELETE = "HARD_DELETE"


# Canonical Retention Periods in Days
DEFAULT_RETENTION_DAYS: dict[str, int] = {
    RetentionDomain.LEADS.value: 730,             # 2 years
    RetentionDomain.CONVERSATIONS.value: 365,      # 1 year
    RetentionDomain.AUDIT_LOGS.value: 2555,        # 7 years (SOC2 / ISO 27001 statutory requirement)
    RetentionDomain.AI_TRACES.value: 90,           # 90 days
    RetentionDomain.EXPORTS.value: 7,              # 7 days (auto-expire download links)
    RetentionDomain.FINANCIAL_RECORDS.value: 2555, # 7 years (Financial reporting statutory requirement)
}


class LegalHoldRecord(BaseModel):
    hold_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    target_type: str  # "organization", "lead", "conversation"
    target_id: str
    reason: str
    placed_by: str
    placed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    released_at: Optional[datetime] = None
    released_by: Optional[str] = None


class LegalHoldActiveError(HTTPException):
    def __init__(self, target_id: str, reason: str):
        super().__init__(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "code": "LEGAL_HOLD_ACTIVE",
                "message": f"Resource '{target_id}' is protected by an active Legal Hold and cannot be deleted or purged.",
                "reason": reason,
            }
        )


class DataRetentionManager:
    """In-memory & persistence-ready legal hold and retention governance manager."""

    _active_holds: Dict[str, LegalHoldRecord] = {}  # hold_id -> LegalHoldRecord
    _target_index: Dict[str, Set[str]] = {}         # target_id -> {hold_id, ...}

    @classmethod
    def place_legal_hold(
        cls,
        *,
        organization_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        placed_by: str
    ) -> LegalHoldRecord:
        """Places a legal hold on a specific target resource or entire organization."""
        record = LegalHoldRecord(
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            placed_by=placed_by
        )
        cls._active_holds[record.hold_id] = record
        if target_id not in cls._target_index:
            cls._target_index[target_id] = set()
        cls._target_index[target_id].add(record.hold_id)
        return record

    @classmethod
    def release_legal_hold(
        cls,
        hold_id: str,
        released_by: str
    ) -> Optional[LegalHoldRecord]:
        """Releases an active legal hold."""
        record = cls._active_holds.get(hold_id)
        if not record or not record.is_active:
            return None
        record.is_active = False
        record.released_at = datetime.now(timezone.utc)
        record.released_by = released_by

        # Remove from index
        target_holds = cls._target_index.get(record.target_id, set())
        target_holds.discard(hold_id)
        return record

    @classmethod
    def is_under_legal_hold(cls, target_id: str, organization_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Checks whether target resource (or its parent organization) is subject to an active legal hold.
        """
        # Check direct target hold
        hold_ids = cls._target_index.get(str(target_id), set())
        for hid in hold_ids:
            rec = cls._active_holds.get(hid)
            if rec and rec.is_active:
                return True, rec.reason

        # Check organization-wide hold
        if organization_id:
            org_hold_ids = cls._target_index.get(str(organization_id), set())
            for hid in org_hold_ids:
                rec = cls._active_holds.get(hid)
                if rec and rec.is_active:
                    return True, f"Organization-wide legal hold: {rec.reason}"

        return False, None

    @classmethod
    def verify_deletion_allowed(cls, target_id: str, organization_id: Optional[str] = None) -> None:
        """Raises LegalHoldActiveError if resource is locked under legal hold."""
        is_held, reason = cls.is_under_legal_hold(target_id, organization_id)
        if is_held:
            raise LegalHoldActiveError(target_id, reason or "Regulatory investigation hold")

    @classmethod
    def get_retention_days(cls, domain: str) -> int:
        """Returns statutory retention policy period in days for given domain."""
        return DEFAULT_RETENTION_DAYS.get(domain.lower(), 365)

    @classmethod
    def is_record_expired(cls, domain: str, created_at: datetime) -> bool:
        """Evaluates whether a record has exceeded its statutory retention window."""
        retention_days = cls.get_retention_days(domain)
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at < cutoff

    @classmethod
    def list_active_holds(cls, organization_id: Optional[str] = None) -> List[LegalHoldRecord]:
        """Lists active legal holds, optionally filtered by organization."""
        results = [h for h in cls._active_holds.values() if h.is_active]
        if organization_id:
            results = [h for h in results if h.organization_id == str(organization_id)]
        return results
