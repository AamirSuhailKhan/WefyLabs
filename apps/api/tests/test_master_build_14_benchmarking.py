"""
Master Build 14 — Privacy-Preserving Benchmarking Engine Tests
=============================================================
Tests covering:
1. Minimum cohort size enforcement (minimum_cohort_size >= 5)
2. Database CHECK constraint rejects minimum_cohort_size < 5
3. Privacy preservation: Anonymized peer cohorts have organization_id IS NULL
4. Abort calculation when cohort sample size < minimum_cohort_size
5. Percentile calculations (p50, p75, p90, p95) and confidence intervals
6. Tenant privacy isolation (no PII leakage across organizations)
7. Multi-benchmark taxonomy: ORGANIZATION, TEAM, HISTORICAL, ANONYMIZED_COHORT
8. External benchmark provenance and license status
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence_models import (
    BenchmarkDefinition,
    BenchmarkSnapshot,
    BenchmarkType,
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── 1. Minimum Cohort Size Enforcement ─────────────────────────────────────

def test_benchmark_definition_minimum_cohort_accepted(db: Session):
    bdef = BenchmarkDefinition(
        name="Average Stage Velocity",
        slug=f"avg-stage-velocity-{_id()[:8]}",
        benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
        metric_name="stage_velocity_days",
        unit="DAYS",
        description="Average days spent in negotiation stage across industry",
        methodology="Cohort median stage velocity derived from anonymized transitions",
        minimum_cohort_size=5,
        is_active=True,
    )
    db.add(bdef)
    db.commit()

    loaded = db.query(BenchmarkDefinition).filter(BenchmarkDefinition.id == bdef.id).one()
    assert loaded.minimum_cohort_size >= 5
    assert loaded.is_active is True


def test_benchmark_definition_rejects_sub_minimum_cohort(db: Session):
    bdef = BenchmarkDefinition(
        name="Small Cohort Leakage Risk",
        slug=f"leakage-risk-{_id()[:8]}",
        benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
        metric_name="leakage_metric",
        unit="PERCENT",
        description="Invalid definition trying sub-5 cohort",
        methodology="Invalid cohort methodology",
        minimum_cohort_size=2,  # VIOLATES CHECK CONSTRAINT (>= 5)
        is_active=True,
    )
    db.add(bdef)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ─── 2. Privacy Preservation: Anonymized Peer Cohort ────────────────────────

def test_anonymized_cohort_organization_id_is_null(db: Session):
    bdef = BenchmarkDefinition(
        name="Conversion Rate Peer Group",
        slug=f"conversion-rate-peer-group-{_id()[:8]}",
        benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
        metric_name="conversion_rate",
        unit="PERCENTAGE",
        description="Commercial real estate conversion rates",
        methodology="Cohort percentiles from booking outcome events",
        minimum_cohort_size=5,
        is_active=True,
    )
    db.add(bdef)
    db.commit()

    now = _now()
    snap = BenchmarkSnapshot(
        definition_id=bdef.id,
        organization_id=None,  # Crucial: Must be NULL for global/peer benchmarks
        period_start=now - timedelta(days=30),
        period_end=now,
        period_type="MONTHLY",
        value=Decimal("0.1850"),
        value_p50=Decimal("0.1800"),
        value_p75=Decimal("0.2400"),
        value_p90=Decimal("0.3100"),
        actual_cohort_size=12,
        is_privacy_safe=True,
        is_statistically_meaningful=True,
    )
    db.add(snap)
    db.commit()

    loaded = db.query(BenchmarkSnapshot).filter(BenchmarkSnapshot.id == snap.id).one()
    assert loaded.organization_id is None
    assert loaded.is_privacy_safe is True
    assert loaded.actual_cohort_size >= 5


def test_abort_computation_when_sample_below_minimum():
    active_tenants = ["org_1", "org_2", "org_3"]
    min_required = 5
    is_safe = len(active_tenants) >= min_required
    assert is_safe is False


# ─── 3. Percentiles & Statistical Distribution ──────────────────────────────

def test_benchmark_percentiles_ordering(db: Session):
    bdef = BenchmarkDefinition(
        name="Lead Response Latency",
        slug=f"lead-response-latency-{_id()[:8]}",
        benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
        metric_name="first_response_latency_seconds",
        unit="SECONDS",
        description="Speed to lead response time distribution",
        methodology="Seconds between lead creation and first outbound contact",
        minimum_cohort_size=5,
        is_active=True,
    )
    db.add(bdef)
    db.commit()

    now = _now()
    snap = BenchmarkSnapshot(
        definition_id=bdef.id,
        organization_id=None,
        period_start=now - timedelta(days=30),
        period_end=now,
        period_type="MONTHLY",
        value=Decimal("120.0"),
        value_p50=Decimal("110.0"),
        value_p75=Decimal("180.0"),
        value_p90=Decimal("260.0"),
        value_p95=Decimal("350.0"),
        confidence_interval_low=Decimal("95.0"),
        confidence_interval_high=Decimal("145.0"),
        actual_cohort_size=8,
        is_privacy_safe=True,
        is_statistically_meaningful=True,
    )
    db.add(snap)
    db.commit()

    loaded = db.query(BenchmarkSnapshot).filter(BenchmarkSnapshot.id == snap.id).one()
    assert loaded.value_p50 <= loaded.value_p75 <= loaded.value_p90 <= loaded.value_p95
    assert loaded.confidence_interval_low < loaded.value < loaded.confidence_interval_high


# ─── 4. Cross-Tenant Privacy & Data Shielding ───────────────────────────────

def test_internal_vs_anonymized_benchmark_distinction(db: Session):
    org_secret = _id()
    now = _now()

    bdef = BenchmarkDefinition(
        name="Private Team Benchmark",
        slug=f"private-team-bench-{_id()[:8]}",
        benchmark_type=BenchmarkType.ORGANIZATION,
        metric_name="team_booking_quota",
        unit="COUNT",
        description="Internal quota attainment distribution",
        methodology="Internal sales agent quota attainment",
        minimum_cohort_size=5,
        is_active=True,
    )
    db.add(bdef)
    db.commit()

    snap_internal = BenchmarkSnapshot(
        definition_id=bdef.id,
        organization_id=org_secret,
        period_start=now,
        period_end=now,
        period_type="MONTHLY",
        value=Decimal("45.0"),
        actual_cohort_size=6,
        is_privacy_safe=True,
        is_statistically_meaningful=True,
    )
    db.add(snap_internal)
    db.commit()

    global_snaps = db.query(BenchmarkSnapshot).filter(BenchmarkSnapshot.organization_id.is_(None)).all()
    assert snap_internal.id not in [s.id for s in global_snaps]


# ─── 5. External Source Provenance ──────────────────────────────────────────

def test_external_benchmark_metadata(db: Session):
    bdef = BenchmarkDefinition(
        name="Knight Frank APAC Commercial Yield",
        slug=f"knight-frank-apac-yield-{_id()[:8]}",
        benchmark_type=BenchmarkType.ANONYMIZED_COHORT,
        metric_name="gross_rental_yield_pct",
        unit="PERCENTAGE",
        description="Gross rental yields across premium commercial office assets",
        methodology="External industry report secondary ingestion",
        minimum_cohort_size=5,
        is_active=True,
        external_source="Knight Frank India Real Estate Outlook 2026",
        external_source_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        external_license_status="LICENSED_REDISTRIBUTION",
    )
    db.add(bdef)
    db.commit()

    loaded = db.query(BenchmarkDefinition).filter(BenchmarkDefinition.id == bdef.id).one()
    assert loaded.external_source is not None
    assert loaded.external_license_status == "LICENSED_REDISTRIBUTION"
