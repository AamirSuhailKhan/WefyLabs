"""
Volume 2 PART 2 — Enrichment Monitoring Metrics
"""
from typing import Dict, Any
from datetime import datetime, timezone


class EnrichmentMetricsCollector:
    _metrics = {
        "total_enrichments": 0,
        "successful_enrichments": 0,
        "failed_enrichments": 0,
        "total_latency_ms": 0.0,
        "total_ai_token_cost": 0.0,
        "provider_calls": 0,
        "provider_failures": 0,
        "average_confidence": 0.0,
        "average_completion_rate": 0.0,
    }

    @classmethod
    def record_enrichment(cls, latency_ms: float, confidence: float, completion_rate: float, ai_cost: float = 0.0, success: bool = True):
        cls._metrics["total_enrichments"] += 1
        if success:
            cls._metrics["successful_enrichments"] += 1
        else:
            cls._metrics["failed_enrichments"] += 1

        cls._metrics["total_latency_ms"] += latency_ms
        cls._metrics["total_ai_token_cost"] += ai_cost

        # Running average
        n = cls._metrics["total_enrichments"]
        cls._metrics["average_confidence"] = round(
            ((cls._metrics["average_confidence"] * (n - 1)) + confidence) / n, 2
        )
        cls._metrics["average_completion_rate"] = round(
            ((cls._metrics["average_completion_rate"] * (n - 1)) + completion_rate) / n, 2
        )

    @classmethod
    def record_provider_call(cls, success: bool = True):
        cls._metrics["provider_calls"] += 1
        if not success:
            cls._metrics["provider_failures"] += 1

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        total = cls._metrics["total_enrichments"]
        avg_latency = round(cls._metrics["total_latency_ms"] / total, 2) if total > 0 else 0.0
        provider_calls = cls._metrics["provider_calls"]
        provider_failure_rate = round(cls._metrics["provider_failures"] / provider_calls, 3) if provider_calls > 0 else 0.0

        return {
            "total_enrichments": total,
            "successful": cls._metrics["successful_enrichments"],
            "failed": cls._metrics["failed_enrichments"],
            "avg_latency_ms": avg_latency,
            "total_ai_token_cost": round(cls._metrics["total_ai_token_cost"], 4),
            "avg_confidence": cls._metrics["average_confidence"],
            "avg_completion_rate": cls._metrics["average_completion_rate"],
            "provider_failure_rate": provider_failure_rate,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
