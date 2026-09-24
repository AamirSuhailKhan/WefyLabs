"""
WefyLabs AI Workforce — Enums and Types
Part 10 Canonical Definitions
"""
from __future__ import annotations
from enum import Enum


class WorkforceRole(str, Enum):
    SALES_AGENT = "sales_agent"
    QUALIFICATION_AGENT = "qualification_agent"
    PROPERTY_ADVISOR = "property_advisor"
    FOLLOW_UP_AGENT = "follow_up_agent"
    APPOINTMENT_ASSISTANT = "appointment_assistant"
    HANDOFF_ASSISTANT = "handoff_assistant"
    REVENUE_COPILOT = "revenue_copilot"
    MANAGER_COMMAND_AGENT = "manager_command_agent"


class AgentCapability(str, Enum):
    READ_ONLY = "read_only"
    READ_WRITE_SUGGEST = "read_write_suggest"
    CONFIRMATION_REQUIRED = "confirmation_required"


class ExecutionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_TOOL = "waiting_tool"
    WAITING_AGENT = "waiting_agent"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class HandoffStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    CONFIRMATION_REQUIRED = "confirmation_required"
    DELEGATED = "delegated"
    FALLBACK = "fallback"
