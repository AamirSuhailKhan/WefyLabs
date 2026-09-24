"""
WefyLabs Task Reliability Matrix & Retry Governance
===================================================
Classifies all background workloads into explicit operational tiers:
- CRITICAL: Essential operations requiring strong delivery guarantees.
- IMPORTANT: Key CRM/intelligence jobs with moderate retry tolerance.
- BEST_EFFORT: Non-blocking analytics, briefs, and telemetry with low retry limits.

Provides deterministic exponential backoff with full jitter to avoid retry storms.
"""
import random
from enum import Enum
from typing import Dict, Any


class TaskReliabilityTier(str, Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    BEST_EFFORT = "BEST_EFFORT"


TIER_POLICIES: Dict[TaskReliabilityTier, Dict[str, Any]] = {
    TaskReliabilityTier.CRITICAL: {
        "max_retries": 7,
        "base_backoff_seconds": 10,
        "max_backoff_seconds": 600,
        "time_limit": 300,
        "soft_time_limit": 270,
        "dead_letter": True,
        "description": "Essential customer mutations, payments, lead capture, appointment confirmations",
    },
    TaskReliabilityTier.IMPORTANT: {
        "max_retries": 3,
        "base_backoff_seconds": 30,
        "max_backoff_seconds": 300,
        "time_limit": 180,
        "soft_time_limit": 150,
        "dead_letter": True,
        "description": "SLA breaches, lead decay calculation, follow-up sequencing, outbound notifications",
    },
    TaskReliabilityTier.BEST_EFFORT: {
        "max_retries": 1,
        "base_backoff_seconds": 60,
        "max_backoff_seconds": 120,
        "time_limit": 120,
        "soft_time_limit": 90,
        "dead_letter": False,
        "description": "Daily briefs, drift monitoring, memory decay, telemetry flush, non-blocking caches",
    },
}


def calculate_jittered_backoff(
    attempt: int,
    base_seconds: int = 10,
    max_seconds: int = 300
) -> float:
    """
    Computes full-jitter exponential backoff (AWS architecture standard).
    Formula: random.uniform(0, min(max_seconds, base_seconds * 2 ** attempt))
    Prevents synchronized retry spikes ("thundering herd").
    """
    exponential_cap = min(max_seconds, base_seconds * (2 ** max(0, attempt)))
    return random.uniform(base_seconds * 0.5, exponential_cap)


def get_task_policy(tier: TaskReliabilityTier) -> Dict[str, Any]:
    """Returns the operational execution policy for a given reliability tier."""
    return TIER_POLICIES.get(tier, TIER_POLICIES[TaskReliabilityTier.IMPORTANT])
