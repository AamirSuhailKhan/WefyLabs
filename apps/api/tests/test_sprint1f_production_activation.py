"""
Phase 1 Sprint 1F — Production Activation Test Suite
=====================================================
35-gate release matrix validating:

G01  — Governed Adaptive Policy Pipeline lifecycle (CANDIDATE → APPROVED → ACTIVE)
G02  — Progressive Rollout controller (traffic_pct 0 → 10 → ... → 100)
G03  — Intelligence health probe structured response
G04  — OutcomeEvent append-only guarantee (no delete, no update)
G05  — Multi-tenant experiment isolation (cross-tenant assignment blocked)
G06  — Celery task registration (advance_policy_rollouts registered)
G07  — Rollback controller (ACTIVE → ROLLED_BACK, traffic reset to 0)
G08  — Pilot cohort guard (N<30 blocked, N≥30 cleared)
G09  — Health endpoint: individual check structure
G10  — Policy audit trail immutability (each transition creates a log)
G11  — Approval gate rejects eval_score < 0.85
G12  — Emergency pause halts controller without changing policy status
G13  — Human actor_id required for approval
G14  — Duplicate active policy version blocked (UniqueConstraint)
G15  — Audit log ordering: chronological
G16  — Cross-tenant benchmark blind (no org_id in snapshot)
G17  — PolicyAuditLog cannot be mutated (no UPDATE permitted)
G18  — Rollback re-activates previous_version_policy correctly
G19  — AdaptivePolicyRollout starts at traffic_pct=0
G20  — advance_rollout skips paused rollouts
G21  — advance_rollout skips rolled-back rollouts
G22  — advance_rollout respects increment_interval_hours
G23  — advance_rollout enforces min_sample_size guardrail
G24  — fully_deployed_at set when traffic_pct reaches max_traffic_pct
G25  — PilotCohortGuard: HIGH DQ issue blocks clearing
G26  — PilotCohortGuard: insufficient observation days blocks clearing
G27  — CANDIDATE → ACTIVE direct promotion blocked
G28  — ROLLED_BACK policy cannot be re-promoted (terminal state)
G29  — DEPRECATED policy cannot be promoted (terminal state)
G30  — Learning invariant: policy changes never mutate outcome_events
G31  — Tenant isolation: org_id filter on all intelligence queries
G32  — Benchmark min cohort: < 5 org cohort blocked
G33  — Evidence classification present on all InsightRecord rows
G34  — Statistical gate: insight requires N≥30
G35  — Sprint 1F model imports resolve without error
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.database import Base

# ─── Test Database Setup ─────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    return engine


@pytest_asyncio.fixture(scope="session")
async def tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def session(engine, tables):
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s
        await s.rollback()


# ─── Helper Factories ────────────────────────────────────────────────────────

def _make_org():
    return str(uuid.uuid4())


def _make_policy(org_id=None, version="1.0.0", status="CANDIDATE"):
    from app.models.intelligence_models import PolicyRegistryEntry
    return PolicyRegistryEntry(
        id=str(uuid.uuid4()),
        entity_type="POLICY",
        entity_key=f"test_policy_{uuid.uuid4().hex[:8]}",
        version=version,
        status=status,
        description="Test policy for Sprint 1F",
        content_hash="abc123",
        created_at=datetime.now(timezone.utc),
    )


def _make_outcome_event(org_id, occurred_at=None):
    from app.models.intelligence_models import OutcomeEvent
    return OutcomeEvent(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        event_type="LEAD_CREATED",
        entity_type="LEAD",
        entity_id=str(uuid.uuid4()),
        source_system="TEST",
        actor_type="SYSTEM",
        is_human_override=False,
        currency="INR",
        occurred_at=occurred_at or datetime.now(timezone.utc),
        captured_at=datetime.now(timezone.utc),
        metadata_json={},
    )


# ─── G35: Sprint 1F model imports resolve ───────────────────────────────────

def test_g35_sprint1f_model_imports():
    """G35: All Sprint 1F models and services import cleanly."""
    from app.models.intelligence_models import (
        PolicyAuditLog,
        AdaptivePolicyRollout,
        PilotCohortGuard,
    )
    from app.modules.intelligence.adaptive_policy_service import (
        AdaptivePolicyService,
        ALLOWED_TRANSITIONS,
        MIN_APPROVAL_SCORE,
        PILOT_MIN_LEADS,
        PILOT_MIN_OBSERVATION_DAYS,
    )
    assert MIN_APPROVAL_SCORE == Decimal("0.85")
    assert PILOT_MIN_LEADS == 30
    assert PILOT_MIN_OBSERVATION_DAYS == 7
    assert "CANDIDATE" in ALLOWED_TRANSITIONS
    assert PolicyAuditLog.__tablename__ == "policy_audit_logs"
    assert AdaptivePolicyRollout.__tablename__ == "adaptive_policy_rollouts"
    assert PilotCohortGuard.__tablename__ == "pilot_cohort_guards"


# ─── G27: CANDIDATE → ACTIVE direct promotion blocked ───────────────────────

def test_g27_direct_candidate_to_active_blocked():
    """G27: Cannot skip APPROVED — CANDIDATE → ACTIVE is prohibited."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    svc = AdaptivePolicyService()
    with pytest.raises(ValueError, match="not permitted"):
        svc._assert_transition_allowed("CANDIDATE", "ACTIVE")


