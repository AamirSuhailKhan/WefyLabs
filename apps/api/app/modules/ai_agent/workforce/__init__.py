"""
WefyLabs AI Workforce Module
Part 10 Canonical Multi-Agent Architecture
"""
from __future__ import annotations

from app.modules.ai_agent.workforce.enums import WorkforceRole, AgentCapability, ExecutionState, HandoffStatus
from app.modules.ai_agent.workforce.protocols import (
    AgentHandoffDTO, AgentResultDTO, ActionReceiptDTO, WorkforceSessionTrace, WorkforceTraceStep
)
from app.modules.ai_agent.workforce.registry import (
    AgentDefinition, WORKFORCE_REGISTRY, get_agent_definition, list_registered_agents, validate_delegation_allowed
)
from app.modules.ai_agent.workforce.tool_matrix import ToolPermission, get_tool_permission, is_tool_authorized
from app.modules.ai_agent.workforce.policy import (
    WorkforcePolicyEngine, WorkforcePolicyViolation, MAX_AGENT_DEPTH, MAX_TOTAL_DELEGATIONS
)
from app.modules.ai_agent.workforce.context import WorkforceContextBuilder
from app.modules.ai_agent.workforce.router import WorkforceRouter, RoutingDecision
from app.modules.ai_agent.workforce.orchestrator import WorkforceOrchestrator
from app.modules.ai_agent.workforce.controller import router as workforce_router

__all__ = [
    "WorkforceRole",
    "AgentCapability",
    "ExecutionState",
    "HandoffStatus",
    "AgentHandoffDTO",
    "AgentResultDTO",
    "ActionReceiptDTO",
    "WorkforceSessionTrace",
    "WorkforceTraceStep",
    "AgentDefinition",
    "WORKFORCE_REGISTRY",
    "get_agent_definition",
    "list_registered_agents",
    "validate_delegation_allowed",
    "ToolPermission",
    "get_tool_permission",
    "is_tool_authorized",
    "WorkforcePolicyEngine",
    "WorkforcePolicyViolation",
    "MAX_AGENT_DEPTH",
    "MAX_TOTAL_DELEGATIONS",
    "WorkforceContextBuilder",
    "WorkforceRouter",
    "RoutingDecision",
    "WorkforceOrchestrator",
    "workforce_router",
]
