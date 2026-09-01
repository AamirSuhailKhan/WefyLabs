"""
OpenAI Adapter — GPT-4o with tool calling support.
Model-independent: business logic never references OpenAI directly.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse

# Cost per 1000 tokens (USD) — update as pricing changes
_COST_PER_1K = {"gpt-4o": {"input": 0.005, "output": 0.015}}


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI GPT-4o adapter.
    Lazy-imports openai so the package is optional at import time.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def supports_tool_calling(self) -> bool:
        return True

    async def complete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError:
            return LLMResponse(
                content="",
                success=False,
                error="openai package not installed",
                provider=self.provider_name,
                model=self._model,
            )

        client = AsyncOpenAI(api_key=self._api_key)
        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        t0 = time.monotonic()
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            return LLMResponse(
                content="",
                success=False,
                error=str(exc),
                provider=self.provider_name,
                model=self._model,
            )
        latency_ms = int((time.monotonic() - t0) * 1000)

        choice = response.choices[0]
        content = choice.message.content or ""

        # Parse tool calls
        parsed_tools: List[Dict[str, Any]] = []
        if choice.message.tool_calls:
            import json
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                parsed_tools.append({"name": tc.function.name, "arguments": args})

        usage = response.usage
        prompt_tok = usage.prompt_tokens if usage else 0
        comp_tok = usage.completion_tokens if usage else 0
        cost_map = _COST_PER_1K.get(self._model, {"input": 0.005, "output": 0.015})
        cost = (prompt_tok / 1000) * cost_map["input"] + (comp_tok / 1000) * cost_map["output"]

        return LLMResponse(
            content=content,
            tool_calls=parsed_tools,
            prompt_tokens=prompt_tok,
            completion_tokens=comp_tok,
            total_tokens=prompt_tok + comp_tok,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self._model,
            finish_reason=choice.finish_reason or "stop",
            success=True,
        )

    async def is_available(self) -> bool:
        try:
            from openai import AsyncOpenAI  # type: ignore
            client = AsyncOpenAI(api_key=self._api_key)
            await client.models.list()
            return True
        except Exception:
            return False
