"""
Comprehensive Test Suite for Workflow Automation & Revenue Operations Engine
=============================================================================
Tests:
1. Sandboxed AST Expression Evaluator (no eval)
2. DAG Graph Validation & Cycle Detection
3. Action Registry execution & domain service dispatch
4. Structured AI Decision Engine & Confidence Tiers
5. Durable Wait State pausing and timer resumption
6. Human-in-the-Loop Approval Ticket creation & resolution
7. Full DAG Workflow Execution (Trigger -> Condition -> Action -> End)
8. Dry Run Mode & Historical What-If Simulation
9. Prompt-to-Workflow Compilation
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.lead import Lead
from app.models.workflow_models import (
    WorkflowDefinition, WorkflowVersion, WorkflowInstance,
    WorkflowNodeExecution, WorkflowApproval, WorkflowWaitState
)
from app.modules.workflow.expressions.expression_evaluator import ExpressionEvaluator
from app.modules.workflow.dag.dag_validator import DAGValidator
from app.modules.workflow.actions.action_registry import ActionRegistry
from app.modules.workflow.ai.ai_decision_engine import AIDecisionEngine
from app.modules.workflow.waits.wait_manager import WaitManager
from app.modules.workflow.approvals.approval_service import ApprovalService
from app.modules.workflow.execution.workflow_engine import WorkflowExecutionEngine
from app.modules.workflow.simulation.workflow_simulator import WorkflowSimulator
from app.modules.workflow.service import WorkflowService


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestExpressionEvaluator:
    """Test deterministic sandboxed expression evaluation."""

    def test_simple_comparisons(self):
        ctx = {"lead": {"score": 85.0, "stage": "qualified", "budget": 3000000}}

        assert ExpressionEvaluator.evaluate_simple_condition("lead.score", ">=", 80.0, ctx) is True
        assert ExpressionEvaluator.evaluate_simple_condition("lead.score", "<", 50.0, ctx) is False
        assert ExpressionEvaluator.evaluate_simple_condition("lead.stage", "==", "qualified", ctx) is True
        assert ExpressionEvaluator.evaluate_simple_condition("lead.stage", "in", ["qualified", "viewing"], ctx) is True
        assert ExpressionEvaluator.evaluate_simple_condition("lead.budget", "between", [2000000, 4000000], ctx) is True

    def test_composite_conditions_and_or(self):
        ctx = {"lead": {"score": 75.0, "has_budget": True, "country": "UAE"}}

        conds_and = [
            {"field": "lead.score", "operator": ">=", "value": 70},
            {"field": "lead.has_budget", "operator": "==", "value": True}
        ]
        assert ExpressionEvaluator.evaluate_composite_conditions(conds_and, "AND", ctx) is True

        conds_or = [
            {"field": "lead.score", "operator": ">=", "value": 90},
            {"field": "lead.country", "operator": "==", "value": "UAE"}
        ]
        assert ExpressionEvaluator.evaluate_composite_conditions(conds_or, "OR", ctx) is True


class TestDAGValidator:
    """Test DAG topology and cycle detection."""

    def test_valid_dag(self):
        nodes = [
            {"id": "n1", "type": "TRIGGER", "name": "Start"},
            {"id": "n2", "type": "ACTION", "name": "Enrich"},
            {"id": "n3", "type": "END", "name": "Finish"}
        ]
        edges = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"}
        ]
        res = DAGValidator.validate_graph(nodes, edges)
        assert res.is_valid is True
        assert len(res.errors) == 0

    def test_cyclic_dag_detection(self):
        nodes = [
            {"id": "n1", "type": "TRIGGER", "name": "Start"},
            {"id": "n2", "type": "ACTION", "name": "Step A"},
            {"id": "n3", "type": "ACTION", "name": "Step B"}
        ]
        # Loop: n2 -> n3 -> n2
        edges = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
            {"source": "n3", "target": "n2"}
        ]
        res = DAGValidator.validate_graph(nodes, edges)
        assert res.is_valid is False
        assert any("Cyclic dependency" in err for err in res.errors)


class TestActionRegistry:
    """Test action execution and dry run simulation."""

    @pytest.mark.asyncio
    async def test_dry_run_action(self, mock_db):
        registry = ActionRegistry(mock_db)
        res = await registry.execute_action(
            action_key="communication.send_whatsapp",
            parameters={"phone": "+971501234567"},
            context={},
            organization_id="org_test",
            is_dry_run=True
        )
        assert res.status == "SUCCESS"
        assert res.result_data["dry_run"] is True

    @pytest.mark.asyncio
    async def test_crm_task_action(self, mock_db):
        registry = ActionRegistry(mock_db)
        res = await registry.execute_action(
            action_key="crm.create_task",
            parameters={"title": "VIP Buyer Follow-up"},
            context={"lead_id": str(uuid.uuid4())},
            organization_id="org_test"
        )
        assert res.status == "SUCCESS"
        assert "task_id" in res.result_data


class TestAIDecisionEngine:
    """Test AI decision node evaluation and confidence gates."""

    def test_high_confidence_viewing_decision(self):
        ctx = {"lead_score": 85.0, "has_budget": True}
        res = AIDecisionEngine.evaluate_ai_decision("Determine if lead should book viewing", ctx)
        assert res.decision == "BOOK_VIEWING"
        assert res.confidence >= 0.85
        assert res.autonomous_allowed is True
        assert res.requires_approval is False

    def test_medium_confidence_requires_approval(self):
        ctx = {"lead_score": 60.0, "has_budget": True}
        res = AIDecisionEngine.evaluate_ai_decision("Determine if lead should book viewing", ctx)
        assert res.requires_approval is True
        assert res.autonomous_allowed is False


class TestWaitManager:
    """Test durable wait states and timer resumes."""

    @pytest.mark.asyncio
    async def test_create_and_resolve_wait(self, mock_db):
        manager = WaitManager(mock_db)
        inst_id = str(uuid.uuid4())

        wait = await manager.create_wait_state(
            instance_id=inst_id,
            node_id="node_wait",
            wait_type="DURATION",
            duration_minutes=30
        )
        assert wait.is_resumed is False
        assert mock_db.commit.called

        # Mock overdue wait resolution
        wait.resume_deadline_utc = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [wait]
        mock_db.execute.return_value = mock_res

        resumed = await manager.resolve_due_waits()
        assert len(resumed) == 1
        assert wait.is_resumed is True


class TestApprovalService:
    """Test human approval gates and decisions."""

    @pytest.mark.asyncio
    async def test_create_and_decide_approval(self, mock_db):
        service = ApprovalService(mock_db)
        inst_id = str(uuid.uuid4())

        ticket = await service.create_approval_ticket(
            instance_id=inst_id,
            node_id="node_approval",
            organization_id="org_test",
            title="VIP Escalation",
            description="High value buyer discount request",
            context_summary={"budget": 10000000}
        )
        assert ticket.status == "PENDING"

        # Mock retrieval for decision
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = ticket
        mock_db.execute.return_value = mock_res

        decided = await service.decide_approval(ticket.id, "APPROVED", "Sales Director", "Approved discount")
        assert decided.status == "APPROVED"
        assert decided.decision_by == "Sales Director"


class TestWorkflowExecutionEngine:
    """Test end-to-end DAG execution runs."""

    @pytest.mark.asyncio
    async def test_full_dag_execution(self, mock_db):
        engine = WorkflowExecutionEngine(mock_db)
        wf_id = str(uuid.uuid4())

        nodes = [
            {"id": "n_trig", "type": "TRIGGER", "name": "Lead Created"},
            {"id": "n_cond", "type": "CONDITION", "name": "Score >= 70", "conditions": [{"field": "lead_score", "operator": ">=", "value": 70}]},
            {"id": "n_act", "type": "ACTION", "name": "Create Task", "action_key": "crm.create_task"},
            {"id": "n_end", "type": "END", "name": "Finish"}
        ]
        edges = [
            {"source": "n_trig", "target": "n_cond"},
            {"source": "n_cond", "target": "n_act", "condition": "true"},
            {"source": "n_cond", "target": "n_end", "condition": "false"},
            {"source": "n_act", "target": "n_end"}
        ]

        version = WorkflowVersion(
            id=str(uuid.uuid4()),
            workflow_definition_id=wf_id,
            version_number=1,
            nodes_json=nodes,
            edges_json=edges,
            variables_schema={}
        )

        created_instances = {}

        def execute_side_effect(stmt):
            m = MagicMock()
            sql_str = str(stmt).lower()
            if "from workflow_versions" in sql_str:
                m.scalar_one_or_none.return_value = version
            elif "from workflow_instances" in sql_str:
                # Return the instance that was added
                inst = list(created_instances.values())[0] if created_instances else None
                m.scalar_one_or_none.return_value = inst
            else:
                m.scalar_one_or_none.return_value = None
            return m

        def add_side_effect(obj):
            if isinstance(obj, WorkflowInstance):
                created_instances[obj.id] = obj

        mock_db.execute.side_effect = execute_side_effect
        mock_db.add.side_effect = add_side_effect

        instance = await engine.start_workflow(
            workflow_definition_id=wf_id,
            entity_id=str(uuid.uuid4()),
            organization_id="org_test",
            trigger_payload={"lead_score": 85.0}
        )

        assert instance.status == "COMPLETED"
        assert instance.completed_at is not None


class TestPromptToWorkflowCompilation:
    """Test natural language compilation into draft DAG."""

    def test_generate_workflow_from_prompt(self):
        prompt = "When a new lead arrives, check intent, recommend properties, and send WhatsApp"
        res = WorkflowService.generate_workflow_from_prompt(prompt)
        assert "nodes" in res
        assert "edges" in res
        assert len(res["nodes"]) >= 4
        # Validate generated DAG
        val = DAGValidator.validate_graph(res["nodes"], res["edges"])
        assert val.is_valid is True


class TestWorkflowSimulation:
    """Test historical What-If workflow simulation."""

    @pytest.mark.asyncio
    async def test_simulate_historical_leads(self, mock_db):
        simulator = WorkflowSimulator(mock_db)

        nodes = [
            {"id": "n1", "type": "TRIGGER", "name": "Start"},
            {"id": "n2", "type": "ACTION", "name": "Send WhatsApp", "action_key": "communication.send_whatsapp"},
            {"id": "n3", "type": "END", "name": "Finish"}
        ]
        edges = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"}
        ]

        fake_leads = [
            Lead(id=uuid.uuid4(), name="Sim Lead 1", score="hot", budget_max=3_000_000.0),
            Lead(id=uuid.uuid4(), name="Sim Lead 2", score="warm", budget_max=1_500_000.0)
        ]
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = fake_leads
        mock_db.execute.return_value = mock_res

        res = await simulator.simulate_historical_leads(nodes, edges, sample_size=2)
        assert res["simulation_status"] == "COMPLETED"
        assert res["total_leads_simulated"] == 2
        assert "communication.send_whatsapp" in res["actions_triggered"]
        assert res["total_estimated_cost_usd"] > 0.0


class TestApprovalRejection:
    """Test approval rejection stopping downstream actions."""

    @pytest.mark.asyncio
    async def test_rejection_resolves_ticket(self, mock_db):
        service = ApprovalService(mock_db)
        ticket = WorkflowApproval(
            id=str(uuid.uuid4()),
            workflow_instance_id=str(uuid.uuid4()),
            node_id="node_appr",
            organization_id="org_test",
            title="High Discount Request",
            description="50% price reduction",
            status="PENDING",
            deadline_utc=datetime.now(timezone.utc) + timedelta(hours=12)
        )

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = ticket
        mock_db.execute.return_value = mock_res

        decided = await service.decide_approval(ticket.id, "REJECTED", "Broker Admin", "Discount exceeds policy")
        assert decided.status == "REJECTED"
        assert "policy" in decided.decision_reason
