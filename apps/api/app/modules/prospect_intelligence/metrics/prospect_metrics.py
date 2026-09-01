"""
Part 21.2A — Prospect Intelligence Observability Metrics
==========================================================
Prometheus-compatible metrics with strict PII masking (hashed tenant IDs, zero lead PII).
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
    """Mask tenant organization ID"""
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


if PROMETHEUS_AVAILABLE:
    PROSPECT_INTEL_ANALYSIS_STARTED_TOTAL = Counter(
        "prospect_intelligence_analysis_started_total",
        "Total AI prospect intelligence analysis runs started",
        ["org_hash", "trigger_type"]
    )

    PROSPECT_INTEL_ANALYSIS_COMPLETED_TOTAL = Counter(
        "prospect_intelligence_analysis_completed_total",
        "Total AI prospect intelligence analysis runs completed successfully",
        ["org_hash", "sales_readiness", "model_provider"]
    )

    PROSPECT_INTEL_ANALYSIS_FAILED_TOTAL = Counter(
        "prospect_intelligence_analysis_failed_total",
        "Total AI prospect intelligence analysis runs that failed",
        ["org_hash", "error_type"]
    )

    PROSPECT_INTEL_ANALYSIS_DURATION_SECONDS = Histogram(
        "prospect_intelligence_analysis_duration_seconds",
        "Latency of prospect intelligence analysis execution in seconds",
        ["org_hash", "model_provider"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
    )

    PROSPECT_INTEL_PROPERTY_MATCHES_TOTAL = Counter(
        "prospect_intelligence_property_matches_total",
        "Total verified property inventory matches generated for prospects",
        ["org_hash"]
    )
else:
    PROSPECT_INTEL_ANALYSIS_STARTED_TOTAL = _DummyMetric()
    PROSPECT_INTEL_ANALYSIS_COMPLETED_TOTAL = _DummyMetric()
    PROSPECT_INTEL_ANALYSIS_FAILED_TOTAL = _DummyMetric()
    PROSPECT_INTEL_ANALYSIS_DURATION_SECONDS = _DummyMetric()
    PROSPECT_INTEL_PROPERTY_MATCHES_TOTAL = _DummyMetric()
