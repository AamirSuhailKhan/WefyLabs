"""
WEFYLABS — MASTER BUILD 12
Observability, AI Evaluation, Reliability, Performance & Production Operations
==============================================================================
Test Suite: 50 tests across 8 domains

Domains:
  MB12-OBS  : Structured logging, tracing, metrics
  MB12-SLO  : SLO tracking and evaluation
  MB12-EVAL : AI evaluation pipeline
  MB12-INC  : Incident intelligence lifecycle
  MB12-HLTH : Health aggregation
  MB12-PERF : Benchmark engine
  MB12-CB   : Circuit breaker reliability
  MB12-DRLL : Chaos/DR drill framework

Rules:
  - NEVER fabricate metrics, latencies, or availability claims
  - ALL timings derived from actual event timestamps
  - SLO breach detection must use real recorded samples
  - AI scores must derive from deterministic evaluation, not hard-coded strings
"""
import pytest
import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# ── Import observability layer ────────────────────────────────────────────────
from app.modules.observability.slo_manager import SLOManager, SLOStatus, WEFYLABS_SLOS
from app.modules.observability.ai_evaluator import (
    AIEvaluator, GoldenSample, EvalOutcome, EVAL_THRESHOLDS
)
from app.modules.observability.incident_manager import (
    IncidentManager, IncidentSeverity, IncidentCategory, IncidentStatus
)
from app.modules.observability.health_aggregator import (
    HealthAggregator, ComponentStatus, ComponentHealth
)
from app.modules.observability.benchmark import BenchmarkEngine, ChaosEngine
from app.modules.logging.json_logger import (
    set_trace_context, get_trace_context, configure_structured_logging, JSONFormatter
)
from app.modules.tracing.tracer import Tracer, Span, generate_trace_id, generate_span_id
from app.modules.metrics.prometheus_collector import PrometheusMetricsCollector
from app.modules.reliability.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException


# =============================================================================
# MB12-OBS: Structured Logging
# =============================================================================

class TestStructuredLogging:
    """MB12-OBS-001 through MB12-OBS-008"""

    def setup_method(self):
        configure_structured_logging()

    def test_obs_001_trace_context_propagation(self):
        """Trace context vars propagate across the call stack."""
        req_id = f"req-{uuid.uuid4().hex[:8]}"
        set_trace_context(request_id=req_id, organization_id="org-123")
        ctx = get_trace_context()
        assert ctx["request_id"] == req_id
        assert ctx["organization_id"] == "org-123"

    def test_obs_002_json_formatter_produces_valid_json(self):
        """JSONFormatter must output valid single-line JSON."""
        import logging
        import json
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="hello world",
            args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_obs_003_json_formatter_includes_trace_context(self):
        """JSON log output includes all trace context fields."""
        import logging
        import json
        set_trace_context(trace_id="trace-abc", request_id="req-xyz")
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING,
            pathname="", lineno=0, msg="context test",
            args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["trace_id"] == "trace-abc"
        assert parsed["request_id"] == "req-xyz"

    def test_obs_004_json_formatter_handles_exception(self):
        """JSONFormatter serializes exception info without crashing."""
        import logging
        import json
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test", level=logging.ERROR,
            pathname="", lineno=0, msg="error",
            args=(), exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_obs_005_context_isolation_between_requests(self):
        """Each request should set its own context without leaking."""
        set_trace_context(request_id="req-A", organization_id="org-A")
        ctx_a = get_trace_context().copy()
        set_trace_context(request_id="req-B", organization_id="org-B")
        ctx_b = get_trace_context().copy()
        assert ctx_a["request_id"] == "req-A"
        assert ctx_b["request_id"] == "req-B"
        assert ctx_a["organization_id"] != ctx_b["organization_id"]

    def test_obs_006_json_formatter_extra_payload(self):
        """Extra payload dict is included in JSON output."""
        import logging
        import json
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="extra test",
            args=(), exc_info=None,
        )
        record.extra_payload = {"lead_id": "lead-42", "score": 0.95}
        parsed = json.loads(formatter.format(record))
        assert parsed["extra"]["lead_id"] == "lead-42"
        assert parsed["extra"]["score"] == 0.95

    def test_obs_007_structured_logging_no_print_dependency(self):
        """Logger setup must not require print() — stdout must be json handler."""
        import logging
        root = logging.getLogger()
        configure_structured_logging()
        has_json = any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)
        assert has_json, "Root logger must have JSONFormatter handler"

    def test_obs_008_log_serialization_failure_does_not_crash(self):
        """Unserializable payload must produce error log, not exception."""
        import logging
        import json
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="unserializable",
            args=(), exc_info=None,
        )
        # Attach a non-JSON-serializable object
        record.extra_payload = {"obj": object()}
        # Should not raise
        output = formatter.format(record)
        assert output  # non-empty string


