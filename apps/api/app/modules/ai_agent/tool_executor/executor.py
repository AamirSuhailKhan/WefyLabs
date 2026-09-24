"""
Tool Executor — production-grade, wired to real service layer.

Dispatches tool calls → real CRM/Property/Knowledge service methods.
Records immutable ToolExecution audit rows.
Runs read-only tools in parallel; write tools sequentially.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_models import ToolExecution
from app.modules.ai_agent.tool_executor.registry import TOOL_MAP
from app.modules.ai_agent.tool_executor.services import (
    PropertyService, CRMService, KnowledgeService,
    NotificationService, WorkflowService,
    ShortlistService, CalendarSlotService, ComparisonService,
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
    # A result is deliberately explicit: callers must never infer success
    # from an empty object or a null value.
    status: str = "success"  # success | failure | not_found | not_authorized | validation_error | unavailable | conflict | partial


def _validate_tool_call(tool_name: str, arguments: Any, context: Dict[str, Any]) -> Optional[str]:
    """Small, dependency-free schema gate for model-produced tool inputs."""
    definition = TOOL_MAP.get(tool_name)
    if not definition:
        return "Unknown tool"
    if not isinstance(arguments, dict):
        return "Tool arguments must be an object"
    schema = definition.parameters
    for key in schema.get("required", []):
        if arguments.get(key) in (None, "", []):
            return f"Missing required argument: {key}"
    properties = schema.get("properties", {})
    for key, value in arguments.items():
        if key not in properties:
            return f"Unknown argument: {key}"
        if isinstance(value, str) and len(value) > 2000:
            return f"Argument too long: {key}"
        declared_type = properties[key].get("type")
        if declared_type == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            return f"Invalid integer argument: {key}"
        if declared_type == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            return f"Invalid numeric argument: {key}"
        if declared_type == "array" and not isinstance(value, list):
            return f"Invalid array argument: {key}"
        if declared_type == "object" and not isinstance(value, dict):
            return f"Invalid object argument: {key}"
    # ConversationManager always sets enforce_tenant_scope.  Keeping the
    # lower-level executor usable for isolated service tests/migrations avoids
    # accidentally treating a synthetic internal call as a tenant request.
    if definition.tenant_scoped and context.get("enforce_tenant_scope") and not context.get("organization_id"):
        return "Missing tenant authorization context"
    if context.get("enforce_tenant_scope") and tool_name == "get_lead_context" and arguments.get("lead_id") != context.get("lead_id"):
        return "Lead is outside the authorized conversation scope"
    if tool_name == "compare_properties" and len(arguments.get("property_ids", [])) > 4:
        return "At most four properties can be compared"
    if tool_name == "get_available_slots" and not 1 <= arguments.get("days_ahead", 7) <= 31:
        return "days_ahead must be between 1 and 31"
    # Booking is a Part 6 external side effect. It can only happen after a
    # trusted application confirmation, never merely because a model asks.
    if tool_name == "book_viewing" and not context.get("confirmed_action"):
        return "Viewing booking requires explicit customer confirmation"
    return None


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


async def _handle_get_available_slots(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id") or ""
    svc = CalendarSlotService(ctx["db"])
    data = await svc.get_available_slots(
        organization_id=org_id,
        property_id=args.get("property_id"),
        days_ahead=int(args.get("days_ahead", 7)),
    )
    return ToolResult(
        tool="get_available_slots",
        success=True,
        result=data,
        source_verified=data.get("source_verified", False),
        data_source="calendar_service",
    )


async def _handle_create_shortlist(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    lead_id = ctx.get("lead_id", "")
    svc = ShortlistService(ctx["db"])
    data = await svc.add(
        lead_id=lead_id,
        property_id=args["property_id"],
        status=args.get("status", "shortlisted"),
        organization_id=org_id,
        notes=args.get("notes"),
    )
    return ToolResult(
        tool="create_shortlist",
        success=data.get("success", False),
        result=data,
        error=data.get("error") if not data.get("success") else None,
        source_verified=data.get("source_verified", True),
        data_source="crm_service",
    )


async def _handle_get_shortlist(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    lead_id = ctx.get("lead_id", "")
    status_filter = args.get("status_filter")
    if status_filter == "all":
        status_filter = None
    svc = ShortlistService(ctx["db"])
    data = await svc.get(
        lead_id=lead_id,
        organization_id=org_id,
        status_filter=status_filter,
    )
    return ToolResult(
        tool="get_shortlist",
        success=True,
        result=data,
        source_verified=data.get("source_verified", True),
        data_source="crm_service",
    )


async def _handle_compare_properties(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = ctx.get("organization_id") or ctx.get("broker_id")
    property_ids = args.get("property_ids", [])
    if not property_ids:
        return ToolResult(
            tool="compare_properties",
            success=False,
            error="No property_ids provided for comparison",
            source_verified=False,
        )
    # Limit to 4 properties to prevent abuse
    property_ids = property_ids[:4]
    svc = ComparisonService(ctx["db"])
    data = await svc.compare(property_ids=property_ids, organization_id=org_id)
    return ToolResult(
        tool="compare_properties",
        success=True,
        result=data,
        source_verified=data.get("source_verified", True),
        data_source="property_service",
    )


async def _handle_get_handoff_context(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    """
    Builds a structured context summary for the human agent.
    Reads from session context — no external calls needed.
    """
    lead_data = ctx.get("lead_data", {})
    qual = ctx.get("qualification", {})
    shortlist_data: Dict[str, Any] = {}
    if args.get("include_shortlist", True):
        org_id = ctx.get("organization_id")
        lead_id = ctx.get("lead_id", "")
        if lead_id:
            svc = ShortlistService(ctx["db"])
            shortlist_data = await svc.get(
                lead_id=lead_id,
                organization_id=org_id,
                status_filter="shortlisted",
            )
    context_summary = {
        "customer": lead_data,
        "qualification": qual,
        "shortlisted_properties": shortlist_data.get("items", []),
        "handoff_ready": True,
        "source_verified": True,
        "handoff_briefing": {
            "customer": lead_data,
            "buyer_requirements": qual,
            "shortlisted_properties": shortlist_data.get("items", []),
            "handoff_ready": True,
        }
    }
    return ToolResult(
        tool="get_handoff_context",
        success=True,
        result=context_summary,
        source_verified=True,
        data_source="crm_service",
    )


# ─── Part 11 Revenue Intelligence & Copilot Handlers ─────────────────────────

def _to_uuid(val: Any) -> Optional[uuid.UUID]:
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except Exception:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


async def _handle_get_revenue_overview(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.overview.get_overview(org_id)
    return ToolResult(tool="get_revenue_overview", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_funnel_metrics(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.funnel.get_funnel_summary(org_id)
    return ToolResult(tool="get_funnel_metrics", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_leakage_summary(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.leakage.get_leakage_report(org_id)
    return ToolResult(tool="get_leakage_summary", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_source_attribution(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.attribution.get_attribution_report(org_id)
    return ToolResult(tool="get_source_attribution", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_opportunity_flow(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.learning.get_learning_summary(org_id)
    return ToolResult(tool="get_opportunity_flow", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_action_effectiveness(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.outcomes.get_outcome_summary(org_id)
    return ToolResult(tool="get_action_effectiveness", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_outcome_history(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.outcomes.get_outcome_summary(org_id)
    return ToolResult(tool="get_outcome_history", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_data_quality(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.data_quality.get_data_quality_report(org_id)
    return ToolResult(tool="get_data_quality", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_lead_revenue_journey(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    lead_id = _to_uuid(args.get("lead_id") or ctx.get("lead_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.journeys.get_lead_journey(org_id, lead_id)
    return ToolResult(tool="get_lead_revenue_journey", success=data is not None, result=data, data_source="revenue_intelligence")


async def _handle_get_property_conversion_history(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    prop_id = _to_uuid(args.get("property_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.journeys.get_property_journey(org_id, prop_id)
    return ToolResult(tool="get_property_conversion_history", success=data is not None, result=data, data_source="revenue_intelligence")


async def _handle_get_agent_action_history(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    data = await svc.team.get_team_metrics(org_id)
    return ToolResult(tool="get_agent_action_history", success=True, result=data, data_source="revenue_intelligence")


async def _handle_get_revenue_at_risk(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
    org_id = _to_uuid(ctx.get("organization_id") or ctx.get("broker_id"))
    from app.modules.revenue_intelligence.service import RevenueIntelligenceService
    svc = RevenueIntelligenceService(ctx["db"])
    rep = await svc.leakage.get_leakage_report(org_id)
    return ToolResult(
        tool="get_revenue_at_risk",
        success=True,
        result={
            "total_estimated_value_at_risk_estimate": rep.get("total_estimated_value_at_risk_estimate"),
            "revenue_at_risk_estimate": rep.get("total_estimated_value_at_risk_estimate"),
            "total_leakage_events": rep.get("total_leakage_events"),
        },
        data_source="revenue_intelligence",
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
    # New tools (Slice B)
    "get_available_slots":  _handle_get_available_slots,
    "create_shortlist":     _handle_create_shortlist,
    "get_shortlist":        _handle_get_shortlist,
    "compare_properties":   _handle_compare_properties,
    "get_handoff_context":  _handle_get_handoff_context,
    # Part 11 Revenue Intelligence & Copilot Tools
    "get_revenue_overview":             _handle_get_revenue_overview,
    "get_funnel_metrics":               _handle_get_funnel_metrics,
    "get_leakage_summary":              _handle_get_leakage_summary,
    "get_source_attribution":           _handle_get_source_attribution,
    "get_opportunity_flow":             _handle_get_opportunity_flow,
    "get_action_effectiveness":         _handle_get_action_effectiveness,
    "get_outcome_history":              _handle_get_outcome_history,
    "get_data_quality":                 _handle_get_data_quality,
    "get_lead_revenue_journey":         _handle_get_lead_revenue_journey,
    "get_property_conversion_history":  _handle_get_property_conversion_history,
    "get_agent_action_history":         _handle_get_agent_action_history,
    "get_revenue_at_risk":              _handle_get_revenue_at_risk,
}

_READ_TOOLS = {
    "search_properties", "check_availability",
    "search_knowledge", "get_lead_context", "get_payment_plan",
    # New read tools
    "get_available_slots", "get_shortlist", "compare_properties", "get_handoff_context",
    # Part 11 Revenue Copilot read tools
    "get_revenue_overview", "get_funnel_metrics", "get_leakage_summary",
    "get_source_attribution", "get_opportunity_flow", "get_action_effectiveness",
    "get_outcome_history", "get_data_quality", "get_lead_revenue_journey",
    "get_property_conversion_history", "get_agent_action_history", "get_revenue_at_risk",
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
        validation_error = _validate_tool_call(tool_name, arguments, ctx)
        if validation_error:
            status = "not_authorized" if "authorized" in validation_error or "scope" in validation_error or "confirmation" in validation_error else "validation_error"
            result = ToolResult(
                tool=tool_name, success=False, error=validation_error,
                source_verified=False, status=status,
            )
        elif not handler:
            result = ToolResult(
                tool=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
                source_verified=False,
                status="validation_error",
            )
        else:
            t0 = time.monotonic()
            try:
                result = await handler(arguments, ctx)
            except Exception as exc:
                result = ToolResult(
                    tool=tool_name, success=False,
                    error=str(exc), source_verified=False, status="unavailable",
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
        # Execute tools in order, safely handling session flush
        results = []
        for tc in tool_calls:
            res = await self.run(db, session_id, turn_index, tc["name"], tc.get("arguments", {}), context)
            results.append(res)
        return results