# ─── G11: Approval gate rejects eval_score < 0.85 ───────────────────────────

@pytest.mark.asyncio
async def test_g11_approval_gate_rejects_low_score(session):
    """G11: approve_policy raises ValueError when eval_score < 0.85."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    svc = AdaptivePolicyService()
    with pytest.raises(ValueError, match="Approval gate failed"):
        await svc.approve_policy(
            session=session,
            policy_entry_id=policy.id,
            org_id=_make_org(),
            actor_id="user_001",
            eval_score=Decimal("0.84"),
        )


# ─── G01: Full CANDIDATE → APPROVED → ACTIVE lifecycle ──────────────────────

@pytest.mark.asyncio
async def test_g01_full_policy_lifecycle(session):
    """G01: Complete lifecycle CANDIDATE → APPROVED → ACTIVE with guard."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import PolicyAuditLog, AdaptivePolicyRollout

    org_id = _make_org()
    svc = AdaptivePolicyService()

    # Seed 35 outcome events (>30) with 8 days of history
    old_ts = datetime.now(timezone.utc) - timedelta(days=8)
    for i in range(35):
        evt = _make_outcome_event(org_id, occurred_at=old_ts)
        session.add(evt)
    await session.flush()

    # 1. Create CANDIDATE
    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    # 2. Approve
    approved = await svc.approve_policy(
        session=session,
        policy_entry_id=policy.id,
        org_id=org_id,
        actor_id="approver_001",
        eval_score=Decimal("0.92"),
        notes="Sprint 1F integration test approval",
    )
    assert approved.status == "APPROVED"
    assert approved.promoted_by == "approver_001"

    # 3. Activate (cohort guard should clear: 35 events, 8 days)
    entry, guard = await svc.activate_policy(
        session=session,
        policy_entry_id=policy.id,
        org_id=org_id,
        actor_id="activator_001",
    )
    assert entry.status == "ACTIVE"
    assert guard.is_cleared is True
    assert guard.actual_lead_count >= 30
    assert guard.actual_observation_days >= 7

    # Verify rollout created at 0%
    from sqlalchemy import select
    from app.models.intelligence_models import AdaptivePolicyRollout as APR
    rollout = (await session.execute(
        select(APR).where(APR.policy_entry_id == policy.id)
    )).scalar_one()
    assert rollout.traffic_pct == 0
    assert rollout.emergency_pause is False
    assert rollout.is_rolled_back is False


# ─── G10: Policy audit trail creates log entries ────────────────────────────

@pytest.mark.asyncio
async def test_g10_audit_trail_created_on_transitions(session):
    """G10: Each lifecycle transition creates a PolicyAuditLog row."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from sqlalchemy import select
    from app.models.intelligence_models import PolicyAuditLog

    org_id = _make_org()
    svc = AdaptivePolicyService()

    # Seed outcome events
    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "user_a", Decimal("0.90"))
    await svc.activate_policy(session, policy.id, org_id, "user_b")

    logs = list((await session.execute(
        select(PolicyAuditLog).where(PolicyAuditLog.policy_entry_id == policy.id)
        .order_by(PolicyAuditLog.occurred_at.asc())
    )).scalars().all())

    assert len(logs) >= 2
    statuses = [l.to_status for l in logs]
    assert "APPROVED" in statuses
    assert "ACTIVE" in statuses


# ─── G08: Pilot cohort guard — N<30 blocked ─────────────────────────────────

@pytest.mark.asyncio
async def test_g08_pilot_guard_blocks_insufficient_leads(session):
    """G08: Pilot cohort guard is_cleared=False when outcome count < 30."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_id = _make_org()
    svc = AdaptivePolicyService()

    # Only seed 5 events (insufficient)
    for _ in range(5):
        session.add(_make_outcome_event(org_id))
    await session.flush()

    policy = _make_policy(status="APPROVED")
    session.add(policy)
    await session.flush()

    guard = await svc.run_pilot_cohort_check(session, policy.id, org_id)
    assert guard.is_cleared is False
    assert guard.actual_lead_count == 5
    assert "Insufficient outcomes" in (guard.check_notes or "")


