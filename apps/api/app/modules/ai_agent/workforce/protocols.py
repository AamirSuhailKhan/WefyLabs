"""
WefyLabs AI Workforce — Protocols, DTOs & Contracts
Part 10 Structured Communications Architecture
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.modules.ai_agent.workforce.enums import WorkforceRole, HandoffStatus, ExecutionState


class ActionReceiptDTO(BaseModel):
    """Authoritative execution receipt for verifiable state changes."""
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str
    status: str = "success"  # success | confirmation_required | rejected | failed
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_verified: bool = True
    details: Dict[str, Any] = Field(default_factory=dict)


class AgentHandoffDTO(BaseModel):
    """
    Structured delegation/handoff contract between specialist agents.
    Never passes arbitrary hidden model state or unbounded transcripts.
    """
    from_agent: WorkforceRole
    to_agent: WorkforceRole
    tenant_id: str
    lead_id: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    objective: str
    relevant_context: Dict[str, Any] = Field(default_factory=dict)
    requested_action: Optional[str] = None
    depth: int = 1
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    delegation_chain: List[str] = Field(default_factory=list)


class AgentResultDTO(BaseModel):
    """
    Structured response returned by every specialist agent.
    Never returns unvalidated free-form raw model completions.
    """
    agent_id: WorkforceRole
    status: HandoffStatus = HandoffStatus.SUCCESS
    summary: str
    data: Dict[str, Any] = Field(default_factory=dict)
    recommended_next_action: Optional[str] = None
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    handoff_needed: bool = False
    handoff_target: Optional[WorkforceRole] = None
    confirmation_required: bool = False
    confirmation_action: Optional[str] = None
    receipt: Optional[ActionReceiptDTO] = None
    duration_ms: int = 0
    fallback_used: bool = False


class WorkforceTraceStep(BaseModel):
    step_index: int
    agent_role: WorkforceRole
    state: ExecutionState
    tool_name: Optional[str] = None
    tool_status: Optional[str] = None
    delegation_target: Optional[WorkforceRole] = None
    policy_outcome: str = "allowed"
    summary: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0


class WorkforceSessionTrace(BaseModel):
    """
    Concise operational audit trace for a turn.
    Strictly NO chain-of-thought or hidden reasoning tokens stored.
    """
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    tenant_id: str
    lead_id: str
    initial_query: str
    routing_decision: WorkforceRole
    routing_reason: str
    steps: List[WorkforceTraceStep] = Field(default_factory=list)
    delegations: List[str] = Field(default_factory=list)
    tools_called: List[str] = Field(default_factory=list)
    policy_outcomes: List[str] = Field(default_factory=list)
    final_response: str
    total_duration_ms: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
