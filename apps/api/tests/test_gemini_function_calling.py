"""
Test Suite: Gemini Function Calling Adapter
Tests:
  - Tool definition schema conversion (OpenAI -> google-genai)
  - Tool call extraction from Gemini SDK response objects
  - Text response extraction
  - Graceful fallback when function calls are absent or tool calls fail
"""
import pytest
from unittest.mock import MagicMock
from app.modules.ai_agent.llm_router.adapters.google_adapter import (
    _convert_tools_to_genai,
    _extract_tool_calls,
    _extract_text,
    GoogleAdapter,
)


def test_convert_tools_to_genai_empty():
    """Empty tool list returns empty list."""
    res = _convert_tools_to_genai([])
    assert res == []


def test_convert_tools_to_genai_standard_schema():
    """Converts OpenAI-style tool schema to google-genai Tool with FunctionDeclaration."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_properties",
                "description": "Search properties by criteria",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "budget_max": {"type": "number"},
                        "bedrooms": {"type": "integer"},
                    },
                    "required": ["budget_max"],
                },
            },
        }
    ]
    genai_tools = _convert_tools_to_genai(tools)
    assert len(genai_tools) == 1
    # Check that function declaration was created
    tool_obj = genai_tools[0]
    # Function declarations attribute exists
    assert hasattr(tool_obj, "function_declarations")
    decls = tool_obj.function_declarations
    assert len(decls) == 1
    decl = decls[0]
    assert decl.name == "search_properties"
    assert decl.description == "Search properties by criteria"


def test_extract_tool_calls_from_response():
    """Extracts function calls and arguments from mock response candidates."""
    mock_resp = MagicMock()
    mock_candidate = MagicMock()
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_fc = MagicMock()
    mock_fc.name = "search_properties"
    mock_fc.args = {"budget_max": 15000000, "bedrooms": 3}
    mock_part.function_call = mock_fc
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    mock_resp.candidates = [mock_candidate]
    # delete response.text attribute to simulate pure function call
    del mock_resp.text

    tool_calls = _extract_tool_calls(mock_resp)
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "search_properties"
    assert tool_calls[0]["arguments"] == {"budget_max": 15000000, "bedrooms": 3}


def test_extract_text_from_response():
    """Extracts text content correctly from response.text or candidate parts."""
    # Case 1: has .text
    mock_resp = MagicMock()
    mock_resp.text = "Hello! I can help you find your dream home."
    assert _extract_text(mock_resp) == "Hello! I can help you find your dream home."

    # Case 2: falls back to parts
    mock_resp2 = MagicMock()
    del mock_resp2.text
    part = MagicMock()
    part.text = "Fallback text from candidate part"
    part.function_call = None
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [part]
    mock_resp2.candidates = [mock_candidate]
    assert _extract_text(mock_resp2) == "Fallback text from candidate part"


@pytest.mark.asyncio
async def test_google_adapter_unconfigured_fallback():
    """Adapter returns graceful failure when API key is unconfigured."""
    adapter = GoogleAdapter(api_key=None, model="gemini-2.5-flash")
    messages = [{"role": "user", "content": "Hello"}]
    res = await adapter.complete(messages=messages, tools=None)
    assert res.success is False
    assert res.provider == "google"
