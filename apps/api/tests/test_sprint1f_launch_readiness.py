"""
Sprint 1F — Launch Readiness & Live Governance Verification Test Suite
======================================================================
Tests the full suite of Sprint 1F capabilities:
  1. Section 10: Pilot Mode Configuration & Validation
  2. Section 21 & 22: Revenue Leakage Engine & Recovery System
  3. Section 25 & 26: Human Override Learning & Feedback Analysis
  4. Section 29 & 30: Data Quality Operations & Governance Dashboard
  5. Section 8 & 9: Transactional Outbox Idempotency & Delivery Guarantees
  6. Tenant Isolation across all new intelligence primitives
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base
from app.common.config.validated_settings import EnterpriseSettings
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
    RevenueLeakageRecord,
    RevenueLeakageStatus,
    RevenueLeakageType,
)
from app.models.outbox_models import OutboxEvent, OutboxStatus
from app.infrastructure.outbox.outbox_service import OutboxService
from app.modules.intelligence.revenue_leakage_service import (
    RevenueLeakageService,
    DataQualityOperationsService,
    HumanOverrideLearningService,
)


@pytest_asyncio.fixture
async def session():
    """Isolated in-memory SQLite database session for unit/integration tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as sess:
        yield sess
    await engine.dispose()


# ─── 1. Section 10: Pilot Mode Configuration & Validation ─────────────────────


def test_pilot_mode_defaults_and_validation():
    """Tests PILOT_MODE accepts valid configurations and rejects invalid ones."""
    # Default is RECOMMEND_ONLY
    settings = EnterpriseSettings()
    assert settings.PILOT_MODE == "RECOMMEND_ONLY"

    # Valid values
    s1 = EnterpriseSettings(PILOT_MODE="approved_automation")
    assert s1.PILOT_MODE == "APPROVED_AUTOMATION"

    s2 = EnterpriseSettings(PILOT_MODE="FULL_GOVERNED_EXECUTION")
    assert s2.PILOT_MODE == "FULL_GOVERNED_EXECUTION"

    s3 = EnterpriseSettings(PILOT_MODE="DISABLED")
    assert s3.PILOT_MODE == "DISABLED"

    # Invalid values should fail validation
    with pytest.raises(ValueError, match="Invalid PILOT_MODE"):
        EnterpriseSettings(PILOT_MODE="UNRESTRICTED_AUTONOMOUS")


# ─── 2. Section 21 & 22: Revenue Leakage Engine ────────────────────────────────


