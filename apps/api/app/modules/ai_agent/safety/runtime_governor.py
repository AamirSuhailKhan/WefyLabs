"""
WefyLabs AI Runtime Safety, Concurrency Governor & Cost Governance
==================================================================
Protects system resources and limits costs during high-concurrency AI operations:
1. Concurrency Throttling:
   - Global semaphore prevents backend starvation.
   - Per-tenant semaphore prevents noisy-neighbor resource monopolization.
2. AI Circuit Breaker:
   - Trips when upstream Gemini provider fails consecutively.
   - Fast-fails without blocking worker threads.
3. Cost Governance:
   - Computes token usage & estimated cost without storing customer prompts or PII.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger("wefylabs.ai.governor")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operations
    OPEN = "OPEN"            # Tripped; fast-fail
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class AIRuntimeGovernor:
    """
    Manages concurrency limits, circuit breaker, and token accounting for AI workloads.
    """
    def __init__(
        self,
        global_concurrency_limit: int = 50,
        tenant_concurrency_limit: int = 10,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout_seconds: float = 20.0
    ):
        self.global_concurrency_limit = global_concurrency_limit
        self.tenant_concurrency_limit = tenant_concurrency_limit
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_recovery_timeout = circuit_recovery_timeout_seconds

        self._global_semaphore = asyncio.Semaphore(global_concurrency_limit)
        self._tenant_semaphores: Dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(tenant_concurrency_limit)
        )

        # Circuit Breaker state
        self._circuit_state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time = 0.0

        # Cost Governance & Usage records (in-memory audit buffer, max 500 records)
        self._usage_records: deque[Dict[str, Any]] = deque(maxlen=500)
        self._tenant_spend_cents: Dict[str, float] = defaultdict(float)

    # ── Concurrency & Circuit Breaker ──────────────────────────────────────────

    def is_circuit_open(self) -> bool:
        """Returns True if the circuit is currently open and blocking calls."""
        if self._circuit_state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.circuit_recovery_timeout:
                self._circuit_state = CircuitState.HALF_OPEN
                logger.info("[AIGovernor] Circuit entered HALF_OPEN state — testing recovery.")
                return False
            return True
        return False

    def record_call_success(self) -> None:
        """Resets the circuit breaker upon successful response."""
        if self._circuit_state != CircuitState.CLOSED:
            logger.info("[AIGovernor] Circuit recovered: state reset to CLOSED.")
        self._circuit_state = CircuitState.CLOSED
        self._consecutive_failures = 0

    def record_call_failure(self, error: Exception) -> None:
        """Increments consecutive failures and trips circuit if threshold exceeded."""
        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        logger.warning(
            f"[AIGovernor] Upstream AI failure #{self._consecutive_failures}: {error}"
        )
        if self._consecutive_failures >= self.circuit_failure_threshold:
            self._circuit_state = CircuitState.OPEN
            logger.error(
                f"[AIGovernor] Circuit breaker TRIPPED (OPEN) after {self._consecutive_failures} failures. "
                f"Fast-failing for {self.circuit_recovery_timeout}s."
            )

    async def acquire_quota(
        self,
        tenant_id: str,
        timeout: float = 3.0
    ) -> bool:
        """
        Acquires both global and tenant concurrency permits within timeout.
        Returns True if acquired, False if timed out or circuit is open.
        """
        if self.is_circuit_open():
            logger.warning(f"[AIGovernor] Request rejected — AI provider circuit is OPEN.")
            return False

        tenant_sem = self._tenant_semaphores[tenant_id]

        try:
            # Wait with bounded timeout to avoid indefinite request holding
            await asyncio.wait_for(self._global_semaphore.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[AIGovernor] Global AI concurrency limit reached ({self.global_concurrency_limit}).")
            return False

        try:
            await asyncio.wait_for(tenant_sem.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            # Release global permit if tenant permit couldn't be acquired
            self._global_semaphore.release()
            logger.warning(
                f"[AIGovernor] Tenant '{tenant_id}' AI concurrency quota reached ({self.tenant_concurrency_limit})."
            )
            return False

    def release_quota(self, tenant_id: str) -> None:
        """Releases acquired permits."""
        try:
            self._tenant_semaphores[tenant_id].release()
        except ValueError:
            pass
        try:
            self._global_semaphore.release()
        except ValueError:
            pass

    # ── Cost Governance ────────────────────────────────────────────────────────

    def record_usage(
        self,
        *,
        tenant_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        feature: str = "general",
        success: bool = True
    ) -> Dict[str, Any]:
        """
        Calculates and logs token usage & cost metrics without storing customer prompts or PII.
        Google Gemini 1.5 / 2.5 Flash pricing baseline:
        - Input: $0.075 per 1M tokens (~0.0075 cents / 1k)
        - Output: $0.30 per 1M tokens (~0.030 cents / 1k)
        """
        cost_cents = (input_tokens * 0.0000075) + (output_tokens * 0.000030)
        self._tenant_spend_cents[tenant_id] += cost_cents

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost_cents": round(cost_cents, 4),
            "latency_ms": round(latency_ms, 2),
            "feature": feature,
            "success": success
        }
        self._usage_records.append(record)
        return record

    def get_tenant_spend(self, tenant_id: str) -> float:
        """Returns total accumulated spend in cents for a tenant."""
        return round(self._tenant_spend_cents.get(tenant_id, 0.0), 4)

    def get_recent_usage(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent usage records (without prompts or PII)."""
        return list(self._usage_records)[-limit:]


# Module singleton
ai_governor = AIRuntimeGovernor()
