"""
SLO / SLA Manager
=================
Tracks Service Level Objectives against real measured signals.

SLOs defined (consistent with Build 12 spec):
  - api_availability        : p99 ≥ 99.9%  (30-day rolling window)
  - api_p99_latency_ms      : p99 ≤ 500ms
  - ai_response_p95_ms      : p95 ≤ 3000ms
  - db_query_p99_ms         : p99 ≤ 100ms
  - queue_processing_p95_ms : p95 ≤ 5000ms
  - error_rate              : < 1% of all requests

Never fabricate SLO compliance — all values derive from recorded metrics.
"""
import time
import logging
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class SLOStatus(str, Enum):
    MEETING    = "MEETING"      # current window within budget
    AT_RISK    = "AT_RISK"      # < 20% error budget remaining
    BREACHED   = "BREACHED"     # error budget exhausted


@dataclass
class SLODefinition:
    name: str
    description: str
    target: float          # e.g. 99.9 for 99.9%
    unit: str              # "percent" | "ms" | "ratio"
    window_seconds: int    # rolling window
    breach_direction: str  # "below" means metric must stay ABOVE target; "above" means BELOW


@dataclass
class SLOWindow:
    """Rolling time-window measurement bucket."""
    slo_name: str
    samples: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, value)

    def prune(self, window_seconds: int) -> None:
        cutoff = time.time() - window_seconds
        self.samples = [(ts, v) for ts, v in self.samples if ts >= cutoff]

    def add(self, value: float) -> None:
        self.samples.append((time.time(), value))

    def values(self) -> List[float]:
        return [v for _, v in self.samples]

    def percentile(self, p: float) -> Optional[float]:
        vals = self.values()
        if not vals:
            return None
        return float(statistics.quantiles(sorted(vals), n=100)[int(p) - 1])

    def mean(self) -> Optional[float]:
        vals = self.values()
        return statistics.mean(vals) if vals else None

    def count(self) -> int:
        return len(self.samples)


# ── Canonical SLO Registry ────────────────────────────────────────────────────
WEFYLABS_SLOS: List[SLODefinition] = [
    SLODefinition(
        name="api_availability",
        description="API endpoint availability (non-5xx / total)",
        target=99.9,
        unit="percent",
        window_seconds=30 * 24 * 3600,   # 30-day
        breach_direction="below",
    ),
    SLODefinition(
        name="api_p99_latency_ms",
        description="API p99 response latency in milliseconds",
        target=500.0,
        unit="ms",
        window_seconds=3600,              # 1-hour rolling
        breach_direction="above",
    ),
    SLODefinition(
        name="ai_response_p95_ms",
        description="AI inference p95 latency in milliseconds",
        target=3000.0,
        unit="ms",
        window_seconds=3600,
        breach_direction="above",
    ),
    SLODefinition(
        name="db_query_p99_ms",
        description="Database query p99 latency in milliseconds",
        target=100.0,
        unit="ms",
        window_seconds=3600,
        breach_direction="above",
    ),
    SLODefinition(
        name="queue_processing_p95_ms",
        description="Celery task processing p95 latency in milliseconds",
        target=5000.0,
        unit="ms",
        window_seconds=3600,
        breach_direction="above",
    ),
    SLODefinition(
        name="error_rate",
        description="Fraction of requests resulting in 5xx errors",
        target=1.0,
        unit="percent",
        window_seconds=3600,
        breach_direction="above",
    ),
]