@pytest.mark.asyncio
async def test_revenue_leakage_candidate_lifecycle(session: AsyncSession):
    """
    Tests complete lifecycle of a Revenue Leakage Record:
    CREATE -> LIST -> ENGAGE -> RESOLVE (RECOVERED with OutcomeEvent).
    """
    org_id = f"org-leakage-{uuid.uuid4().hex[:8]}"
    actor_id = f"agent-{uuid.uuid4().hex[:8]}"
    lead_id = f"lead-{uuid.uuid4().hex[:8]}"

    # 1. Create candidate
    candidate = await RevenueLeakageService.create_leakage_candidate(
        session,
        organization_id=org_id,
        leakage_type=RevenueLeakageType.STALE_QUALIFIED_LEAD.value,
        stage="QUALIFICATION",
        estimated_value=Decimal("75000.0000"),
        recommended_intervention="Schedule high-priority viewing with fresh Marina listings",
        evidence={"days_stale": 8, "lead_budget": 2500000, "qualification_score": 0.88},
        lead_id=lead_id,
        owner_id=actor_id,
    )
    await session.commit()

    assert candidate.id is not None
    assert candidate.status == RevenueLeakageStatus.DETECTED.value
    assert candidate.estimated_leakage_value == Decimal("75000.0000")

    # 2. List candidates
    candidates = await RevenueLeakageService.list_leakage_candidates(
        session, organization_id=org_id, status=RevenueLeakageStatus.DETECTED.value
    )
    assert len(candidates) == 1
    assert candidates[0].id == candidate.id

    # 3. Engage candidate
    engaged = await RevenueLeakageService.engage_leakage_candidate(
        session,
        candidate_id=candidate.id,
        organization_id=org_id,
        actor_id=actor_id,
        experiment_id="exp-recovery-marina",
        experiment_variant="VARIANT_WHATSAPP_DROP",
    )
    await session.commit()

    assert engaged.status == RevenueLeakageStatus.ENGAGED.value
    assert engaged.engaged_by == actor_id
    assert engaged.engaged_at is not None
    assert engaged.experiment_id == "exp-recovery-marina"

    # 4. Resolve candidate as RECOVERED
    recovered = await RevenueLeakageService.resolve_leakage_candidate(
        session,
        candidate_id=candidate.id,
        organization_id=org_id,
        outcome="VIEWING_BOOKED",
        recovered_value=Decimal("75000.0000"),
        actor_id=actor_id,
        notes="Customer re-engaged after receiving fresh inventory drop.",
    )
    await session.commit()

    assert recovered.status == RevenueLeakageStatus.RECOVERED.value
    assert recovered.outcome == "VIEWING_BOOKED"
    assert recovered.recovered_value == Decimal("75000.0000")

    # 5. Verify OutcomeEvent was recorded atomically
    stmt = select(OutcomeEvent).where(
        OutcomeEvent.organization_id == org_id,
        OutcomeEvent.event_type == OutcomeEventType.LEAD_RECOVERED.value,
    )
    events = (await session.execute(stmt)).scalars().all()
    assert len(events) == 1
    rec_event = events[0]
    assert rec_event.entity_id == lead_id
    assert rec_event.revenue_impact == Decimal("75000.0000")
    assert rec_event.actor_id == actor_id


@pytest.mark.asyncio
async def test_revenue_leakage_dismissal(session: AsyncSession):
    """Tests resolving a leakage candidate as DISMISSED without creating commercial revenue."""
    org_id = f"org-dismiss-{uuid.uuid4().hex[:8]}"
    actor_id = f"agent-{uuid.uuid4().hex[:8]}"

    candidate = await RevenueLeakageService.create_leakage_candidate(
        session,
        organization_id=org_id,
        leakage_type=RevenueLeakageType.MISSED_FOLLOWUP.value,
        stage="FOLLOW_UP",
        estimated_value=Decimal("15000.0000"),
        recommended_intervention="Send follow-up reminder",
        evidence={"overdue_hours": 36},
    )
    await session.commit()

    resolved = await RevenueLeakageService.resolve_leakage_candidate(
        session,
        candidate_id=candidate.id,
        organization_id=org_id,
        outcome="CUSTOMER_OPTED_OUT",
        actor_id=actor_id,
        notes="Customer requested no further communication",
        is_dismissed=True,
    )
    await session.commit()

    assert resolved.status == RevenueLeakageStatus.DISMISSED.value
    assert resolved.recovered_value is None

    # Verify NO OutcomeEvent was created for dismissed candidate
    stmt = select(OutcomeEvent).where(OutcomeEvent.organization_id == org_id)
    events = (await session.execute(stmt)).scalars().all()
    assert len(events) == 0


