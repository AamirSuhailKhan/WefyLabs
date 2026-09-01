"""
Base LLM Adapter — abstract interface all provider adapters must implement.

Ensures the LLM Router can swap providers without touching any business logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    content: str                          # Text response from model
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # List of {name, arguments}
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider: str = ""
    model: str = ""
    finish_reason: str = "stop"
    success: bool = True
    error: Optional[str] = None


class BaseLLMAdapter(ABC):
    """
    Abstract base class for all LLM provider adapters.
    Every concrete adapter must implement complete().
    The LLMRouter calls only this interface — never provider SDKs directly.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        ...

    @property
    @abstractmethod
    def supports_tool_calling(self) -> bool:
        """Return True if this provider/model supports function/tool calling."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """
        Send messages to the LLM and return a normalized LLMResponse.
        Never raises; returns LLMResponse(success=False, error=...) on failure.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if this provider is currently reachable (used by circuit breaker).
        Returns True/False; never raises.
        """
        ...
