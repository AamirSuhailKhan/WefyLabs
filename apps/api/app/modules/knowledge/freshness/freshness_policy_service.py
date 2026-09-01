"""
Freshness Policy Service
=========================
Evaluates and enforces per-organization freshness policies on knowledge.

Each organization configures max_age_days and warn_at_days
per knowledge_type in KnowledgeFreshnessPolicy.

The service:
  1. Loads the active policy for a given knowledge_type
  2. Evaluates whether a document/chunk meets the freshness requirement
  3. Returns FRESH | WARN | STALE | EXPIRED with a safe AI response template

CRITICAL:
  STALE or EXPIRED knowledge must NEVER be presented as current fact.
  The AI agent must see the staleness status before generating any answer
  about prices, availability, or payment plans.

Example AI behavior:
  [STALE: 45 days]
  AI response: "I found a price list, but it's 45 days old and may not
  reflect current pricing. Please contact our team for the latest rates."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"        # Within policy max_age_days
    WARN = "WARN"          # Between warn_at_days and max_age_days
    STALE = "STALE"        # Beyond max_age_days
    EXPIRED = "EXPIRED"    # expires_at explicitly passed
    UNKNOWN = "UNKNOWN"    # No effective_at date; cannot determine age


# Safe responses by staleness level for transactional fact types
_STALE_RESPONSES = {
    FreshnessStatus.WARN: (
        "Note: This information is {days} days old and may not reflect "
        "the latest details. Please verify with our team."
    ),
    FreshnessStatus.STALE: (
        "This information is from {days} days ago and may be outdated. "
        "For accurate current details, please contact us directly."
    ),
    FreshnessStatus.EXPIRED: (
        "This knowledge source has expired and cannot be used to answer "
        "current factual questions. Please refer to our team for up-to-date information."
    ),
}

# Knowledge types where freshness is CRITICAL (transactional facts)
_CRITICAL_TYPES = {"PRICE", "AVAILABILITY", "PAYMENT_PLAN", "UNIT"}

# Default policy when no org-specific policy exists
_DEFAULT_POLICY = {
    "PRICE": {"max_age_days": 30, "warn_at_days": 25},
    "AVAILABILITY": {"max_age_days": 7, "warn_at_days": 5},
    "PAYMENT_PLAN": {"max_age_days": 90, "warn_at_days": 75},
    "UNIT": {"max_age_days": 14, "warn_at_days": 10},
    "FAQ": {"max_age_days": 365, "warn_at_days": 300},
    "POLICY": {"max_age_days": 730, "warn_at_days": 600},
    "MARKETING": {"max_age_days": 180, "warn_at_days": 150},
    "OTHER": {"max_age_days": 365, "warn_at_days": 300},
}


@dataclass
class FreshnessEvaluation:
    """Result of evaluating a document's freshness against policy."""
    status: FreshnessStatus
    age_days: int
    max_age_days: int
    warn_at_days: int
    knowledge_type: str
    is_critical: bool
    safe_response: Optional[str] = None  # Set when WARN/STALE/EXPIRED
    policy_source: str = "default"       # "org_policy" | "default"


class FreshnessPolicyService:
    """
    Evaluates document freshness against configurable per-org policies.
    Used during retrieval to flag stale/expired facts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate(
        self,
        organization_id: str,
        knowledge_type: str,
        effective_at: Optional[datetime],
        expires_at: Optional[datetime],
        updated_at: Optional[datetime],
    ) -> FreshnessEvaluation:
        """
        Evaluate whether a document is fresh for its knowledge type.

        Priority:
          1. Check explicit expires_at (always authoritative)
          2. Load org freshness policy (or default)
          3. Compute age from effective_at or updated_at
          4. Compare against policy thresholds
        """
        now = datetime.now(timezone.utc)
        is_critical = knowledge_type in _CRITICAL_TYPES

        # 1. Explicit expiration check
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                return FreshnessEvaluation(
                    status=FreshnessStatus.EXPIRED,
                    age_days=-1,
                    max_age_days=0,
                    warn_at_days=0,
                    knowledge_type=knowledge_type,
                    is_critical=is_critical,
                    safe_response=_STALE_RESPONSES[FreshnessStatus.EXPIRED],
                )

        # 2. Load policy
        policy = await self._load_policy(organization_id, knowledge_type)

        # 3. Compute document age
        reference = effective_at or updated_at
        if not reference:
            return FreshnessEvaluation(
                status=FreshnessStatus.UNKNOWN,
                age_days=-1,
                max_age_days=policy["max_age_days"],
                warn_at_days=policy["warn_at_days"],
                knowledge_type=knowledge_type,
                is_critical=is_critical,
                policy_source=policy.get("source", "default"),
            )

        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)

        age_days = max(0, (now - reference).days)
        max_age = policy["max_age_days"]
        warn_at = policy["warn_at_days"]

        # 4. Evaluate
        if age_days > max_age:
            status = FreshnessStatus.STALE
            safe_response = _STALE_RESPONSES[FreshnessStatus.STALE].format(days=age_days)
        elif age_days >= warn_at:
            status = FreshnessStatus.WARN
            safe_response = _STALE_RESPONSES[FreshnessStatus.WARN].format(days=age_days)
        else:
            status = FreshnessStatus.FRESH
            safe_response = None

        return FreshnessEvaluation(
            status=status,
            age_days=age_days,
            max_age_days=max_age,
            warn_at_days=warn_at,
            knowledge_type=knowledge_type,
            is_critical=is_critical,
            safe_response=safe_response,
            policy_source=policy.get("source", "default"),
        )

    def is_usable(self, evaluation: FreshnessEvaluation) -> bool:
        """
        Returns True if the knowledge is safe to use for AI answers.
        EXPIRED knowledge is NEVER usable.
        STALE critical knowledge is NOT usable.
        """
        if evaluation.status == FreshnessStatus.EXPIRED:
            return False
        if evaluation.status == FreshnessStatus.STALE and evaluation.is_critical:
            return False
        return True

    async def _load_policy(
        self, organization_id: str, knowledge_type: str
    ) -> Dict[str, Any]:
        """Load freshness policy from DB or fall back to defaults."""
        try:
            from app.models.knowledge_models import KnowledgeFreshnessPolicy
            result = await self.db.execute(
                select(KnowledgeFreshnessPolicy).where(
                    KnowledgeFreshnessPolicy.organization_id == organization_id,
                    KnowledgeFreshnessPolicy.knowledge_type == knowledge_type,
                    KnowledgeFreshnessPolicy.is_active == True,
                )
            )
            policy_row = result.scalars().first()
            if policy_row:
                return {
                    "max_age_days": policy_row.max_age_days,
                    "warn_at_days": policy_row.warn_at_days,
                    "source": "org_policy",
                }
        except Exception as exc:
            logger.warning(f"[FRESHNESS] Policy load failed: {exc}")

        # Fall back to default
        defaults = _DEFAULT_POLICY.get(knowledge_type, _DEFAULT_POLICY["OTHER"])
        return {**defaults, "source": "default"}
