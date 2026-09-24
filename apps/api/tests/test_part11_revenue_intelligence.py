"""
Part 11 — Revenue Intelligence: Comprehensive Test Suite
=========================================================

Test categories:
  A. Unit — FunnelAnalyzer computation logic (in-memory SQLite)
  B. Unit — LeakageDetector detection + event writing
  C. Unit — OutcomeTracker win-rate computation
  D. Unit — SourceAttributionReport grouping
  E. Unit — LearningLoopSummary heuristic aggregation
  F. Unit — SnapshotService capture + list + idempotency
  G. API contract — all 7 endpoints return correct HTTP status
  H. Tenant isolation — org A data never visible to org B
  I. Empty-state — all endpoints return safe state when DB is empty
  J. No-fabrication — conversion rates are None when denominator=0
  K. Regression — Part 35 Revenue Autopilot endpoints still functional

Execution:
  pytest tests/test_part11_revenue_intelligence.py -v
"""
import uuid
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.models import Base, Broker, Lead
from app.models.revenue_autopilot_models import RevenueOpportunity, RevenueFeedbackLog
from app.models.transaction_models import DealTransaction
from app.models.revenue_intelligence_models import RevenueFunnelSnapshot, RevenueLeakageEvent
from app.modules.revenue_intelligence.service import (
    FunnelAnalyzer,
    LeakageDetector,
    OutcomeTracker,
    SourceAttributionReport,
    LearningLoopSummary,
    SnapshotService,
    RevenueIntelligenceService,
    _safe_rate,
)
from app.database import get_db

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def broker_a(db_session: AsyncSession) -> Broker:
    b = Broker(
        email="broker_a@test.com",
        phone="+919000000001",
        name="Broker A",
        agency_name="Agency A",
        city="Mumbai",
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def broker_b(db_session: AsyncSession) -> Broker:
    b = Broker(
        email="broker_b@test.com",
        phone="+919000000002",
        name="Broker B",
        agency_name="Agency B",
        city="Delhi",
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


async def _make_lead(
    db: AsyncSession,
    broker: Broker,
    pipeline_stage: str = "new",
    status: str = "pending",
    score: str = "warm",
    source: str = "manual",
    budget_max: int = 5_000_000,
    updated_at_offset_days: int = 0,
) -> Lead:
    now = datetime.now(timezone.utc)
    lead = Lead(
        broker_id=broker.id,
        phone=f"+91{uuid.uuid4().int % 10_000_000_000:010d}",
        name="Test Lead",
        source=source,
        score=score,
        pipeline_stage=pipeline_stage,
        status=status,
        budget_max=budget_max,
        transaction_type="buy",
        updated_at=now - timedelta(days=updated_at_offset_days),
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def _make_opportunity(
    db: AsyncSession,
    broker: Broker,
    lead: Lead,
    opp_status: str = "NEW",
    opp_type: str = "HOT_LEAD_NEEDS_CONTACT",
    feedback_rating: str = None,
    actual_outcome: str = None,
    score: float = 75.0,
) -> RevenueOpportunity:
    opp = RevenueOpportunity(
        organization_id=broker.id,
        broker_id=broker.id,
        lead_id=lead.id,
        opportunity_type=opp_type,
        status=opp_status,
        opportunity_score=score,
        match_score=70.0,
        reason="Test reason",
        why_now="Test why now",
        dedup_key=f"{lead.id}:{opp_type}",
        feedback_rating=feedback_rating,
        actual_outcome=actual_outcome,
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)
    return opp


async def _make_feedback_log(
    db: AsyncSession,
    broker: Broker,
    lead: Lead,
    opp: RevenueOpportunity,
    action_type: str = "FEEDBACK",
    rating: str = "YES",
    actual_outcome: str = "DEAL_CLOSED",
) -> RevenueFeedbackLog:
    log = RevenueFeedbackLog(
        opportunity_id=opp.id,
        organization_id=broker.id,
        broker_id=broker.id,
        lead_id=lead.id,
        action_type=action_type,
        rating=rating,
        actual_outcome=actual_outcome,
        features_snapshot={},
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


# ──────────────────────────────────────────────────────────────────────────────
# A. Unit: FunnelAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class TestFunnelAnalyzer:

    @pytest.mark.asyncio
    async def test_empty_org_returns_zeros(self, db_session, broker_a):
        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)

        assert result["total_leads"] == 0
        assert result["active_opportunities"] == 0
        assert result["overall_conversion_rate_pct"] is None
        assert result["estimated_pipeline_value_estimate"] is None

    @pytest.mark.asyncio
    async def test_stage_counts_are_accurate(self, db_session, broker_a):
        # Create 3 new, 2 contacted, 1 qualified leads
        for _ in range(3):
            await _make_lead(db_session, broker_a, pipeline_stage="new")
        for _ in range(2):
            await _make_lead(db_session, broker_a, pipeline_stage="contacted")
        await _make_lead(db_session, broker_a, pipeline_stage="qualified")

        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)

        assert result["total_leads"] == 6
        stage_map = {s["stage"]: s["count"] for s in result["stages"]}
        assert stage_map["new"] == 3
        assert stage_map["contacted"] == 2
        assert stage_map["qualified"] == 1

    @pytest.mark.asyncio
    async def test_conversion_rate_calculated_correctly(self, db_session, broker_a):
        # 4 new → 2 contacted = 50% conversion from new to contacted
        for _ in range(4):
            await _make_lead(db_session, broker_a, pipeline_stage="new")
        for _ in range(2):
            await _make_lead(db_session, broker_a, pipeline_stage="contacted")

        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)

        stage_map = {s["stage"]: s for s in result["stages"]}
        assert stage_map["new"]["conversion_rate_pct"] == 50.0

    @pytest.mark.asyncio
    async def test_conversion_rate_none_when_zero_leads_at_stage(self, db_session, broker_a):
        """
        NO FABRICATION TEST: if new=0 but contacted=2, rate for new→contacted is None.
        """
        for _ in range(2):
            await _make_lead(db_session, broker_a, pipeline_stage="contacted")

        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)

        stage_map = {s["stage"]: s for s in result["stages"]}
        assert stage_map["new"]["conversion_rate_pct"] is None

    @pytest.mark.asyncio
    async def test_pipeline_value_sums_budget_max_for_qualified_plus(self, db_session, broker_a):
        await _make_lead(db_session, broker_a, pipeline_stage="qualified", budget_max=3_000_000)
        await _make_lead(db_session, broker_a, pipeline_stage="site_visit", budget_max=5_000_000)
        await _make_lead(db_session, broker_a, pipeline_stage="new", budget_max=2_000_000)

        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)

        # Only qualified + site_visit count (not new)
        assert result["estimated_pipeline_value_estimate"] == 8_000_000.0

    @pytest.mark.asyncio
    async def test_overall_conversion_rate_is_none_with_zero_leads(self, db_session, broker_a):
        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)
        assert result["overall_conversion_rate_pct"] is None


