"""
Pydantic V2 DTO Schemas for Workflow Automation Engine
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# ─── Workflow Definition DTOs ──────────────────────────────────────────────────

class CreateWorkflowDefinitionRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: str = Field("lead_lifecycle", max_length=50)
    trigger_type: str = Field("LeadCreated", max_length=100)
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    variables_schema: Dict[str, Any] = Field(default_factory=dict)


class UpdateWorkflowDefinitionRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    variables_schema: Optional[Dict[str, Any]] = None


class WorkflowVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_definition_id: str
    version_number: int
    nodes_json: List[Dict[str, Any]]
    edges_json: List[Dict[str, Any]]
    variables_schema: Dict[str, Any]
    published_by: Optional[str] = None
    published_at: datetime


class WorkflowDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    category: str
    trigger_type: str
    trigger_config_json: Dict[str, Any]
    status: str
    active_version_number: int
    is_active: bool
    created_by: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ─── Execution Instance DTOs ───────────────────────────────────────────────────

class ExecuteWorkflowRequest(BaseModel):
    entity_id: str = Field(..., description="ID of the target entity (e.g. lead_id, deal_id)")
    entity_type: str = Field("LEAD", description="LEAD | OPPORTUNITY | MEETING")
    payload: Dict[str, Any] = Field(default_factory=dict)
    is_test_run: bool = False


class WorkflowNodeExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    node_id: str
    node_type: str
    node_name: str
    status: str
    output_snapshot: Dict[str, Any]
    error_details: Optional[str] = None
    duration_ms: float
    executed_at: datetime


class WorkflowInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_definition_id: str
    workflow_version_id: str
    organization_id: str
    entity_id: str
    entity_type: str
    status: str
    current_node_id: Optional[str] = None
    context_data: Dict[str, Any]
    error_message: Optional[str] = None
    is_test_run: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    node_executions: Optional[List[WorkflowNodeExecutionResponse]] = None


# ─── Approval DTOs ─────────────────────────────────────────────────────────────

class DecideApprovalRequest(BaseModel):
    decision: str = Field(..., description="APPROVED | REJECTED")
    reason: Optional[str] = None


class WorkflowApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_instance_id: str
    node_id: str
    organization_id: str
    title: str
    description: str
    context_summary: Dict[str, Any]
    status: str
    assigned_role: str
    decision_by: Optional[str] = None
    decision_reason: Optional[str] = None
    decision_at: Optional[datetime] = None
    deadline_utc: datetime


# ─── Template & AI DTOs ────────────────────────────────────────────────────────

class WorkflowTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_key: str
    name: str
    description: str
    category: str
    trigger_type: str
    nodes_json: List[Dict[str, Any]]
    edges_json: List[Dict[str, Any]]


class AIGenerateWorkflowRequest(BaseModel):
    prompt: str = Field(..., description="Natural language workflow prompt")


class ValidateWorkflowResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
