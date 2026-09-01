"""
Workflow Automation & Autonomous Revenue Operations Engine REST API Router
===========================================================================
Endpoints for:
- Workflow Definitions, Node Graphs & Version Freezing
- Graph Topology Validation (Cycle / Orphan Detection)
- Durable Execution Runs & Historical Tracing
- Human-in-the-Loop Approval Decision Gates
- Dry Run & Historical What-If Simulation
- Natural Language Prompt-to-Workflow Compilation
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.workflow.service import WorkflowService
from app.modules.workflow.dto.workflow_schemas import (
    CreateWorkflowDefinitionRequest, UpdateWorkflowDefinitionRequest,
    WorkflowDefinitionResponse, WorkflowInstanceResponse,
    WorkflowApprovalResponse, DecideApprovalRequest,
    ValidateWorkflowResponse, AIGenerateWorkflowRequest
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/workflows", tags=["Workflow Automation & Revenue Operations"])

# ─── Workflow Definitions ──────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[WorkflowDefinitionResponse],
    summary="List Workflow Definitions"
)
async def list_workflows(
    status: Optional[str] = Query(None),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists all workflow definitions for the current organization."""
    service = WorkflowService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.list_definitions(org_id, status)


@router.post(
    "",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Workflow Definition"
)
async def create_workflow(
    req: CreateWorkflowDefinitionRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new draft workflow with an initial DAG node graph."""
    service = WorkflowService(db)
    org_id = str(current_broker.organization_id or "org_default")
    creator = str(current_broker.email or current_broker.name or "admin")
    return await service.create_definition(
        organization_id=org_id,
        name=req.name,
        description=req.description,
        category=req.category,
        trigger_type=req.trigger_type,
        trigger_config=req.trigger_config,
        nodes=req.nodes,
        edges=req.edges,
        variables_schema=req.variables_schema,
        created_by=creator
    )


@router.get(
    "/{workflow_id}",
    response_model=WorkflowDefinitionResponse,
    summary="Get Workflow Definition Graph"
)
async def get_workflow(
    workflow_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves full workflow definition."""
    service = WorkflowService(db)
    wf = await service.get_definition(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return wf


@router.post(
    "/{workflow_id}/validate",
    response_model=ValidateWorkflowResponse,
    summary="Validate DAG Graph Topology"
)
async def validate_workflow(
    workflow_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Checks graph for cycles, orphan nodes, and schema errors."""
    service = WorkflowService(db)
    res = await service.validate_definition(workflow_id)
    return res.to_dict()


@router.post(
    "/{workflow_id}/publish",
    response_model=WorkflowDefinitionResponse,
    summary="Publish & Freeze Workflow Version"
)
async def publish_workflow(
    workflow_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Validates and publishes the workflow, making it immutable and active for triggers."""
    service = WorkflowService(db)
    publisher = str(current_broker.email or current_broker.name or "admin")
    try:
        return await service.publish_definition(workflow_id, published_by=publisher)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# ─── Execution Runs ────────────────────────────────────────────────────────────

@router.post(
    "/{workflow_id}/execute",
    response_model=WorkflowInstanceResponse,
    summary="Trigger Workflow Execution"
)
async def execute_workflow(
    workflow_id: str,
    entity_id: str = Query(..., description="Target lead or deal ID"),
    is_test_run: bool = Query(False, description="Dry run mode without side effects"),
    payload: Dict[str, Any] = {},
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Executes a workflow run for a target entity."""
    service = WorkflowService(db)
    org_id = str(current_broker.organization_id or "org_default")
    try:
        instance = await service.execute_workflow(
            workflow_id=workflow_id,
            entity_id=entity_id,
            organization_id=org_id,
            payload=payload,
            is_test_run=is_test_run
        )
        return instance
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get(
    "/runs",
    response_model=List[WorkflowInstanceResponse],
    summary="List Execution Run History"
)
async def list_runs(
    workflow_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists execution runs and node statuses."""
    service = WorkflowService(db)
    org_id = str(current_broker.organization_id or "org_default")
    return await service.list_instances(org_id, workflow_id, status)


@router.get(
    "/runs/{run_id}",
    response_model=WorkflowInstanceResponse,
    summary="Get Detailed Run Trace"
)
async def get_run_details(
    run_id: str,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves step-by-step execution trace for a run."""
    service = WorkflowService(db)
    instance = await service.get_instance(run_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return instance


# ─── Approvals & Simulation ────────────────────────────────────────────────────

@router.post(
    "/approvals/{approval_id}/decide",
    response_model=WorkflowApprovalResponse,
    summary="Decide Human Approval Gate"
)
async def decide_approval(
    approval_id: str,
    req: DecideApprovalRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Resolves a human approval gate (APPROVED | REJECTED) and resumes workflow execution."""
    service = WorkflowService(db)
    decider = str(current_broker.email or current_broker.name or "manager")
    try:
        return await service.decide_approval(approval_id, req.decision, decider, req.reason)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post(
    "/{workflow_id}/simulate",
    summary="Run Historical What-If Simulation"
)
async def simulate_workflow_endpoint(
    workflow_id: str,
    sample_size: int = Query(50, ge=5, le=500),
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Simulates workflow path and cost over historical leads without side effects."""
    service = WorkflowService(db)
    try:
        return await service.simulate_workflow(workflow_id, sample_size)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post(
    "/from-ai",
    summary="Generate Draft DAG from Natural Language Prompt"
)
async def generate_from_ai(
    req: AIGenerateWorkflowRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Compiles natural language prompt into structured draft DAG JSON."""
    return WorkflowService.generate_workflow_from_prompt(req.prompt)