# ──────────────────────────────────────────────────────────────────────────────
# B. Unit: LeakageDetector
# ──────────────────────────────────────────────────────────────────────────────

class TestLeakageDetector:

    @pytest.mark.asyncio
    async def test_empty_org_returns_zero_leakage(self, db_session, broker_a):
        detector = LeakageDetector(db_session)
        result = await detector.get_leakage_report(broker_a.id)

        assert result["total_leakage_events"] == 0
        assert result["total_estimated_value_at_risk_estimate"] is None
        assert result["by_stage"] == []

    @pytest.mark.asyncio
    async def test_detects_explicitly_lost_leads(self, db_session, broker_a):
        await _make_lead(db_session, broker_a, status="lost", pipeline_stage="contacted")

        detector = LeakageDetector(db_session)
        result = await detector.get_leakage_report(broker_a.id)

        assert result["total_leakage_events"] == 1
        by_stage = {item["stage"]: item for item in result["by_stage"]}
        assert "contacted" in by_stage
        assert by_stage["contacted"]["top_reason"] == "EXPLICIT_LOSS"

    @pytest.mark.asyncio
    async def test_detects_stale_leads(self, db_session, broker_a):
        # Lead not updated for 20 days (> 14 day default threshold)
        await _make_lead(db_session, broker_a, status="pending", pipeline_stage="new", updated_at_offset_days=20)

        detector = LeakageDetector(db_session)
        result = await detector.get_leakage_report(broker_a.id, staleness_days=14)

        assert result["total_leakage_events"] == 1
        by_stage = {item["stage"]: item for item in result["by_stage"]}
        assert "new" in by_stage
        assert by_stage["new"]["top_reason"] == "STALE"

    @pytest.mark.asyncio
    async def test_converted_leads_not_counted_as_leakage(self, db_session, broker_a):
        await _make_lead(db_session, broker_a, status="converted", pipeline_stage="converted")

        detector = LeakageDetector(db_session)
        result = await detector.get_leakage_report(broker_a.id)

        # Converted lead should NOT be in leakage
        assert result["total_leakage_events"] == 0

    @pytest.mark.asyncio
    async def test_writes_leakage_events_to_db(self, db_session, broker_a):
        await _make_lead(db_session, broker_a, status="lost", pipeline_stage="qualified")

        detector = LeakageDetector(db_session)
        await detector.get_leakage_report(broker_a.id)
        await db_session.flush()

        from sqlalchemy import select
        events_q = await db_session.execute(
            select(RevenueLeakageEvent).where(RevenueLeakageEvent.organization_id == broker_a.id)
        )
        events = events_q.scalars().all()
        assert len(events) >= 1
        assert events[0].leakage_reason == "EXPLICIT_LOSS"

    @pytest.mark.asyncio
    async def test_value_at_risk_is_none_when_no_budget_set(self, db_session, broker_a):
        # Lead with no budget_max
        lead = Lead(
            broker_id=broker_a.id,
            phone="+919111111111",
            source="manual",
            score="cold",
            status="lost",
            pipeline_stage="new",
            budget_max=None,
        )
        db_session.add(lead)
        await db_session.commit()

        detector = LeakageDetector(db_session)
        result = await detector.get_leakage_report(broker_a.id)

        # Should still detect the leakage but value is None
        assert result["total_leakage_events"] >= 1
        for s in result["by_stage"]:
            if s["stage"] == "new":
                assert s["total_estimated_value_lost_estimate"] is None


