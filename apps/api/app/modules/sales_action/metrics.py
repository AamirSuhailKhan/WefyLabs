"""
Part 21.5 — Sales Action Observability Metrics
==============================================
PII-Safe Prometheus metrics tracking action proposals, approvals, blocks,
executions, follow-ups, and human handoffs.
"""
import hashlib
import logging

logger = logging.getLogger(__name__)

def mask_org_id(org_id: str) -> str:
    """Returns a deterministic, PII-safe SHA-256 8-char prefix."""
    if not org_id:
        return "unknown"
    return hashlib.sha256(org_id.encode("utf-8")).hexdigest()[:8]

try:
    from prometheus_client import Counter, Histogram

    SALES_ACTIONS_PROPOSED_TOTAL = Counter(
        "sales_actions_proposed_total",
        "Total sales actions proposed by Next Best Action engine",
        ["org_hash", "action_type"],
    )

    SALES_ACTIONS_APPROVED_TOTAL = Counter(
        "sales_actions_approved_total",
        "Total sales actions approved (automatically or manually)",
        ["org_hash", "action_type"],
    )

    SALES_ACTIONS_BLOCKED_TOTAL = Counter(
        "sales_actions_blocked_total",
        "Total sales actions blocked by compliance/guard policies",
        ["org_hash", "reason"],
    )

    SALES_ACTIONS_EXECUTED_TOTAL = Counter(
        "sales_actions_executed_total",
        "Total sales actions successfully executed/dispatched",
        ["org_hash", "action_type", "channel"],
    )

    SALES_ACTIONS_FAILED_TOTAL = Counter(
        "sales_actions_failed_total",
        "Total sales action execution failures",
        ["org_hash", "action_type", "channel", "error_type"],
    )

    SALES_ACTION_FOLLOWUPS_SENT_TOTAL = Counter(
        "sales_action_followups_sent_total",
        "Total automated follow-ups dispatched",
        ["org_hash", "channel"],
    )

    SALES_ACTION_FOLLOWUPS_BLOCKED_TOTAL = Counter(
        "sales_action_followups_blocked_total",
        "Total follow-ups blocked by quiet hours, consent, or fatigue",
        ["org_hash", "guard_type"],
    )

    SALES_ACTION_HUMAN_HANDOFFS_TOTAL = Counter(
        "sales_action_human_handoffs_total",
        "Total lead escalations to human broker review",
        ["org_hash", "handoff_reason"],
    )

    SALES_ACTION_EVALUATION_LATENCY = Histogram(
        "sales_action_evaluation_latency_seconds",
        "Latency of Next Best Action evaluations in seconds",
        ["org_hash"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )

except Exception as e:
    logger.debug(f"[SALES_ACTION_METRICS] Prometheus client init fallback: {e}")

    class _DummyMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def observe(self, amount):
            pass

    SALES_ACTIONS_PROPOSED_TOTAL = _DummyMetric()
    SALES_ACTIONS_APPROVED_TOTAL = _DummyMetric()
    SALES_ACTIONS_BLOCKED_TOTAL = _DummyMetric()
    SALES_ACTIONS_EXECUTED_TOTAL = _DummyMetric()
    SALES_ACTIONS_FAILED_TOTAL = _DummyMetric()
    SALES_ACTION_FOLLOWUPS_SENT_TOTAL = _DummyMetric()
    SALES_ACTION_FOLLOWUPS_BLOCKED_TOTAL = _DummyMetric()
    SALES_ACTION_HUMAN_HANDOFFS_TOTAL = _DummyMetric()
    SALES_ACTION_EVALUATION_LATENCY = _DummyMetric()
