"""
Part 21.7 — Conversation Intelligence PII-Safe Prometheus Observability
========================================================================
Prometheus metrics tracking customer response intelligence, signal extraction,
objection detection, qualification updates, property match refreshes, and handoffs.

STRICT PRIVACY RULES:
1. All organization IDs MUST be masked using mask_org_id (SHA-256 8-char hash).
2. NEVER use phone numbers, emails, customer names, or message bodies in metric labels.
"""
from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)


def mask_org_id(org_id: str) -> str:
    """Returns an 8-character cryptographic hash of the organization ID."""
    if not org_id:
        return "unknown"
    return hashlib.sha256(org_id.encode("utf-8")).hexdigest()[:8]


try:
    from prometheus_client import Counter, Histogram

    RESPONSE_INTELLIGENCE_TOTAL = Counter(
        "response_intelligence_total",
        "Total customer responses processed for intelligence",
        ["org_hash", "channel", "language"],
    )

    RESPONSE_INTELLIGENCE_SUCCESS_TOTAL = Counter(
        "response_intelligence_success_total",
        "Total customer responses successfully analyzed",
        ["org_hash", "channel"],
    )

    RESPONSE_INTELLIGENCE_FAILURE_TOTAL = Counter(
        "response_intelligence_failure_total",
        "Total customer response analysis failures",
        ["org_hash", "channel", "error_type"],
    )

    INTENT_DETECTED_TOTAL = Counter(
        "intent_detected_total",
        "Total customer intents classified",
        ["org_hash", "intent_type"],
    )

    OBJECTION_DETECTED_TOTAL = Counter(
        "objection_detected_total",
        "Total objections detected",
        ["org_hash", "category", "severity"],
    )

    QUALIFICATION_UPDATE_TOTAL = Counter(
        "qualification_update_total",
        "Total qualification updates triggered from conversation intelligence",
        ["org_hash", "field_name"],
    )

    PROPERTY_MATCH_REFRESH_TOTAL = Counter(
        "property_match_refresh_total",
        "Total property match refreshes triggered by customer response changes",
        ["org_hash"],
    )

    HUMAN_HANDOFF_TOTAL = Counter(
        "human_handoff_total",
        "Total human handoff escalations triggered",
        ["org_hash", "trigger_type", "urgency"],
    )

    OPT_OUT_DETECTED_TOTAL = Counter(
        "opt_out_detected_total",
        "Total customer opt-out and stop communication events",
        ["org_hash", "channel"],
    )

    RESPONSE_GENERATION_TOTAL = Counter(
        "response_generation_total",
        "Total grounded AI draft replies generated",
        ["org_hash", "channel", "language"],
    )

    RESPONSE_GENERATION_FAILURE_TOTAL = Counter(
        "response_generation_failure_total",
        "Total grounded AI draft generation failures",
        ["org_hash", "channel"],
    )

    PROCESSING_LATENCY_HISTOGRAM = Histogram(
        "response_intelligence_latency_seconds",
        "Latency of response intelligence analysis pipeline",
        ["org_hash"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

except ImportError:
    # Graceful fallback when prometheus_client is not installed
    class _MockMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def observe(self, amount):
            pass

    _m = _MockMetric()
    RESPONSE_INTELLIGENCE_TOTAL = _m
    RESPONSE_INTELLIGENCE_SUCCESS_TOTAL = _m
    RESPONSE_INTELLIGENCE_FAILURE_TOTAL = _m
    INTENT_DETECTED_TOTAL = _m
    OBJECTION_DETECTED_TOTAL = _m
    QUALIFICATION_UPDATE_TOTAL = _m
    PROPERTY_MATCH_REFRESH_TOTAL = _m
    HUMAN_HANDOFF_TOTAL = _m
    OPT_OUT_DETECTED_TOTAL = _m
    RESPONSE_GENERATION_TOTAL = _m
    RESPONSE_GENERATION_FAILURE_TOTAL = _m
    PROCESSING_LATENCY_HISTOGRAM = _m