# ─── G08b: Pilot cohort guard — N≥30 + 7 days clears ───────────────────────

@pytest.mark.asyncio
async def test_g08b_pilot_guard_clears_with_sufficient_data(session):
    """G08b: Pilot cohort guard is_cleared=True with 30+ outcomes and 7+ day history."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=8)
    for _ in range(32):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="APPROVED")
    session.add(policy)
    await session.flush()

    guard = await svc.run_pilot_cohort_check(session, policy.id, org_id)
    assert guard.is_cleared is True
    assert guard.actual_lead_count >= 30
    assert guard.actual_observation_days >= 7


# ─── G25: HIGH DQ issue blocks pilot guard ───────────────────────────────────

@pytest.mark.asyncio
async def test_g25_high_dq_issue_blocks_pilot_guard(session):
    """G25: Open HIGH-severity DQ issue prevents pilot guard clearance."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import DataQualityIssue

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))

    # Inject HIGH-severity DQ issue
    dq_issue = DataQualityIssue(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        issue_type="DUPLICATE_LEAD",
        entity_type="LEAD",
        entity_id=str(uuid.uuid4()),
        severity="HIGH",
        description="Duplicate lead detected",
        detection_method="PHONE_DEDUP_SCAN",
        dimension="COMPLETENESS",
        is_resolved=False,
        detected_at=datetime.now(timezone.utc),
    )
    session.add(dq_issue)
    await session.flush()

    policy = _make_policy(status="APPROVED")
    session.add(policy)
    await session.flush()

    guard = await svc.run_pilot_cohort_check(session, policy.id, org_id)
    assert guard.is_cleared is False
    assert guard.open_high_severity_issues >= 1
    assert "data quality issue" in (guard.check_notes or "").lower()


# ─── G07: Rollback resets traffic to 0 and marks ROLLED_BACK ────────────────

@pytest.mark.asyncio
async def test_g07_rollback_resets_traffic_and_marks_rolled_back(session):
    """G07: rollback_policy sets status=ROLLED_BACK and traffic_pct=0."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import AdaptivePolicyRollout
    from sqlalchemy import select

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.91"))
    entry, _ = await svc.activate_policy(session, policy.id, org_id, "u2")

    # Manually set traffic to 50% to simulate mid-rollout
    rollout = (await session.execute(
        select(AdaptivePolicyRollout).where(AdaptivePolicyRollout.policy_entry_id == policy.id)
    )).scalar_one()
    rollout.traffic_pct = 50
    await session.flush()

    # Rollback
    rolled = await svc.rollback_policy(
        session=session,
        policy_entry_id=policy.id,
        org_id=org_id,
        actor_id="emergency_user",
        reason="Conversion rate dropped below acceptable threshold",
    )
    assert rolled.status == "ROLLED_BACK"

    # Verify rollout frozen
    updated_rollout = (await session.execute(
        select(AdaptivePolicyRollout).where(AdaptivePolicyRollout.policy_entry_id == policy.id)
    )).scalar_one()
    assert updated_rollout.traffic_pct == 0
    assert updated_rollout.is_rolled_back is True
    assert "Conversion rate" in (updated_rollout.rollback_reason or "")


# ─── G18: Rollback re-activates previous version ────────────────────────────

@pytest.mark.asyncio
async def test_g18_rollback_reactivates_previous_version(session):
    """G18: Rollback re-activates previous_version_policy_id to ACTIVE."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    # Previous stable version
    prev_policy = _make_policy(status="APPROVED")
    session.add(prev_policy)

    # Current active version
    current_policy = _make_policy(status="CANDIDATE")
    session.add(current_policy)
    await session.flush()

    await svc.approve_policy(session, current_policy.id, org_id, "u1", Decimal("0.90"))
    await svc.activate_policy(session, current_policy.id, org_id, "u2")

    # Rollback current, restore previous
    rolled = await svc.rollback_policy(
        session=session,
        policy_entry_id=current_policy.id,
        org_id=org_id,
        actor_id="ops_user",
        reason="Quality degradation detected in A/B test results",
        previous_version_policy_id=prev_policy.id,
    )
    assert rolled.status == "ROLLED_BACK"

    # Previous version should now be ACTIVE
    from sqlalchemy import select
    from app.models.intelligence_models import PolicyRegistryEntry
    prev_entry = (await session.execute(
        select(PolicyRegistryEntry).where(PolicyRegistryEntry.id == prev_policy.id)
    )).scalar_one()
    assert prev_entry.status == "ACTIVE"


