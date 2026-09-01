"""
Part 21.3 — Property Recommendation Observability Metrics
===========================================================
Prometheus-compatible metrics with strict tenant ID hashing and zero lead PII.
"""
from __future__ import annotations
import hashlib
import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


def mask_org_id(org_id: str) -> str:
    """Safely hash organization/tenant ID to avoid high-cardinality PII in Prometheus."""
    if not org_id:
        return "unknown"
    return hashlib.sha256(org_id.encode("utf-8")).hexdigest()[:12]


class _DummyMetric:
    def labels(self, *args, **kwargs):
        return self

    def inc(self, amount: float = 1):
        pass

    def observe(self, amount: float):
        pass

    def set(self, amount: float):
        pass


if PROMETHEUS_AVAILABLE:
    PROPERTY_RECOMMENDATION_REQUESTS_TOTAL = Counter(
        "property_recommendation_requests_total",
        "Total AI property recommendation generation requests",
        ["org_hash", "trigger_type"]
    )

    PROPERTY_RECOMMENDATION_GENERATION_DURATION = Histogram(
        "property_recommendation_generation_duration_seconds",
        "Latency of property recommendation generation in seconds",
        ["org_hash", "scoring_version"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )

    PROPERTY_RECOMMENDATION_NO_MATCH_TOTAL = Counter(
        "property_recommendation_no_match_total",
        "Total recommendation runs yielding zero inventory matches",
        ["org_hash"]
    )

    PROPERTY_RECOMMENDATION_CACHE_HITS_TOTAL = Counter(
        "property_recommendation_cache_hits_total",
        "Total recommendation cache hits",
        ["org_hash"]
    )

    PROPERTY_RECOMMENDATION_AI_CALLS_TOTAL = Counter(
        "property_recommendation_ai_calls_total",
        "Total AI LLM / embedding inferences executed for property recommendations",
        ["org_hash", "provider"]
    )

    PROPERTY_RECOMMENDATION_ERRORS_TOTAL = Counter(
        "property_recommendation_errors_total",
        "Total errors encountered during property recommendation pipeline",
        ["org_hash", "error_type"]
    )
else:
    PROPERTY_RECOMMENDATION_REQUESTS_TOTAL = _DummyMetric()
    PROPERTY_RECOMMENDATION_GENERATION_DURATION = _DummyMetric()
    PROPERTY_RECOMMENDATION_NO_MATCH_TOTAL = _DummyMetric()
    PROPERTY_RECOMMENDATION_CACHE_HITS_TOTAL = _DummyMetric()
    PROPERTY_RECOMMENDATION_AI_CALLS_TOTAL = _DummyMetric()
    PROPERTY_RECOMMENDATION_ERRORS_TOTAL = _DummyMetric()
