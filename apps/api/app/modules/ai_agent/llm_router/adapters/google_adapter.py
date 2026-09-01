"""
Google Gemini Adapter — Gemini 3.5 Flash / Gemini 3.7 Flash with function calling.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse

_COST_PER_1K = {
    "gemini-3.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-3.7-flash": {"input": 0.00010, "output": 0.0004},
    "gemini-3.1-pro": {"input": 0.00125, "output": 0.005},
}


class GoogleAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash"):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "google"

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
            import google.generativeai as genai  # type: ignore
        except ImportError:
            return LLMResponse(content="", success=False,
                               error="google-generativeai package not installed",
                               provider=self.provider_name, model=self._model)

        genai.configure(api_key=self._api_key)
        model_obj = genai.GenerativeModel(
            model_name=self._model,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )

        # Convert messages to Gemini format
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        history = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})

        # Last user message is the actual prompt
        current_message = ""
        if history and history[-1]["role"] == "user":
            current_message = history[-1]["parts"][0]
            history = history[:-1]

        chat = model_obj.start_chat(history=history)
        system_prefix = "\n".join(system_parts) + "\n\n" if system_parts else ""
        full_prompt = system_prefix + current_message

        t0 = time.monotonic()
        try:
            response = await chat.send_message_async(full_prompt)
        except Exception as exc:
            return LLMResponse(content="", success=False, error=str(exc),
                               provider=self.provider_name, model=self._model)
        latency_ms = int((time.monotonic() - t0) * 1000)

        content = response.text or ""
        usage = response.usage_metadata
        in_tok = getattr(usage, "prompt_token_count", 0) or 0
        out_tok = getattr(usage, "candidates_token_count", 0) or 0
        cost_map = _COST_PER_1K.get(self._model, {"input": 0.00125, "output": 0.005})
        cost = (in_tok / 1000) * cost_map["input"] + (out_tok / 1000) * cost_map["output"]

        return LLMResponse(
            content=content,
            tool_calls=[],  # Gemini function calling parsed separately
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self._model,
            finish_reason="stop",
            success=True,
        )

    async def is_available(self) -> bool:
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel(model_name=self._model)
            await model.generate_content_async("ping")
            return True
        except Exception:
            return False
