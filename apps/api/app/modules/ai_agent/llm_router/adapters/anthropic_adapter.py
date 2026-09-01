"""
Anthropic Claude Adapter — Claude 3.5 Sonnet with tool use support.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse

_COST_PER_1K = {
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
}


class AnthropicAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "anthropic"

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
            import anthropic  # type: ignore
        except ImportError:
            return LLMResponse(content="", success=False,
                               error="anthropic package not installed",
                               provider=self.provider_name, model=self._model)

        client = anthropic.AsyncAnthropic(api_key=self._api_key)

        # Anthropic separates system from messages
        system_content = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system_content += m["content"] + "\n"
            else:
                user_messages.append(m)

        kwargs: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_content:
            kwargs["system"] = system_content.strip()
        if tools:
            # Convert OpenAI tool format to Anthropic tool format
            anthropic_tools = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in tools
            ]
            kwargs["tools"] = anthropic_tools

        t0 = time.monotonic()
        try:
            response = await client.messages.create(**kwargs)
        except Exception as exc:
            return LLMResponse(content="", success=False, error=str(exc),
                               provider=self.provider_name, model=self._model)
        latency_ms = int((time.monotonic() - t0) * 1000)

        content = ""
        parsed_tools: List[Dict[str, Any]] = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                parsed_tools.append({"name": block.name, "arguments": block.input})

        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        cost_map = _COST_PER_1K.get(self._model, {"input": 0.003, "output": 0.015})
        cost = (in_tok / 1000) * cost_map["input"] + (out_tok / 1000) * cost_map["output"]

        return LLMResponse(
            content=content,
            tool_calls=parsed_tools,
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self._model,
            finish_reason=response.stop_reason or "stop",
            success=True,
        )

    async def is_available(self) -> bool:
        try:
            import anthropic  # type: ignore
            client = anthropic.AsyncAnthropic(api_key=self._api_key)
            await client.messages.create(
                model=self._model, max_tokens=5,
                messages=[{"role": "user", "content": "ping"}]
            )
            return True
        except Exception:
            return False