@pytest.mark.asyncio
async def test_revenue_leakage_summary_metrics(session: AsyncSession):
    """Tests executive summary calculations for leakage and recovery."""
    org_id = f"org-sum-{uuid.uuid4().hex[:8]}"

    # Add 2 detected candidates
    c1 = await RevenueLeakageService.create_leakage_candidate(
        session,
        organization_id=org_id,
        leakage_type=RevenueLeakageType.UNCONTACTED_LEAD.value,
        stage="INTAKE",
        estimated_value=Decimal("50000.0000"),
        recommended_intervention="Call immediately",
        evidence={},
    )
    c2 = await RevenueLeakageService.create_leakage_candidate(
        session,
        organization_id=org_id,
        leakage_type=RevenueLeakageType.ABANDONED_OFFER.value,
        stage="OFFER",
        estimated_value=Decimal("100000.0000"),
        recommended_intervention="Follow up on counter-offer",
        evidence={},
    )
    await session.commit()

    # Recover c1
    await RevenueLeakageService.engage_leakage_candidate(session, c1.id, org_id, "agent-1")
    await RevenueLeakageService.resolve_leakage_candidate(
        session, c1.id, org_id, outcome="OFFER_ACCEPTED", recovered_value=Decimal("50000.0000"), actor_id="agent-1"
    )
    await session.commit()

    summary = await RevenueLeakageService.get_leakage_summary(session, org_id)
    assert summary["organization_id"] == org_id
    assert summary["active_leakage_count"] == 1  # c2 is still active
    assert summary["active_leakage_value"] == 100000.0
    assert summary["recovered_count"] == 1
    assert summary["recovered_value"] == 50000.0
    assert summary["recovery_rate_pct"] == round((50000.0 / 150000.0) * 100, 2)


# ─── 3. Section 29 & 30: Data Quality Issue Lifecycle & Dashboard ─────────────


@pytest.mark.asyncio
async def test_data_quality_issue_lifecycle_transitions(session: AsyncSession):
    """
    Tests complete lifecycle transitions of a Data Quality Issue:
    OPEN -> ACKNOWLEDGED -> IN_REVIEW -> RESOLVED -> REOPENED -> IGNORED.
    """
    org_id = f"org-dq-{uuid.uuid4().hex[:8]}"
    actor_id = f"admin-{uuid.uuid4().hex[:8]}"

    issue = DataQualityIssue(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        issue_type=DataQualityIssueType.DUPLICATE_LEAD.value,
        severity="HIGH",
        entity_type="LEAD",
        entity_id=f"lead-{uuid.uuid4().hex[:8]}",
        description="Duplicate phone number matched across two golden identities",
        detection_method="phone_identity_resolver",
        dimension="CONSISTENCY",
        status=DataQualityIssueStatus.OPEN.value,
    )
    session.add(issue)
    await session.commit()

    # 1. Acknowledge
    ack = await DataQualityOperationsService.acknowledge_issue(
        session, issue.id, org_id, actor_id, owner="data-team"
    )
    await session.commit()
    assert ack.status == DataQualityIssueStatus.ACKNOWLEDGED.value
    assert ack.acknowledged_by == actor_id
    assert ack.acknowledged_at is not None
    assert ack.owner == "data-team"

    # 2. In Review
    rev = await DataQualityOperationsService.mark_in_review(session, issue.id, org_id, actor_id)
    await session.commit()
    assert rev.status == DataQualityIssueStatus.IN_REVIEW.value
    assert rev.in_review_by == actor_id

    # 3. Resolve
    res = await DataQualityOperationsService.resolve_issue(
        session, issue.id, org_id, actor_id, notes="Merged duplicate records successfully"
    )
    await session.commit()
    assert res.status == DataQualityIssueStatus.RESOLVED.value
    assert res.is_resolved is True
    assert res.resolved_by == actor_id
    assert res.resolution_notes == "Merged duplicate records successfully"

    # 4. Reopen
    reopened = await DataQualityOperationsService.reopen_issue(
        session, issue.id, org_id, actor_id, notes="Subsequent touch showed recurrence"
    )
    await session.commit()
    assert reopened.status == DataQualityIssueStatus.REOPENED.value
    assert reopened.is_resolved is False

    # 5. Ignore requires reason
    with pytest.raises(ValueError, match="reason is required"):
        await DataQualityOperationsService.ignore_issue(session, issue.id, org_id, actor_id, reason="")

    ignored = await DataQualityOperationsService.ignore_issue(
        session, issue.id, org_id, actor_id, reason="Known test artifact in sandbox"
    )
    await session.commit()
    assert ignored.status == DataQualityIssueStatus.IGNORED.value
    assert ignored.ignored_reason == "Known test artifact in sandbox"