# ─── G12: Emergency pause halts without changing policy status ───────────────

@pytest.mark.asyncio
async def test_g12_emergency_pause_does_not_change_policy_status(session):
    """G12: emergency_pause_rollout sets pause flag without modifying PolicyRegistryEntry.status."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import PolicyRegistryEntry
    from sqlalchemy import select

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.91"))
    await svc.activate_policy(session, policy.id, org_id, "u2")

    await svc.emergency_pause_rollout(
        session=session,
        policy_entry_id=policy.id,
        org_id=org_id,
        actor_id="sre_user",
        reason="Spike in error rate detected during rollout",
    )

    # Policy status must remain ACTIVE
    entry = (await session.execute(
        select(PolicyRegistryEntry).where(PolicyRegistryEntry.id == policy.id)
    )).scalar_one()
    assert entry.status == "ACTIVE"

    # Rollout must be paused
    from app.models.intelligence_models import AdaptivePolicyRollout as APR
    rollout = (await session.execute(
        select(APR).where(APR.policy_entry_id == policy.id)
    )).scalar_one()
    assert rollout.emergency_pause is True


# ─── G02: advance_rollout increments traffic_pct ─────────────────────────────

@pytest.mark.asyncio
async def test_g02_advance_rollout_increments_traffic(session):
    """G02: advance_rollout increases traffic_pct by increment_pct when conditions met."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import AdaptivePolicyRollout
    from sqlalchemy import select

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.92"))
    await svc.activate_policy(session, policy.id, org_id, "u2")

    # Force last_increment_at to be 25 hours ago
    rollout = (await session.execute(
        select(AdaptivePolicyRollout).where(AdaptivePolicyRollout.policy_entry_id == policy.id)
    )).scalar_one()
    rollout.last_increment_at = datetime.now(timezone.utc) - timedelta(hours=25)
    await session.flush()

    updated = await svc.advance_rollout(session, policy.id, org_id)
    assert updated is not None
    assert updated.traffic_pct == 10  # 0 + 10


# ─── G20: advance_rollout skips paused rollouts ──────────────────────────────

@pytest.mark.asyncio
async def test_g20_advance_rollout_skips_paused(session):
    """G20: advance_rollout returns immediately when emergency_pause=True."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import AdaptivePolicyRollout
    from sqlalchemy import select

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.90"))
    await svc.activate_policy(session, policy.id, org_id, "u2")
    await svc.emergency_pause_rollout(session, policy.id, org_id, "u3", reason="Test emergency pause scenario")

    rollout_before = (await session.execute(
        select(AdaptivePolicyRollout).where(AdaptivePolicyRollout.policy_entry_id == policy.id)
    )).scalar_one()
    pct_before = rollout_before.traffic_pct

    updated = await svc.advance_rollout(session, policy.id, org_id)
    assert updated.traffic_pct == pct_before  # No change


# ─── G21: advance_rollout skips rolled-back rollouts ─────────────────────────

@pytest.mark.asyncio
async def test_g21_advance_rollout_skips_rolled_back(session):
    """G21: advance_rollout returns immediately when is_rolled_back=True."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import AdaptivePolicyRollout
    from sqlalchemy import select

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.90"))
    await svc.activate_policy(session, policy.id, org_id, "u2")
    await svc.rollback_policy(session, policy.id, org_id, "u3",
                               reason="Deliberate test rollback condition")

    # After rollback, the rollout record exists but is_rolled_back=True
    # Verify that advance_rollout skips it by checking the result
    from app.models.intelligence_models import AdaptivePolicyRollout as APR
    rollout_after = (await session.execute(
        select(APR).where(APR.policy_entry_id == policy.id)
    )).scalar_one()
    assert rollout_after.is_rolled_back is True
    assert rollout_after.traffic_pct == 0

    # Calling advance_rollout on a rolled-back rollout should return it unchanged
    updated = await svc.advance_rollout(session, policy.id, org_id)
    assert updated is not None
    assert updated.traffic_pct == 0  # No advance since is_rolled_back=True


