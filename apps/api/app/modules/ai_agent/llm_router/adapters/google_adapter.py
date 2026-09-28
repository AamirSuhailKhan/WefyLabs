"""
Google Gemini Adapter — google-genai SDK with native function calling support.

Uses the modern google-genai SDK (v2+) which supports:
- Native tool/function calling with structured inputs/outputs
- System instructions as a first-class parameter
- Async API for non-blocking FastAPI integration

Migrated from deprecated google-generativeai 0.8.x to google-genai 2.x.
"""
from __future__ import annotations

import json
import time
import logging
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.llm_router.base_adapter import BaseLLMAdapter, LLMResponse

logger = logging.getLogger("wefylabs.llm.google")

_COST_PER_1K = {
    # Gemini 3.x / 2.x pricing (USD per 1K tokens)
    "gemini-3.8-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-2.0-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-2.0-flash-lite": {"input": 0.000038, "output": 0.00015},
    # Legacy name mappings (backward compat with env vars)
    "gemini-3.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-3.7-flash": {"input": 0.00010, "output": 0.0004},
    "gemini-3.1-pro": {"input": 0.00125, "output": 0.005},
}

# Canonical model to use if environment specifies a non-existent name
_MODEL_ALIAS = {
    "gemini-2.5-flash": "gemini-3.8-flash",
    "gemini-3.5-flash": "gemini-3.8-flash",
    "gemini-3.7-flash": "gemini-3.8-flash",
    "gemini-3.1-pro": "gemini-2.5-pro",
}


def _convert_tools_to_genai(tools: List[Dict[str, Any]]) -> List[Any]:
    """
    Convert OpenAI-style tool definitions to google-genai FunctionDeclaration objects.

    Input format (OpenAI/standard):
      [{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]

    Output: list of google.genai.types.Tool wrapping FunctionDeclarations.
    """
    if not tools:
        return []
    try:
        from google import genai  # type: ignore
        from google.genai import types as gtypes  # type: ignore

        declarations = []
        for t in tools:
            fn = t.get("function", t)  # handle both {function: ...} and flat dict
            declarations.append(
                gtypes.FunctionDeclaration(
                    name=fn["name"],
                    description=fn.get("description", ""),
                    parameters=fn.get("parameters", {}),
                )
            )
        return [gtypes.Tool(function_declarations=declarations)]
    except Exception as exc:
        logger.warning(f"[GoogleAdapter] Tool conversion failed: {exc}")
        return []


def _extract_tool_calls(response: Any) -> List[Dict[str, Any]]:
    """
    Extract function call(s) from a google-genai response object.

    The new SDK returns function calls in candidate.content.parts[].function_call.
    Each function_call has .name and .args (a dict-like object).
    """
    tool_calls: List[Dict[str, Any]] = []
    try:
        candidates = getattr(response, "candidates", []) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            parts = getattr(content, "parts", []) or []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    name = getattr(fc, "name", None) or ""
                    args = getattr(fc, "args", {}) or {}
                    # args is a MapComposite — convert to plain dict
                    if hasattr(args, "items"):
                        args = dict(args)
                    if name:
                        tool_calls.append({"name": name, "arguments": args})
    except Exception as exc:
        logger.warning(f"[GoogleAdapter] Tool call extraction error: {exc}")
    return tool_calls


def _extract_text(response: Any) -> str:
    """
    Extract text from a google-genai response.
    Falls back gracefully if the response is a function call (no text part).
    """
    try:
        # Primary: response.text property
        text = getattr(response, "text", None)
        if text:
            return text.strip()
        # Fallback: iterate parts
        candidates = getattr(response, "candidates", []) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            parts = getattr(content, "parts", []) or []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    return text.strip()
    except Exception:
        pass
    return ""