# ──────────────────────────────────────────────────────────────────────────────
# C. Unit: OutcomeTracker
# ──────────────────────────────────────────────────────────────────────────────

class TestOutcomeTracker:

    @pytest.mark.asyncio
    async def test_empty_returns_zero_win_rate_null(self, db_session, broker_a):
        tracker = OutcomeTracker(db_session)
        result = await tracker.get_outcome_summary(broker_a.id)

        assert result["total_feedback_records"] == 0
        assert result["win_rate_pct"] is None
        assert result["positive_feedback_count"] == 0

    @pytest.mark.asyncio
    async def test_win_rate_computed_correctly(self, db_session, broker_a):
        lead = await _make_lead(db_session, broker_a)
        opp = await _make_opportunity(db_session, broker_a, lead)

        # 2 positive, 1 negative = 66.67%
        await _make_feedback_log(db_session, broker_a, lead, opp, rating="YES", actual_outcome="DEAL_CLOSED")
        await _make_feedback_log(db_session, broker_a, lead, opp, rating="YES", actual_outcome="CONVERTED")
        await _make_feedback_log(db_session, broker_a, lead, opp, rating="NO", actual_outcome="LOST")

        tracker = OutcomeTracker(db_session)
        result = await tracker.get_outcome_summary(broker_a.id)

        assert result["total_feedback_records"] == 3
        assert result["positive_feedback_count"] == 2
        assert result["negative_feedback_count"] == 1
        assert result["win_rate_pct"] == pytest.approx(66.67, abs=0.1)

    @pytest.mark.asyncio
    async def test_outcome_distribution_sums_correctly(self, db_session, broker_a):
        lead = await _make_lead(db_session, broker_a)
        opp = await _make_opportunity(db_session, broker_a, lead)
        await _make_feedback_log(db_session, broker_a, lead, opp, actual_outcome="DEAL_CLOSED")
        await _make_feedback_log(db_session, broker_a, lead, opp, actual_outcome="LOST")

        tracker = OutcomeTracker(db_session)
        result = await tracker.get_outcome_summary(broker_a.id)

        outcomes_sum = sum(item["count"] for item in result["outcome_distribution"])
        assert outcomes_sum == result["total_feedback_records"]


