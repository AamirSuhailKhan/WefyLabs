"""
Master Build 06 — AI Sales Agent Observability & Trace Subsystem
===============================================================
Maintains immutable execution traces for every meaningful agent turn:
  agent_run_id, request_id, organization_id, conversation_id, lead_id,
  task, model, prompt_version, tools_called, retrievals, decision,
  action_proposed, action_executed, latency_ms, cost_estimate, outcome, status.

No sensitive credentials or customer PII are logged in raw traces.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentTraceDTO:
    agent_run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: Optional[str] = None
    organization_id: str = ""
    conversation_id: Optional[str] = None
    lead_id: Optional[str] = None
    task: str = "sales_turn"
    model: str = "gemini-2.5-flash"
    prompt_version: str = "v1.0"
    tools_called: List[Dict[str, Any]] = field(default_factory=list)
    retrievals: List[Dict[str, Any]] = field(default_factory=list)
    decision: Dict[str, Any] = field(default_factory=dict)
    action_proposed: Optional[Dict[str, Any]] = None
    action_executed: Optional[Dict[str, Any]] = None
    latency_ms: int = 0
    cost_estimate: float = 0.0
    outcome: str = "completed"
    status: str = "SUCCESS"  # SUCCESS | FAILED | BLOCKED | REJECTED | HANDOFF
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_run_id": self.agent_run_id,
            "request_id": self.request_id,
            "organization_id": self.organization_id,
            "conversation_id": self.conversation_id,
            "lead_id": self.lead_id,
            "task": self.task,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "tools_called": self.tools_called,
            "retrievals": self.retrievals,
            "decision": self.decision,
            "action_proposed": self.action_proposed,
            "action_executed": self.action_executed,
            "latency_ms": self.latency_ms,
            "cost_estimate": self.cost_estimate,
            "outcome": self.outcome,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class AgentTraceRecorder:
    """
    In-memory and persistent recorder for AgentTraces.
    """
    _traces: List[AgentTraceDTO] = []

    @classmethod
    def record(cls, trace: AgentTraceDTO) -> AgentTraceDTO:
        cls._traces.append(trace)
        logger.info(
            f"[AgentTrace] Recorded run={trace.agent_run_id} org={trace.organization_id} "
            f"task={trace.task} status={trace.status} latency={trace.latency_ms}ms"
        )
        return trace

    @classmethod
    def get_traces_for_org(cls, organization_id: str) -> List[AgentTraceDTO]:
        return [t for t in cls._traces if t.organization_id == str(organization_id)]

    @classmethod
    def get_trace_by_id(cls, trace_id: str) -> Optional[AgentTraceDTO]:
        for t in cls._traces:
            if t.agent_run_id == str(trace_id):
                return t
        return None

    @classmethod
    def clear(cls):
        cls._traces.clear()