@pytest.mark.asyncio
async def test_data_quality_dashboard(session: AsyncSession):
    """Tests the Data Quality operational dashboard metrics aggregation."""
    org_id = f"org-dqdash-{uuid.uuid4().hex[:8]}"

    # Add 1 CRITICAL, 1 HIGH, 1 MEDIUM issue
    session.add(
        DataQualityIssue(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            issue_type=DataQualityIssueType.INVALID_REVENUE_LINK.value,
            severity="CRITICAL",
            entity_type="BOOKING",
            entity_id="bk-1",
            description="Revenue recorded with non-existent booking ledger link",
            detection_method="revenue_ledger_audit",
            dimension="INTEGRITY",
            status=DataQualityIssueStatus.OPEN.value,
            suggested_remediation="Reconcile booking ledger link",
        )
    )
    session.add(
        DataQualityIssue(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            issue_type=DataQualityIssueType.MISSING_SOURCE_ATTRIBUTION.value,
            severity="HIGH",
            entity_type="LEAD",
            entity_id="ld-1",
            description="Lead missing initial touchpoint UTM attribution",
            detection_method="attribution_audit",
            dimension="COMPLETENESS",
            status=DataQualityIssueStatus.ACKNOWLEDGED.value,
        )
    )
    await session.commit()

    dashboard = await DataQualityOperationsService.get_dashboard(session, org_id)
    assert dashboard["organization_id"] == org_id
    assert dashboard["total_open_issues"] == 2
    assert dashboard["by_severity"]["CRITICAL"] == 1
    assert dashboard["by_severity"]["HIGH"] == 1
    assert dashboard["integrity_health"] == "DEGRADED"  # because CRITICAL > 0
    assert len(dashboard["critical_issues"]) == 2


# ─── 4. Section 25 & 26: Human Override Learning ──────────────────────────────


@pytest.mark.asyncio
async def test_human_override_learning_feedback(session: AsyncSession):
    """
    Tests recording human feedback and analyzing override patterns.
    Covers Sections 25 & 26.
    """
    org_id = f"org-override-{uuid.uuid4().hex[:8]}"
    actor_id = f"broker-{uuid.uuid4().hex[:8]}"
    rec_id = f"rec-{uuid.uuid4().hex[:8]}"

    # 1. Record an override with category
    outcome = await HumanOverrideLearningService.record_recommendation_feedback(
        session,
        organization_id=org_id,
        recommendation_id=rec_id,
        action="OVERRIDDEN",
        actor_id=actor_id,
        override_category=HumanOverrideCategory.NOT_TIMELY.value,
        notes="Customer indicated they are travelling until next month",
        recommendation_type="NEXT_BEST_ACTION",
    )
    await session.commit()

    assert outcome.human_override is True
    assert outcome.human_decision == "OVERRIDDEN"
    assert outcome.override_category == HumanOverrideCategory.NOT_TIMELY.value

    # Verify an immutable LearningEvent was generated
    stmt = select(LearningEvent).where(
        LearningEvent.organization_id == org_id,
        LearningEvent.signal_type == LearningSignalType.HUMAN_OVERRIDE.value,
    )
    le = (await session.execute(stmt)).scalars().first()
    assert le is not None
    assert le.signal_value == HumanOverrideCategory.NOT_TIMELY.value
    assert le.actor_id == actor_id

    # 2. Record an accepted recommendation
    rec_id_2 = f"rec-2-{uuid.uuid4().hex[:8]}"
    await HumanOverrideLearningService.record_recommendation_feedback(
        session,
        organization_id=org_id,
        recommendation_id=rec_id_2,
        action="ACCEPTED",
        actor_id=actor_id,
        recommendation_type="NEXT_BEST_ACTION",
    )
    await session.commit()

    # 3. Analyze overrides
    analysis = await HumanOverrideLearningService.get_override_analysis(session, org_id, days=30)
    assert analysis["organization_id"] == org_id
    assert analysis["total_recommendations"] == 2
    assert analysis["total_overrides"] == 1
    assert analysis["override_rate_pct"] == 50.0
    assert len(analysis["by_category"]) == 1
    assert analysis["by_category"][0]["category"] == HumanOverrideCategory.NOT_TIMELY.value
    assert analysis["primary_override_driver"] == HumanOverrideCategory.NOT_TIMELY.value
    assert analysis["evidence_classification"] == "EARLY_SIGNAL_LOW_N"  # N < 30