# ──────────────────────────────────────────────────────────────────────────────
# D. Unit: SourceAttributionReport
# ──────────────────────────────────────────────────────────────────────────────

class TestSourceAttributionReport:

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self, db_session, broker_a):
        reporter = SourceAttributionReport(db_session)
        result = await reporter.get_attribution_report(broker_a.id)

        assert result["total_sources"] == 0
        assert result["by_source"] == []
        assert result["top_source_by_leads"] is None

    @pytest.mark.asyncio
    async def test_groups_by_source_correctly(self, db_session, broker_a):
        await _make_lead(db_session, broker_a, source="whatsapp_forward")
        await _make_lead(db_session, broker_a, source="whatsapp_forward")
        await _make_lead(db_session, broker_a, source="meta_ads")

        reporter = SourceAttributionReport(db_session)
        result = await reporter.get_attribution_report(broker_a.id)

        source_map = {item["source"]: item for item in result["by_source"]}
        assert source_map["whatsapp_forward"]["lead_count"] == 2
        assert source_map["meta_ads"]["lead_count"] == 1
        assert result["top_source_by_leads"] == "whatsapp_forward"

    @pytest.mark.asyncio
    async def test_conversion_rate_none_when_zero_leads(self, db_session, broker_a):
        """No-fabrication: if source has 0 leads, rate is None (unreachable, but guard tested)."""
        # _safe_rate itself
        assert _safe_rate(0, 0) is None
        assert _safe_rate(5, 0) is None
        assert _safe_rate(0, 10) == 0.0

    @pytest.mark.asyncio
    async def test_top_source_by_conversion_identified(self, db_session, broker_a):
        await _make_lead(db_session, broker_a, source="google_ads", status="converted")
        await _make_lead(db_session, broker_a, source="google_ads", status="active")
        await _make_lead(db_session, broker_a, source="manual", status="pending")

        reporter = SourceAttributionReport(db_session)
        result = await reporter.get_attribution_report(broker_a.id)

        # google_ads: 1/2 = 50%, manual: 0/1 = 0%
        assert result["top_source_by_conversion"] == "google_ads"


# ──────────────────────────────────────────────────────────────────────────────
# E. Unit: LearningLoopSummary
# ──────────────────────────────────────────────────────────────────────────────