class SLOManager:
    """
    Tracks, evaluates, and reports on all WefyLabs SLOs.

    Usage:
        slo = SLOManager()
        slo.record("api_p99_latency_ms", 234.5)
        report = slo.evaluate_all()
    """

    def __init__(self):
        self._definitions: Dict[str, SLODefinition] = {s.name: s for s in WEFYLABS_SLOS}
        self._windows: Dict[str, SLOWindow] = {
            s.name: SLOWindow(slo_name=s.name) for s in WEFYLABS_SLOS
        }

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def record(self, slo_name: str, value: float) -> None:
        """Record a measurement for the named SLO."""
        if slo_name not in self._windows:
            logger.warning(f"[SLO] Unknown SLO name: {slo_name}")
            return
        defn = self._definitions[slo_name]
        self._windows[slo_name].prune(defn.window_seconds)
        self._windows[slo_name].add(value)

    def record_http_request(self, status_code: int, duration_ms: float) -> None:
        """Convenience recorder for HTTP API calls."""
        self.record("api_p99_latency_ms", duration_ms)
        # Availability: 1.0 = success, 0.0 = server error
        availability = 0.0 if status_code >= 500 else 100.0
        self.record("api_availability", availability)
        # Error rate: 1.0 = error, 0.0 = ok
        self.record("error_rate", 100.0 if status_code >= 500 else 0.0)

    def record_ai_request(self, duration_ms: float) -> None:
        self.record("ai_response_p95_ms", duration_ms)

    def record_db_query(self, duration_ms: float) -> None:
        self.record("db_query_p99_ms", duration_ms)

    def record_queue_job(self, duration_ms: float) -> None:
        self.record("queue_processing_p95_ms", duration_ms)

    # ── Evaluation ────────────────────────────────────────────────────────────

    def _compute_current_value(self, slo_name: str) -> Optional[float]:
        """Compute current representative metric value for an SLO."""
        window = self._windows[slo_name]
        defn = self._definitions[slo_name]
        window.prune(defn.window_seconds)
        vals = window.values()
        if not vals:
            return None

        if slo_name == "api_availability":
            return statistics.mean(vals)  # mean availability %
        if slo_name == "api_p99_latency_ms":
            return float(statistics.quantiles(sorted(vals), n=100)[98])
        if slo_name == "ai_response_p95_ms":
            return float(statistics.quantiles(sorted(vals), n=100)[94])
        if slo_name == "db_query_p99_ms":
            return float(statistics.quantiles(sorted(vals), n=100)[98])
        if slo_name == "queue_processing_p95_ms":
            return float(statistics.quantiles(sorted(vals), n=100)[94])
        if slo_name == "error_rate":
            return statistics.mean(vals)
        return statistics.mean(vals)

    def evaluate(self, slo_name: str) -> Dict:
        """Evaluate a single SLO and return detailed status dict."""
        if slo_name not in self._definitions:
            return {"error": f"Unknown SLO: {slo_name}"}

        defn = self._definitions[slo_name]
        current = self._compute_current_value(slo_name)
        sample_count = self._windows[slo_name].count()

        if current is None:
            return {
                "slo": slo_name,
                "status": "NO_DATA",
                "target": defn.target,
                "current": None,
                "sample_count": 0,
                "unit": defn.unit,
            }

        # Determine compliance
        if defn.breach_direction == "above":
            # metric must stay BELOW target (e.g. latency, error_rate)
            compliant = current <= defn.target
            error_budget_remaining = max(0.0, ((defn.target - current) / defn.target) * 100)
        else:
            # metric must stay ABOVE target (e.g. availability)
            compliant = current >= defn.target
            error_budget_remaining = max(0.0, ((current - (100 - defn.target)) / (100 - defn.target)) * 100) if defn.target < 100 else 100.0

        if compliant:
            status = SLOStatus.MEETING if error_budget_remaining > 20 else SLOStatus.AT_RISK
        else:
            status = SLOStatus.BREACHED

        return {
            "slo": slo_name,
            "description": defn.description,
            "status": status.value,
            "target": defn.target,
            "current": round(current, 3),
            "unit": defn.unit,
            "error_budget_remaining_pct": round(error_budget_remaining, 2),
            "sample_count": sample_count,
            "window_seconds": defn.window_seconds,
            "compliant": compliant,
        }

    def evaluate_all(self) -> Dict:
        """Evaluate all SLOs and return aggregate report."""
        results = {name: self.evaluate(name) for name in self._definitions}
        breached = [n for n, r in results.items() if r.get("status") == SLOStatus.BREACHED]
        at_risk  = [n for n, r in results.items() if r.get("status") == SLOStatus.AT_RISK]
        meeting  = [n for n, r in results.items() if r.get("status") == SLOStatus.MEETING]
        no_data  = [n for n, r in results.items() if r.get("status") == "NO_DATA"]

        overall = "GREEN"
        if breached:
            overall = "RED"
        elif at_risk:
            overall = "YELLOW"

        return {
            "overall_status": overall,
            "summary": {
                "total": len(self._definitions),
                "meeting": len(meeting),
                "at_risk": len(at_risk),
                "breached": len(breached),
                "no_data": len(no_data),
            },
            "breached": breached,
            "at_risk": at_risk,
            "slos": results,
        }


# Global singleton
slo_manager = SLOManager()
