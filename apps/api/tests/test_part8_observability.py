"""
PART 8 — Enterprise Observability & Reliability Tests
=====================================================
Comprehensive tests for:
  - JSON Logger & ContextVars
  - OpenTelemetry W3C Distributed Tracer & Spans
  - Prometheus Metrics Collector (HTTP, DB, Redis, Queues, AI per Org)
  - Circuit Breaker Reliability Pattern
  - Observability Models
"""
import pytest
import json
import logging
from unittest.mock import MagicMock

from app.modules.logging.json_logger import JSONFormatter, set_trace_context, get_trace_context
from app.modules.tracing.tracer import Tracer, generate_trace_id, generate_span_id
from app.modules.metrics.prometheus_collector import PrometheusMetricsCollector
from app.modules.reliability.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
from app.models.observability_models import Incident, AlertRule, MetricSnapshot, CapacityForecast


# ─── Structured JSON Logger Tests ─────────────────────────────────────────────

def test_json_formatter_structure():
    set_trace_context(
        request_id="req-999",
        correlation_id="corr-999",
        trace_id="trc-999",
        organization_id="org-test-123",
        service="test-service",
    )

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test structured log",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["message"] == "Test structured log"
    assert data["request_id"] == "req-999"
    assert data["correlation_id"] == "corr-999"
    assert data["organization_id"] == "org-test-123"
    assert data["level"] == "INFO"


# ─── OpenTelemetry W3C Tracing Tests ──────────────────────────────────────────

def test_tracer_traceparent_parsing_and_formatting():
    valid_header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    parsed = Tracer.parse_traceparent(valid_header)

    assert parsed["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parsed["parent_span_id"] == "00f067aa0ba902b7"

    reformatted = Tracer.format_traceparent(parsed["trace_id"], "1122334455667788")
    assert reformatted == "00-4bf92f3577b34da6a3ce929d0e0e4736-1122334455667788-01"


def test_tracer_span_context_manager():
    with Tracer.start_span("unit_test_operation") as span:
        span.set_attribute("tenant", "org-alpha")
        assert span.name == "unit_test_operation"
        assert span.status == "OK"
        assert span.attributes["tenant"] == "org-alpha"


# ─── Prometheus Metrics Collector Tests ───────────────────────────────────────

def test_prometheus_metrics_export():
    collector = PrometheusMetricsCollector()

    # Record sample HTTP requests
    collector.record_http_request("GET", "/api/v1/leads", 200, 0.045)
    collector.record_http_request("POST", "/api/v1/leads", 201, 0.120)

    # Record sample DB queries
    collector.record_db_query(0.010, is_slow=False)
    collector.record_db_query(0.550, is_slow=True)

    # Record Cache & AI
    collector.record_cache_hit()
    collector.record_cache_miss()
    collector.record_ai_usage("org-enterprise-1", prompt_tokens=500, completion_tokens=150, cost_usd=0.0025)

    exported = collector.export_prometheus_text()

    assert "http_requests_total" in exported
    assert 'method="GET",path="/api/v1/leads",status="200"' in exported
    assert "db_queries_total 2" in exported
    assert "db_slow_queries_total 1" in exported
    assert "redis_cache_hits_total 1" in exported
    assert 'ai_prompt_tokens_total{organization_id="org-enterprise-1"} 500' in exported
    assert 'ai_cost_usd_total{organization_id="org-enterprise-1"} 0.002500' in exported


# ─── Circuit Breaker Reliability Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_circuit_breaker_transitions_and_fallback():
    cb = CircuitBreaker("test_cb", failure_threshold=2, recovery_time_seconds=1.0)

    async def failing_func():
        raise ValueError("Downstream service failure")

    async def fallback_func():
        return "fallback_result"

    # Call 1: fails
    with pytest.raises(ValueError):
        await cb.call(failing_func)
    assert cb.failure_count == 1
    assert cb.state == "CLOSED"

    # Call 2: fails -> trips breaker OPEN
    with pytest.raises(ValueError):
        await cb.call(failing_func)
    assert cb.state == "OPEN"

    # Call 3: rejected by OPEN breaker -> executes fallback
    result = await cb.call(failing_func, fallback=fallback_func)
    assert result == "fallback_result"


# ─── Observability Models Instantiation Tests ─────────────────────────────────

def test_observability_models_instantiation():
    inc = Incident(
        incident_number="INC-1001",
        title="High DB Latency Spike",
        severity="P1",
        status="investigating",
        service_affected="database",
    )
    assert inc.incident_number == "INC-1001"
    assert inc.severity == "P1"

    rule = AlertRule(
        name="High CPU Utilization",
        metric_name="cpu_usage_pct",
        condition=">",
        threshold=85.0,
        severity="critical",
    )
    assert rule.threshold == 85.0

    forecast = CapacityForecast(
        resource_name="db_storage",
        unit="GB",
        current_value=120.0,
        projected_30d=150.0,
        projected_90d=220.0,
        max_capacity=1000.0,
    )
    assert forecast.projected_90d == 220.0
