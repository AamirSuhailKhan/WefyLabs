"""
LLM Router — selects the best provider adapter for each turn.

Selection criteria (in order):
  1. Configured primary provider (from AgentConfiguration)
  2. If primary is unavailable, fallback to secondary
  3. If secondary is unavailable, return deterministic rule-based response

Circuit breaker: after 3 consecutive failures, skip a provider for 60 seconds.
Cost control: max_tokens is clamped to MAX_TOKENS_CAP (2048) on every call.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse
from app.modules.ai_agent.prompt_engine.templates import FALLBACK_RULE_RESPONSE

logger = logging.getLogger("wefylabs.llm_router")

# ─── Cost Control ──────────────────────────────────────────────────────────────
MAX_TOKENS_CAP = 2048  # Hard ceiling on token budget per LLM call


# ─── Circuit Breaker State ──────────────────────────────────────────────────────────────

class _CircuitBreaker:
    """Per-provider lightweight circuit breaker."""
    _failures: Dict[str, int] = {}
    _open_until: Dict[str, float] = {}
    THRESHOLD = 3
    OPEN_SECONDS = 60.0

    @classmethod
    def record_failure(cls, provider: str) -> None:
        cls._failures[provider] = cls._failures.get(provider, 0) + 1
        if cls._failures[provider] >= cls.THRESHOLD:
            cls._open_until[provider] = time.monotonic() + cls.OPEN_SECONDS
            logger.warning(
                "[LLMRouter] circuit_breaker_opened",
                extra={"provider": provider, "failures": cls._failures[provider], "open_seconds": cls.OPEN_SECONDS},
            )

    @classmethod
    def record_success(cls, provider: str) -> None:
        was_open = provider in cls._open_until
        cls._failures[provider] = 0
        cls._open_until.pop(provider, None)
        if was_open:
            logger.info(
                "[LLMRouter] circuit_breaker_closed",
                extra={"provider": provider},
            )

    @classmethod
    def is_open(cls, provider: str) -> bool:
        until = cls._open_until.get(provider, 0)
        if until and time.monotonic() < until:
            return True
        if until and time.monotonic() >= until:
            # Reset after timeout
            cls._open_until.pop(provider, None)
            cls._failures[provider] = 0
            logger.info(
                "[LLMRouter] circuit_breaker_reset_after_timeout",
                extra={"provider": provider},
            )
        return False


# ─── LLM Router ───────────────────────────────────────────────────────────────

class LLMRouter:
    """
    Model-independent LLM router.
    Accepts adapter instances for primary and fallback providers.
    Swapping providers requires only changing which adapters are injected —
    no business logic changes.
    """

    def __init__(
        self,
        primary: BaseLLMAdapter,
        fallback: Optional[BaseLLMAdapter] = None,
    ):
        self.primary = primary
        self.fallback = fallback

    async def route(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        current_state: str = "greeting",
    ) -> LLMResponse:
        """
        Route the completion request through:
        1. Primary adapter (if circuit not open)
        2. Fallback adapter (if primary fails and fallback configured)
        3. Deterministic rule response (if all adapters fail)

        Cost control: `max_tokens` is silently clamped to MAX_TOKENS_CAP.
        """
        # ── Cost Control: clamp token budget ───────────────────────────────────
        effective_max_tokens = min(max_tokens, MAX_TOKENS_CAP)
        if effective_max_tokens < max_tokens:
            logger.debug(
                "[LLMRouter] max_tokens_clamped",
                extra={"requested": max_tokens, "effective": effective_max_tokens, "cap": MAX_TOKENS_CAP},
            )

        call_start = time.monotonic()

        # ── Try primary ────────────────────────────────────────────────────
        if not _CircuitBreaker.is_open(self.primary.provider_name):
            result = await self.primary.complete(messages, tools, effective_max_tokens, temperature)
            duration_ms = int((time.monotonic() - call_start) * 1000)
            if result.success:
                _CircuitBreaker.record_success(self.primary.provider_name)
                logger.info(
                    "[LLMRouter] llm_call_success",
                    extra={
                        "provider": self.primary.provider_name,
                        "max_tokens": effective_max_tokens,
                        "duration_ms": duration_ms,
                        "state": current_state,
                    },
                )
                return result
            else:
                _CircuitBreaker.record_failure(self.primary.provider_name)
                logger.warning(
                    "[LLMRouter] llm_call_failed_primary",
                    extra={"provider": self.primary.provider_name, "error": result.error, "duration_ms": duration_ms},
                )

        # ── Try fallback ───────────────────────────────────────────────────
        if self.fallback and not _CircuitBreaker.is_open(self.fallback.provider_name):
            result = await self.fallback.complete(messages, tools, effective_max_tokens, temperature)
            duration_ms = int((time.monotonic() - call_start) * 1000)
            if result.success:
                _CircuitBreaker.record_success(self.fallback.provider_name)
                logger.info(
                    "[LLMRouter] llm_call_success_fallback",
                    extra={
                        "provider": self.fallback.provider_name,
                        "max_tokens": effective_max_tokens,
                        "duration_ms": duration_ms,
                        "state": current_state,
                    },
                )
                return result
            else:
                _CircuitBreaker.record_failure(self.fallback.provider_name)
                logger.warning(
                    "[LLMRouter] llm_call_failed_fallback",
                    extra={"provider": self.fallback.provider_name, "error": result.error, "duration_ms": duration_ms},
                )

        # ── Deterministic fallback ───────────────────────────────────────────────
        logger.warning("[LLMRouter] all_providers_failed_using_rule_fallback", extra={"state": current_state})
        return self._rule_fallback(current_state)

    def _rule_fallback(self, current_state: str) -> LLMResponse:
        """
        Return a deterministic response based on FSM state.
        Used when all LLM providers are unavailable.
        """
        content = FALLBACK_RULE_RESPONSE.get(
            current_state,
            FALLBACK_RULE_RESPONSE["greeting"]
        )
        return LLMResponse(
            content=content,
            tool_calls=[],
            success=True,
            provider="rule_fallback",
            model="deterministic",
        )


def build_router_from_env() -> LLMRouter:
    """
    Build an LLMRouter from environment variables.
    Used by ConversationManager when no AgentConfiguration is present.
    Primary: Google Gemini (via GEMINI_API_KEY).
    """
    from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    primary = GoogleAdapter(api_key=gemini_key, model=gemini_model)
    return LLMRouter(primary=primary, fallback=None)