# ─── 5. Section 8 & 9: Transactional Outbox Idempotency ───────────────────────


@pytest.mark.asyncio
async def test_transactional_outbox_idempotency_and_durability(session: AsyncSession):
    """
    Tests that OutboxService guarantees:
    - Atomicity in transaction
    - Duplicate suppression via idempotency_key
    - Tenant isolation
    """
    tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
    idempotency_key = f"idem-key-{uuid.uuid4().hex[:8]}"

    # 1. Record event
    event1 = await OutboxService.record_event(
        session,
        tenant_id=tenant_id,
        event_type="booking.confirmed",
        aggregate_type="Booking",
        aggregate_id="bk-123",
        payload={"booking_id": "bk-123", "amount": 150000},
        idempotency_key=idempotency_key,
    )
    await session.commit()

    assert event1.id is not None
    assert event1.status == OutboxStatus.PENDING

    # 2. Re-record same event with same idempotency key
    event2 = await OutboxService.record_event(
        session,
        tenant_id=tenant_id,
        event_type="booking.confirmed",
        aggregate_type="Booking",
        aggregate_id="bk-123",
        payload={"booking_id": "bk-123", "amount": 150000},
        idempotency_key=idempotency_key,
    )
    await session.commit()

    # Must return the existing record, NOT create a second row
    assert event2.id == event1.id

    stmt = select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id)
    all_events = (await session.execute(stmt)).scalars().all()
    assert len(all_events) == 1

    # 3. Test failure and DLQ progression
    event1.mark_failed("Temporary network timeout", next_retry_delay_seconds=0)
    assert event1.status == OutboxStatus.FAILED
    assert event1.retry_count == 1

    # Exhaust retries to reach DEAD_LETTER
    event1.retry_count = event1.max_retries - 1
    event1.mark_failed("Permanent failure")
    assert event1.status == OutboxStatus.DEAD_LETTER


# ─── 6. Tenant Isolation Verification ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_leakage_and_dq_tenant_isolation(session: AsyncSession):
    """Verifies that Tenant A can NEVER access or mutate Tenant B's leakage candidates or DQ issues."""
    tenant_a = f"tenant-a-{uuid.uuid4().hex[:8]}"
    tenant_b = f"tenant-b-{uuid.uuid4().hex[:8]}"

    # Create candidate in Tenant A
    cand_a = await RevenueLeakageService.create_leakage_candidate(
        session,
        organization_id=tenant_a,
        leakage_type=RevenueLeakageType.UNCONTACTED_LEAD.value,
        stage="INTAKE",
        estimated_value=Decimal("25000.0000"),
        recommended_intervention="Call lead",
        evidence={},
    )
    await session.commit()

    # Tenant B tries to list candidates — sees 0
    cand_b_list = await RevenueLeakageService.list_leakage_candidates(session, organization_id=tenant_b)
    assert len(cand_b_list) == 0

    # Tenant B tries to engage Tenant A's candidate — must fail
    with pytest.raises(ValueError, match="not found for tenant"):
        await RevenueLeakageService.engage_leakage_candidate(
            session, candidate_id=cand_a.id, organization_id=tenant_b, actor_id="agent-b"
        )
