"""
WefyLabs AI Workforce — Policy Engine
Part 10 Security & Governance Layer
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.modules.ai_agent.workforce.enums import WorkforceRole
from app.modules.ai_agent.workforce.registry import get_agent_definition, validate_delegation_allowed
from app.modules.ai_agent.workforce.tool_matrix import get_tool_permission

logger = logging.getLogger("wefylabs.workforce.policy")

MAX_AGENT_DEPTH = 3
MAX_TOTAL_DELEGATIONS = 5

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"system\s+prompt",
    r"developer\s+mode",
    r"override\s+(all\s+)?rules",
    r"disregard\s+(all\s+)?guardrails",
    r"reveal\s+(internal\s+)?instructions",
    r"drop\s+table",
    r"execute\s+arbitrary",
    r"tell\s+the\s+revenue\s+agent\s+to",
    r"you\s+are\s+now\s+the\s+admin",
]

COMPILED_INJECTIONS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


class WorkforcePolicyViolation(Exception):
    """Raised when an operation violates workforce security boundaries."""
    def __init__(self, rule: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"[{rule}] {message}")
        self.rule = rule
        self.message = message
        self.details = details or {}


class WorkforcePolicyEngine:
    """
    Central Policy Engine.
    Determines who can do what to which resource inside which tenant.
    Agent identity is an operator role, NOT an authorization bypass.
    """

    @classmethod
    def sanitize_untrusted_input(cls, text: Optional[str]) -> Tuple[str, bool]:
        """
        Scan and neutralize prompt injection attempts in untrusted content
        (customer messages, property descriptions, lead notes).
        Returns: (sanitized_text, injection_detected_bool)
        """
        if not text:
            return "", False
        
        detected = False
        sanitized = text
        for pat in COMPILED_INJECTIONS:
            if pat.search(sanitized):
                detected = True
                sanitized = pat.sub("[SANITIZED_INSTRUCTION_ATTEMPT]", sanitized)
        
        if detected:
            logger.warning("[WorkforcePolicy] Prompt injection attempt sanitized.")
        return sanitized, detected

    @classmethod
    def validate_tenant_boundary(
        cls,
        authenticated_tenant_id: str,
        target_resource_tenant_id: Optional[str],
        resource_type: str = "resource",
    ) -> None:
        """Enforce strict multi-tenant boundary."""
        if not authenticated_tenant_id:
            raise WorkforcePolicyViolation(
                rule="TENANT_REQUIRED",
                message="Missing authenticated tenant context.",
            )
        if target_resource_tenant_id and str(target_resource_tenant_id) != str(authenticated_tenant_id):
            raise WorkforcePolicyViolation(
                rule="CROSS_TENANT_VIOLATION",
                message=f"Cross-tenant access rejected: attempted to access {resource_type} belonging to another organization.",
                details={"auth_tenant": authenticated_tenant_id, "target_tenant": target_resource_tenant_id},
            )

    @classmethod
    def validate_agent_execution_role(
        cls,
        requested_role: WorkforceRole,
        caller_is_internal_manager: bool = False,
        is_customer_facing: bool = True,
    ) -> None:
        """
        Prevent agent role spoofing.
        Internal manager agents cannot be triggered directly by external customers.
        """
        if requested_role == WorkforceRole.MANAGER_COMMAND_AGENT and is_customer_facing and not caller_is_internal_manager:
            raise WorkforcePolicyViolation(
                rule="ROLE_SPOOFING_REJECTED",
                message="MANAGER_COMMAND_AGENT is an internal operational role and cannot be invoked directly by external customers.",
            )

    @classmethod
    def validate_delegation(
        cls,
        from_role: WorkforceRole,
        to_role: WorkforceRole,
        current_depth: int,
        delegation_chain: List[str],
        authenticated_tenant_id: str,
    ) -> None:
        """
        Enforce delegation authorization, depth limits, and cycle prevention.
        """
        # 1. Check if delegation is permitted by registry
        if not validate_delegation_allowed(from_role, to_role):
            raise WorkforcePolicyViolation(
                rule="UNAUTHORIZED_DELEGATION",
                message=f"Agent '{from_role.value}' has no authority to delegate to '{to_role.value}'.",
                details={"from": from_role.value, "to": to_role.value},
            )

        # 2. Check depth ceiling
        if current_depth >= MAX_AGENT_DEPTH:
            raise WorkforcePolicyViolation(
                rule="MAX_AGENT_DEPTH_EXCEEDED",
                message=f"Maximum agent delegation depth of {MAX_AGENT_DEPTH} exceeded.",
                details={"current_depth": current_depth, "max_depth": MAX_AGENT_DEPTH},
            )

        # 3. Check total delegation count
        if len(delegation_chain) >= MAX_TOTAL_DELEGATIONS:
            raise WorkforcePolicyViolation(
                rule="MAX_DELEGATIONS_EXCEEDED",
                message=f"Maximum turn delegation count of {MAX_TOTAL_DELEGATIONS} reached.",
                details={"chain_length": len(delegation_chain)},
            )

        # 4. Cycle detection
        if to_role.value in delegation_chain:
            raise WorkforcePolicyViolation(
                rule="CYCLIC_DELEGATION_DETECTED",
                message=f"Cyclic delegation rejected: '{to_role.value}' is already active in chain: {delegation_chain}.",
                details={"target": to_role.value, "chain": delegation_chain},
            )

    @classmethod
    def validate_tool_call(
        cls,
        role: WorkforceRole,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        """
        Validate tool authorization, confirmation requirements, and arguments before execution.
        """
        # 1. Tool permission matrix check
        perm = get_tool_permission(role, tool_name)
        if not perm.allowed:
            raise WorkforcePolicyViolation(
                rule="UNAUTHORIZED_TOOL",
                message=f"Specialist agent '{role.value}' is not authorized to call tool '{tool_name}'.",
                details={"role": role.value, "tool": tool_name},
            )

        # 2. Confirmation gate
        if perm.confirmation_required:
            is_confirmed = bool(
                context.get("confirmed_action") is True or
                context.get("is_confirmed") is True or
                (context.get("metadata") and context["metadata"].get("confirmed_action") is True)
            )
            if not is_confirmed:
                raise WorkforcePolicyViolation(
                    rule="CONFIRMATION_REQUIRED",
                    message=f"Tool '{tool_name}' causes sensitive side effects and requires explicit confirmation before execution.",
                    details={"tool": tool_name, "arguments": arguments},
                )

        # 3. Tenant scope validation
        auth_org = context.get("organization_id")
        if not auth_org:
            raise WorkforcePolicyViolation(
                rule="TENANT_SCOPE_MISSING",
                message="Tool execution context is missing authenticated organization_id.",
            )
