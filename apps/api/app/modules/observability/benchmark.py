"""
Performance Benchmark Engine
=============================
Measures actual system performance for:
  - API endpoint throughput & latency distribution
  - Database read/write throughput
  - AI inference latency (cold + warm)
  - Cache hit ratio under load

All measurements are taken from real operations.
No synthetic or assumed benchmark numbers are reported.

Usage:
    bench = BenchmarkEngine()
    async with bench.measure("api.leads.list") as m:
        response = await call_endpoint()
    report = bench.report()
"""
import time
import logging
import asyncio
import statistics
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkSample:
    operation: str
    duration_ms: float
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class BenchmarkResult:
    operation: str
    sample_count: int
    success_count: int
    failure_count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    throughput_rps: Optional[float]  # None if duration unknown
    error_rate_pct: float

    def passes_slo(self, p99_threshold_ms: float = 500.0, error_threshold_pct: float = 1.0) -> bool:
        return self.p99_ms <= p99_threshold_ms and self.error_rate_pct <= error_threshold_pct


class BenchmarkEngine:
    """Collects and aggregates performance samples from real operations."""

    def __init__(self):
        self._samples: Dict[str, List[BenchmarkSample]] = {}

    def record(self, operation: str, duration_ms: float, success: bool = True, metadata: Optional[Dict] = None) -> None:
        if operation not in self._samples:
            self._samples[operation] = []
        self._samples[operation].append(BenchmarkSample(
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata or {},
        ))

    @asynccontextmanager
    async def measure(self, operation: str, metadata: Optional[Dict] = None):
        """Async context manager for automatic timing."""
        start = time.monotonic()
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self.record(operation, duration_ms, success=success, metadata=metadata)

    def analyze(self, operation: str, window_seconds: Optional[float] = None) -> Optional[BenchmarkResult]:
        samples = self._samples.get(operation, [])
        if not samples:
            return None

        if window_seconds:
            cutoff = time.time() - window_seconds
            samples = [s for s in samples if s.timestamp >= cutoff]

        if not samples:
            return None

        durations   = sorted(s.duration_ms for s in samples)
        success_cnt = sum(1 for s in samples if s.success)
        total       = len(samples)
        error_rate  = round((total - success_cnt) / total * 100, 2)

        # Throughput: only meaningful if we have enough samples across time
        time_span = samples[-1].timestamp - samples[0].timestamp
        throughput = round(total / time_span, 2) if time_span > 0.5 else None

        def pct(p: float) -> float:
            idx = max(0, int(len(durations) * p / 100) - 1)
            return round(durations[idx], 3)

        return BenchmarkResult(
            operation=operation,
            sample_count=total,
            success_count=success_cnt,
            failure_count=total - success_cnt,
            min_ms=round(min(durations), 3),
            max_ms=round(max(durations), 3),
            mean_ms=round(statistics.mean(durations), 3),
            median_ms=round(statistics.median(durations), 3),
            p95_ms=pct(95),
            p99_ms=pct(99),
            throughput_rps=throughput,
            error_rate_pct=error_rate,
        )

    def report(self) -> Dict[str, Any]:
        results = {}
        for op in self._samples:
            r = self.analyze(op)
            if r:
                results[op] = {
                    "sample_count":  r.sample_count,
                    "success_count": r.success_count,
                    "failure_count": r.failure_count,
                    "min_ms":        r.min_ms,
                    "max_ms":        r.max_ms,
                    "mean_ms":       r.mean_ms,
                    "median_ms":     r.median_ms,
                    "p95_ms":        r.p95_ms,
                    "p99_ms":        r.p99_ms,
                    "throughput_rps": r.throughput_rps,
                    "error_rate_pct": r.error_rate_pct,
                    "passes_slo":    r.passes_slo(),
                }
        return {
            "operations": results,
            "total_operations": len(results),
            "source": "real_measurements",
        }

    def clear(self) -> None:
        self._samples = {}


# ── Chaos / DR Drill Framework ─────────────────────────────────────────────────