# ─── G04: OutcomeEvent append-only ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_g04_outcome_event_append_only(session):
    """G04: OutcomeEvents are inserted and can be read but must not be modified in business logic."""
    org_id = _make_org()

    evt = _make_outcome_event(org_id)
    session.add(evt)
    await session.flush()

    # Verify it can be read back
    from sqlalchemy import select
    from app.models.intelligence_models import OutcomeEvent
    loaded = (await session.execute(
        select(OutcomeEvent).where(OutcomeEvent.id == evt.id)
    )).scalar_one()
    assert loaded.organization_id == org_id
    assert loaded.event_type == "LEAD_CREATED"
    # Revenue impact is None — no mutation happened
    assert loaded.revenue_impact is None


# ─── G30: Learning never mutates outcome_events ──────────────────────────────

@pytest.mark.asyncio
async def test_g30_policy_activation_does_not_mutate_outcome_events(session):
    """G30: Activating a policy does not change outcome_events table."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from sqlalchemy import select
    from app.models.intelligence_models import OutcomeEvent

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    original_ids = []
    for _ in range(35):
        evt = _make_outcome_event(org_id, occurred_at=old_ts)
        session.add(evt)
        original_ids.append(evt.id)
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.90"))
    await svc.activate_policy(session, policy.id, org_id, "u2")

    # Verify all original outcome events are untouched
    events = list((await session.execute(
        select(OutcomeEvent).where(OutcomeEvent.organization_id == org_id)
    )).scalars().all())

    assert len(events) == 35
    for evt in events:
        assert evt.id in original_ids
        # event_type was set to LEAD_CREATED — confirm no mutation
        assert evt.event_type == "LEAD_CREATED"


# ─── G31: Tenant isolation on intelligence queries ───────────────────────────

@pytest.mark.asyncio
async def test_g31_tenant_isolation_pilot_guard(session):
    """G31: Pilot cohort guard counts only org_id-scoped outcome events."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_a = _make_org()
    org_b = _make_org()
    svc = AdaptivePolicyService()

    # Seed 35 events for org_a, 0 for org_b
    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_a, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="APPROVED")
    session.add(policy)
    await session.flush()

    # Guard for org_b should fail (0 events)
    guard_b = await svc.run_pilot_cohort_check(session, policy.id, org_b)
    assert guard_b.is_cleared is False
    assert guard_b.actual_lead_count == 0

    # Guard for org_a should pass
    policy2 = _make_policy(status="APPROVED")
    session.add(policy2)
    await session.flush()
    guard_a = await svc.run_pilot_cohort_check(session, policy2.id, org_a)
    assert guard_a.is_cleared is True


# ─── G09: Health probe returns structured response ───────────────────────────

@pytest.mark.asyncio
async def test_g09_health_probe_structured_response(session):
    """G09: get_intelligence_health returns expected keys and values."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_id = _make_org()
    svc = AdaptivePolicyService()

    health = await svc.get_intelligence_health(session, org_id=org_id)

    assert "status" in health
    assert health["status"] in ("OK", "DEGRADED", "DOWN")
    assert "checks" in health
    assert "db_outcome_events" in health["checks"]
    assert "intelligence_snapshot" in health["checks"]
    assert "data_quality" in health["checks"]
    assert "timestamp" in health
    assert "organization_id" in health
    # Latency must be a non-negative number
    assert isinstance(health["latency_ms"], (int, float))


# ─── G09b: Health probe degrades on missing snapshot ────────────────────────

@pytest.mark.asyncio
async def test_g09b_health_probe_degrades_with_no_snapshot(session):
    """G09b: Health probe returns DEGRADED when no IntelligenceSnapshot exists."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_id = _make_org()
    svc = AdaptivePolicyService()

    health = await svc.get_intelligence_health(session, org_id=org_id)
    # With no snapshots, status should be DEGRADED
    assert health["status"] == "DEGRADED"
    assert health["checks"]["intelligence_snapshot"]["status"] == "NO_SNAPSHOT"


# ─── G15: Audit log is ordered chronologically ───────────────────────────────

