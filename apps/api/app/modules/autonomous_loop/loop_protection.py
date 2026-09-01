"""
Part 21.8 — Autonomous Sales Loop Loop Protection Service
==========================================================
Prevents runaway loops, excessive retries, and action budget overruns.

Protections:
  1. Max daily actions per lead (policy-configurable, default 3)
  2. Max consecutive failures (default 5)
  3. Orchestration depth counter (prevents recursive event loops)
  4. Daily counter reset at midnight UTC

INVARIANT: LoopProtection must NEVER allow more actions than permitted.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow_up_models import FollowUpPolicy
from app.modules.autonomous_loop.models import LeadAutomationState

logger = logging.getLogger(__name__)

# ── Default limits ─────────────────────────────────────────────────────────────
DEFAULT_MAX_DAILY_ACTIONS = 3
DEFAULT_MAX_CONSECUTIVE_FAILURES = 5
DEFAULT_MAX_ORCHESTRATION_DEPTH = 10


class LoopProtectionService:
    """
    Stateless per-request loop protection evaluation.
    State is read from LeadAutomationState in the database.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def evaluate(
        self,
        automation_state: LeadAutomationState,
        policy: Optional[FollowUpPolicy] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates loop protection rules.
        Returns (is_permitted, reason_if_blocked).
        """
        max_daily = (
            policy.max_messages_per_day if policy and policy.max_messages_per_day else DEFAULT_MAX_DAILY_ACTIONS
        )

        # ── 1. Reset daily counter if new day ─────────────────────────────────
        now_utc = datetime.now(timezone.utc)
        if automation_state.daily_action_reset_at:
            reset_date = automation_state.daily_action_reset_at.date()
            if now_utc.date() > reset_date:
                # Counter reset would happen during execute_action_recorded call
                # For evaluation purposes, treat as 0 if day has reset
                daily_count = 0
            else:
                daily_count = automation_state.daily_action_count
        else:
            daily_count = automation_state.daily_action_count

        # ── 2. Daily action budget ─────────────────────────────────────────────
        if daily_count >= max_daily:
            return (
                False,
                f"Daily action budget exhausted: {daily_count}/{max_daily} actions taken today. "
                f"Loop protection engaged.",
            )

        # ── 3. Consecutive failures ────────────────────────────────────────────
        if automation_state.consecutive_failures >= DEFAULT_MAX_CONSECUTIVE_FAILURES:
            return (
                False,
                f"Consecutive failure limit reached: {automation_state.consecutive_failures} failures. "
                f"Lead requires human review.",
            )

        # ── 4. Orchestration depth ─────────────────────────────────────────────
        if automation_state.orchestration_depth >= DEFAULT_MAX_ORCHESTRATION_DEPTH:
            return (
                False,
                f"Orchestration depth limit reached: {automation_state.orchestration_depth}. "
                f"Recursive event loop protection engaged.",
            )

        return True, None

    async def record_action_executed(
        self,
        automation_state: LeadAutomationState,
    ) -> None:
        """Updates loop counters after a successful action dispatch."""
        now_utc = datetime.now(timezone.utc)

        # Reset daily counter if new day
        if automation_state.daily_action_reset_at:
            if now_utc.date() > automation_state.daily_action_reset_at.date():
                automation_state.daily_action_count = 0

        automation_state.daily_action_count += 1
        automation_state.daily_action_reset_at = now_utc
        automation_state.consecutive_failures = 0
        automation_state.orchestration_depth = max(0, automation_state.orchestration_depth - 1)
        automation_state.updated_at = now_utc
        await self.db.flush()

    async def record_failure(self, automation_state: LeadAutomationState) -> None:
        """Increments consecutive failure counter."""
        automation_state.consecutive_failures += 1
        automation_state.orchestration_depth = max(0, automation_state.orchestration_depth - 1)
        automation_state.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def increment_depth(self, automation_state: LeadAutomationState) -> None:
        """Increments orchestration depth counter."""
        automation_state.orchestration_depth += 1
        automation_state.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