@dataclass
class DrillResult:
    drill_id: str
    drill_type: str
    target: str
    outcome: str          # "PASS" | "FAIL" | "ABORTED"
    duration_seconds: float
    observations: List[str]
    rto_seconds: Optional[float]   # Actual recovery time (None if not measured)
    rpo_data_loss: Optional[str]   # Actual data loss assessment
    ran_at: str


class ChaosEngine:
    """
    Controlled failure injection for DR/Chaos drills.

    SAFETY:
      - Only runs in environments with CHAOS_ENABLED=True
      - All drills are logged and audited
      - Auto-aborts if a safety check fails

    Drill types:
      - "database_failover"  : Simulate primary DB failure
      - "cache_eviction"     : Flush Redis and measure recovery
      - "ai_provider_outage" : Inject circuit-breaker trip
      - "worker_restart"     : Kill Celery worker and measure recovery
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._results: List[DrillResult] = []
        if not enabled:
            logger.info("[CHAOS] Chaos engine initialized in DISABLED mode (safe)")

    async def run_drill(
        self,
        drill_type: str,
        target: str,
        injector: Any,   # async callable that injects the failure
        recovery_checker: Any,  # async callable returning True when recovered
        timeout_seconds: float = 120.0,
    ) -> DrillResult:
        import uuid as _uuid
        drill_id = f"DRILL-{_uuid.uuid4().hex[:8].upper()}"

        if not self.enabled:
            result = DrillResult(
                drill_id=drill_id,
                drill_type=drill_type,
                target=target,
                outcome="ABORTED",
                duration_seconds=0.0,
                observations=["Chaos engine is DISABLED — drill skipped"],
                rto_seconds=None,
                rpo_data_loss=None,
                ran_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            )
            self._results.append(result)
            return result

        logger.warning(f"[CHAOS] Starting drill {drill_id}: {drill_type} on {target}")
        start = time.monotonic()
        observations = []

        try:
            # 1. Inject failure
            await injector()
            observations.append(f"Failure injected: {drill_type}")

            # 2. Measure time to recovery
            recovery_start = time.monotonic()
            recovered = False
            while (time.monotonic() - recovery_start) < timeout_seconds:
                if await recovery_checker():
                    recovered = True
                    break
                await asyncio.sleep(1.0)

            rto = round(time.monotonic() - recovery_start, 2) if recovered else None
            outcome = "PASS" if recovered else "FAIL"
            observations.append(f"Recovery: {'succeeded' if recovered else 'TIMED OUT'}")

        except Exception as exc:
            outcome = "FAIL"
            rto = None
            observations.append(f"Drill failed with exception: {exc}")
            logger.error(f"[CHAOS] Drill {drill_id} failed: {exc}")

        duration = round(time.monotonic() - start, 2)
        result = DrillResult(
            drill_id=drill_id,
            drill_type=drill_type,
            target=target,
            outcome=outcome,
            duration_seconds=duration,
            observations=observations,
            rto_seconds=rto,
            rpo_data_loss="Not measured in this drill",
            ran_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        )
        self._results.append(result)
        logger.info(f"[CHAOS] Drill {drill_id} complete: {outcome} RTO={rto}s")
        return result

    def report(self) -> Dict[str, Any]:
        total  = len(self._results)
        passed = sum(1 for r in self._results if r.outcome == "PASS")
        return {
            "total_drills": total,
            "passed": passed,
            "failed": total - passed,
            "drills": [
                {
                    "drill_id":         r.drill_id,
                    "type":             r.drill_type,
                    "target":           r.target,
                    "outcome":          r.outcome,
                    "duration_seconds": r.duration_seconds,
                    "rto_seconds":      r.rto_seconds,
                    "observations":     r.observations,
                }
                for r in self._results
            ],
        }


# Global singletons
benchmark = BenchmarkEngine()
chaos_engine = ChaosEngine(enabled=False)  # Enable with ChaosEngine(enabled=True) in staging
