"""
Part 21.8 — AI Autonomous Sales Loop Taxonomies
================================================
Controlled enumerations for the autonomous sales loop orchestration engine.

NON-NEGOTIABLE PRINCIPLE:
All event types, processing states, automation permissions, and failure classes
are enumerated here. AI may not invent event types or authorization at runtime.
"""
from enum import Enum


class SalesLoopEventType(str, Enum):
    """
    Controlled event taxonomy for the autonomous sales loop.
    36 event types covering the full lead lifecycle from acquisition to conversion.
    """
    # Lead lifecycle
    NEW_LEAD = "NEW_LEAD"
    LEAD_IMPORTED = "LEAD_IMPORTED"
    PROSPECT_NORMALIZED = "PROSPECT_NORMALIZED"
    LEAD_ASSIGNED = "LEAD_ASSIGNED"

    # Qualification
    QUALIFICATION_UPDATED = "QUALIFICATION_UPDATED"
    QUALIFICATION_COMPLETED = "QUALIFICATION_COMPLETED"

    # Customer communication
    CUSTOMER_MESSAGE_RECEIVED = "CUSTOMER_MESSAGE_RECEIVED"
    CUSTOMER_MESSAGE_ANALYZED = "CUSTOMER_MESSAGE_ANALYZED"
    BUYING_SIGNAL_CHANGED = "BUYING_SIGNAL_CHANGED"
    OBJECTION_DETECTED = "OBJECTION_DETECTED"
    NEGOTIATION_DETECTED = "NEGOTIATION_DETECTED"

    # Viewings & appointments
    APPOINTMENT_REQUESTED = "APPOINTMENT_REQUESTED"
    VIEWING_BOOKED = "VIEWING_BOOKED"
    VIEWING_RESCHEDULED = "VIEWING_RESCHEDULED"
    VIEWING_CANCELLED = "VIEWING_CANCELLED"
    VIEWING_COMPLETED = "VIEWING_COMPLETED"

    # Property matching
    PROPERTY_REQUIREMENTS_CHANGED = "PROPERTY_REQUIREMENTS_CHANGED"
    PROPERTY_MATCHES_CHANGED = "PROPERTY_MATCHES_CHANGED"

    # Sales actions
    SALES_ACTION_CREATED = "SALES_ACTION_CREATED"
    SALES_ACTION_APPROVED = "SALES_ACTION_APPROVED"
    SALES_ACTION_REJECTED = "SALES_ACTION_REJECTED"
    SALES_ACTION_EXECUTED = "SALES_ACTION_EXECUTED"

    # Delivery
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_DELIVERED = "MESSAGE_DELIVERED"
    MESSAGE_FAILED = "MESSAGE_FAILED"
    MESSAGE_REPLIED = "MESSAGE_REPLIED"

    # Follow-up scheduling
    FOLLOWUP_SCHEDULED = "FOLLOWUP_SCHEDULED"
    FOLLOWUP_DUE = "FOLLOWUP_DUE"
    FOLLOWUP_CANCELLED = "FOLLOWUP_CANCELLED"

    # Lifecycle milestones
    LEAD_BECAME_INACTIVE = "LEAD_BECAME_INACTIVE"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    BROKER_HANDOFF_REQUIRED = "BROKER_HANDOFF_REQUIRED"
    BROKER_ACTION_COMPLETED = "BROKER_ACTION_COMPLETED"
    LEAD_CONVERTED = "LEAD_CONVERTED"
    LEAD_LOST = "LEAD_LOST"
    LEAD_DORMANT = "LEAD_DORMANT"


class EventProcessingState(str, Enum):
    """Lifecycle states of a persisted domain event during processing."""
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYABLE = "RETRYABLE"
    DEAD_LETTER = "DEAD_LETTER"


class AutomationPermission(str, Enum):
    """
    Deterministic automation permission categories.
    LLMs NEVER decide these — only the AutonomyPolicyEngine does.
    """
    AUTOMATIC = "AUTOMATIC"           # Execute without broker approval
    HUMAN_APPROVAL = "HUMAN_APPROVAL" # Block until broker approves
    FORBIDDEN = "FORBIDDEN"           # Never automate — always fail safe
    SCHEDULED = "SCHEDULED"           # Defer to policy-determined time
    NO_ACTION = "NO_ACTION"           # Nothing to do right now


class FailureClass(str, Enum):
    """Controlled failure classifications for error handling and retry policy."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TENANT_SECURITY_ERROR = "TENANT_SECURITY_ERROR"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    TRANSIENT_PROVIDER_ERROR = "TRANSIENT_PROVIDER_ERROR"
    PERMANENT_PROVIDER_ERROR = "PERMANENT_PROVIDER_ERROR"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CONSENT_BLOCKED = "CONSENT_BLOCKED"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"
    LOOP_PROTECTION_TRIGGERED = "LOOP_PROTECTION_TRIGGERED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class LeadLifecycleState(str, Enum):
    """
    Explicit lead lifecycle states used by the autonomous loop state machine.
    Maps to existing Lead.status + Lead.pipeline_stage (does NOT change Lead DB schema).
    """
    NEW = "NEW"
    CONTACTING = "CONTACTING"
    ENGAGING = "ENGAGING"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    PROPERTY_MATCHED = "PROPERTY_MATCHED"
    VIEWING_PENDING = "VIEWING_PENDING"
    VIEWING_SCHEDULED = "VIEWING_SCHEDULED"
    VIEWING_COMPLETED = "VIEWING_COMPLETED"
    NEGOTIATION = "NEGOTIATION"
    BOOKING = "BOOKING"
    CONVERTED = "CONVERTED"
    # Terminal / exceptional states
    DORMANT = "DORMANT"
    LOST = "LOST"
    OPTED_OUT = "OPTED_OUT"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class GuardName(str, Enum):
    """Named guards in the orchestrator guard chain."""
    CONSENT = "CONSENT"
    QUIET_HOURS = "QUIET_HOURS"
    FATIGUE = "FATIGUE"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    LOOP_PROTECTION = "LOOP_PROTECTION"
    LEAD_LIFECYCLE = "LEAD_LIFECYCLE"
    AUTOMATION_POLICY = "AUTOMATION_POLICY"


class ActorType(str, Enum):
    """Who triggered a lifecycle event or decision."""
    SYSTEM = "SYSTEM"
    AI = "AI"
    BROKER = "BROKER"
    CUSTOMER = "CUSTOMER"
    WEBHOOK = "WEBHOOK"
    SCHEDULER = "SCHEDULER"
