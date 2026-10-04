"""
Sprint 1F — Revenue Leakage Engine, Data Quality Operations & Human Override Learning
=====================================================================================
Covers Sprint 1F Sections:
  - Section 21 & 22: Revenue Leakage Engine & Recovery Experiments
  - Section 25 & 26: Human Override Learning & Agent Feedback Loop
  - Section 29 & 30: Data Quality Operations & Governance Dashboard
  - Section 10: Pilot Mode Enforcement Helpers

INVARIANTS:
1. Tenant Isolation: Every query and mutation is strictly scoped to organization_id.
2. Property & Financial Truth: Leakage detection and recovery never mutate inventory or financial ledgers.
3. Append-only signals: Recoveries and human overrides record canonical OutcomeEvent and LearningEvent rows.
4. No Silently Deleted Data: Data quality issues follow explicit lifecycle transitions (OPEN -> ACKNOWLEDGED -> IN_REVIEW -> RESOLVED | IGNORED -> REOPENED).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence_models import (
    DataQualityIssue,
    DataQualityIssueStatus,
    DataQualityIssueType,
    AIActionOutcome,
    HumanOverrideCategory,
    LearningEvent,
    LearningSignalType,
    OutcomeEvent,
    OutcomeEventType,
    OutcomeEntityType,
    OutcomeSource,
    RevenueLeakageRecord,
    RevenueLeakageStatus,
    RevenueLeakageType,
)
from app.modules.intelligence.outcome_recorder import OutcomeRecorder

logger = logging.getLogger("wefylabs.intelligence.revenue_leakage")


class RevenueLeakageService:
    """
    Structured Revenue Leakage Engine & Recovery System.
    Identifies, tracks, engages, and recovers commercial opportunities.
    """

    @staticmethod
    async def create_leakage_candidate(
        db: AsyncSession,
        *,
        organization_id: str,
        leakage_type: str,
        stage: str,
        estimated_value: Decimal,
        recommended_intervention: str,
        evidence: Dict[str, Any],
        lead_id: Optional[str] = None,
        deal_id: Optional[str] = None,
        property_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        currency: str = "AED",
        expiry_hours: int = 72,
        experiment_id: Optional[str] = None,
        experiment_variant: Optional[str] = None,
    ) -> RevenueLeakageRecord:
        """Creates a tracked revenue leakage candidate record."""
        now = datetime.now(timezone.utc)
        record = RevenueLeakageRecord(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            leakage_type=leakage_type,
            stage=stage,
            lead_id=lead_id,
            deal_id=deal_id,
            property_id=property_id,
            owner_id=owner_id,
            estimated_leakage_value=estimated_value,
            currency=currency,
            evidence=evidence,
            recommended_intervention=recommended_intervention,
            status=RevenueLeakageStatus.DETECTED.value,
            experiment_id=experiment_id,
            experiment_variant=experiment_variant,
            expiry_at=now + timedelta(hours=expiry_hours),
            detected_at=now,
        )
        db.add(record)
        await db.flush()
        logger.info(
            "[RevenueLeakage] Created leakage record id=%s type=%s value=%s org=%s",
            record.id,
            leakage_type,
            estimated_value,
            organization_id,
        )
        return record

    @staticmethod
    async def list_leakage_candidates(
        db: AsyncSession,
        organization_id: str,
        *,
        status: Optional[str] = None,
        leakage_type: Optional[str] = None,
        stage: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RevenueLeakageRecord]:
        """Lists leakage candidates for a tenant with optional filtering."""
        conditions = [RevenueLeakageRecord.organization_id == organization_id]
        if status:
            conditions.append(RevenueLeakageRecord.status == status)
        if leakage_type:
            conditions.append(RevenueLeakageRecord.leakage_type == leakage_type)
        if stage:
            conditions.append(RevenueLeakageRecord.stage == stage)
        if owner_id:
            conditions.append(RevenueLeakageRecord.owner_id == owner_id)

        stmt = (
            select(RevenueLeakageRecord)
            .where(and_(*conditions))
            .order_by(desc(RevenueLeakageRecord.estimated_leakage_value), desc(RevenueLeakageRecord.detected_at))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def engage_leakage_candidate(
        db: AsyncSession,
        candidate_id: str,
        organization_id: str,
        actor_id: str,
        *,
        experiment_id: Optional[str] = None,
        experiment_variant: Optional[str] = None,
    ) -> RevenueLeakageRecord:
        """Transitions candidate from DETECTED to ENGAGED."""
        stmt = select(RevenueLeakageRecord).where(
            and_(
                RevenueLeakageRecord.id == candidate_id,
                RevenueLeakageRecord.organization_id == organization_id,
            )
        )
        result = await db.execute(stmt)
        record = result.scalars().first()
        if not record:
            raise ValueError(f"RevenueLeakageRecord '{candidate_id}' not found for tenant '{organization_id}'")

        if record.status not in (RevenueLeakageStatus.DETECTED.value, RevenueLeakageStatus.EXPIRED.value):
            raise ValueError(f"Cannot engage record in status '{record.status}'. Must be DETECTED or EXPIRED.")

        now = datetime.now(timezone.utc)
        record.status = RevenueLeakageStatus.ENGAGED.value
        record.engaged_at = now
        record.engaged_by = actor_id
        if experiment_id:
            record.experiment_id = experiment_id
        if experiment_variant:
            record.experiment_variant = experiment_variant

        await db.flush()
        logger.info("[RevenueLeakage] Engaged candidate id=%s by actor=%s", candidate_id, actor_id)
        return record

    @staticmethod
    async def resolve_leakage_candidate(
        db: AsyncSession,
        candidate_id: str,
        organization_id: str,
        *,
        outcome: str,
        recovered_value: Optional[Decimal] = None,
        actor_id: str,
        notes: Optional[str] = None,
        is_dismissed: bool = False,
    ) -> RevenueLeakageRecord:
        """
        Resolves a leakage candidate as RECOVERED or DISMISSED.
        If recovered with value > 0, records an immutable OutcomeEvent.
        """
        stmt = select(RevenueLeakageRecord).where(
            and_(
                RevenueLeakageRecord.id == candidate_id,
                RevenueLeakageRecord.organization_id == organization_id,
            )
        )
        result = await db.execute(stmt)
        record = result.scalars().first()
        if not record:
            raise ValueError(f"RevenueLeakageRecord '{candidate_id}' not found for tenant '{organization_id}'")

        now = datetime.now(timezone.utc)
        if is_dismissed:
            record.status = RevenueLeakageStatus.DISMISSED.value
            record.outcome = outcome or "DISMISSED"
        else:
            record.status = RevenueLeakageStatus.RECOVERED.value
            record.outcome = outcome or "RECOVERED"
            record.recovered_value = recovered_value or record.estimated_leakage_value

        record.resolved_at = now
        record.resolved_by = actor_id
        record.resolution_notes = notes

        await db.flush()

        # Record commercial outcome event if recovered
        if not is_dismissed and record.recovered_value and record.recovered_value > Decimal("0"):
            await OutcomeRecorder.safe_record(
                db=db,
                org_id=organization_id,
                event_type=OutcomeEventType.LEAD_RECOVERED,
                entity_type=OutcomeEntityType.LEAD,
                entity_id=record.lead_id or record.id,
                source_table="revenue_leakage_records",
                occurred_at=now,
                source_event_id=record.id,
                lead_id=record.lead_id,
                opportunity_id=record.deal_id,
                property_id=record.property_id,
                agent_id=actor_id,
                actor_type="HUMAN",
                revenue_impact=record.recovered_value,
                currency=record.currency,
                metadata={
                    "leakage_type": record.leakage_type,
                    "stage": record.stage,
                    "resolution_notes": notes,
                    "experiment_id": record.experiment_id,
                    "experiment_variant": record.experiment_variant,
                },
            )

        logger.info(
            "[RevenueLeakage] Resolved candidate id=%s status=%s outcome=%s recovered_val=%s",
            candidate_id,
            record.status,
            record.outcome,
            record.recovered_value,
        )
        return record

    @staticmethod
    async def get_leakage_summary(db: AsyncSession, organization_id: str) -> Dict[str, Any]:
        """Provides an executive summary of revenue leakage and recovery metrics."""
        # Total active leakage value
        active_stmt = select(
            func.count(RevenueLeakageRecord.id),
            func.coalesce(func.sum(RevenueLeakageRecord.estimated_leakage_value), Decimal("0")),
        ).where(
            and_(
                RevenueLeakageRecord.organization_id == organization_id,
                RevenueLeakageRecord.status.in_([RevenueLeakageStatus.DETECTED.value, RevenueLeakageStatus.ENGAGED.value]),
            )
        )
        active_res = (await db.execute(active_stmt)).first()
        active_count = active_res[0] or 0
        active_value = Decimal(str(active_res[1] or "0"))

        # Total recovered value
        recovered_stmt = select(
            func.count(RevenueLeakageRecord.id),
            func.coalesce(func.sum(RevenueLeakageRecord.recovered_value), Decimal("0")),
        ).where(
            and_(
                RevenueLeakageRecord.organization_id == organization_id,
                RevenueLeakageRecord.status == RevenueLeakageStatus.RECOVERED.value,
            )
        )
        rec_res = (await db.execute(recovered_stmt)).first()
        recovered_count = rec_res[0] or 0
        recovered_value = Decimal(str(rec_res[1] or "0"))

        # Breakdown by leakage type
        type_stmt = (
            select(
                RevenueLeakageRecord.leakage_type,
                func.count(RevenueLeakageRecord.id),
                func.coalesce(func.sum(RevenueLeakageRecord.estimated_leakage_value), Decimal("0")),
            )
            .where(RevenueLeakageRecord.organization_id == organization_id)
            .group_by(RevenueLeakageRecord.leakage_type)
        )
        by_type = [
            {"leakage_type": row[0], "count": row[1], "value": float(row[2])}
            for row in (await db.execute(type_stmt)).all()
        ]

        # Breakdown by status
        status_stmt = (
            select(
                RevenueLeakageRecord.status,
                func.count(RevenueLeakageRecord.id),
            )
            .where(RevenueLeakageRecord.organization_id == organization_id)
            .group_by(RevenueLeakageRecord.status)
        )
        by_status = {row[0]: row[1] for row in (await db.execute(status_stmt)).all()}

        return {
            "organization_id": organization_id,
            "active_leakage_count": active_count,
            "active_leakage_value": float(active_value),
            "recovered_count": recovered_count,
            "recovered_value": float(recovered_value),
            "recovery_rate_pct": (
                round(float((recovered_value / (active_value + recovered_value)) * 100), 2)
                if (active_value + recovered_value) > Decimal("0")
                else 0.0
            ),
            "by_type": by_type,
            "by_status": by_status,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


class DataQualityOperationsService:
    """
    Operational lifecycle management for Data Quality Issues.
    Implements: OPEN -> ACKNOWLEDGED -> IN_REVIEW -> RESOLVED | IGNORED -> REOPENED
    """

    VALID_TRANSITIONS = {
        DataQualityIssueStatus.OPEN.value: [
            DataQualityIssueStatus.ACKNOWLEDGED.value,
            DataQualityIssueStatus.IN_REVIEW.value,
            DataQualityIssueStatus.RESOLVED.value,
            DataQualityIssueStatus.IGNORED.value,
        ],
        DataQualityIssueStatus.ACKNOWLEDGED.value: [
            DataQualityIssueStatus.IN_REVIEW.value,
            DataQualityIssueStatus.RESOLVED.value,
            DataQualityIssueStatus.IGNORED.value,
        ],
        DataQualityIssueStatus.IN_REVIEW.value: [
            DataQualityIssueStatus.RESOLVED.value,
            DataQualityIssueStatus.IGNORED.value,
            DataQualityIssueStatus.OPEN.value,
        ],
        DataQualityIssueStatus.RESOLVED.value: [
            DataQualityIssueStatus.REOPENED.value,
        ],
        DataQualityIssueStatus.IGNORED.value: [
            DataQualityIssueStatus.REOPENED.value,
        ],
        DataQualityIssueStatus.REOPENED.value: [
            DataQualityIssueStatus.ACKNOWLEDGED.value,
            DataQualityIssueStatus.IN_REVIEW.value,
            DataQualityIssueStatus.RESOLVED.value,
            DataQualityIssueStatus.IGNORED.value,
        ],
    }

    @classmethod
    async def get_issue(cls, db: AsyncSession, issue_id: str, organization_id: str) -> DataQualityIssue:
        stmt = select(DataQualityIssue).where(
            and_(
                DataQualityIssue.id == issue_id,
                DataQualityIssue.organization_id == organization_id,
            )
        )
        res = await db.execute(stmt)
        issue = res.scalars().first()
        if not issue:
            raise ValueError(f"DataQualityIssue '{issue_id}' not found for tenant '{organization_id}'")
        return issue

    @classmethod
    async def acknowledge_issue(
        cls, db: AsyncSession, issue_id: str, organization_id: str, actor_id: str, owner: Optional[str] = None
    ) -> DataQualityIssue:
        issue = await cls.get_issue(db, issue_id, organization_id)
        current = issue.status or DataQualityIssueStatus.OPEN.value
        allowed = cls.VALID_TRANSITIONS.get(current, [])
        if DataQualityIssueStatus.ACKNOWLEDGED.value not in allowed:
            raise ValueError(f"Cannot transition issue from '{current}' to 'ACKNOWLEDGED'")

        now = datetime.now(timezone.utc)
        issue.status = DataQualityIssueStatus.ACKNOWLEDGED.value
        issue.acknowledged_at = now
        issue.acknowledged_by = actor_id
        if owner:
            issue.owner = owner
        await db.flush()
        return issue

    @classmethod
    async def mark_in_review(
        cls, db: AsyncSession, issue_id: str, organization_id: str, actor_id: str
    ) -> DataQualityIssue:
        issue = await cls.get_issue(db, issue_id, organization_id)
        current = issue.status or DataQualityIssueStatus.OPEN.value
        allowed = cls.VALID_TRANSITIONS.get(current, [])
        if DataQualityIssueStatus.IN_REVIEW.value not in allowed:
            raise ValueError(f"Cannot transition issue from '{current}' to 'IN_REVIEW'")

        now = datetime.now(timezone.utc)
        issue.status = DataQualityIssueStatus.IN_REVIEW.value
        issue.in_review_at = now
        issue.in_review_by = actor_id
        await db.flush()
        return issue

    @classmethod
    async def resolve_issue(
        cls, db: AsyncSession, issue_id: str, organization_id: str, actor_id: str, notes: Optional[str] = None
    ) -> DataQualityIssue:
        issue = await cls.get_issue(db, issue_id, organization_id)
        current = issue.status or DataQualityIssueStatus.OPEN.value
        allowed = cls.VALID_TRANSITIONS.get(current, [])
        if DataQualityIssueStatus.RESOLVED.value not in allowed:
            raise ValueError(f"Cannot transition issue from '{current}' to 'RESOLVED'")

        now = datetime.now(timezone.utc)
        issue.status = DataQualityIssueStatus.RESOLVED.value
        issue.is_resolved = True
        issue.resolved_at = now
        issue.resolved_by = actor_id
        issue.resolution_notes = notes
        await db.flush()
        return issue

    @classmethod
    async def ignore_issue(
        cls, db: AsyncSession, issue_id: str, organization_id: str, actor_id: str, reason: str
    ) -> DataQualityIssue:
        if not reason or not reason.strip():
            raise ValueError("An explicit ignore reason is required to suppress a data quality issue.")

        issue = await cls.get_issue(db, issue_id, organization_id)
        current = issue.status or DataQualityIssueStatus.OPEN.value
        allowed = cls.VALID_TRANSITIONS.get(current, [])
        if DataQualityIssueStatus.IGNORED.value not in allowed:
            raise ValueError(f"Cannot transition issue from '{current}' to 'IGNORED'")

        issue.status = DataQualityIssueStatus.IGNORED.value
        issue.ignored_reason = reason
        await db.flush()
        return issue

    @classmethod
    async def reopen_issue(
        cls, db: AsyncSession, issue_id: str, organization_id: str, actor_id: str, notes: Optional[str] = None
    ) -> DataQualityIssue:
        issue = await cls.get_issue(db, issue_id, organization_id)
        current = issue.status or DataQualityIssueStatus.OPEN.value
        allowed = cls.VALID_TRANSITIONS.get(current, [])
        if DataQualityIssueStatus.REOPENED.value not in allowed:
            raise ValueError(f"Cannot transition issue from '{current}' to 'REOPENED'")

        now = datetime.now(timezone.utc)
        issue.status = DataQualityIssueStatus.REOPENED.value
        issue.is_resolved = False
        issue.reopened_at = now
        if notes:
            issue.description = f"{issue.description} [REOPENED: {notes}]"
        await db.flush()
        return issue

    @classmethod
    async def get_dashboard(cls, db: AsyncSession, organization_id: str) -> Dict[str, Any]:
        """Returns the operational Data Quality Dashboard metrics."""
        # Counts by status
        status_stmt = (
            select(DataQualityIssue.status, func.count(DataQualityIssue.id))
            .where(DataQualityIssue.organization_id == organization_id)
            .group_by(DataQualityIssue.status)
        )
        status_counts = {row[0]: row[1] for row in (await db.execute(status_stmt)).all()}

        # Counts by severity
        sev_stmt = (
            select(DataQualityIssue.severity, func.count(DataQualityIssue.id))
            .where(
                and_(
                    DataQualityIssue.organization_id == organization_id,
                    DataQualityIssue.is_resolved == False,
                )
            )
            .group_by(DataQualityIssue.severity)
        )
        severity_counts = {row[0]: row[1] for row in (await db.execute(sev_stmt)).all()}

        # Counts by dimension
        dim_stmt = (
            select(DataQualityIssue.dimension, func.count(DataQualityIssue.id))
            .where(
                and_(
                    DataQualityIssue.organization_id == organization_id,
                    DataQualityIssue.is_resolved == False,
                )
            )
            .group_by(DataQualityIssue.dimension)
        )
        dim_counts = {row[0]: row[1] for row in (await db.execute(dim_stmt)).all()}

        # High priority critical issues
        crit_stmt = (
            select(DataQualityIssue)
            .where(
                and_(
                    DataQualityIssue.organization_id == organization_id,
                    DataQualityIssue.severity.in_(["CRITICAL", "HIGH"]),
                    DataQualityIssue.is_resolved == False,
                )
            )
            .order_by(desc(DataQualityIssue.detected_at))
            .limit(10)
        )
        critical_issues = [
            {
                "id": issue.id,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "entity_type": issue.entity_type,
                "entity_id": issue.entity_id,
                "description": issue.description,
                "status": issue.status,
                "suggested_remediation": issue.suggested_remediation,
                "detected_at": issue.detected_at.isoformat() if issue.detected_at else None,
            }
            for issue in (await db.execute(crit_stmt)).scalars().all()
        ]

        total_open = sum(v for k, v in status_counts.items() if k in ("OPEN", "ACKNOWLEDGED", "IN_REVIEW", "REOPENED"))
        total_resolved = status_counts.get("RESOLVED", 0)

        return {
            "organization_id": organization_id,
            "total_open_issues": total_open,
            "total_resolved_issues": total_resolved,
            "by_status": status_counts,
            "by_severity": severity_counts,
            "by_dimension": dim_counts,
            "critical_issues": critical_issues,
            "integrity_health": "DEGRADED" if severity_counts.get("CRITICAL", 0) > 0 or severity_counts.get("HIGH", 0) > 3 else "HEALTHY",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


class HumanOverrideLearningService:
    """
    Analyzes human overrides and feedback on AI recommendations.
    Sprint 1F Section 25 & 26.
    """

    @staticmethod
    async def record_recommendation_feedback(
        db: AsyncSession,
        *,
        organization_id: str,
        recommendation_id: str,
        action: str,  # ACCEPTED | DISMISSED | SNOOZED | OVERRIDDEN | EDITED
        actor_id: str,
        override_category: Optional[str] = None,
        notes: Optional[str] = None,
        recommendation_type: str = "NEXT_BEST_ACTION",
        lead_id: Optional[str] = None,
    ) -> AIActionOutcome:
        """Records agent/human feedback or override on an AI recommendation."""
        now = datetime.now(timezone.utc)
        is_override = action in ("OVERRIDDEN", "EDITED", "DISMISSED")

        if is_override and override_category:
            valid_categories = {c.value for c in HumanOverrideCategory}
            if override_category not in valid_categories:
                raise ValueError(f"Invalid override_category '{override_category}'. Must be one of: {sorted(valid_categories)}")

        # Find existing or create outcome record
        stmt = select(AIActionOutcome).where(
            and_(
                AIActionOutcome.recommendation_id == recommendation_id,
                AIActionOutcome.organization_id == organization_id,
            )
        )
        res = await db.execute(stmt)
        record = res.scalars().first()

        if not record:
            record = AIActionOutcome(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                recommendation_id=recommendation_id,
                recommendation_type=recommendation_type,
                ai_model_version="wefylabs-nba-v1",
                lead_id=lead_id,
                agent_id=actor_id,
                recommended_at=now,
                captured_at=now,
            )
            db.add(record)

        record.human_decision = action
        record.human_override = is_override
        record.outcome_at = now
        if action == "ACCEPTED":
            record.accepted_at = now
        elif action in ("REJECTED", "DISMISSED"):
            record.rejected_at = now
        elif action == "EXECUTED":
            record.executed_at = now

        if is_override:
            record.override_category = override_category
            record.override_reason = notes
            record.override_feedback = notes

        await db.flush()

        # Write immutable LearningEvent signal
        signal_map = {
            "ACCEPTED": LearningSignalType.RECOMMENDATION_ACCEPTED.value,
            "DISMISSED": LearningSignalType.HUMAN_DISMISS.value,
            "SNOOZED": LearningSignalType.HUMAN_SNOOZE.value,
            "OVERRIDDEN": LearningSignalType.HUMAN_OVERRIDE.value,
            "EDITED": LearningSignalType.HUMAN_EDIT.value,
        }
        signal_type = signal_map.get(action, LearningSignalType.HUMAN_OVERRIDE.value)

        learning_event = LearningEvent(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            event_type="RECOMMENDATION_FEEDBACK",
            signal_type=signal_type,
            signal_value=override_category or action,
            source_event_id=record.id,
            source_table="ai_action_outcomes",
            entity_type="AI_ACTION",
            entity_id=recommendation_id,
            actor_type="HUMAN",
            actor_id=actor_id,
            occurred_at=now,
            captured_at=now,
            metadata_json={
                "action": action,
                "override_category": override_category,
                "notes": notes,
                "recommendation_type": recommendation_type,
            },
        )
        db.add(learning_event)
        await db.flush()

        logger.info(
            "[HumanOverride] Recorded feedback action=%s cat=%s for rec_id=%s org=%s",
            action,
            override_category,
            recommendation_id,
            organization_id,
        )
        return record

    @staticmethod
    async def get_override_analysis(
        db: AsyncSession, organization_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyzes human override patterns over the last N days.
        Answers: 'Why are humans overriding recommendations?'
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Total actions and overrides
        total_stmt = select(
            func.count(AIActionOutcome.id),
            func.coalesce(func.sum(func.cast(AIActionOutcome.human_override, func.INTEGER if db.bind.dialect.name == "sqlite" else None) if False else 0), 0),
        ).where(
            and_(
                AIActionOutcome.organization_id == organization_id,
                AIActionOutcome.recommended_at >= cutoff,
            )
        )
        # Safe count queries
        all_actions_stmt = select(func.count(AIActionOutcome.id)).where(
            and_(
                AIActionOutcome.organization_id == organization_id,
                AIActionOutcome.recommended_at >= cutoff,
            )
        )
        total_actions = (await db.execute(all_actions_stmt)).scalar() or 0

        override_count_stmt = select(func.count(AIActionOutcome.id)).where(
            and_(
                AIActionOutcome.organization_id == organization_id,
                AIActionOutcome.human_override == True,
                AIActionOutcome.recommended_at >= cutoff,
            )
        )
        total_overrides = (await db.execute(override_count_stmt)).scalar() or 0

        # Breakdown by category
        cat_stmt = (
            select(
                AIActionOutcome.override_category,
                func.count(AIActionOutcome.id),
            )
            .where(
                and_(
                    AIActionOutcome.organization_id == organization_id,
                    AIActionOutcome.human_override == True,
                    AIActionOutcome.recommended_at >= cutoff,
                    AIActionOutcome.override_category.isnot(None),
                )
            )
            .group_by(AIActionOutcome.override_category)
        )
        cat_rows = (await db.execute(cat_stmt)).all()
        by_category = [
            {
                "category": row[0],
                "count": row[1],
                "pct_of_overrides": round((row[1] / total_overrides) * 100, 1) if total_overrides > 0 else 0.0,
            }
            for row in cat_rows
        ]

        # Breakdown by recommendation type
        type_stmt = (
            select(
                AIActionOutcome.recommendation_type,
                func.count(AIActionOutcome.id),
            )
            .where(
                and_(
                    AIActionOutcome.organization_id == organization_id,
                    AIActionOutcome.human_override == True,
                    AIActionOutcome.recommended_at >= cutoff,
                )
            )
            .group_by(AIActionOutcome.recommendation_type)
        )
        by_rec_type = [
            {"recommendation_type": row[0], "override_count": row[1]}
            for row in (await db.execute(type_stmt)).all()
        ]

        override_rate = round((total_overrides / total_actions) * 100, 2) if total_actions > 0 else 0.0

        # Synthesize top actionable takeaway
        top_category = max(by_category, key=lambda x: x["count"])["category"] if by_category else "INSUFFICIENT_DATA"

        return {
            "organization_id": organization_id,
            "observation_window_days": days,
            "total_recommendations": total_actions,
            "total_overrides": total_overrides,
            "override_rate_pct": override_rate,
            "by_category": by_category,
            "by_recommendation_type": by_rec_type,
            "primary_override_driver": top_category,
            "evidence_classification": "VALIDATED" if total_overrides >= 30 else "EARLY_SIGNAL_LOW_N",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