class GoogleAdapter(BaseLLMAdapter):
    """
    Google Gemini adapter using google-genai SDK v2+.

    Supports:
    - System instructions (passed as system_instruction param, not in history)
    - Native function/tool calling with proper argument parsing
    - Async non-blocking API via generate_content_async
    - Cost tracking via usage_metadata
    - Circuit breaker friendly: never raises, always returns LLMResponse
    """

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash"):
        self._api_key = api_key
        # Resolve legacy model name aliases
        self._model = _MODEL_ALIAS.get(model, model)
        if model != self._model:
            logger.info(f"[GoogleAdapter] Model alias resolved: {model} -> {self._model}")

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
        """
        Send messages to Gemini and return a normalized LLMResponse.

        System messages are extracted and passed as system_instruction.
        Tool calls are parsed from response function_call parts.
        Text and tool calls can both be present in one response.
        """
        if not self._api_key:
            return LLMResponse(
                content="",
                success=False,
                error="GEMINI_API_KEY not configured",
                provider=self.provider_name,
                model=self._model,
            )

        try:
            from google import genai  # type: ignore
            from google.genai import types as gtypes  # type: ignore
        except ImportError:
            return LLMResponse(
                content="",
                success=False,
                error="google-genai package not installed. Run: pip install google-genai",
                provider=self.provider_name,
                model=self._model,
            )

        # ── Separate system messages from conversation history ────────────────
        system_parts: List[str] = []
        history: List[gtypes.Content] = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role in ("user", "human"):
                history.append(gtypes.Content(role="user", parts=[gtypes.Part(text=content)]))
            elif role in ("assistant", "model"):
                history.append(gtypes.Content(role="model", parts=[gtypes.Part(text=content)]))

        system_instruction = "\n\n".join(system_parts) if system_parts else None

        # ── Extract the last user message as the actual prompt ────────────────
        # It must be sent via chat.send_message, not in history
        if history and history[-1].role == "user":
            last_user_content = history[-1]
            history = history[:-1]
        else:
            # No user message found — shouldn't happen, but handle gracefully
            last_user_content = gtypes.Content(role="user", parts=[gtypes.Part(text="")])

        # ── Build generation config ───────────────────────────────────────────
        gen_config = gtypes.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        # ── Wire tools if provided ────────────────────────────────────────────
        genai_tools = _convert_tools_to_genai(tools) if tools else None
        if genai_tools:
            gen_config.tools = genai_tools

        # ── Create client and send message ────────────────────────────────────
        t0 = time.monotonic()
        try:
            client = genai.Client(api_key=self._api_key)
            chat = client.aio.chats.create(
                model=self._model,
                history=history,
                config=gen_config,
            )
            response = await chat.send_message(last_user_content.parts)
        except Exception as exc:
            logger.error(f"[GoogleAdapter] Gemini API error: {exc}", exc_info=True)
            return LLMResponse(
                content="",
                success=False,
                error=str(exc),
                provider=self.provider_name,
                model=self._model,
            )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # ── Extract text and tool calls from response ─────────────────────────
        content_text = _extract_text(response)
        extracted_tool_calls = _extract_tool_calls(response)

        # ── Token usage + cost tracking ───────────────────────────────────────
        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) or 0
        out_tok = getattr(usage, "candidates_token_count", 0) or 0
        cost_map = _COST_PER_1K.get(self._model, {"input": 0.00125, "output": 0.005})
        cost = (in_tok / 1000) * cost_map["input"] + (out_tok / 1000) * cost_map["output"]

        # ── Determine finish reason ───────────────────────────────────────────
        finish_reason = "tool_use" if extracted_tool_calls else "stop"

        logger.debug(
            f"[GoogleAdapter] model={self._model} in={in_tok} out={out_tok} "
            f"latency={latency_ms}ms tool_calls={len(extracted_tool_calls)}"
        )

        return LLMResponse(
            content=content_text,
            tool_calls=extracted_tool_calls,
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self._model,
            finish_reason=finish_reason,
            success=True,
        )

    async def is_available(self) -> bool:
        """Lightweight ping to check if Gemini is reachable."""
        try:
            from google import genai  # type: ignore
            client = genai.Client(api_key=self._api_key)
            await client.aio.models.get(model=self._model)
            return True
        except Exception:
            return False
