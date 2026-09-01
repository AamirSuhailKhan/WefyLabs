"""
Enterprise Circuit Breaker & Reliability Pattern
================================================
Prevents cascade failures across downstream integrations, search engines,
and AI APIs using the Circuit Breaker state pattern:
  CLOSED (normal) -> OPEN (tripped) -> HALF_OPEN (probing recovery).
"""
import time
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerOpenException(Exception):
    """Raised when a call is executed while the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Thread-safe / Async-safe Circuit Breaker.
    """
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_time_seconds: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self.state = "CLOSED" # CLOSED | OPEN | HALF_OPEN
        self.failure_count = 0
        self.last_state_change = time.time()

    async def call(self, func: Callable, *args, fallback: Optional[Callable] = None, **kwargs) -> Any:
        """Executes func within circuit breaker protection."""
        now = time.time()

        # Check if OPEN and ready to transition to HALF_OPEN
        if self.state == "OPEN":
            if now - self.last_state_change > self.recovery_time_seconds:
                logger.info(f"[CIRCUIT BREAKER] {self.name}: OPEN -> HALF_OPEN (probing recovery)")
                self.state = "HALF_OPEN"
                self.last_state_change = now
            else:
                logger.warning(f"[CIRCUIT BREAKER] {self.name} is OPEN. Rejecting call.")
                if fallback:
                    return await fallback(*args, **kwargs) if callable(fallback) else fallback
                raise CircuitBreakerOpenException(f"Circuit Breaker '{self.name}' is OPEN.")

        try:
            result = await func(*args, **kwargs)

            # Success in HALF_OPEN recovers to CLOSED
            if self.state == "HALF_OPEN":
                logger.info(f"[CIRCUIT BREAKER] {self.name}: HALF_OPEN -> CLOSED (recovered)")
                self.state = "CLOSED"
                self.failure_count = 0
                self.last_state_change = now

            return result

        except Exception as exc:
            self.failure_count += 1
            logger.error(f"[CIRCUIT BREAKER] {self.name} call failed ({self.failure_count}/{self.failure_threshold}): {exc}")

            if self.failure_count >= self.failure_threshold:
                logger.error(f"[CIRCUIT BREAKER] {self.name}: CLOSED/HALF_OPEN -> OPEN (threshold exceeded)")
                self.state = "OPEN"
                self.last_state_change = now

            if fallback:
                return await fallback(*args, **kwargs) if callable(fallback) else fallback
            raise
