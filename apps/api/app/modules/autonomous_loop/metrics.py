"""
Part 21.8 — Prometheus Metrics for the Autonomous Sales Loop
============================================================
PII-safe, tenant-hashed observability for the orchestration engine.

Rules:
  - No phone numbers, emails, or names in metric labels
  - Organization IDs are hashed (first 8 chars of SHA-256)
  - Event types are controlled taxonomy values (no customer data)
"""
import hashlib
import logging

logger = logging.getLogger(__name__)


def mask_org_id(org_id: str) -> str:
    """Returns first 8 hex chars of SHA-256 hash of org_id for PII-safe labels."""
    if not org_id:
        return "unknown"
    return hashlib.sha256(org_id.encode("utf-8")).hexdigest()[:8]


try:
    from prometheus_client import Counter, Histogram

    LOOP_EVENTS_TOTAL = Counter(
        "beetlelabs_autonomous_loop_events_total",
        "Total events received by the autonomous sales loop",
        labelnames=["event_type", "org"],
    )

    LOOP_EVENTS_PROCESSED = Counter(
        "beetlelabs_autonomous_loop_events_processed_total",
        "Events successfully processed by the autonomous sales loop",
        labelnames=["event_type", "org"],
    )

    LOOP_EVENTS_FAILED = Counter(
        "beetlelabs_autonomous_loop_events_failed_total",
        "Events that failed processing in the autonomous sales loop",
        labelnames=["event_type", "org"],
    )

    LOOP_GUARD_BLOCKS = Counter(
        "beetlelabs_autonomous_loop_guard_blocks_total",
        "Actions blocked by guard chain in the autonomous sales loop",
        labelnames=["guard_name", "org"],
    )

    LOOP_ACTIONS_DISPATCHED = Counter(
        "beetlelabs_autonomous_loop_actions_dispatched_total",
        "Sales actions dispatched by the autonomous sales loop",
        labelnames=["action_type", "provider", "org"],
    )

    LOOP_DEAD_LETTERS = Counter(
        "beetlelabs_autonomous_loop_dead_letters_total",
        "Events permanently failed and moved to dead-letter queue",
        labelnames=["org"],
    )

    LOOP_DUPLICATE_EVENTS = Counter(
        "beetlelabs_autonomous_loop_duplicate_events_total",
        "Duplicate events suppressed by idempotency enforcement",
        labelnames=["org"],
    )

    LOOP_PROCESSING_LATENCY = Histogram(
        "beetlelabs_autonomous_loop_processing_latency_seconds",
        "Processing latency of autonomous sales loop events",
        labelnames=["event_type", "org"],
        buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    )

    LOOP_STATE_TRANSITIONS = Counter(
        "beetlelabs_autonomous_loop_state_transitions_total",
        "Lead lifecycle state transitions triggered by the autonomous loop",
        labelnames=["from_state", "to_state", "org"],
    )

    LOOP_BROKER_APPROVALS_PENDING = Counter(
        "beetlelabs_autonomous_loop_broker_approvals_pending_total",
        "Actions pending broker approval",
        labelnames=["action_type", "org"],
    )

except Exception as e:
    logger.debug(f"[AUTONOMOUS_LOOP_METRICS] Prometheus fallback: {e}")

    class _DummyMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def observe(self, amount):
            pass

    LOOP_EVENTS_TOTAL = _DummyMetric()
    LOOP_EVENTS_PROCESSED = _DummyMetric()
    LOOP_EVENTS_FAILED = _DummyMetric()
    LOOP_GUARD_BLOCKS = _DummyMetric()
    LOOP_ACTIONS_DISPATCHED = _DummyMetric()
    LOOP_DEAD_LETTERS = _DummyMetric()
    LOOP_DUPLICATE_EVENTS = _DummyMetric()
    LOOP_PROCESSING_LATENCY = _DummyMetric()
    LOOP_STATE_TRANSITIONS = _DummyMetric()
    LOOP_BROKER_APPROVALS_PENDING = _DummyMetric()
