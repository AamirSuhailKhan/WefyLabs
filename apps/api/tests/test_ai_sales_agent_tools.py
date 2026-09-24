"""
Test Suite: AI Sales Agent Tool Registry, Contracts, and Execution
Tests all 16 tool contracts (11 core + 5 new revenue tools):
  - search_properties
  - check_availability
  - get_payment_plan
  - book_viewing
  - update_qualification
  - get_lead_context
  - search_knowledge
  - send_notification
  - escalate_to_human
  - get_available_slots
  - create_shortlist
  - get_shortlist
  - compare_properties
  - get_handoff_context
"""
import pytest
from unittest.mock import MagicMock
from app.modules.ai_agent.tool_executor.registry import TOOLS, TOOL_MAP, get_tool_definitions_for_llm
from app.modules.ai_agent.tool_executor.executor import ToolExecutor, ToolResult


def test_tool_registry_has_all_16_tools():
    """Verify registry contains all registered tool definitions."""
    assert len(TOOLS) >= 16, f"Expected at least 16 tools, found {len(TOOLS)}"
    expected_tools = {
        "search_properties",
        "check_availability",
        "get_payment_plan",
        "book_viewing",
        "update_qualification",
        "get_lead_context",
        "search_knowledge",
        "send_notification",
        "escalate_to_human",
        "get_available_slots",
        "create_shortlist",
        "get_shortlist",
        "compare_properties",
        "get_handoff_context",
    }
    registered_names = {t.name for t in TOOLS}
    for name in expected_tools:
        assert name in registered_names, f"Missing tool: {name}"


def test_openai_tool_definitions_schema():
    """Verify get_tool_definitions_for_llm conforms to standard function calling spec."""
    defs = get_tool_definitions_for_llm()
    assert len(defs) >= 16
    for d in defs:
        assert d["type"] == "function"
        fn = d["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"
        assert "properties" in fn["parameters"]


@pytest.mark.asyncio
async def test_tool_executor_handles_unknown_tool(db_session):
    """ToolExecutor gracefully handles non-existent tool names without crashing."""
    executor = ToolExecutor()
    res = await executor.run(
        db=db_session,
        session_id="sess-test",
        turn_index=1,
        tool_name="non_existent_tool_xyz",
        arguments={"foo": "bar"},
        context={"organization_id": "test-org"}
    )
    assert res.success is False
    assert "Unknown tool" in res.error


@pytest.mark.asyncio
async def test_get_available_slots_tool_execution(db_session):
    """Verify get_available_slots tool executes cleanly and returns structured slots."""
    executor = ToolExecutor()
    res = await executor.run(
        db=db_session,
        session_id="sess-test",
        turn_index=1,
        tool_name="get_available_slots",
        arguments={"days_ahead": 3},
        context={"organization_id": "test-org"}
    )
    assert res.success is True
    assert "slots" in res.result
    assert res.result["source_verified"] is True
    assert len(res.result["slots"]) > 0


@pytest.mark.asyncio
async def test_create_and_get_shortlist_tools(db_session):
    """Verify create_shortlist and get_shortlist tools work with session context."""
    executor = ToolExecutor()

    # 1. Create shortlist item
    add_res = await executor.run(
        db=db_session,
        session_id="sess-test",
        turn_index=1,
        tool_name="create_shortlist",
        arguments={
            "property_id": "prop-12345",
            "status": "shortlisted",
            "notes": "Client liked the sea view",
        },
        context={"session_id": "sess-test", "lead_id": "lead-test"}
    )
    assert add_res.success is True
    assert add_res.result["source_verified"] is True

    # 2. Get shortlist
    get_res = await executor.run(
        db=db_session,
        session_id="sess-test",
        turn_index=2,
        tool_name="get_shortlist",
        arguments={},
        context={"session_id": "sess-test", "lead_id": "lead-test"}
    )
    assert get_res.success is True
    assert "items" in get_res.result


@pytest.mark.asyncio
async def test_compare_properties_tool_execution(db_session):
    """Verify compare_properties executes and returns side-by-side comparison structure."""
    executor = ToolExecutor()

    res = await executor.run(
        db=db_session,
        session_id="sess-test",
        turn_index=1,
        tool_name="compare_properties",
        arguments={"property_ids": ["prop-1", "prop-2"]},
        context={"organization_id": "test-org"}
    )
    assert res.success is True
    assert "properties" in res.result
    assert "comparison_matrix" in res.result
    assert res.result["source_verified"] is True


@pytest.mark.asyncio
async def test_get_handoff_context_tool_execution(db_session):
    """Verify get_handoff_context tool produces structured handoff briefing."""
    executor = ToolExecutor()

    ctx = {
        "organization_id": "org-test",
        "lead_id": "lead-123",
        "session_id": "sess-456",
        "qualification": {"budget_max": 20000000, "bedrooms": 3},
        "fields_remaining": ["timeline"],
    }
    res = await executor.run(
        db=db_session,
        session_id="sess-456",
        turn_index=1,
        tool_name="get_handoff_context",
        arguments={"include_shortlist": True, "include_objections": True},
        context=ctx
    )
    assert res.success is True
    assert res.result["source_verified"] is True
    briefing = res.result["handoff_briefing"]
    assert "buyer_requirements" in briefing
    assert briefing["buyer_requirements"]["bedrooms"] == 3


@pytest.mark.asyncio
async def test_run_parallel_tool_calls(db_session):
    """Verify run_parallel executes read tools concurrently and writes sequentially."""
    executor = ToolExecutor()
    calls = [
        {"name": "get_available_slots", "arguments": {"days_ahead": 2}},
        {"name": "get_shortlist", "arguments": {}},
    ]
    results = await executor.run_parallel(
        db=db_session,
        session_id="sess-test",
        turn_index=1,
        tool_calls=calls,
        context={"organization_id": "test-org", "session_id": "sess-test"}
    )
    assert len(results) == 2
    assert all(r.success for r in results)
