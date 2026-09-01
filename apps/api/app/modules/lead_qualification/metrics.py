"""
Part 21.4.1 & Part 21.4.2 — PII-Safe Lead Qualification Observability Metrics
=============================================================================
Prometheus-compatible metrics with strict tenant ID hashing and zero lead PII.
Falls back to no-op DummyMetric when prometheus_client is not installed.
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
    """Mask organization identifier with SHA-256 prefix for privacy-safe metrics."""
    if not org_id:
        return "anonymous"
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
    QUALIFICATION_SNAPSHOT_READS = Counter(
        "qualification_snapshot_reads_total",
        "Total count of lead qualification snapshot reads",
        ["org_hash", "state"],
    )

    QUALIFICATION_FACT_WRITES = Counter(
        "qualification_fact_writes_total",
        "Total count of recorded qualification facts",
        ["org_hash", "field_name", "source_type"],
    )

    QUALIFICATION_CONFLICTS_TOTAL = Counter(
        "qualification_conflicts_total",
        "Total count of detected qualification evidence conflicts",
        ["org_hash", "field_name"],
    )

    QUALIFICATION_HUMAN_OVERRIDES_TOTAL = Counter(
        "qualification_human_overrides_total",
        "Total count of authorized human qualification state overrides",
        ["org_hash", "target_state"],
    )

    QUALIFICATION_EVALUATION_LATENCY = Histogram(
        "qualification_evaluation_duration_seconds",
        "Latency of deterministic qualification policy evaluation in seconds",
        ["org_hash"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    )

    # Part 21.4.2 Fact Extraction Metrics
    QUALIFICATION_EXTRACTION_ATTEMPTS = Counter(
        "qualification_extraction_attempts_total",
        "Total attempts to extract qualification facts from conversations/messages",
        ["org_hash", "source_type"],
    )

    QUALIFICATION_EXTRACTION_SUCCESS = Counter(
        "qualification_extraction_success_total",
        "Total successful fact extractions from conversations/messages",
        ["org_hash", "source_type"],
    )

    QUALIFICATION_EXTRACTION_FAILURES = Counter(
        "qualification_extraction_failures_total",
        "Total failed or rejected fact extraction attempts",
        ["org_hash", "reason"],
    )

    QUALIFICATION_EXTRACTION_DURATION = Histogram(
        "qualification_extraction_duration_seconds",
        "Latency of qualification fact extraction pipeline in seconds",
        ["org_hash", "model_provider"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
    )

    # Part 21.4.4 Conversation Engine Metrics
    QUALIFICATION_CONVERSATIONS_STARTED = Counter(
        "qualification_conversations_started_total",
        "Total qualification conversations initiated or resumed",
        ["org_hash", "channel"],
    )

    QUALIFICATION_QUESTIONS_GENERATED = Counter(
        "qualification_questions_generated_total",
        "Total qualification questions generated via LLM or template",
        ["org_hash", "field_name", "generation_mode"],
    )

    QUALIFICATION_QUESTIONS_FALLBACK = Counter(
        "qualification_questions_fallback_total",
        "Total times deterministic template fallback was used",
        ["org_hash", "field_name", "reason"],
    )

    QUALIFICATION_RESPONSES_PROCESSED = Counter(
        "qualification_responses_processed_total",
        "Total customer qualification responses processed",
        ["org_hash", "channel"],
    )

    QUALIFICATION_HUMAN_HANDOFFS = Counter(
        "qualification_human_handoffs_total",
        "Total human handoffs triggered from qualification conversation",
        ["org_hash", "reason"],
    )

    QUALIFICATION_CONVERSATIONS_COMPLETED = Counter(
        "qualification_conversations_completed_total",
        "Total qualification conversations completed successfully",
        ["org_hash", "final_state"],
    )

    QUALIFICATION_REPEATED_QUESTIONS_PREVENTED = Counter(
        "qualification_repeated_questions_prevented_total",
        "Total duplicate or repeated questions prevented by fatigue safeguards",
        ["org_hash", "field_name"],
    )
else:
    QUALIFICATION_SNAPSHOT_READS = _DummyMetric()
    QUALIFICATION_FACT_WRITES = _DummyMetric()
    QUALIFICATION_CONFLICTS_TOTAL = _DummyMetric()
    QUALIFICATION_HUMAN_OVERRIDES_TOTAL = _DummyMetric()
    QUALIFICATION_EVALUATION_LATENCY = _DummyMetric()
    QUALIFICATION_EXTRACTION_ATTEMPTS = _DummyMetric()
    QUALIFICATION_EXTRACTION_SUCCESS = _DummyMetric()
    QUALIFICATION_EXTRACTION_FAILURES = _DummyMetric()
    QUALIFICATION_EXTRACTION_DURATION = _DummyMetric()
    QUALIFICATION_CONVERSATIONS_STARTED = _DummyMetric()
    QUALIFICATION_QUESTIONS_GENERATED = _DummyMetric()
    QUALIFICATION_QUESTIONS_FALLBACK = _DummyMetric()
    QUALIFICATION_RESPONSES_PROCESSED = _DummyMetric()
    QUALIFICATION_HUMAN_HANDOFFS = _DummyMetric()
    QUALIFICATION_CONVERSATIONS_COMPLETED = _DummyMetric()
    QUALIFICATION_REPEATED_QUESTIONS_PREVENTED = _DummyMetric()

