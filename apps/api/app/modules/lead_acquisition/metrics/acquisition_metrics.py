"""
Part 21.1 — Acquisition Prometheus Metrics
============================================
Organization-safe Prometheus counters and histograms for lead acquisition.

Metrics:
  lead_acquisition_received_total      - All incoming events (by source/channel/org)
  lead_acquisition_success_total       - Successfully created prospects
  lead_acquisition_failed_total        - Failed processing (by error_type)
  lead_prospect_total                  - Prospect lifecycle transitions
  lead_duplicate_total                 - Duplicate detections
  lead_import_total                    - Prospects imported as CRM leads
  lead_rejected_total                  - Rejected prospects
  lead_source_latency_seconds          - Acquisition pipeline latency
  webhook_failure_total                - Webhook validation failures
  acquisition_quality_score_histogram  - Distribution of quality scores

Security: NEVER include PII in metric labels.
          org_id is HASHED before use as label to prevent label cardinality explosions.
"""
from __future__ import annotations
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.debug("[METRICS] prometheus_client not available — metrics are no-ops")


def _hash_org(org_id: str) -> str:
    """Hash org_id for use as label — prevents PII exposure in metric labels."""
    return hashlib.sha256(org_id.encode()).hexdigest()[:16]


if PROMETHEUS_AVAILABLE:
    lead_acquisition_received_total = Counter(
        "lead_acquisition_received_total",
        "Total acquisition events received",
        ["channel", "provider", "org_hash"],
    )
    lead_acquisition_success_total = Counter(
        "lead_acquisition_success_total",
        "Successfully processed acquisition events",
        ["channel", "org_hash"],
    )
    lead_acquisition_failed_total = Counter(
        "lead_acquisition_failed_total",
        "Failed acquisition event processing",
        ["channel", "error_type", "org_hash"],
    )
    lead_prospect_created_total = Counter(
        "lead_prospect_total",
        "Lead prospects created or updated",
        ["status", "org_hash"],
    )
    lead_duplicate_total = Counter(
        "lead_duplicate_total",
        "Duplicate detections during acquisition",
        ["match_status", "org_hash"],
    )
    lead_import_total = Counter(
        "lead_import_total",
        "Prospects imported as canonical CRM leads",
        ["org_hash"],
    )
    lead_rejected_total = Counter(
        "lead_rejected_total",
        "Prospects rejected during acquisition",
        ["reason", "org_hash"],
    )
    lead_source_latency_seconds = Histogram(
        "lead_source_latency_seconds",
        "Acquisition pipeline processing latency in seconds",
        ["channel"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    webhook_failure_total = Counter(
        "webhook_failure_total",
        "Webhook validation failures",
        ["provider", "failure_type"],
    )
    acquisition_quality_score_histogram = Histogram(
        "acquisition_quality_score_histogram",
        "Distribution of acquisition quality scores",
        ["channel"],
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
else:
    # No-op fallbacks
    class _NoOp:
        def labels(self, **kwargs): return self
        def inc(self, amount=1): pass
        def observe(self, value): pass

    _noop = _NoOp()
    lead_acquisition_received_total = _noop
    lead_acquisition_success_total = _noop
    lead_acquisition_failed_total = _noop
    lead_prospect_created_total = _noop
    lead_duplicate_total = _noop
    lead_import_total = _noop
    lead_rejected_total = _noop
    lead_source_latency_seconds = _noop
    webhook_failure_total = _noop
    acquisition_quality_score_histogram = _noop


# ── Helper functions ──────────────────────────────────────────────────────────

def record_acquisition_received(org_id: str, channel: str, provider: str = "unknown") -> None:
    org_hash = _hash_org(org_id)
    lead_acquisition_received_total.labels(
        channel=channel, provider=provider, org_hash=org_hash
    ).inc()


def record_acquisition_success(org_id: str, channel: str) -> None:
    org_hash = _hash_org(org_id)
    lead_acquisition_success_total.labels(channel=channel, org_hash=org_hash).inc()


def record_acquisition_failure(org_id: str, channel: str, error_type: str) -> None:
    org_hash = _hash_org(org_id)
    lead_acquisition_failed_total.labels(
        channel=channel, error_type=error_type, org_hash=org_hash
    ).inc()


def record_prospect_created(org_id: str, status: str) -> None:
    org_hash = _hash_org(org_id)
    lead_prospect_created_total.labels(status=status, org_hash=org_hash).inc()


def record_duplicate(org_id: str, match_status: str) -> None:
    org_hash = _hash_org(org_id)
    lead_duplicate_total.labels(match_status=match_status, org_hash=org_hash).inc()


def record_import(org_id: str) -> None:
    lead_import_total.labels(org_hash=_hash_org(org_id)).inc()


def record_rejected(org_id: str, reason: str) -> None:
    reason_short = reason[:30] if reason else "unknown"
    lead_rejected_total.labels(reason=reason_short, org_hash=_hash_org(org_id)).inc()


def record_webhook_failure(provider: str, failure_type: str) -> None:
    webhook_failure_total.labels(provider=provider, failure_type=failure_type).inc()


def record_quality_score(channel: str, score: float) -> None:
    acquisition_quality_score_histogram.labels(channel=channel).observe(score)


def record_latency(channel: str, seconds: float) -> None:
    lead_source_latency_seconds.labels(channel=channel).observe(seconds)
