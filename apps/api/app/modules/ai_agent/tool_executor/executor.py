"""
Tool Executor — production-grade, wired to real service layer.

Dispatches tool calls → real CRM/Property/Knowledge service methods.
Records immutable ToolExecution audit rows.
Runs read-only tools in parallel; write tools sequentially.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_models import ToolExecution
from app.modules.ai_agent.tool_executor.registry import TOOL_MAP
from app.modules.ai_agent.tool_executor.services import (
    PropertyService, CRMService, KnowledgeService,
    NotificationService, WorkflowService
)


# ─── ToolResult ──────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    tool: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    source_verified: bool = True
    duration_ms: int = 0
    data_source: Optional[str] = None


# ─── Production Tool Handlers ─────────────────────────────────────────────────

async def _handle_search_properties(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    svc = PropertyService(ctx["db"])
    data = await svc.search(
        property_type=args.get("property_type"),
        bedrooms=args.get("bedrooms"),
        budget_max=args.get("budget_max"),
        locations=args.get("locations"),
        purpose=args.get("purpose"),
        limit=int(args.get("limit", 3)),
        organization_id=org_id,
    )
    return ToolResult(
        tool="search_properties",
        success=True,
        result=data,
        source_verified=data.get("source_verified", True),
        data_source="property_service",
    )


async def _handle_check_availability(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    svc = PropertyService(ctx["db"])
    data = await svc.check_availability(args["property_id"], organization_id=org_id)
    return ToolResult(
        tool="check_availability",
        success=True,
        result=data,
        source_verified=data.get("source_verified", True),
        data_source="property_service",
    )


async def _handle_get_payment_plan(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    svc = PropertyService(ctx["db"])
    data = await svc.get_payment_plan(args["property_id"], organization_id=org_id)
    return ToolResult(
        tool="get_payment_plan",
        success=True,
        result=data,
        source_verified=data.get("source_verified", True),
        data_source="property_service",
    )


async def _handle_book_viewing(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    svc = CRMService(ctx["db"])
    data = await svc.create_meeting(
        lead_id=ctx.get("lead_id", ""),
        property_id=args["property_id"],
        preferred_date=args["preferred_date"],
        preferred_time=args.get("preferred_time"),
        notes=args.get("notes"),
        organization_id=org_id,
    )
    success = data.get("booking_id") is not None
    return ToolResult(
        tool="book_viewing",
        success=success,
        result=data,
        error=data.get("error") if not success else None,
        source_verified=data.get("source_verified", True),
        data_source="crm_service",
    )


async def _handle_update_qualification(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    # Qualification updates are handled by ConversationManager._patch_qualification
    # after tool execution. The tool signals intent only.
    return ToolResult(
        tool="update_qualification",
        success=True,
        result={"updated_fields": list(args.keys()), "stored": True, "pending_crm_patch": True},
        data_source="crm_service",
    )


async def _handle_update_lead_crm(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    svc = CRMService(ctx["db"])
    ok = await svc.update_lead(
        lead_id=ctx.get("lead_id", ""),
        status=args.get("status"),
        pipeline_stage=args.get("pipeline_stage"),
        notes=args.get("notes"),
        organization_id=org_id,
    )
    return ToolResult(
        tool="update_lead_crm",
        success=ok,
        result={"updated": ok, "fields": list(args.keys())},
        error=None if ok else "CRM update failed",
        data_source="crm_service",
    )


async def _handle_search_knowledge(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id") or ""
    svc = KnowledgeService(ctx["db"])
    data = await svc.search(
        query=args["query"],
        organization_id=org_id,
        category=args.get("category"),
    )
    return ToolResult(
        tool="search_knowledge",
        success=True,
        result=data,
        source_verified=data.get("source_verified", True),
        data_source="knowledge_service",
    )


async def _handle_get_lead_context(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    svc = CRMService(ctx["db"])
    lead = await svc.get_lead(args["lead_id"], organization_id=org_id)
    return ToolResult(
        tool="get_lead_context",
        success=lead is not None,
        result={"lead_id": args["lead_id"], "profile": lead or {}},
        error=None if lead else "Lead not found",
        data_source="crm_service",
    )


async def _handle_trigger_workflow(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    svc = WorkflowService(ctx["db"])
    ok = await svc.trigger(
        workflow_name=args["workflow_name"],
        payload=args.get("payload"),
    )
    return ToolResult(
        tool="trigger_workflow",
        success=ok,
        result={"workflow": args["workflow_name"], "triggered": ok},
        error=None if ok else "Workflow trigger failed",
        data_source="workflow_service",
    )


async def _handle_send_notification(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    svc = NotificationService(ctx["db"])
    ok = await svc.send(
        organization_id=ctx.get("organization_id", ""),
        message=args["message"],
        priority=args.get("priority", "medium"),
        lead_id=ctx.get("lead_id"),
    )
    return ToolResult(
        tool="send_notification",
        success=ok,
        result={"sent": ok, "message": args["message"]},
        error=None if ok else "Notification send failed",
        data_source="notification_service",
    )


async def _handle_escalate_to_human(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    # Actual escalation record is created by HandoffService in ConversationManager.
    # This tool signals the intent — the manager acts on it via DecisionEngine.
    return ToolResult(
        tool="escalate_to_human",
        success=True,
        result={
            "escalated": True,
            "reason": args["reason"],
            "priority": args.get("priority", "medium"),
        },
        data_source="crm_service",
    )


# ─── Handler Registry ─────────────────────────────────────────────────────────

_HANDLERS: Dict[str, Callable] = {
    "search_properties":    _handle_search_properties,
    "check_availability":   _handle_check_availability,
    "get_payment_plan":     _handle_get_payment_plan,
    "book_viewing":         _handle_book_viewing,
    "update_qualification": _handle_update_qualification,
    "update_lead_crm":      _handle_update_lead_crm,
    "search_knowledge":     _handle_search_knowledge,
    "get_lead_context":     _handle_get_lead_context,
    "trigger_workflow":     _handle_trigger_workflow,
    "send_notification":    _handle_send_notification,
    "escalate_to_human":    _handle_escalate_to_human,
}

_READ_TOOLS = {
    "search_properties", "check_availability",
    "search_knowledge", "get_lead_context", "get_payment_plan"
}


# ─── Tool Executor ────────────────────────────────────────────────────────────

class ToolExecutor:
    """
    Production tool executor.
    - Dispatches to real CRM/Property/Knowledge service layer.
    - Writes immutable ToolExecution audit row for every call.
    - Parallel execution for read-only tools; sequential for writes.
    """

    async def run(
        self,
        db: AsyncSession,
        session_id: str,
        turn_index: int,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        ctx = {**(context or {}), "db": db}
        handler = _HANDLERS.get(tool_name)
        if not handler:
            result = ToolResult(
                tool=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
                source_verified=False,
            )
        else:
            t0 = time.monotonic()
            try:
                result = await handler(arguments, ctx)
            except Exception as exc:
                result = ToolResult(
                    tool=tool_name, success=False,
                    error=str(exc), source_verified=False,
                )
            result.duration_ms = int((time.monotonic() - t0) * 1000)

        execution = ToolExecution(
            session_id=session_id,
            turn_index=turn_index,
            tool_name=tool_name,
            input_json=arguments,
            output_json={"result": result.result, "error": result.error},
            duration_ms=result.duration_ms,
            success=result.success,
            error_message=result.error,
            source_verified=result.source_verified,
            data_source=result.data_source,
        )
        db.add(execution)
        await db.flush()
        return result

    async def run_parallel(
        self,
        db: AsyncSession,
        session_id: str,
        turn_index: int,
        tool_calls: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ToolResult]:
        read_calls = [tc for tc in tool_calls if tc["name"] in _READ_TOOLS]
        write_calls = [tc for tc in tool_calls if tc["name"] not in _READ_TOOLS]

        read_tasks = [
            self.run(db, session_id, turn_index, tc["name"], tc.get("arguments", {}), context)
            for tc in read_calls
        ]
        read_results = list(await asyncio.gather(*read_tasks, return_exceptions=False))

        write_results = []
        for tc in write_calls:
            res = await self.run(db, session_id, turn_index, tc["name"], tc.get("arguments", {}), context)
            write_results.append(res)

        return read_results + write_results
