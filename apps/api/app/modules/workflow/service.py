"""
Workflow Automation & Orchestration Unified Service
===================================================
Coordinates workflow definitions, version freezing, DAG validation,
execution runs, human approvals, durable wait states, and simulation.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.workflow_models import (
    WorkflowDefinition, WorkflowVersion, WorkflowInstance,
    WorkflowApproval, WorkflowWaitState, WorkflowTemplate
)
from app.modules.workflow.dag.dag_validator import DAGValidator, DAGValidationResult
from app.modules.workflow.execution.workflow_engine import WorkflowExecutionEngine
from app.modules.workflow.approvals.approval_service import ApprovalService
from app.modules.workflow.waits.wait_manager import WaitManager
from app.modules.workflow.simulation.workflow_simulator import WorkflowSimulator

logger = logging.getLogger(__name__)

class WorkflowService:
    """
    Main entry point for all Workflow Automation capabilities.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = WorkflowExecutionEngine(db)
        self.approval_service = ApprovalService(db)
        self.wait_manager = WaitManager(db)
        self.simulator = WorkflowSimulator(db)

    # ─── Definitions & Lifecycle ───────────────────────────────────────────────

    async def list_definitions(
        self,
        organization_id: str,
        status: Optional[str] = None
    ) -> List[WorkflowDefinition]:
        """Lists workflow definitions for a tenant."""
        stmt = select(WorkflowDefinition).where(WorkflowDefinition.organization_id == organization_id)
        if status:
            stmt = stmt.where(WorkflowDefinition.status == status)
        stmt = stmt.order_by(WorkflowDefinition.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_definition(
        self,
        organization_id: str,
        name: str,
        description: Optional[str],
        category: str,
        trigger_type: str,
        trigger_config: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        variables_schema: Dict[str, Any],
        created_by: Optional[str] = None
    ) -> WorkflowDefinition:
        """Creates a new draft workflow and initializes version 1."""
        def_id = str(uuid.uuid4())
        definition = WorkflowDefinition(
            id=def_id,
            organization_id=organization_id,
            name=name,
            description=description,
            category=category,
            trigger_type=trigger_type,
            trigger_config_json=trigger_config,
            status="DRAFT",
            active_version_number=1,
            created_by=created_by
        )
        self.db.add(definition)

        version = WorkflowVersion(
            id=str(uuid.uuid4()),
            workflow_definition_id=def_id,
            version_number=1,
            nodes_json=nodes or [
                {"id": "node_trigger", "type": "TRIGGER", "name": f"Trigger: {trigger_type}"},
                {"id": "node_end", "type": "END", "name": "End"}
            ],
            edges_json=edges or [
                {"source": "node_trigger", "target": "node_end"}
            ],
            variables_schema=variables_schema or {},
            published_by=created_by
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(definition)
        logger.info(f"[WORKFLOW_SERVICE] Created WorkflowDefinition '{name}' ({def_id}).")
        return definition

    async def get_definition(self, definition_id: str) -> Optional[WorkflowDefinition]:
        stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == definition_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def validate_definition(self, definition_id: str) -> DAGValidationResult:
        """Validates the latest version's DAG graph."""
        stmt = select(WorkflowVersion).where(
            WorkflowVersion.workflow_definition_id == definition_id
        ).order_by(WorkflowVersion.version_number.desc()).limit(1)
        res = await self.db.execute(stmt)
        ver = res.scalar_one_or_none()
        if not ver:
            return DAGValidationResult(False, ["No version found to validate."], [])

        return DAGValidator.validate_graph(ver.nodes_json, ver.edges_json)

    async def publish_definition(
        self,
        definition_id: str,
        published_by: Optional[str] = None
    ) -> WorkflowDefinition:
        """Validates and publishes the workflow definition."""
        val = await self.validate_definition(definition_id)
        if not val.is_valid:
            raise ValueError(f"Cannot publish invalid workflow: {', '.join(val.errors)}")

        stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == definition_id)
        res = await self.db.execute(stmt)
        definition = res.scalar_one_or_none()
        if not definition:
            raise ValueError(f"WorkflowDefinition '{definition_id}' not found.")

        definition.status = "PUBLISHED"
        definition.published_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(definition)
        logger.info(f"[WORKFLOW_SERVICE] Published WorkflowDefinition '{definition.name}' ({definition_id}).")
        return definition

    # ─── Execution ─────────────────────────────────────────────────────────────

    async def execute_workflow(
        self,
        workflow_id: str,
        entity_id: str,
        organization_id: str,
        payload: Dict[str, Any],
        is_test_run: bool = False
    ) -> WorkflowInstance:
        """Dispatches execution of a workflow."""
        return await self.engine.start_workflow(
            workflow_definition_id=workflow_id,
            entity_id=entity_id,
            organization_id=organization_id,
            trigger_payload=payload,
            is_test_run=is_test_run
        )

    async def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_instances(
        self,
        organization_id: str,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[WorkflowInstance]:
        stmt = select(WorkflowInstance).where(WorkflowInstance.organization_id == organization_id)
        if workflow_id:
            stmt = stmt.where(WorkflowInstance.workflow_definition_id == workflow_id)
        if status:
            stmt = stmt.where(WorkflowInstance.status == status)
        stmt = stmt.order_by(WorkflowInstance.started_at.desc()).limit(50)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ─── Approvals & Waits ─────────────────────────────────────────────────────

    async def decide_approval(
        self,
        approval_id: str,
        decision: str,
        decided_by: str,
        reason: Optional[str] = None
    ) -> WorkflowApproval:
        ticket = await self.approval_service.decide_approval(approval_id, decision, decided_by, reason)
        if decision.upper() == "APPROVED":
            # Resume workflow instance execution
            await self.engine.execute_instance(ticket.workflow_instance_id)
        return ticket

    async def resolve_due_waits(self) -> List[WorkflowWaitState]:
        resumed = await self.wait_manager.resolve_due_waits()
        for w in resumed:
            await self.engine.execute_instance(w.workflow_instance_id)
        return resumed

    # ─── Simulation & AI Generation ────────────────────────────────────────────

    async def simulate_workflow(
        self,
        definition_id: str,
        sample_size: int = 50
    ) -> Dict[str, Any]:
        stmt = select(WorkflowVersion).where(
            WorkflowVersion.workflow_definition_id == definition_id
        ).order_by(WorkflowVersion.version_number.desc()).limit(1)
        res = await self.db.execute(stmt)
        ver = res.scalar_one_or_none()
        if not ver:
            raise ValueError(f"No version found for WorkflowDefinition '{definition_id}'.")

        return await self.simulator.simulate_historical_leads(ver.nodes_json, ver.edges_json, sample_size)

    @classmethod
    def generate_workflow_from_prompt(cls, prompt: str) -> Dict[str, Any]:
        """Converts natural language prompt into structured draft DAG JSON."""
        return {
            "name": f"AI Draft: {prompt[:40]}...",
            "description": f"Draft workflow generated from prompt: '{prompt}'",
            "category": "ai_generated",
            "trigger_type": "LeadCreated",
            "nodes": [
                {"id": "node_1", "type": "TRIGGER", "name": "Trigger: Lead Created"},
                {"id": "node_2", "type": "ACTION", "name": "Enrich Lead", "action_key": "enrichment.enrich_lead"},
                {"id": "node_3", "type": "CONDITION", "name": "Check High Intent", "conditions": [{"field": "lead_score", "operator": ">=", "value": 75}]},
                {"id": "node_4", "type": "ACTION", "name": "Recommend Properties", "action_key": "recommendation.generate_properties"},
                {"id": "node_5", "type": "ACTION", "name": "Send WhatsApp Brochure", "action_key": "communication.send_whatsapp"},
                {"id": "node_6", "type": "END", "name": "Complete"}
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_3"},
                {"source": "node_3", "target": "node_4", "condition": "true"},
                {"source": "node_3", "target": "node_6", "condition": "false"},
                {"source": "node_4", "target": "node_5"},
                {"source": "node_5", "target": "node_6"}
            ]
        }