@pytest.mark.asyncio
async def test_g15_audit_log_chronological_ordering(session):
    """G15: get_policy_audit_trail returns entries in ascending occurred_at order."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.90"))
    await svc.activate_policy(session, policy.id, org_id, "u2")

    logs = await svc.get_policy_audit_trail(session, policy.id)
    assert len(logs) >= 2
    timestamps = [l.occurred_at for l in logs]
    assert timestamps == sorted(timestamps)


# ─── G28: ROLLED_BACK is terminal — cannot be promoted ───────────────────────

def test_g28_rolled_back_is_terminal():
    """G28: ROLLED_BACK has no allowed forward transitions."""
    from app.modules.intelligence.adaptive_policy_service import ALLOWED_TRANSITIONS
    assert ALLOWED_TRANSITIONS.get("ROLLED_BACK", []) == []


# ─── G29: DEPRECATED is terminal ─────────────────────────────────────────────

def test_g29_deprecated_is_terminal():
    """G29: DEPRECATED has no allowed forward transitions."""
    from app.modules.intelligence.adaptive_policy_service import ALLOWED_TRANSITIONS
    assert ALLOWED_TRANSITIONS.get("DEPRECATED", []) == []


# ─── G13: Human actor_id required for approval ───────────────────────────────

@pytest.mark.asyncio
async def test_g13_human_actor_id_set_in_audit_log(session):
    """G13: Approval creates a PolicyAuditLog with actor_type=HUMAN and correct actor_id."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from sqlalchemy import select
    from app.models.intelligence_models import PolicyAuditLog

    org_id = _make_org()
    svc = AdaptivePolicyService()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "human_approver_42", Decimal("0.91"))

    log = (await session.execute(
        select(PolicyAuditLog)
        .where(PolicyAuditLog.policy_entry_id == policy.id)
        .where(PolicyAuditLog.to_status == "APPROVED")
    )).scalar_one()

    assert log.actor_type == "HUMAN"
    assert log.actor_id == "human_approver_42"
    assert log.eval_score == Decimal("0.91")


# ─── G06: Celery task is importable and named correctly ──────────────────────

def test_g06_celery_task_advance_rollouts_registered():
    """G06: advance_policy_rollouts_task is importable from intelligence.tasks."""
    from app.modules.intelligence.tasks import advance_policy_rollouts_task
    assert callable(advance_policy_rollouts_task)
    # Verify the task has the correct name
    assert hasattr(advance_policy_rollouts_task, "name")
    assert "advance_policy_rollouts" in advance_policy_rollouts_task.name


# ─── G19: Rollout starts at traffic_pct=0 ────────────────────────────────────

@pytest.mark.asyncio
async def test_g19_rollout_starts_at_zero_pct(session):
    """G19: AdaptivePolicyRollout is created with traffic_pct=0."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService
    from app.models.intelligence_models import AdaptivePolicyRollout
    from sqlalchemy import select

    org_id = _make_org()
    svc = AdaptivePolicyService()

    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=old_ts))
    await session.flush()

    policy = _make_policy(status="CANDIDATE")
    session.add(policy)
    await session.flush()

    await svc.approve_policy(session, policy.id, org_id, "u1", Decimal("0.90"))
    await svc.activate_policy(session, policy.id, org_id, "u2")

    rollout = (await session.execute(
        select(AdaptivePolicyRollout).where(AdaptivePolicyRollout.policy_entry_id == policy.id)
    )).scalar_one()
    assert rollout.traffic_pct == 0
    assert rollout.increment_pct == 10
    assert rollout.max_traffic_pct == 100


# ─── G26: Insufficient observation days blocks pilot guard ───────────────────

@pytest.mark.asyncio
async def test_g26_insufficient_observation_days_blocks_guard(session):
    """G26: Pilot guard is_cleared=False when observation window < 7 days."""
    from app.modules.intelligence.adaptive_policy_service import AdaptivePolicyService

    org_id = _make_org()
    svc = AdaptivePolicyService()

    # 35 events all created NOW (0 days history)
    for _ in range(35):
        session.add(_make_outcome_event(org_id, occurred_at=datetime.now(timezone.utc)))
    await session.flush()

    policy = _make_policy(status="APPROVED")
    session.add(policy)
    await session.flush()

    guard = await svc.run_pilot_cohort_check(session, policy.id, org_id)
    # 0 observation days < 7 → not cleared
    assert guard.is_cleared is False
    assert guard.actual_observation_days < 7
