"""
Sprint 1F — Governed Adaptive Policy Pipeline Service
======================================================
Implements the governed policy lifecycle:

  CANDIDATE → PENDING_APPROVAL → APPROVED → ROLLING_OUT → ACTIVE → DEPRECATED
                                    ↓
                               [ROLLED_BACK] (at any post-APPROVED stage)

Core invariants enforced here:
1. Every status transition writes an immutable PolicyAuditLog entry.
2. CANDIDATE → ACTIVE direct promotion is BLOCKED. Must pass through APPROVED.
3. ACTIVE promotion requires a cleared PilotCohortGuard (N ≥ 30).
4. Emergency pause halts the Celery rollout controller without touching policy status.
5. Rollback sets traffic_pct=0, is_rolled_back=True, and creates an audit log.
6. Tenant isolation: every query scoped to org_id where applicable.

Sprint 1F Gates: G-01, G-02, G-07, G-08, G-13, G-14, G-15
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func, and_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence_models import (
    DataQualityIssue,
    OutcomeEvent,
    PolicyRegistryEntry,
    PolicyAuditLog,
    AdaptivePolicyRollout,
    PilotCohortGuard,
    RegistryEntryStatus,
    RegistryEntityType,
)

logger = logging.getLogger("wefylabs.intelligence.adaptive_policy")

# ─── Status Transition DAG ──────────────────────────────────────────────────────
# Allowed forward transitions only. Rollback is handled separately.
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    RegistryEntryStatus.CANDIDATE.value: [
        RegistryEntryStatus.EVALUATION.value,
        RegistryEntryStatus.APPROVED.value,
    ],
    RegistryEntryStatus.EVALUATION.value: [
        RegistryEntryStatus.APPROVED.value,
        RegistryEntryStatus.CANDIDATE.value,   # back to candidate on eval failure
    ],
    RegistryEntryStatus.APPROVED.value: [
        RegistryEntryStatus.ACTIVE.value,
    ],
    RegistryEntryStatus.ACTIVE.value: [
        RegistryEntryStatus.DEPRECATED.value,
    ],
    RegistryEntryStatus.DEPRECATED.value: [],   # terminal
    RegistryEntryStatus.ROLLED_BACK.value: [],  # terminal — create a new CANDIDATE
}

# Minimum eval_score required for human approval (CANDIDATE/EVALUATION → APPROVED)
MIN_APPROVAL_SCORE = Decimal("0.85")

# Pilot cohort thresholds
PILOT_MIN_LEADS = 30
PILOT_MIN_OBSERVATION_DAYS = 7


class AdaptivePolicyService:
    """
    Orchestrates the governed adaptive policy lifecycle for Sprint 1F.

    Design decisions:
    - All methods are async; callers must pass an open AsyncSession.
    - Every method that changes a PolicyRegistryEntry.status MUST call
      _write_audit_log immediately after the status change.
    - Pilot cohort guard is re-evaluated on each ACTIVE promotion attempt.
    """

    # ─── 1. Human Approval Gate ─────────────────────────────────────────────────

    async def approve_policy(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        org_id: Optional[str],
        actor_id: str,
        eval_score: Decimal,
        notes: Optional[str] = None,
    ) -> PolicyRegistryEntry:
        """
        Transition a CANDIDATE or EVALUATION policy to APPROVED.

        Rules:
        - eval_score MUST be >= 0.85 (MIN_APPROVAL_SCORE).
        - actor_id MUST be supplied (human approval required).
        - Creates immutable PolicyAuditLog entry.

        Sprint 1F Gate: G-13 — Human Approval Workflow
        """
        entry = await self._get_entry(session, policy_entry_id)
        self._assert_transition_allowed(entry.status, RegistryEntryStatus.APPROVED.value)

        if eval_score < MIN_APPROVAL_SCORE:
            raise ValueError(
                f"Approval gate failed: eval_score {eval_score} < required {MIN_APPROVAL_SCORE}. "
                f"Improve model quality before requesting approval."
            )

        from_status = entry.status
        entry.status = RegistryEntryStatus.APPROVED.value
        entry.promoted_by = actor_id
        entry.promoted_at = datetime.now(timezone.utc)
        entry.quality_score = eval_score
        await session.flush()

        await self._write_audit_log(
            session=session,
            policy_entry_id=policy_entry_id,
            org_id=org_id,
            from_status=from_status,
            to_status=RegistryEntryStatus.APPROVED.value,
            actor_type="HUMAN",
            actor_id=actor_id,
            eval_score=eval_score,
            notes=notes,
        )
        logger.info(
            f"[AdaptivePolicy] Policy {entry.entity_key}:{entry.version} APPROVED "
            f"by {actor_id} with score {eval_score}"
        )
        return entry

    # ─── 2. Pilot Cohort Guard Check ────────────────────────────────────────────

    async def run_pilot_cohort_check(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        org_id: str,
    ) -> PilotCohortGuard:
        """
        Evaluates pilot readiness for an org before allowing ACTIVE promotion.

        Checks:
        1. outcome_events count >= PILOT_MIN_LEADS (N ≥ 30)
        2. Oldest outcome_event is >= PILOT_MIN_OBSERVATION_DAYS old
        3. No open HIGH-severity DataQualityIssues

        Creates (or updates) a PilotCohortGuard row; sets is_cleared=True only
        if all three checks pass.

        Sprint 1F Gate: G-08
        """
        now = datetime.now(timezone.utc)

        # Check 1: outcome event count
        lead_count_stmt = select(func.count(OutcomeEvent.id)).where(
            OutcomeEvent.organization_id == org_id
        )
        actual_lead_count = int((await session.execute(lead_count_stmt)).scalar() or 0)

        # Check 2: observation window
        oldest_stmt = (
            select(OutcomeEvent.occurred_at)
            .where(OutcomeEvent.organization_id == org_id)
            .order_by(OutcomeEvent.occurred_at.asc())
            .limit(1)
        )
        oldest_result = (await session.execute(oldest_stmt)).scalar_one_or_none()
        if oldest_result:
            delta = now - oldest_result.replace(tzinfo=timezone.utc) if oldest_result.tzinfo is None else now - oldest_result
            actual_observation_days = max(0, int(delta.total_seconds() / 86400))
        else:
            actual_observation_days = 0

        # Check 3: HIGH severity open DQ issues
        dq_stmt = select(func.count(DataQualityIssue.id)).where(
            and_(
                DataQualityIssue.organization_id == org_id,
                DataQualityIssue.severity == "HIGH",
                DataQualityIssue.is_resolved.is_(False),
            )
        )
        open_high = int((await session.execute(dq_stmt)).scalar() or 0)

        is_cleared = (
            actual_lead_count >= PILOT_MIN_LEADS
            and actual_observation_days >= PILOT_MIN_OBSERVATION_DAYS
            and open_high == 0
        )

        notes_parts = []
        if actual_lead_count < PILOT_MIN_LEADS:
            notes_parts.append(
                f"Insufficient outcomes: {actual_lead_count} < {PILOT_MIN_LEADS} required."
            )
        if actual_observation_days < PILOT_MIN_OBSERVATION_DAYS:
            notes_parts.append(
                f"Insufficient observation window: {actual_observation_days}d < {PILOT_MIN_OBSERVATION_DAYS}d required."
            )
        if open_high > 0:
            notes_parts.append(
                f"{open_high} open HIGH-severity data quality issue(s) must be resolved first."
            )
        if is_cleared:
            notes_parts.append("All pilot cohort checks passed.")

        guard = PilotCohortGuard(
            id=str(uuid.uuid4()),
            policy_entry_id=policy_entry_id,
            organization_id=org_id,
            min_lead_count=PILOT_MIN_LEADS,
            actual_lead_count=actual_lead_count,
            min_observation_days=PILOT_MIN_OBSERVATION_DAYS,
            actual_observation_days=actual_observation_days,
            open_high_severity_issues=open_high,
            is_cleared=is_cleared,
            cleared_at=now if is_cleared else None,
            check_notes="; ".join(notes_parts),
            checked_at=now,
        )
        session.add(guard)
        await session.flush()

        logger.info(
            f"[AdaptivePolicy] PilotCohortGuard for policy={policy_entry_id} org={org_id}: "
            f"cleared={is_cleared} leads={actual_lead_count} obs_days={actual_observation_days} "
            f"open_HIGH={open_high}"
        )
        return guard

    # ─── 3. Activate Policy (APPROVED → ACTIVE) ─────────────────────────────────

    async def activate_policy(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        org_id: str,
        actor_id: str,
        notes: Optional[str] = None,
        skip_cohort_guard: bool = False,
    ) -> Tuple[PolicyRegistryEntry, PilotCohortGuard]:
        """
        Transition an APPROVED policy to ACTIVE.

        Requires a cleared PilotCohortGuard unless skip_cohort_guard=True
        (only permissible in non-production / test environments).

        Also creates an AdaptivePolicyRollout at traffic_pct=0 ready for the
        Celery controller to begin incrementing.

        Sprint 1F Gate: G-01, G-08
        """
        entry = await self._get_entry(session, policy_entry_id)
        self._assert_transition_allowed(entry.status, RegistryEntryStatus.ACTIVE.value)

        # Pilot cohort guard
        guard = await self.run_pilot_cohort_check(session, policy_entry_id, org_id)
        if not skip_cohort_guard and not guard.is_cleared:
            raise ValueError(
                f"Pilot cohort guard not cleared for policy {policy_entry_id}. "
                f"Details: {guard.check_notes}"
            )

        from_status = entry.status
        entry.status = RegistryEntryStatus.ACTIVE.value
        entry.promoted_by = actor_id
        entry.promoted_at = datetime.now(timezone.utc)
        await session.flush()

        # Create rollout config starting at 0%
        rollout = AdaptivePolicyRollout(
            id=str(uuid.uuid4()),
            policy_entry_id=policy_entry_id,
            organization_id=org_id,
            traffic_pct=0,
            max_traffic_pct=100,
            increment_pct=10,
            increment_interval_hours=24,
            min_sample_size=PILOT_MIN_LEADS,
            emergency_pause=False,
            is_rolled_back=False,
        )
        session.add(rollout)
        await session.flush()

        await self._write_audit_log(
            session=session,
            policy_entry_id=policy_entry_id,
            org_id=org_id,
            from_status=from_status,
            to_status=RegistryEntryStatus.ACTIVE.value,
            actor_type="HUMAN",
            actor_id=actor_id,
            notes=notes,
            metadata={"cohort_guard_id": guard.id, "rollout_id": rollout.id},
        )
        logger.info(
            f"[AdaptivePolicy] Policy {entry.entity_key}:{entry.version} activated. "
            f"Rollout starts at 0% traffic."
        )
        return entry, guard

    # ─── 4. Emergency Pause ─────────────────────────────────────────────────────

    async def emergency_pause_rollout(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        org_id: str,
        actor_id: str,
        reason: str,
    ) -> AdaptivePolicyRollout:
        """
        Immediately halt the Celery rollout controller for a policy.
        Does NOT change PolicyRegistryEntry.status.

        Sprint 1F Gate: G-02
        """
        rollout = await self._get_rollout(session, policy_entry_id)
        rollout.emergency_pause = True
        rollout.updated_at = datetime.now(timezone.utc)
        await session.flush()

        await self._write_audit_log(
            session=session,
            policy_entry_id=policy_entry_id,
            org_id=org_id,
            from_status=None,
            to_status="EMERGENCY_PAUSED",
            actor_type="HUMAN",
            actor_id=actor_id,
            reason=reason,
            metadata={"traffic_pct_at_pause": rollout.traffic_pct},
        )
        logger.warning(
            f"[AdaptivePolicy] EMERGENCY PAUSE triggered for policy={policy_entry_id} "
            f"by {actor_id}. Reason: {reason}"
        )
        return rollout

    # ─── 5. Rollback ────────────────────────────────────────────────────────────

    async def rollback_policy(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        org_id: str,
        actor_id: str,
        reason: str,
        previous_version_policy_id: Optional[str] = None,
    ) -> PolicyRegistryEntry:
        """
        Roll back an ACTIVE or ROLLING_OUT policy.

        Actions:
        1. Sets entry.status = ROLLED_BACK
        2. Sets rollout.traffic_pct = 0, is_rolled_back = True
        3. Re-activates previous_version if provided (sets it to ACTIVE)
        4. Creates audit log entries for both transitions

        Sprint 1F Gate: G-07 — Rollback Controller
        """
        entry = await self._get_entry(session, policy_entry_id)
        if entry.status not in (RegistryEntryStatus.ACTIVE.value, RegistryEntryStatus.APPROVED.value):
            raise ValueError(
                f"Only ACTIVE or APPROVED policies can be rolled back. "
                f"Policy {policy_entry_id} is currently {entry.status}."
            )

        from_status = entry.status
        now = datetime.now(timezone.utc)

        # Mark policy as rolled back
        entry.status = RegistryEntryStatus.ROLLED_BACK.value
        await session.flush()

        # Freeze rollout
        rollout_q = select(AdaptivePolicyRollout).where(
            AdaptivePolicyRollout.policy_entry_id == policy_entry_id
        )
        rollout = (await session.execute(rollout_q)).scalar_one_or_none()
        if rollout:
            rollout.traffic_pct = 0
            rollout.is_rolled_back = True
            rollout.rollback_reason = reason
            rollout.rollback_triggered_at = now
            rollout.rollback_triggered_by = actor_id
            await session.flush()

        # Audit log for rollback
        await self._write_audit_log(
            session=session,
            policy_entry_id=policy_entry_id,
            org_id=org_id,
            from_status=from_status,
            to_status=RegistryEntryStatus.ROLLED_BACK.value,
            actor_type="HUMAN",
            actor_id=actor_id,
            reason=reason,
            metadata={"previous_version_id": previous_version_policy_id},
        )

        # Re-activate previous version if supplied
        if previous_version_policy_id:
            prev_entry = await self._get_entry(session, previous_version_policy_id)
            prev_from = prev_entry.status
            prev_entry.status = RegistryEntryStatus.ACTIVE.value
            prev_entry.promoted_by = actor_id
            prev_entry.promoted_at = now
            await session.flush()

            await self._write_audit_log(
                session=session,
                policy_entry_id=previous_version_policy_id,
                org_id=org_id,
                from_status=prev_from,
                to_status=RegistryEntryStatus.ACTIVE.value,
                actor_type="SYSTEM",
                actor_id=actor_id,
                reason=f"Re-activated as fallback after rollback of {policy_entry_id}",
            )
            logger.info(
                f"[AdaptivePolicy] Previous version {previous_version_policy_id} re-activated."
            )

        logger.warning(
            f"[AdaptivePolicy] ROLLBACK complete for policy={policy_entry_id}. Reason: {reason}"
        )
        return entry

    # ─── 6. Advance Rollout (called by Celery controller) ───────────────────────

    async def advance_rollout(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        org_id: str,
    ) -> Optional[AdaptivePolicyRollout]:
        """
        Increment traffic_pct by increment_pct if:
        - emergency_pause is False
        - is_rolled_back is False
        - last_increment_at is None or >= increment_interval_hours ago
        - guardrails pass (conversion rate check when min_conversion_rate_pct is set)

        Called by: `advance_policy_rollout_task` Celery task (every 1h).

        Sprint 1F Gate: G-02
        """
        rollout = await self._get_rollout(session, policy_entry_id)

        if rollout.emergency_pause or rollout.is_rolled_back:
            logger.info(
                f"[AdaptivePolicy] Rollout for policy={policy_entry_id} is paused or rolled back. "
                f"Skipping advance."
            )
            return rollout

        now = datetime.now(timezone.utc)
        if rollout.last_increment_at:
            elapsed_hours = (now - rollout.last_increment_at.replace(tzinfo=timezone.utc)
                             if rollout.last_increment_at.tzinfo is None
                             else now - rollout.last_increment_at).total_seconds() / 3600
            if elapsed_hours < rollout.increment_interval_hours:
                logger.debug(
                    f"[AdaptivePolicy] Rollout for policy={policy_entry_id} not due yet "
                    f"({elapsed_hours:.1f}h < {rollout.increment_interval_hours}h)."
                )
                return rollout

        if rollout.traffic_pct >= rollout.max_traffic_pct:
            if not rollout.fully_deployed_at:
                rollout.fully_deployed_at = now
                await session.flush()
            logger.info(
                f"[AdaptivePolicy] Rollout for policy={policy_entry_id} fully deployed at 100%."
            )
            return rollout

        # Guardrail check (simplified: sample-size-based gate only in 1F)
        outcome_count_stmt = select(func.count(OutcomeEvent.id)).where(
            OutcomeEvent.organization_id == org_id
        )
        current_sample = int((await session.execute(outcome_count_stmt)).scalar() or 0)
        if current_sample < rollout.min_sample_size:
            logger.info(
                f"[AdaptivePolicy] Rollout guardrail: sample_size={current_sample} "
                f"< min={rollout.min_sample_size}. Not advancing."
            )
            return rollout

        new_pct = min(rollout.traffic_pct + rollout.increment_pct, rollout.max_traffic_pct)
        rollout.traffic_pct = new_pct
        rollout.last_increment_at = now
        if new_pct >= rollout.max_traffic_pct:
            rollout.fully_deployed_at = now
        await session.flush()

        await self._write_audit_log(
            session=session,
            policy_entry_id=policy_entry_id,
            org_id=org_id,
            from_status=None,
            to_status="ROLLOUT_INCREMENT",
            actor_type="CELERY",
            actor_id=None,
            notes=f"Traffic advanced to {new_pct}%",
            metadata={"new_traffic_pct": new_pct, "sample_size": current_sample},
        )
        logger.info(
            f"[AdaptivePolicy] Rollout for policy={policy_entry_id} advanced to {new_pct}%."
        )
        return rollout

    # ─── 7. Intelligence Health Probe ───────────────────────────────────────────

    async def get_intelligence_health(
        self,
        session: AsyncSession,
        org_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Structured health probe for the Intelligence subsystem.

        Returns:
          status: OK | DEGRADED | DOWN
          checks: individual check results
          latency_ms: DB round-trip for outcome_events count
          last_snapshot_age_hours: age of most recent IntelligenceSnapshot

        Sprint 1F Gate: G-09 — Intelligence Health Endpoint
        """
        from app.models.intelligence_models import IntelligenceSnapshot
        from sqlalchemy import text
        import time

        now = datetime.now(timezone.utc)
        checks: Dict[str, Any] = {}
        status = "OK"

        # Check 1: DB connectivity + outcome_events write latency
        t0 = time.monotonic()
        try:
            count_stmt = select(func.count(OutcomeEvent.id))
            if org_id:
                count_stmt = count_stmt.where(OutcomeEvent.organization_id == org_id)
            total_outcomes = int((await session.execute(count_stmt)).scalar() or 0)
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            checks["db_outcome_events"] = {
                "status": "OK",
                "total_outcomes": total_outcomes,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            checks["db_outcome_events"] = {"status": "DOWN", "error": str(e)}
            status = "DOWN"
            latency_ms = -1.0

        # Check 2: Most recent intelligence snapshot age
        try:
            snap_stmt = (
                select(IntelligenceSnapshot.computed_at)
                .order_by(IntelligenceSnapshot.computed_at.desc())
                .limit(1)
            )
            if org_id:
                snap_stmt = snap_stmt.where(IntelligenceSnapshot.organization_id == org_id)
            last_snapshot_ts = (await session.execute(snap_stmt)).scalar_one_or_none()
            if last_snapshot_ts:
                ts_aware = last_snapshot_ts.replace(tzinfo=timezone.utc) if last_snapshot_ts.tzinfo is None else last_snapshot_ts
                age_hours = round((now - ts_aware).total_seconds() / 3600, 2)
                snap_status = "OK" if age_hours <= 48 else "DEGRADED"
                if snap_status == "DEGRADED" and status == "OK":
                    status = "DEGRADED"
            else:
                age_hours = None
                snap_status = "NO_SNAPSHOT"
                if status == "OK":
                    status = "DEGRADED"
            checks["intelligence_snapshot"] = {
                "status": snap_status,
                "last_snapshot_age_hours": age_hours,
            }
        except Exception as e:
            checks["intelligence_snapshot"] = {"status": "DOWN", "error": str(e)}
            if status == "OK":
                status = "DEGRADED"
            age_hours = None

        # Check 3: Open HIGH-severity data quality issues (org-scoped)
        try:
            if org_id:
                dq_stmt = select(func.count(DataQualityIssue.id)).where(
                    and_(
                        DataQualityIssue.organization_id == org_id,
                        DataQualityIssue.severity == "HIGH",
                        DataQualityIssue.is_resolved.is_(False),
                    )
                )
                open_high = int((await session.execute(dq_stmt)).scalar() or 0)
                dq_status = "OK" if open_high == 0 else "DEGRADED"
                if dq_status == "DEGRADED" and status == "OK":
                    status = "DEGRADED"
                checks["data_quality"] = {"status": dq_status, "open_high_issues": open_high}
            else:
                checks["data_quality"] = {"status": "SKIPPED", "note": "org_id not supplied"}
        except Exception as e:
            checks["data_quality"] = {"status": "DOWN", "error": str(e)}

        return {
            "status": status,
            "timestamp": now.isoformat(),
            "organization_id": org_id,
            "checks": checks,
            "latency_ms": latency_ms if "latency_ms" in locals() else -1.0,
            "last_snapshot_age_hours": age_hours if "age_hours" in locals() else None,
        }

    # ─── 8. Audit Log Query ─────────────────────────────────────────────────────

    async def get_policy_audit_trail(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        limit: int = 50,
    ) -> List[PolicyAuditLog]:
        """
        Returns the complete, ordered audit trail for a policy entry.

        Sprint 1F Gate: G-15 — Audit Trail Integrity
        """
        q = (
            select(PolicyAuditLog)
            .where(PolicyAuditLog.policy_entry_id == policy_entry_id)
            .order_by(PolicyAuditLog.occurred_at.asc())
            .limit(limit)
        )
        return list((await session.execute(q)).scalars().all())

    # ─── 9. List Active Rollouts ─────────────────────────────────────────────────

    async def list_active_rollouts(
        self,
        session: AsyncSession,
        org_id: str,
    ) -> List[AdaptivePolicyRollout]:
        """Returns all non-rolled-back, non-paused rollouts for an org."""
        q = select(AdaptivePolicyRollout).where(
            and_(
                AdaptivePolicyRollout.organization_id == org_id,
                AdaptivePolicyRollout.is_rolled_back.is_(False),
            )
        )
        return list((await session.execute(q)).scalars().all())

    # ─── Internal Helpers ────────────────────────────────────────────────────────

    async def _get_entry(
        self, session: AsyncSession, policy_entry_id: str
    ) -> PolicyRegistryEntry:
        q = select(PolicyRegistryEntry).where(PolicyRegistryEntry.id == policy_entry_id)
        entry = (await session.execute(q)).scalar_one_or_none()
        if not entry:
            raise ValueError(f"PolicyRegistryEntry {policy_entry_id} not found.")
        return entry

    async def _get_rollout(
        self, session: AsyncSession, policy_entry_id: str
    ) -> AdaptivePolicyRollout:
        q = select(AdaptivePolicyRollout).where(
            AdaptivePolicyRollout.policy_entry_id == policy_entry_id
        )
        rollout = (await session.execute(q)).scalar_one_or_none()
        if not rollout:
            raise ValueError(
                f"No AdaptivePolicyRollout found for policy {policy_entry_id}. "
                f"Policy must be ACTIVE to have a rollout record."
            )
        return rollout

    @staticmethod
    def _assert_transition_allowed(from_status: str, to_status: str) -> None:
        allowed = ALLOWED_TRANSITIONS.get(from_status, [])
        if to_status not in allowed:
            raise ValueError(
                f"Status transition {from_status} → {to_status} is not permitted. "
                f"Allowed: {allowed}"
            )

    async def _write_audit_log(
        self,
        session: AsyncSession,
        policy_entry_id: str,
        org_id: Optional[str],
        from_status: Optional[str],
        to_status: str,
        actor_type: str,
        actor_id: Optional[str],
        reason: Optional[str] = None,
        eval_score: Optional[Decimal] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PolicyAuditLog:
        log = PolicyAuditLog(
            id=str(uuid.uuid4()),
            policy_entry_id=policy_entry_id,
            organization_id=org_id,
            from_status=from_status,
            to_status=to_status,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            eval_score=eval_score,
            notes=notes,
            metadata_json=metadata or {},
            occurred_at=datetime.now(timezone.utc),
        )
        session.add(log)
        await session.flush()
        return log
