"""
Part 21.6 — PII-Safe Communication Observability & Prometheus Metrics
====================================================================
Declares Prometheus counters and histograms with strict privacy guarantees:
- Organization IDs are cryptographically hashed (SHA-256, first 8 characters)
- ZERO customer phone numbers, emails, names, or message bodies are ever used as metric labels.
"""
from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)

_MASK_CACHE: dict[str, str] = {}


def mask_org_id(org_id: str) -> str:
    """Returns an 8-character cryptographic hash of the tenant ID."""
    if not org_id:
        return "unknown"
    if org_id not in _MASK_CACHE:
        _MASK_CACHE[org_id] = hashlib.sha256(str(org_id).encode("utf-8")).hexdigest()[:8]
    return _MASK_CACHE[org_id]


try:
    from prometheus_client import Counter, Histogram

    COMMUNICATION_SEND_ATTEMPT_TOTAL = Counter(
        "communication_send_attempt_total",
        "Total outbound communication delivery attempts",
        ["org_hash", "channel", "provider"],
    )

    COMMUNICATION_SEND_SUCCESS_TOTAL = Counter(
        "communication_send_success_total",
        "Total successful outbound communications dispatched to provider",
        ["org_hash", "channel", "provider"],
    )

    COMMUNICATION_SEND_FAILURE_TOTAL = Counter(
        "communication_send_failure_total",
        "Total outbound communication failures",
        ["org_hash", "channel", "provider", "error_code"],
    )

    COMMUNICATION_DELIVERY_STATUS_TOTAL = Counter(
        "communication_delivery_status_total",
        "Total communication delivery state transitions",
        ["org_hash", "channel", "status"],
    )

    COMMUNICATION_RETRY_TOTAL = Counter(
        "communication_retry_total",
        "Total communication retries scheduled",
        ["org_hash", "channel"],
    )

    COMMUNICATION_RATE_LIMIT_TOTAL = Counter(
        "communication_rate_limit_total",
        "Total provider rate limit events encountered",
        ["org_hash", "channel"],
    )

    COMMUNICATION_LATENCY_HISTOGRAM = Histogram(
        "communication_provider_latency_seconds",
        "Latency of provider API calls in seconds",
        ["org_hash", "channel"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

except Exception as e:
    logger.debug(f"[COMMUNICATION_METRICS] Prometheus fallback: {e}")

    class _DummyMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def observe(self, amount):
            pass

    COMMUNICATION_SEND_ATTEMPT_TOTAL = _DummyMetric()
    COMMUNICATION_SEND_SUCCESS_TOTAL = _DummyMetric()
    COMMUNICATION_SEND_FAILURE_TOTAL = _DummyMetric()
    COMMUNICATION_DELIVERY_STATUS_TOTAL = _DummyMetric()
    COMMUNICATION_RETRY_TOTAL = _DummyMetric()
    COMMUNICATION_RATE_LIMIT_TOTAL = _DummyMetric()
    COMMUNICATION_LATENCY_HISTOGRAM = _DummyMetric()
