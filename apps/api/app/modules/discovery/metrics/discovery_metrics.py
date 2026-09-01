"""
Part 21.2 — Discovery Prometheus Metrics
==========================================
PII-safe Prometheus metrics for AI lead discovery.
Labels use SHA-256 hashed organization IDs to prevent PII exposure and label cardinality explosion.
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


def _hash_org(org_id: str) -> str:
    return hashlib.sha256(org_id.encode()).hexdigest()[:16]


if PROMETHEUS_AVAILABLE:
    discovery_candidates_total = Counter(
        "discovery_candidates_total",
        "Total discovery candidates processed",
        ["status", "org_hash"],
    )
    discovery_runs_total = Counter(
        "discovery_runs_total",
        "Total discovery execution runs",
        ["status", "org_hash"],
    )
    discovery_duplicates_total = Counter(
        "discovery_duplicates_total",
        "Duplicates detected in discovery",
        ["match_status", "org_hash"],
    )
    discovery_relevance_histogram = Histogram(
        "discovery_relevance_score_histogram",
        "Distribution of discovery relevance scores",
        ["provider"],
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
    discovery_provider_latency = Histogram(
        "discovery_provider_latency_seconds",
        "Latency of discovery provider queries",
        ["provider"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    discovery_quota_exceeded_total = Counter(
        "discovery_quota_exceeded_total",
        "Discovery source quota limits exceeded",
        ["provider", "org_hash"],
    )
else:
    class _NoOp:
        def labels(self, **kwargs): return self
        def inc(self, amount=1): pass
        def observe(self, value): pass

    _noop = _NoOp()
    discovery_candidates_total = _noop
    discovery_runs_total = _noop
    discovery_duplicates_total = _noop
    discovery_relevance_histogram = _noop
    discovery_provider_latency = _noop
    discovery_quota_exceeded_total = _noop


def record_candidate_processed(org_id: str, status: str) -> None:
    discovery_candidates_total.labels(status=status, org_hash=_hash_org(org_id)).inc()


def record_discovery_run(org_id: str, status: str) -> None:
    discovery_runs_total.labels(status=status, org_hash=_hash_org(org_id)).inc()


def record_discovery_duplicate(org_id: str, match_status: str) -> None:
    discovery_duplicates_total.labels(match_status=match_status, org_hash=_hash_org(org_id)).inc()


def record_relevance_score(provider: str, score: float) -> None:
    discovery_relevance_histogram.labels(provider=provider).observe(score)


def record_provider_latency(provider: str, seconds: float) -> None:
    discovery_provider_latency.labels(provider=provider).observe(seconds)


def record_quota_exceeded(org_id: str, provider: str) -> None:
    discovery_quota_exceeded_total.labels(provider=provider, org_hash=_hash_org(org_id)).inc()