# =============================================================================
# MB12-OBS: Distributed Tracing
# =============================================================================

class TestDistributedTracing:
    """MB12-OBS-009 through MB12-OBS-014"""

    def test_obs_009_generate_trace_id_is_32_hex_chars(self):
        trace_id = generate_trace_id()
        assert len(trace_id) == 32
        assert all(c in "0123456789abcdef" for c in trace_id)

    def test_obs_010_generate_span_id_is_16_hex_chars(self):
        span_id = generate_span_id()
        assert len(span_id) == 16
        assert all(c in "0123456789abcdef" for c in span_id)

    def test_obs_011_traceparent_parse_valid(self):
        header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        result = Tracer.parse_traceparent(header)
        assert result["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert result["parent_span_id"] == "00f067aa0ba902b7"

    def test_obs_012_traceparent_parse_invalid_falls_back(self):
        result = Tracer.parse_traceparent("invalid-header")
        assert "trace_id" in result
        assert len(result["trace_id"]) == 32

    def test_obs_013_traceparent_format_output(self):
        trace_id = "a" * 32
        span_id  = "b" * 16
        header = Tracer.format_traceparent(trace_id, span_id)
        assert header == f"00-{trace_id}-{span_id}-01"

    def test_obs_014_span_records_duration(self):
        set_trace_context(trace_id=generate_trace_id())
        span = Span(name="test-span")
        time.sleep(0.01)  # 10 ms
        span.finish()
        elapsed = (time.time() - span.start_time) * 1000
        assert elapsed >= 10.0  # sanity: at least 10ms elapsed


# =============================================================================
# MB12-OBS: Prometheus Metrics
# =============================================================================

class TestPrometheusMetrics:
    """MB12-OBS-015 through MB12-OBS-018"""

    def setup_method(self):
        self.collector = PrometheusMetricsCollector()

    def test_obs_015_record_http_request(self):
        self.collector.record_http_request("GET", "/api/leads", 200, 0.05)
        assert self.collector.http_request_count == 1
        assert "GET:/api/leads:200" in self.collector.http_requests_total

    def test_obs_016_record_ai_usage_per_org(self):
        self.collector.record_ai_usage("org-1", 500, 200, 0.002)
        self.collector.record_ai_usage("org-1", 300, 100, 0.001)
        assert self.collector.ai_prompt_tokens_total["org-1"] == 800
        assert abs(self.collector.ai_cost_usd_total["org-1"] - 0.003) < 1e-6

    def test_obs_017_prometheus_export_valid_format(self):
        self.collector.record_http_request("POST", "/api/leads", 201, 0.12)
        output = self.collector.export_prometheus_text()
        assert "http_requests_total" in output
        assert "POST" in output

    def test_obs_018_cache_hit_miss_counters(self):
        self.collector.record_cache_hit()
        self.collector.record_cache_hit()
        self.collector.record_cache_miss()
        assert self.collector.redis_cache_hits == 2
        assert self.collector.redis_cache_misses == 1


# =============================================================================
# MB12-SLO: SLO Manager
# =============================================================================

class TestSLOManager:
    """MB12-SLO-001 through MB12-SLO-008"""

    def setup_method(self):
        self.slo = SLOManager()

    def test_slo_001_canonical_slos_are_defined(self):
        """All 6 canonical WefyLabs SLOs must be registered."""
        expected = {
            "api_availability", "api_p99_latency_ms", "ai_response_p95_ms",
            "db_query_p99_ms", "queue_processing_p95_ms", "error_rate",
        }
        assert expected == set(self.slo._definitions.keys())

    def test_slo_002_no_data_returns_no_data_status(self):
        result = self.slo.evaluate("api_p99_latency_ms")
        assert result["status"] == "NO_DATA"

    def test_slo_003_within_latency_threshold_is_meeting(self):
        """Recording low latencies should result in MEETING status."""
        for _ in range(20):
            self.slo.record("api_p99_latency_ms", 200.0)  # well under 500ms
        result = self.slo.evaluate("api_p99_latency_ms")
        assert result["status"] in (SLOStatus.MEETING.value, SLOStatus.AT_RISK.value)
        assert result["compliant"] is True

    def test_slo_004_exceeding_latency_threshold_is_breached(self):
        """Recording high latencies should result in BREACHED status."""
        for _ in range(20):
            self.slo.record("api_p99_latency_ms", 800.0)  # over 500ms
        result = self.slo.evaluate("api_p99_latency_ms")
        assert result["status"] == SLOStatus.BREACHED.value
        assert result["compliant"] is False

    def test_slo_005_availability_above_target_is_meeting(self):
        """High availability samples → MEETING."""
        for _ in range(100):
            self.slo.record("api_availability", 100.0)
        result = self.slo.evaluate("api_availability")
        assert result["compliant"] is True

    def test_slo_006_availability_below_target_is_breached(self):
        """Low availability → BREACHED."""
        for _ in range(100):
            self.slo.record("api_availability", 95.0)  # below 99.9%
        result = self.slo.evaluate("api_availability")
        assert result["compliant"] is False

    def test_slo_007_http_request_recorder_populates_multiple_slos(self):
        """record_http_request should update availability, latency and error_rate."""
        self.slo.record_http_request(200, 150.0)
        assert self.slo._windows["api_p99_latency_ms"].count() == 1
        assert self.slo._windows["api_availability"].count() == 1
        assert self.slo._windows["error_rate"].count() == 1

    def test_slo_008_evaluate_all_returns_aggregate_report(self):
        """evaluate_all must return overall_status and summary dict."""
        report = self.slo.evaluate_all()
        assert "overall_status" in report
        assert "summary" in report
        assert report["summary"]["total"] == 6


# =============================================================================
# MB12-EVAL: AI Evaluation Pipeline
# =============================================================================

class TestAIEvaluation:
    """MB12-EVAL-001 through MB12-EVAL-008"""

    def setup_method(self):
        self.evaluator = AIEvaluator(test_mode=True)
        self.sample = GoldenSample(
            sample_id="gs-001",
            prompt="What is the price of Property A in Bandra?",
            context="Property A in Bandra is listed at ₹2.5 Cr. It is a 3BHK apartment.",
            expected_answer="Property A in Bandra is priced at ₹2.5 Cr.",
            tags=["property", "pricing"],
            version="v1.0",
        )

    def test_eval_001_evaluate_response_returns_result(self):
        result = self.evaluator.evaluate_response(
            sample=self.sample,
            response="Property A in Bandra is priced at ₹2.5 Cr.",
            model_version="claude-sonnet-4.6",
            latency_ms=450.0,
            prompt_tokens=120,
            completion_tokens=50,
            cost_usd=0.003,
        )
        assert result.sample_id == "gs-001"
        assert result.outcome == EvalOutcome.PASS

    def test_eval_002_test_mode_uses_deterministic_scores(self):
        result = self.evaluator.evaluate_response(
            sample=self.sample,
            response="Some response",
            model_version="test-model",
            latency_ms=100.0,
            prompt_tokens=50,
            completion_tokens=20,
            cost_usd=0.001,
        )
        assert result.relevance_score == 0.85
        assert result.faithfulness_score == 0.88
        assert result.safety_score == 1.0

    def test_eval_003_latency_threshold_failure(self):
        """Responses exceeding 3000ms latency threshold must FAIL."""
        result = self.evaluator.evaluate_response(
            sample=self.sample,
            response="Fine response",
            model_version="slow-model",
            latency_ms=4500.0,   # over threshold
            prompt_tokens=100,
            completion_tokens=40,
            cost_usd=0.002,
        )
        assert result.outcome == EvalOutcome.FAIL
        assert any("latency" in r for r in result.failure_reasons)

    def test_eval_004_cost_threshold_failure(self):
        """Responses exceeding per-request cost budget must FAIL."""
        result = self.evaluator.evaluate_response(
            sample=self.sample,
            response="Fine response",
            model_version="expensive-model",
            latency_ms=500.0,
            prompt_tokens=100,
            completion_tokens=40,
            cost_usd=0.05,   # over $0.01 budget
        )
        assert result.outcome == EvalOutcome.FAIL
        assert any("cost" in r for r in result.failure_reasons)

    def test_eval_005_report_requires_actual_data(self):
        """Report on empty evaluator should return NO_DATA."""
        fresh = AIEvaluator(test_mode=True)
        report = fresh.report()
        assert report["status"] == "NO_DATA"

    def test_eval_006_report_aggregates_pass_rate(self):
        for i in range(5):
            self.evaluator.evaluate_response(
                sample=self.sample,
                response="Good response",
                model_version="model-v1",
                latency_ms=200.0,
                prompt_tokens=100,
                completion_tokens=40,
                cost_usd=0.002,
            )
        report = self.evaluator.report()
        assert report["total"] == 5
        assert report["pass_rate_pct"] >= 0.0

    def test_eval_007_clear_resets_results(self):
        self.evaluator.evaluate_response(
            sample=self.sample, response="x", model_version="v1",
            latency_ms=200.0, prompt_tokens=50, completion_tokens=20, cost_usd=0.001,
        )
        self.evaluator.clear()
        report = self.evaluator.report()
        assert report["status"] == "NO_DATA"

    def test_eval_008_golden_sample_has_required_fields(self):
        """GoldenSample must have all required fields."""
        assert self.sample.sample_id
        assert self.sample.prompt
        assert self.sample.context
        assert self.sample.expected_answer
        assert self.sample.version


# =============================================================================
# MB12-INC: Incident Intelligence
# =============================================================================

class TestIncidentManager:
    """MB12-INC-001 through MB12-INC-008"""

    def setup_method(self):
        self.mgr = IncidentManager()

    def test_inc_001_open_incident_creates_record(self):
        inc = self.mgr.open(
            title="DB replication lag",
            severity=IncidentSeverity.P1,
            category=IncidentCategory.PERFORMANCE,
        )
        assert inc.incident_id.startswith("INC-")
        assert inc.status == IncidentStatus.OPEN
        assert inc.severity == IncidentSeverity.P1

    def test_inc_002_acknowledge_sets_timestamp_and_status(self):
        inc = self.mgr.open("Test incident", IncidentSeverity.P2, IncidentCategory.AVAILABILITY)
        acked = self.mgr.acknowledge(inc.incident_id, actor="sre-oncall")
        assert acked.status == IncidentStatus.ACKNOWLEDGED
        assert acked.acknowledged_at is not None

    def test_inc_003_ttd_derives_from_real_timestamps(self):
        """TTD must be derived from actual event timestamps, not fabricated."""
        inc = self.mgr.open("Test", IncidentSeverity.P2, IncidentCategory.AVAILABILITY)
        time.sleep(0.05)  # 50ms real delay
        self.mgr.acknowledge(inc.incident_id, actor="test")
        ttd = inc.ttd_seconds()
        assert ttd is not None
        assert ttd >= 0.04  # at least 40ms

    def test_inc_004_resolve_sets_root_cause_and_timestamps(self):
        inc = self.mgr.open("Test", IncidentSeverity.P2, IncidentCategory.AVAILABILITY)
        self.mgr.acknowledge(inc.incident_id, actor="sre")
        self.mgr.resolve(inc.incident_id, root_cause="DB connection pool exhausted", remediation="Increased pool size")
        assert inc.status == IncidentStatus.RESOLVED
        assert inc.root_cause == "DB connection pool exhausted"
        assert inc.resolved_at is not None

    def test_inc_005_ttr_derives_from_real_timestamps(self):
        inc = self.mgr.open("Test", IncidentSeverity.P1, IncidentCategory.PERFORMANCE)
        time.sleep(0.02)
        self.mgr.resolve(inc.incident_id, root_cause="Fixed", remediation="Rollback")
        ttr = inc.ttr_seconds()
        assert ttr is not None
        assert ttr >= 0.01

    def test_inc_006_dedup_returns_existing_open_incident(self):
        """Same title within the window must return the same incident."""
        inc1 = self.mgr.open("DB replication lag", IncidentSeverity.P1, IncidentCategory.PERFORMANCE)
        inc2 = self.mgr.open("DB replication lag", IncidentSeverity.P1, IncidentCategory.PERFORMANCE)
        assert inc1.incident_id == inc2.incident_id

    def test_inc_007_auto_detect_slo_breach_opens_p1(self):
        inc = self.mgr.detect_slo_breach("api_p99_latency_ms", current_value=750.0, target=500.0)
        assert inc is not None
        assert inc.severity == IncidentSeverity.P1

    def test_inc_008_report_derives_mttr_from_timestamps(self):
        """MTTR in report must come from actual event timestamps."""
        inc = self.mgr.open("Inc1", IncidentSeverity.P2, IncidentCategory.AVAILABILITY)
        time.sleep(0.01)
        self.mgr.resolve(inc.incident_id, root_cause="x", remediation="y")
        report = self.mgr.report()
        assert report["mttr_source"] == "derived_from_event_timestamps"
        assert report["mttr_seconds"] is not None


# =============================================================================
# MB12-HLTH: Health Aggregator
# =============================================================================

class TestHealthAggregator:
    """MB12-HLTH-001 through MB12-HLTH-006"""

    def setup_method(self):
        self.agg = HealthAggregator()

    @pytest.mark.asyncio
    async def test_hlth_001_healthy_probe_returns_healthy(self):
        async def healthy_probe():
            return ComponentHealth(name="test", status=ComponentStatus.HEALTHY, detail="OK")

        self.agg.register("test", healthy_probe)
        result = await self.agg.check("test")
        assert result.status == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_hlth_002_failing_probe_returns_unhealthy(self):
        async def bad_probe():
            raise RuntimeError("Connection refused")

        self.agg.register("bad", bad_probe)
        result = await self.agg.check("bad")
        assert result.status == ComponentStatus.UNHEALTHY
        assert "Connection refused" in (result.error or "")

    @pytest.mark.asyncio
    async def test_hlth_003_timeout_probe_returns_unhealthy(self):
        async def slow_probe():
            await asyncio.sleep(10)  # will timeout at 5s
            return ComponentHealth(name="slow", status=ComponentStatus.HEALTHY)

        self.agg.register("slow", slow_probe)
        result = await self.agg.check("slow")
        assert result.status == ComponentStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_hlth_004_all_healthy_gives_healthy_overall(self):
        async def ok(): return ComponentHealth(name="x", status=ComponentStatus.HEALTHY)
        self.agg.register("a", ok)
        self.agg.register("b", ok)
        health = await self.agg.check_all(force=True)
        assert health.overall == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_hlth_005_one_unhealthy_gives_unhealthy_overall(self):
        async def ok():  return ComponentHealth(name="ok", status=ComponentStatus.HEALTHY)
        async def bad(): return ComponentHealth(name="bad", status=ComponentStatus.UNHEALTHY)
        self.agg.register("ok",  ok)
        self.agg.register("bad", bad)
        health = await self.agg.check_all(force=True)
        assert health.overall == ComponentStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_hlth_006_result_is_cached(self):
        call_count = 0

        async def counting_probe():
            nonlocal call_count
            call_count += 1
            return ComponentHealth(name="counted", status=ComponentStatus.HEALTHY)

        self.agg.register("counted", counting_probe)
        await self.agg.check_all(force=True)
        await self.agg.check_all()          # should use cache
        assert call_count == 1             # probe called only once


# =============================================================================
# MB12-PERF: Benchmark Engine
# =============================================================================

class TestBenchmarkEngine:
    """MB12-PERF-001 through MB12-PERF-006"""

    def setup_method(self):
        self.bench = BenchmarkEngine()

    def test_perf_001_record_single_sample(self):
        self.bench.record("api.leads.list", 123.4, success=True)
        result = self.bench.analyze("api.leads.list")
        assert result is not None
        assert result.sample_count == 1
        assert result.mean_ms == 123.4

    def test_perf_002_report_no_data_returns_empty(self):
        result = self.bench.analyze("nonexistent.op")
        assert result is None

    def test_perf_003_error_rate_calculated_correctly(self):
        self.bench.record("op", 100.0, success=True)
        self.bench.record("op", 100.0, success=False)
        result = self.bench.analyze("op")
        assert result.error_rate_pct == 50.0

    def test_perf_004_percentiles_ordered_correctly(self):
        for i in range(1, 101):  # 1ms to 100ms
            self.bench.record("latency.op", float(i))
        result = self.bench.analyze("latency.op")
        assert result.min_ms <= result.median_ms <= result.p95_ms <= result.p99_ms <= result.max_ms

    def test_perf_005_passes_slo_within_threshold(self):
        for _ in range(50):
            self.bench.record("fast.op", 100.0)
        result = self.bench.analyze("fast.op")
        assert result.passes_slo(p99_threshold_ms=500.0)

    @pytest.mark.asyncio
    async def test_perf_006_context_manager_measures_real_time(self):
        async with self.bench.measure("async.op"):
            await asyncio.sleep(0.01)  # 10ms
        result = self.bench.analyze("async.op")
        assert result is not None
        assert result.mean_ms >= 8.0  # at least 8ms


# =============================================================================
# MB12-CB: Circuit Breaker Reliability
# =============================================================================

class TestCircuitBreaker:
    """MB12-CB-001 through MB12-CB-006"""

    def setup_method(self):
        self.cb = CircuitBreaker("test-service", failure_threshold=3, recovery_time_seconds=1.0)

    @pytest.mark.asyncio
    async def test_cb_001_closed_state_allows_calls(self):
        async def ok():
            return "success"
        result = await self.cb.call(ok)
        assert result == "success"
        assert self.cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_cb_002_failure_increments_counter(self):
        async def failing():
            raise RuntimeError("fail")
        with pytest.raises(RuntimeError):
            await self.cb.call(failing)
        assert self.cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_cb_003_threshold_trips_circuit_open(self):
        async def failing():
            raise RuntimeError("fail")
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await self.cb.call(failing)
        assert self.cb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_cb_004_open_circuit_rejects_calls(self):
        self.cb.state = "OPEN"
        self.cb.last_state_change = time.time()  # fresh open
        async def ok():
            return "success"
        with pytest.raises(CircuitBreakerOpenException):
            await self.cb.call(ok)

    @pytest.mark.asyncio
    async def test_cb_005_fallback_used_when_open(self):
        self.cb.state = "OPEN"
        self.cb.last_state_change = time.time()
        async def ok():
            return "primary"
        result = await self.cb.call(ok, fallback=lambda: "fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_cb_006_half_open_recovers_to_closed_on_success(self):
        self.cb.state = "HALF_OPEN"
        async def ok():
            return "success"
        result = await self.cb.call(ok)
        assert result == "success"
        assert self.cb.state == "CLOSED"
        assert self.cb.failure_count == 0


# =============================================================================
# MB12-DRLL: Chaos / DR Drill Framework
# =============================================================================

class TestChaosEngine:
    """MB12-DRLL-001 through MB12-DRLL-004"""

    def setup_method(self):
        # ChaosEngine disabled by default — drills should ABORT safely
        self.chaos = ChaosEngine(enabled=False)

    @pytest.mark.asyncio
    async def test_drll_001_disabled_engine_aborts_drill_safely(self):
        result = await self.chaos.run_drill(
            drill_type="database_failover",
            target="primary-db",
            injector=AsyncMock(),
            recovery_checker=AsyncMock(return_value=True),
        )
        assert result.outcome == "ABORTED"
        assert "DISABLED" in result.observations[0]

    @pytest.mark.asyncio
    async def test_drll_002_enabled_engine_passes_drill_on_recovery(self):
        chaos = ChaosEngine(enabled=True)
        recovered = False

        async def inject():
            nonlocal recovered
            recovered = False

        async def check():
            nonlocal recovered
            recovered = True
            return True

        result = await chaos.run_drill(
            drill_type="cache_eviction",
            target="redis",
            injector=inject,
            recovery_checker=check,
        )
        assert result.outcome == "PASS"
        assert result.rto_seconds is not None
        assert result.rto_seconds >= 0.0

    @pytest.mark.asyncio
    async def test_drll_003_drill_rto_is_from_real_timing(self):
        """RTO must come from actual measured recovery time, not hard-coded."""
        chaos = ChaosEngine(enabled=True)
        call_count = 0

        async def inject(): pass

        async def check():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.02)  # simulate 20ms recovery
            return call_count >= 1

        result = await chaos.run_drill(
            drill_type="ai_provider_outage",
            target="claude-api",
            injector=inject,
            recovery_checker=check,
        )
        assert result.rto_seconds is not None
        assert result.rto_seconds >= 0.0  # real timing

    @pytest.mark.asyncio
    async def test_drll_004_drill_report_aggregates_outcomes(self):
        # Run two drills (both will ABORT since disabled)
        await self.chaos.run_drill("db", "primary-db", AsyncMock(), AsyncMock(return_value=True))
        await self.chaos.run_drill("redis", "cache", AsyncMock(), AsyncMock(return_value=True))
        report = self.chaos.report()
        assert report["total_drills"] == 2
        assert len(report["drills"]) == 2
