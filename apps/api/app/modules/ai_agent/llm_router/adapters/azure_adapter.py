"""
Azure OpenAI Adapter — Azure-hosted GPT-4o endpoint.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse


class AzureOpenAIAdapter(BaseLLMAdapter):
    def __init__(
        self,
        api_key: str,
        azure_endpoint: str,
        deployment_name: str = "gpt-4o",
        api_version: str = "2024-05-01-preview",
    ):
        self._api_key = api_key
        self._endpoint = azure_endpoint
        self._deployment = deployment_name
        self._api_version = api_version

    @property
    def provider_name(self) -> str:
        return "azure"

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
            from openai import AsyncAzureOpenAI  # type: ignore
        except ImportError:
            return LLMResponse(content="", success=False,
                               error="openai package not installed",
                               provider=self.provider_name, model=self._deployment)

        client = AsyncAzureOpenAI(
            api_key=self._api_key,
            azure_endpoint=self._endpoint,
            api_version=self._api_version,
        )
        kwargs: Dict[str, Any] = {
            "model": self._deployment,
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
            return LLMResponse(content="", success=False, error=str(exc),
                               provider=self.provider_name, model=self._deployment)
        latency_ms = int((time.monotonic() - t0) * 1000)

        choice = response.choices[0]
        content = choice.message.content or ""
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
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0

        return LLMResponse(
            content=content,
            tool_calls=parsed_tools,
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            cost_usd=0.0,  # Azure billing is handled separately
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self._deployment,
            finish_reason=choice.finish_reason or "stop",
            success=True,
        )

    async def is_available(self) -> bool:
        try:
            from openai import AsyncAzureOpenAI  # type: ignore
            client = AsyncAzureOpenAI(
                api_key=self._api_key,
                azure_endpoint=self._endpoint,
                api_version=self._api_version,
            )
            await client.models.list()
            return True
        except Exception:
            return False
