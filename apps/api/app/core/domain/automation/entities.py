import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class NodeType(str, Enum):
    TRIGGER = "trigger"
    CONDITION = "condition"
    ACTION = "action"

class WorkflowTriggerType(str, Enum):
    LEAD_CREATED = "lead_created"
    LEAD_UPDATED = "lead_updated"
    WHATSAPP_RECEIVED = "whatsapp_received"
    CALL_ENDED = "call_ended"
    DEAL_MOVED = "deal_moved"
    PAYMENT_RECEIVED = "payment_received"

class WorkflowActionType(str, Enum):
    ASSIGN_LEAD = "assign_lead"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    NOTIFY_MANAGER = "notify_manager"
    RUN_AI_QUALIFICATION = "run_ai_qualification"
    WAIT_DELAY = "wait_delay"

@dataclass
class WorkflowNodeEntity:
    id: str
    node_type: NodeType
    title: str
    action_or_trigger_type: str
    config: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})

@dataclass
class WorkflowEdgeEntity:
    id: str
    source_node_id: str
    target_node_id: str
    condition_label: Optional[str] = None # e.g. "Yes" / "No"

@dataclass
class WorkflowEntity:
    """Pure Domain Entity for a Visual Workflow Automation Definition."""
    id: uuid.UUID
    broker_id: uuid.UUID
    name: str
    description: str
    is_active: bool = True
    trigger_type: WorkflowTriggerType = WorkflowTriggerType.LEAD_CREATED
    nodes: List[WorkflowNodeEntity] = field(default_factory=list)
    edges: List[WorkflowEdgeEntity] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