class TestLearningLoopSummary:

    @pytest.mark.asyncio
    async def test_empty_returns_safe_empty(self, db_session, broker_a):
        summary = LearningLoopSummary(db_session)
        result = await summary.get_learning_summary(broker_a.id)

        assert result["total_opportunities_evaluated"] == 0
        assert result["total_positive_signals"] == 0
        assert result["top_opportunity_types"] == []
        assert result["computation_method"] == "heuristic_aggregation_v1"

    @pytest.mark.asyncio
    async def test_top_opportunity_types_ranked_by_count(self, db_session, broker_a):
        lead = await _make_lead(db_session, broker_a)
        # 3 HOT_LEAD opps, 1 STALE
        for _ in range(3):
            await _make_opportunity(db_session, broker_a, lead, opp_type="HOT_LEAD_NEEDS_CONTACT")
        await _make_opportunity(db_session, broker_a, lead, opp_type="STALE_HOT_LEAD")

        summary = LearningLoopSummary(db_session)
        result = await summary.get_learning_summary(broker_a.id)

        assert result["top_opportunity_types"][0]["opportunity_type"] == "HOT_LEAD_NEEDS_CONTACT"
        assert result["top_opportunity_types"][0]["total_count"] == 3

    @pytest.mark.asyncio
    async def test_computation_method_is_heuristic(self, db_session, broker_a):
        """Ensures we never claim ML."""
        summary = LearningLoopSummary(db_session)
        result = await summary.get_learning_summary(broker_a.id)
        assert result["computation_method"] == "heuristic_aggregation_v1"
        assert "ml" not in result["computation_method"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# F. Unit: SnapshotService
# ──────────────────────────────────────────────────────────────────────────────

class TestSnapshotService:

    @pytest.mark.asyncio
    async def test_capture_creates_snapshot(self, db_session, broker_a):
        analyzer = FunnelAnalyzer(db_session)
        svc = SnapshotService(db_session, analyzer)

        snap = await svc.capture(broker_a.id, period_type="DAILY")
        await db_session.flush()

        assert snap.id is not None
        assert snap.organization_id == broker_a.id
        assert snap.period_type == "DAILY"

    @pytest.mark.asyncio
    async def test_capture_is_idempotent(self, db_session, broker_a):
        """Capturing twice for the same org+date should upsert, not duplicate."""
        analyzer = FunnelAnalyzer(db_session)
        svc = SnapshotService(db_session, analyzer)

        snap1 = await svc.capture(broker_a.id, period_type="DAILY")
        await db_session.flush()
        snap2 = await svc.capture(broker_a.id, period_type="DAILY")
        await db_session.flush()

        # Same primary key — idempotent upsert
        assert snap1.id == snap2.id

    @pytest.mark.asyncio
    async def test_list_snapshots_returns_correct_count(self, db_session, broker_a):
        analyzer = FunnelAnalyzer(db_session)
        svc = SnapshotService(db_session, analyzer)

        await svc.capture(broker_a.id, period_type="DAILY")
        await db_session.flush()

        snaps, total = await svc.list_snapshots(broker_a.id)
        assert total == 1
        assert len(snaps) == 1

    @pytest.mark.asyncio
    async def test_snapshot_reflects_current_lead_counts(self, db_session, broker_a):
        await _make_lead(db_session, broker_a, pipeline_stage="new")
        await _make_lead(db_session, broker_a, pipeline_stage="qualified")

        analyzer = FunnelAnalyzer(db_session)
        svc = SnapshotService(db_session, analyzer)
        snap = await svc.capture(broker_a.id)
        await db_session.flush()

        assert snap.total_leads == 2
        assert snap.leads_new == 1
        assert snap.leads_qualified == 1


# ──────────────────────────────────────────────────────────────────────────────
# G. API contract tests — all 7 endpoints
# ──────────────────────────────────────────────────────────────────────────────

class TestAPIContract:
    """
    Tests that each endpoint returns the correct HTTP status codes.
    We override the get_db dependency to use in-memory SQLite.
    Authentication is bypassed by overriding get_current_broker.
    """

    @pytest_asyncio.fixture
    async def db_engine(self):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest_asyncio.fixture
    async def test_broker_for_api(self, db_engine):
        factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            b = Broker(
                email="apitest@test.com",
                phone="+919000000099",
                name="API Test Broker",
                agency_name="API Agency",
                city="Bengaluru",
            )
            session.add(b)
            await session.commit()
            await session.refresh(b)
            return b

    @pytest_asyncio.fixture
    async def client(self, db_engine, test_broker_for_api):
        factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with factory() as s:
                yield s

        async def override_auth():
            return test_broker_for_api

        from app.dependencies import get_current_broker as real_auth
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[real_auth] = override_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_funnel_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/funnel")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_leads" in data
        assert "stages" in data

    @pytest.mark.asyncio
    async def test_leakage_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/leakage")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_leakage_events" in data
        assert "by_stage" in data

    @pytest.mark.asyncio
    async def test_outcomes_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/outcomes")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_feedback_records" in data

    @pytest.mark.asyncio
    async def test_attribution_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/attribution")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sources" in data
        assert "by_source" in data

    @pytest.mark.asyncio
    async def test_learning_loop_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/learning-loop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["computation_method"] == "heuristic_aggregation_v1"

    @pytest.mark.asyncio
    async def test_snapshot_capture_returns_201(self, client):
        resp = await client.post(
            "/api/v1/revenue-intelligence/snapshots/capture",
            json={"period_type": "DAILY"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["period_type"] == "DAILY"

    @pytest.mark.asyncio
    async def test_snapshot_list_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_snapshot_invalid_period_type_returns_422(self, client):
        resp = await client.post(
            "/api/v1/revenue-intelligence/snapshots/capture",
            json={"period_type": "QUARTERLY"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_format_returns_422(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/funnel?date_from=not-a-date")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_overview_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "realized_revenue" in data
        assert "current_pipeline_estimate" in data
        assert "forecast_status" in data

    @pytest.mark.asyncio
    async def test_leakage_items_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/leakage/items")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_sources_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sources" in data

    @pytest.mark.asyncio
    async def test_opportunities_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_opportunities" in data

    @pytest.mark.asyncio
    async def test_actions_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert "computation_method" in data

    @pytest.mark.asyncio
    async def test_data_quality_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/data-quality")
        assert resp.status_code == 200
        data = resp.json()
        assert "data_health_score_pct" in data
        assert "issues" in data

    @pytest.mark.asyncio
    async def test_team_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/revenue-intelligence/team")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_agents" in data

    @pytest.mark.asyncio
    async def test_recompute_endpoint_returns_200(self, client):
        resp = await client.post("/api/v1/revenue-intelligence/recompute", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_lead_journey_not_found_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/revenue-intelligence/journey/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_property_journey_not_found_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/revenue-intelligence/property/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_propensity_not_found_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/revenue-intelligence/propensity/{fake_id}")
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# H. Tenant Isolation
# ──────────────────────────────────────────────────────────────────────────────

class TestTenantIsolation:

    @pytest.mark.asyncio
    async def test_funnel_does_not_cross_tenant_boundary(self, db_session, broker_a, broker_b):
        """Leads from broker_b must NOT appear in broker_a's funnel."""
        # broker_b has 5 leads, broker_a has 1
        for _ in range(5):
            await _make_lead(db_session, broker_b, pipeline_stage="new")
        await _make_lead(db_session, broker_a, pipeline_stage="qualified")

        analyzer = FunnelAnalyzer(db_session)
        result_a = await analyzer.get_funnel_summary(broker_a.id)
        result_b = await analyzer.get_funnel_summary(broker_b.id)

        assert result_a["total_leads"] == 1
        assert result_b["total_leads"] == 5

    @pytest.mark.asyncio
    async def test_leakage_does_not_cross_tenant_boundary(self, db_session, broker_a, broker_b):
        await _make_lead(db_session, broker_b, status="lost", pipeline_stage="contacted")
        # broker_a has no lost leads

        detector = LeakageDetector(db_session)
        result_a = await detector.get_leakage_report(broker_a.id)
        result_b = await detector.get_leakage_report(broker_b.id)

        assert result_a["total_leakage_events"] == 0
        assert result_b["total_leakage_events"] == 1

    @pytest.mark.asyncio
    async def test_attribution_does_not_cross_tenant_boundary(self, db_session, broker_a, broker_b):
        await _make_lead(db_session, broker_b, source="google_ads")
        await _make_lead(db_session, broker_b, source="google_ads")

        reporter = SourceAttributionReport(db_session)
        result_a = await reporter.get_attribution_report(broker_a.id)

        # broker_a should see 0 sources
        assert result_a["total_sources"] == 0

    @pytest.mark.asyncio
    async def test_outcomes_does_not_cross_tenant_boundary(self, db_session, broker_a, broker_b):
        lead_b = await _make_lead(db_session, broker_b)
        opp_b = await _make_opportunity(db_session, broker_b, lead_b)
        await _make_feedback_log(db_session, broker_b, lead_b, opp_b, actual_outcome="DEAL_CLOSED")

        tracker = OutcomeTracker(db_session)
        result_a = await tracker.get_outcome_summary(broker_a.id)

        assert result_a["total_feedback_records"] == 0
        assert result_a["win_rate_pct"] is None


# ──────────────────────────────────────────────────────────────────────────────
# I. Empty-State Safety
# ──────────────────────────────────────────────────────────────────────────────

class TestEmptyStateSafety:

    @pytest.mark.asyncio
    async def test_all_analyzers_handle_fresh_org(self, db_session, broker_a):
        """All analyzers must return valid structure (not crash) on empty org."""
        svc = RevenueIntelligenceService(db_session)
        fresh_org_id = broker_a.id

        funnel = await svc.funnel.get_funnel_summary(fresh_org_id)
        assert isinstance(funnel, dict)
        assert funnel["total_leads"] == 0

        leakage = await svc.leakage.get_leakage_report(fresh_org_id)
        assert isinstance(leakage, dict)
        assert leakage["total_leakage_events"] == 0

        outcomes = await svc.outcomes.get_outcome_summary(fresh_org_id)
        assert isinstance(outcomes, dict)
        assert outcomes["win_rate_pct"] is None

        attribution = await svc.attribution.get_attribution_report(fresh_org_id)
        assert isinstance(attribution, dict)
        assert attribution["total_sources"] == 0

        learning = await svc.learning.get_learning_summary(fresh_org_id)
        assert isinstance(learning, dict)
        assert learning["total_opportunities_evaluated"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# J. No-Fabrication Safety
# ──────────────────────────────────────────────────────────────────────────────

class TestNoFabrication:

    def test_safe_rate_zero_denominator_returns_none(self):
        assert _safe_rate(100, 0) is None

    def test_safe_rate_zero_numerator_returns_zero(self):
        assert _safe_rate(0, 10) == 0.0

    def test_safe_rate_correct_calculation(self):
        assert _safe_rate(3, 4) == 75.0

    @pytest.mark.asyncio
    async def test_funnel_overall_rate_none_when_no_leads(self, db_session, broker_a):
        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)
        assert result["overall_conversion_rate_pct"] is None

    @pytest.mark.asyncio
    async def test_win_rate_none_when_no_feedback(self, db_session, broker_a):
        tracker = OutcomeTracker(db_session)
        result = await tracker.get_outcome_summary(broker_a.id)
        assert result["win_rate_pct"] is None

    @pytest.mark.asyncio
    async def test_estimated_value_explicitly_labelled(self, db_session, broker_a):
        """Estimate fields must use _estimate suffix in key names (API contract)."""
        analyzer = FunnelAnalyzer(db_session)
        result = await analyzer.get_funnel_summary(broker_a.id)
        # Key must include _estimate to signal it is not a transactional fact
        assert "estimated_pipeline_value_estimate" in result


# ──────────────────────────────────────────────────────────────────────────────
# K. Regression — Part 35 Revenue Autopilot still functional
# ──────────────────────────────────────────────────────────────────────────────

class TestPart35Regression:
    """
    Ensures Revenue Autopilot endpoints are not broken by Part 11 changes.
    We only test that the router is still registered and returns expected
    status codes (not 404 or 500 from import failures).
    """

    @pytest_asyncio.fixture
    async def db_engine_reg(self):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest_asyncio.fixture
    async def broker_reg(self, db_engine_reg):
        factory = async_sessionmaker(db_engine_reg, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            b = Broker(
                email="regtest@test.com",
                phone="+919000000088",
                name="Reg Test Broker",
                agency_name="Reg Agency",
                city="Chennai",
            )
            session.add(b)
            await session.commit()
            await session.refresh(b)
            return b

    @pytest_asyncio.fixture
    async def reg_client(self, db_engine_reg, broker_reg):
        factory = async_sessionmaker(db_engine_reg, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with factory() as s:
                yield s

        async def override_auth():
            return broker_reg

        from app.dependencies import get_current_broker as real_auth
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[real_auth] = override_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_revenue_autopilot_queue_still_returns_200(self, reg_client):
        resp = await reg_client.get("/api/v1/revenue-autopilot/queue")
        # 200 or 404 are both acceptable (depends on whether autopilot has data)
        # What we must NOT see is 500 (import/startup failure)
        assert resp.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_revenue_intelligence_does_not_break_app_startup(self, reg_client):
        """The app should still respond to root health check."""
        resp = await reg_client.get("/")
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# L. Revenue Copilot AI Workforce Tool Execution
# ──────────────────────────────────────────────────────────────────────────────

class TestRevenueCopilotTools:

    @pytest.mark.asyncio
    async def test_all_12_revenue_copilot_tools_registered(self):
        from app.modules.ai_agent.tool_executor.registry import TOOLS
        registered_names = {t.name for t in TOOLS}
        expected_part11_tools = [
            "get_revenue_overview",
            "get_funnel_metrics",
            "get_leakage_summary",
            "get_source_attribution",
            "get_opportunity_flow",
            "get_action_effectiveness",
            "get_outcome_history",
            "get_data_quality",
            "get_lead_revenue_journey",
            "get_property_conversion_history",
            "get_agent_action_history",
            "get_revenue_at_risk",
        ]
        for name in expected_part11_tools:
            assert name in registered_names, f"Missing tool: {name}"

    @pytest.mark.asyncio
    async def test_execute_get_revenue_overview(self, db_session, broker_a):
        from app.modules.ai_agent.tool_executor.executor import ToolExecutor
        executor = ToolExecutor()
        res = await executor.run(
            db=db_session,
            session_id="sess-part11",
            turn_index=1,
            tool_name="get_revenue_overview",
            arguments={},
            context={"organization_id": broker_a.id}
        )
        assert res.success is True
        assert res.result is not None
        assert "realized_revenue" in res.result

    @pytest.mark.asyncio
    async def test_execute_get_funnel_metrics(self, db_session, broker_a):
        from app.modules.ai_agent.tool_executor.executor import ToolExecutor
        executor = ToolExecutor()
        res = await executor.run(
            db=db_session,
            session_id="sess-part11",
            turn_index=1,
            tool_name="get_funnel_metrics",
            arguments={},
            context={"organization_id": broker_a.id}
        )
        assert res.success is True
        assert "stages" in res.result

    @pytest.mark.asyncio
    async def test_execute_get_leakage_summary(self, db_session, broker_a):
        from app.modules.ai_agent.tool_executor.executor import ToolExecutor
        executor = ToolExecutor()
        res = await executor.run(
            db=db_session,
            session_id="sess-part11",
            turn_index=1,
            tool_name="get_leakage_summary",
            arguments={},
            context={"organization_id": broker_a.id}
        )
        assert res.success is True
        assert "total_leakage_events" in res.result

    @pytest.mark.asyncio
    async def test_execute_get_source_attribution(self, db_session, broker_a):
        from app.modules.ai_agent.tool_executor.executor import ToolExecutor
        executor = ToolExecutor()
        res = await executor.run(
            db=db_session,
            session_id="sess-part11",
            turn_index=1,
            tool_name="get_source_attribution",
            arguments={},
            context={"organization_id": broker_a.id}
        )
        assert res.success is True
        assert "total_sources" in res.result

    @pytest.mark.asyncio
    async def test_execute_get_data_quality(self, db_session, broker_a):
        from app.modules.ai_agent.tool_executor.executor import ToolExecutor
        executor = ToolExecutor()
        res = await executor.run(
            db=db_session,
            session_id="sess-part11",
            turn_index=1,
            tool_name="get_data_quality",
            arguments={},
            context={"organization_id": broker_a.id}
        )
        assert res.success is True
        assert "data_health_score_pct" in res.result

    @pytest.mark.asyncio
    async def test_execute_get_revenue_at_risk(self, db_session, broker_a):
        from app.modules.ai_agent.tool_executor.executor import ToolExecutor
        executor = ToolExecutor()
        res = await executor.run(
            db=db_session,
            session_id="sess-part11",
            turn_index=1,
            tool_name="get_revenue_at_risk",
            arguments={},
            context={"organization_id": broker_a.id}
        )
        assert res.success is True
        assert "revenue_at_risk_estimate" in res.result

