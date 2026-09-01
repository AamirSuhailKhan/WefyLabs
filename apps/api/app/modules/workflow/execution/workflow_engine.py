"""
Durable DAG Workflow Execution Engine
=====================================
Executes node graphs step-by-step, persisting state transitions and execution logs
after every node to guarantee crash-resilient, durable, and idempotent automations.
"""

import time
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.workflow_models import (
    WorkflowDefinition, WorkflowVersion, WorkflowInstance,
    WorkflowNodeExecution
)
from app.modules.workflow.expressions.expression_evaluator import ExpressionEvaluator
from app.modules.workflow.actions.action_registry import ActionRegistry
from app.modules.workflow.ai.ai_decision_engine import AIDecisionEngine
from app.modules.workflow.waits.wait_manager import WaitManager
from app.modules.workflow.approvals.approval_service import ApprovalService

logger = logging.getLogger(__name__)

class WorkflowExecutionEngine:
    """
    Durable DAG graph execution orchestrator.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.action_registry = ActionRegistry(db)
        self.wait_manager = WaitManager(db)
        self.approval_service = ApprovalService(db)

    async def start_workflow(
        self,
        workflow_definition_id: str,
        entity_id: str,
        organization_id: str,
        trigger_payload: Dict[str, Any],
        is_test_run: bool = False
    ) -> WorkflowInstance:
        """
        Instantiates and begins execution of a published workflow.
        """
        # 1. Fetch active version
        stmt = select(WorkflowVersion).where(
            WorkflowVersion.workflow_definition_id == workflow_definition_id
        ).order_by(WorkflowVersion.version_number.desc()).limit(1)
        res = await self.db.execute(stmt)
        version = res.scalar_one_or_none()
        if not version:
            raise ValueError(f"No published version found for WorkflowDefinition '{workflow_definition_id}'.")

        # 2. Create Instance
        now = datetime.now(timezone.utc)
        instance = WorkflowInstance(
            id=str(uuid.uuid4()),
            workflow_definition_id=workflow_definition_id,
            workflow_version_id=version.id,
            organization_id=organization_id,
            entity_id=entity_id,
            status="RUNNING",
            context_data=dict(trigger_payload),
            trigger_payload=dict(trigger_payload),
            is_test_run=is_test_run,
            started_at=now
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)

        # 3. Execute DAG
        await self.execute_instance(instance.id)
        return instance

    async def execute_instance(self, instance_id: str) -> WorkflowInstance:
        """
        Advances the workflow DAG from its current state until a terminal node,
        wait pause, or approval gate is reached.
        """
        stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_id)
        res = await self.db.execute(stmt)
        instance = res.scalar_one_or_none()
        if not instance or instance.status not in ("PENDING", "RUNNING"):
            return instance

        stmt_v = select(WorkflowVersion).where(WorkflowVersion.id == instance.workflow_version_id)
        res_v = await self.db.execute(stmt_v)
        version = res_v.scalar_one_or_none()
        if not version:
            instance.status = "FAILED"
            instance.error_message = "Workflow version artifact missing."
            await self.db.commit()
            return instance

        nodes_map = {n["id"]: n for n in version.nodes_json}
        edges_map: Dict[str, List[Dict[str, Any]]] = {}
        for e in version.edges_json:
            src = e.get("source")
            if src not in edges_map:
                edges_map[src] = []
            edges_map[src].append(e)

        # Determine starting node
        if instance.current_node_id:
            current_id = instance.current_node_id
        else:
            trigger_nodes = [n["id"] for n in version.nodes_json if n.get("type", "").upper() == "TRIGGER"]
            current_id = trigger_nodes[0] if trigger_nodes else list(nodes_map.keys())[0]

        # Execution Loop
        while current_id and instance.status == "RUNNING":
            curr_node = nodes_map.get(current_id)
            if not curr_node:
                break

            node_type = (curr_node.get("type") or "").upper()
            node_name = curr_node.get("name") or curr_node.get("id")
            start_t = time.perf_counter()
            node_status = "COMPLETED"
            output_data: Dict[str, Any] = {}
            error_msg: Optional[str] = None
            next_node_id: Optional[str] = None

            try:
                # ─── Node Handler Logic ───────────────────────────────────────
                if node_type == "TRIGGER":
                    output_data = {"trigger_executed": True}
                    next_node_id = self._get_next_default_node(current_id, edges_map)

                elif node_type == "CONDITION":
                    conds = curr_node.get("conditions", [])
                    logic_op = curr_node.get("logical_operator", "AND")
                    is_true = ExpressionEvaluator.evaluate_composite_conditions(
                        conds, logic_op, instance.context_data
                    )
                    output_data = {"condition_result": is_true}
                    next_node_id = self._get_branch_target(current_id, is_true, edges_map)

                elif node_type == "ACTION":
                    action_key = curr_node.get("action_key", "crm.create_task")
                    params = curr_node.get("parameters", {})
                    # Merge context parameters
                    action_res = await self.action_registry.execute_action(
                        action_key=action_key,
                        parameters=params,
                        context=instance.context_data,
                        organization_id=instance.organization_id,
                        is_dry_run=instance.is_test_run
                    )
                    if action_res.status == "SUCCESS":
                        output_data = action_res.result_data
                        instance.context_data.update(output_data)
                        next_node_id = self._get_next_default_node(current_id, edges_map)
                    else:
                        node_status = "FAILED"
                        error_msg = action_res.error_message
                        instance.status = "FAILED"
                        instance.error_message = error_msg

                elif node_type == "AI_DECISION":
                    prompt = curr_node.get("decision_prompt", "Evaluate lead qualification")
                    ai_res = AIDecisionEngine.evaluate_ai_decision(prompt, instance.context_data)
                    output_data = ai_res.to_dict()
                    instance.context_data["ai_decision"] = ai_res.decision

                    if ai_res.requires_approval:
                        # Route to Human Approval Gate
                        await self.approval_service.create_approval_ticket(
                            instance_id=instance.id,
                            node_id=current_id,
                            organization_id=instance.organization_id,
                            title=f"AI Decision Review: {ai_res.decision}",
                            description=ai_res.explanation,
                            context_summary=instance.context_data
                        )
                        node_status = "WAITING"
                        instance.status = "WAITING"
                        break
                    else:
                        next_node_id = self._get_branch_target(current_id, ai_res.autonomous_allowed, edges_map)

                elif node_type == "WAIT":
                    mins = curr_node.get("duration_minutes", 60)
                    evt = curr_node.get("expected_event")
                    await self.wait_manager.create_wait_state(
                        instance_id=instance.id,
                        node_id=current_id,
                        wait_type="DURATION" if not evt else "EVENT_WAIT",
                        duration_minutes=mins,
                        expected_event=evt
                    )
                    node_status = "WAITING"
                    instance.status = "WAITING"
                    output_data = {"wait_duration_minutes": mins, "expected_event": evt}
                    break

                elif node_type == "APPROVAL":
                    title = curr_node.get("title", "Manager Action Approval")
                    desc = curr_node.get("description", "Requires human review")
                    await self.approval_service.create_approval_ticket(
                        instance_id=instance.id,
                        node_id=current_id,
                        organization_id=instance.organization_id,
                        title=title,
                        description=desc,
                        context_summary=instance.context_data
                    )
                    node_status = "WAITING"
                    instance.status = "WAITING"
                    break

                elif node_type == "END":
                    instance.status = "COMPLETED"
                    instance.completed_at = datetime.now(timezone.utc)
                    output_data = {"workflow_finished": True}
                    break

            except Exception as ex:
                logger.error(f"[WORKFLOW_ENGINE] Error at node {current_id}: {ex}", exc_info=True)
                node_status = "FAILED"
                error_msg = str(ex)
                instance.status = "FAILED"
                instance.error_message = error_msg

            # Record Node Execution Log
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            node_exec = WorkflowNodeExecution(
                id=str(uuid.uuid4()),
                workflow_instance_id=instance.id,
                node_id=current_id,
                node_type=node_type,
                node_name=node_name,
                status=node_status,
                input_snapshot={},
                output_snapshot=output_data,
                error_details=error_msg,
                duration_ms=round(duration_ms, 2)
            )
            self.db.add(node_exec)

            # Move to next node or finish
            current_id = next_node_id
            instance.current_node_id = current_id

        if not current_id and instance.status == "RUNNING":
            instance.status = "COMPLETED"
            instance.completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    def _get_next_default_node(self, node_id: str, edges_map: Dict[str, List[Dict[str, Any]]]) -> Optional[str]:
        edges = edges_map.get(node_id, [])
        return edges[0].get("target") if edges else None

    def _get_branch_target(self, node_id: str, condition_met: bool, edges_map: Dict[str, List[Dict[str, Any]]]) -> Optional[str]:
        edges = edges_map.get(node_id, [])
        target_label = "true" if condition_met else "false"
        for e in edges:
            lbl = str(e.get("label") or e.get("condition") or "").lower()
            if lbl == target_label:
                return e.get("target")
        return edges[0].get("target") if edges else None
