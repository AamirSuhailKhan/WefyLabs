"""
PolicyService — Global Compliance Policy Evaluator
===================================================
Evaluates compliance policies before any regulated action.
Checked before: WhatsApp dispatch, SMS, Email, AI auto-actions, bulk messaging, etc.

Resolution: Most-specific policy wins.
  Lead-level → Organization+Market → Organization → Market → Country → Global

Decision outcomes:
  ALLOWED            — action is permitted
  BLOCKED            — action is not permitted
  REQUIRES_APPROVAL  — action requires human review
  UNKNOWN            — no applicable policy found (caller decides)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.global_models import CompliancePolicy

logger = logging.getLogger(__name__)


class PolicyDecision:
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class PolicyContext:
    """Context for policy evaluation."""
    organization_id: Optional[str] = None
    market_id: Optional[str] = None
    country_id: Optional[str] = None
    lead_id: Optional[str] = None
    channel: Optional[str] = None              # WHATSAPP | SMS | EMAIL | VOICE
    time_utc: Optional[datetime] = None
    # Agent performing the action
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    # Additional signals
    extras: Optional[Dict[str, Any]] = None


@dataclass
class PolicyEvaluationResult:
    """Full policy evaluation result with audit trail."""
    decision: str                  # ALLOWED | BLOCKED | REQUIRES_APPROVAL | UNKNOWN
    reason: str
    policy_id: Optional[str] = None
    policy_key: Optional[str] = None
    policy_version: Optional[int] = None
    category: Optional[str] = None
    action: Optional[str] = None
    timestamp: Optional[str] = None

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOWED

    @property
    def is_blocked(self) -> bool:
        return self.decision == PolicyDecision.BLOCKED

    @property
    def requires_approval(self) -> bool:
        return self.decision == PolicyDecision.REQUIRES_APPROVAL


class PolicyService:
    """
    Central policy evaluation service.
    All communication services, AI services, and workflow engines
    must call PolicyService.evaluate() before performing regulated actions.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def evaluate(
        self,
        category: str,       # COMMUNICATION | AI_ACTION | DATA_RETENTION | CONSENT | KYC | MARKETING
        action: str,         # e.g. "send_whatsapp", "auto_book_viewing", "bulk_message"
        context: PolicyContext,
    ) -> PolicyEvaluationResult:
        """
        Evaluate whether an action is permitted under current policies.
        Resolves the most-specific applicable policy.
        """
        now = context.time_utc or datetime.now(timezone.utc)
        timestamp = now.isoformat()

        # Load candidate policies — ordered by specificity (org+market most specific, then broader)
        policies = await self._load_policies(category, context, now)

        if not policies:
            logger.debug(f"[Policy] No policy found for category={category} action={action}. Decision: UNKNOWN.")
            return PolicyEvaluationResult(
                decision=PolicyDecision.UNKNOWN,
                reason=f"No policy configured for category={category}, action={action}.",
                category=category, action=action, timestamp=timestamp,
            )

        for policy in policies:
            result = self._evaluate_rule(policy, action, context, timestamp)
            if result is not None:
                logger.debug(
                    f"[Policy] Evaluated {category}/{action} → {result.decision} "
                    f"(policy={policy.policy_key} v{policy.version})"
                )
                return result

        return PolicyEvaluationResult(
            decision=PolicyDecision.UNKNOWN,
            reason=f"Policies found but no rule matched action={action}.",
            category=category, action=action, timestamp=timestamp,
        )

    async def evaluate_communication(
        self,
        channel: str,           # WHATSAPP | SMS | EMAIL | VOICE
        context: PolicyContext,
    ) -> PolicyEvaluationResult:
        """
        Evaluate whether a communication action is permitted.
        Convenience wrapper for COMMUNICATION category.
        """
        return await self.evaluate(
            category="COMMUNICATION",
            action=f"send_{channel.lower()}",
            context=context,
        )

    async def evaluate_ai_action(
        self,
        ai_action: str,         # auto_book_viewing | bulk_message | send_contract | auto_schedule
        context: PolicyContext,
    ) -> PolicyEvaluationResult:
        """
        Evaluate whether an AI-driven action is permitted.
        Convenience wrapper for AI_ACTION category.
        """
        return await self.evaluate(
            category="AI_ACTION",
            action=ai_action,
            context=context,
        )

    def _evaluate_rule(
        self,
        policy: CompliancePolicy,
        action: str,
        context: PolicyContext,
        timestamp: str,
    ) -> Optional[PolicyEvaluationResult]:
        """
        Evaluate a single policy rule against the action and context.
        Returns None if the policy does not apply to this action.
        """
        rule = policy.rule_json or {}
        applicable_actions = rule.get("actions", [])

        # Check if this rule applies to the requested action
        if applicable_actions and action not in applicable_actions:
            return None

        # Check time-based rules (quiet hours)
        if context.time_utc and "quiet_hours" in rule:
            qh = rule["quiet_hours"]
            local_hour = self._get_local_hour(context.time_utc, qh.get("timezone", "UTC"))
            quiet_start = qh.get("start_hour", 21)
            quiet_end = qh.get("end_hour", 8)
            in_quiet = (
                (quiet_start > quiet_end and (local_hour >= quiet_start or local_hour < quiet_end)) or
                (quiet_start <= quiet_end and quiet_start <= local_hour < quiet_end)
            )
            if in_quiet:
                return PolicyEvaluationResult(
                    decision=PolicyDecision.BLOCKED,
                    reason=f"Action blocked: within quiet hours ({quiet_start}:00–{quiet_end}:00 local).",
                    policy_id=str(policy.id),
                    policy_key=policy.policy_key,
                    policy_version=policy.version,
                    category=policy.category,
                    action=action, timestamp=timestamp,
                )

        # Check explicit decision
        decision_str = rule.get("decision", "UNKNOWN").upper()
        reason = rule.get("reason", f"Policy {policy.policy_key} decision: {decision_str}.")

        if decision_str in (PolicyDecision.ALLOWED, PolicyDecision.BLOCKED, PolicyDecision.REQUIRES_APPROVAL):
            return PolicyEvaluationResult(
                decision=decision_str,
                reason=reason,
                policy_id=str(policy.id),
                policy_key=policy.policy_key,
                policy_version=policy.version,
                category=policy.category,
                action=action, timestamp=timestamp,
            )

        return None

    async def _load_policies(
        self,
        category: str,
        context: PolicyContext,
        now: datetime,
    ) -> list[CompliancePolicy]:
        """
        Load all active policies for the given context, ordered from most-specific to least.
        """
        filters = [
            CompliancePolicy.category == category,
            CompliancePolicy.status == "ACTIVE",
            CompliancePolicy.effective_from <= now,
            or_(CompliancePolicy.expires_at.is_(None), CompliancePolicy.expires_at > now),
        ]

        # Scope filters — retrieve all relevant scopes, sort by specificity in Python
        scope_filters = [
            and_(
                CompliancePolicy.organization_id == context.organization_id,
                CompliancePolicy.market_id == context.market_id,
            ),
            and_(
                CompliancePolicy.organization_id == context.organization_id,
                CompliancePolicy.market_id.is_(None),
            ),
            and_(
                CompliancePolicy.organization_id.is_(None),
                CompliancePolicy.market_id == context.market_id,
            ),
            and_(
                CompliancePolicy.organization_id.is_(None),
                CompliancePolicy.market_id.is_(None),
                CompliancePolicy.country_id == context.country_id,
            ),
            and_(
                CompliancePolicy.organization_id.is_(None),
                CompliancePolicy.market_id.is_(None),
                CompliancePolicy.country_id.is_(None),
            ),
        ]

        stmt = (
            select(CompliancePolicy)
            .where(and_(*filters, or_(*scope_filters)))
            .order_by(
                CompliancePolicy.organization_id.desc().nulls_last(),
                CompliancePolicy.market_id.desc().nulls_last(),
                CompliancePolicy.country_id.desc().nulls_last(),
                CompliancePolicy.version.desc(),
            )
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _get_local_hour(utc_dt: datetime, timezone_str: str) -> int:
        """Get local hour for quiet hours check."""
        try:
            from zoneinfo import ZoneInfo
            local_dt = utc_dt.astimezone(ZoneInfo(timezone_str))
            return local_dt.hour
        except Exception:
            return utc_dt.hour
