"""Contract tests for normalized Google adapter behavior; all provider I/O is mocked."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter


@pytest.mark.parametrize(
    ("requested", "resolved"),
    [
        ("gemini-1.5-flash", "gemini-3.6-flash"),
        ("gemini-1.5-pro", "gemini-3.6-flash"),
        ("gemini-2.0-flash", "gemini-2.5-flash"),
        ("gemini-3.1-pro", "gemini-2.5-pro"),
        ("gemini-2.5-flash", "gemini-2.5-flash"),
        ("gemini-3.8-flash", "gemini-3.8-flash"),
        ("gemini-3.6-flash", "gemini-3.6-flash"),
        ("gemini-3.5-flash", "gemini-3.5-flash"),
    ],
)
def test_model_alias_resolution_preserves_supported_operator_choices(requested, resolved):
    assert GoogleAdapter(api_key="test-key", model=requested)._model == resolved


def test_google_adapter_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-3.8-flash")
    adapter = GoogleAdapter(api_key="test-key")
    assert adapter._model == "gemini-3.8-flash"


def _sdk(monkeypatch, response=None, error=None):
    from google import genai

    client = MagicMock()
    chat = MagicMock()

    async def send_message(_parts):
        if error:
            raise error
        return response

    chat.send_message = send_message
    client.aio.chats.create.return_value = chat
    monkeypatch.setattr(genai, "Client", MagicMock(return_value=client))


@pytest.mark.asyncio
async def test_complete_extracts_sdk_text(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    response = SimpleNamespace(text=" adapter text ", candidates=[], usage_metadata=SimpleNamespace(prompt_token_count=2, candidates_token_count=3))
    _sdk(monkeypatch, response=response)
    result = await GoogleAdapter("test-key").complete([{"role": "user", "content": "hi"}])
    assert result.success is True
    assert result.content == "adapter text"
    assert result.total_tokens == 5


@pytest.mark.asyncio
async def test_complete_marks_empty_and_token_limited_responses_unsuccessful(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    response = SimpleNamespace(
        text="",
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[]), finish_reason="MAX_TOKENS")],
        usage_metadata=SimpleNamespace(prompt_token_count=2, candidates_token_count=3),
    )
    _sdk(monkeypatch, response=response)
    result = await GoogleAdapter("test-key").complete([{"role": "user", "content": "hi"}])
    assert result.success is False
    assert result.finish_reason == "length"
    assert "token limit" in result.error


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_error", [RuntimeError("429 rate limit"), TimeoutError("timed out"), RuntimeError("401 authentication failed"), RuntimeError("invalid model")])
async def test_complete_normalizes_provider_failures(monkeypatch, provider_error):
    monkeypatch.delenv("ENV", raising=False)
    _sdk(monkeypatch, error=provider_error)
    result = await GoogleAdapter("test-key").complete([{"role": "user", "content": "hi"}])
    assert result.success is False
    assert str(provider_error) in result.error


@pytest.mark.asyncio
async def test_complete_prohibits_network_in_test_mode(monkeypatch):
    monkeypatch.setenv("ENV", "testing")
    result = await GoogleAdapter("test-key").complete([{"role": "user", "content": "hi"}])
    assert result.success is False
    assert "disabled" in result.error.lower()


@pytest.mark.asyncio
async def test_complete_safe_live_inference_path_when_authorized():
    import os
    if os.getenv("ALLOW_LIVE_AI_CALLS_IN_TESTS") != "1":
        pytest.skip("Skipping live inference test (ALLOW_LIVE_AI_CALLS_IN_TESTS!=1)")
    from app.config import settings
    key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not key or key.startswith("placeholder") or key.startswith("AIzaSy_placeholder"):
        pytest.skip("Valid non-placeholder GEMINI_API_KEY required for live test")
    adapter = GoogleAdapter(api_key=key, model="gemini-3.6-flash")
    result = await adapter.complete([{"role": "user", "content": "Respond with PONG"}], max_tokens=1024)
    assert result.success is True
    assert "PONG" in result.content
