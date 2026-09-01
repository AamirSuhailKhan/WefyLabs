"""
Comprehensive Test Suite for CRM Intelligence & Autonomous Sales Operations Engine
===================================================================================
Tests:
1. Lead Health calculation with 9 dimensions
2. Lead Neglect detection
3. Lead Decay detection (e.g. cancelled viewing)
4. SLA monitoring & breach detection
5. Pipeline velocity & stagnation detection
6. Opportunity health & revenue at risk
7. Agent workload & overload detection
8. Statistical anomaly detection
9. Next Best Action generation & execution
10. Sales Insight generation, dismissal, and snoozing
11. Manager & Agent daily operational briefs
12. Copilot controlled intelligence tools
13. Celery periodic task execution wrappers
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.crm_models import Task, Meeting, Activity
from app.models.conversation import Conversation
from app.models.crm_intelligence_models import (
    LeadHealthSnapshot, LeadRisk, SlaPolicy, SlaInstance, SlaBreach,
    PipelineHealthSnapshot, OpportunityHealthSnapshot, AgentWorkloadSnapshot,
    SalesInsight, OperationalNextBestAction, ActionExecution,
    ManagerDailyBrief, AgentDailyBrief, AnomalyEvent
)
from app.modules.crm_intelligence.service import CRMIntelligenceService
from app.modules.crm_intelligence.lead_health.lead_health_engine import LeadHealthEngine
from app.modules.crm_intelligence.sla_monitoring.sla_engine import SlaMonitoringEngine
from app.modules.crm_intelligence.pipeline_health.pipeline_engine import PipelineIntelligenceEngine
from app.modules.crm_intelligence.workload_intelligence.workload_engine import WorkloadIntelligenceEngine
from app.modules.crm_intelligence.anomaly_detection.anomaly_engine import AnomalyDetectionEngine
from app.modules.crm_intelligence.next_best_action.nba_engine import NextBestActionEngine
from app.modules.crm_intelligence.insight_engine.insight_service import InsightEngineService
from app.modules.crm_intelligence.daily_brief.brief_service import DailyBriefService
from app.modules.crm_intelligence.tools.copilot_tools import CopilotIntelligenceTools


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


class TestLeadHealthAndDecay:
    """Test 9-dimensional lead health and neglect/decay detection."""

    @pytest.mark.asyncio
    async def test_neglect_detection_high_value_lead(self, mock_db):
        engine = LeadHealthEngine(mock_db)

        fake_features = {
            "lead_id": str(uuid.uuid4()),
            "organization_id": "org_test",
            "broker_id": str(uuid.uuid4()),
            "lead_score": 85.0,
            "score_confidence": 0.9,
            "stage_name": "qualified",
            "days_in_current_stage": 4.0,
            "hours_since_last_activity": 48.0,  # 48 hours inactive
            "hours_since_customer_message": 12.0,
            "first_response_time_seconds": 120.0,
            "activity_count": 1,
            "message_count": 2,
            "meeting_count": 0,
            "cancelled_meetings_count": 0,
            "no_show_meetings_count": 0,
            "overdue_tasks_count": 0,
            "budget_max": 3_500_000.0,
            "has_preferred_locations": True,
        }

        with patch.object(engine.aggregator, "extract_lead_features", return_value=fake_features):
            snap = await engine.evaluate_lead_health(fake_features["lead_id"], "org_test")

            assert snap.health_state == "NEGLECTED"
            assert snap.neglect_detected is True
            assert "high intent" in snap.explanation.lower()
            assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_decay_detection_cancelled_viewing(self, mock_db):
        engine = LeadHealthEngine(mock_db)

        fake_features = {
            "lead_id": str(uuid.uuid4()),
            "organization_id": "org_test",
            "broker_id": str(uuid.uuid4()),
            "lead_score": 60.0,
            "score_confidence": 0.8,
            "stage_name": "viewing",
            "days_in_current_stage": 5.0,
            "hours_since_last_activity": 50.0,
            "hours_since_customer_message": 48.0,
            "first_response_time_seconds": 180.0,
            "activity_count": 2,
            "message_count": 3,
            "meeting_count": 1,
            "cancelled_meetings_count": 1,  # Cancelled viewing
            "no_show_meetings_count": 0,
            "overdue_tasks_count": 0,
            "budget_max": 2_000_000.0,
            "has_preferred_locations": True,
        }

        with patch.object(engine.aggregator, "extract_lead_features", return_value=fake_features):
            snap = await engine.evaluate_lead_health(fake_features["lead_id"], "org_test")

            assert snap.health_state == "AT_RISK"
            assert snap.decay_detected is True
            assert "viewing was cancelled" in snap.explanation.lower()

    @pytest.mark.asyncio
    async def test_cooling_lead_detection(self, mock_db):
        engine = LeadHealthEngine(mock_db)

        fake_features = {
            "lead_id": str(uuid.uuid4()),
            "organization_id": "org_test",
            "broker_id": str(uuid.uuid4()),
            "lead_score": 65.0,
            "score_confidence": 0.85,
            "stage_name": "contacted",
            "days_in_current_stage": 8.0,
            "hours_since_last_activity": 12.0,
            "hours_since_customer_message": 150.0,  # Inactive customer > 6 days
            "first_response_time_seconds": 90.0,
            "activity_count": 5,
            "message_count": 4,
            "meeting_count": 0,
            "cancelled_meetings_count": 0,
            "no_show_meetings_count": 0,
            "overdue_tasks_count": 0,
            "budget_max": 1_800_000.0,
            "has_preferred_locations": True,
        }

        with patch.object(engine.aggregator, "extract_lead_features", return_value=fake_features):
            snap = await engine.evaluate_lead_health(fake_features["lead_id"], "org_test")
            assert snap.health_state == "COOLING"
            assert snap.decay_detected is True


class TestSlaMonitoring:
    """Test SLA timers, breaches, and completion."""

    @pytest.mark.asyncio
    async def test_create_and_breach_sla(self, mock_db):
        engine = SlaMonitoringEngine(mock_db)

        lead_id = str(uuid.uuid4())
        inst = await engine.create_sla_instance("org_test", lead_id, "FIRST_RESPONSE", target_minutes=5)
        assert inst.status == "RUNNING"
        assert inst.sla_type == "FIRST_RESPONSE"

        # Mock overdue query result
        overdue_instance = SlaInstance(
            id=str(uuid.uuid4()),
            organization_id="org_test",
            lead_id=lead_id,
            broker_id=str(uuid.uuid4()),
            sla_type="FIRST_RESPONSE",
            target_deadline_utc=datetime.now(timezone.utc) - timedelta(minutes=10),
            status="RUNNING"
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [overdue_instance]
        mock_db.execute.return_value = mock_result

        breaches = await engine.check_and_record_breaches("org_test")
        assert len(breaches) == 1
        assert breaches[0].sla_type == "FIRST_RESPONSE"
        assert breaches[0].overdue_minutes >= 10
        assert overdue_instance.status == "BREACHED"

    @pytest.mark.asyncio
    async def test_mark_sla_met(self, mock_db):
        engine = SlaMonitoringEngine(mock_db)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        res = await engine.mark_sla_met(str(uuid.uuid4()), "FIRST_RESPONSE")
        assert res is True


class TestPipelineAndOpportunityHealth:
    """Test pipeline stagnation and deal risk."""

    @pytest.mark.asyncio
    async def test_evaluate_opportunity_stagnation(self, mock_db):
        engine = PipelineIntelligenceEngine(mock_db)

        lead_id = str(uuid.uuid4())
        fake_lead = Lead(
            id=uuid.UUID(lead_id),
            name="Aamir Khan",
            phone="+971501234567",
            pipeline_stage="qualified",
            budget_max=4_000_000.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=20),
            updated_at=datetime.now(timezone.utc) - timedelta(days=18)  # Stagnant 18 days
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_lead
        mock_db.execute.return_value = mock_result

        opp = await engine.evaluate_opportunity_health(lead_id, "org_test")
        assert opp.deal_health in ("CRITICAL", "AT_RISK")
        assert opp.stagnation_days >= 18
        assert opp.revenue_at_risk_aed > 0

    @pytest.mark.asyncio
    async def test_evaluate_pipeline_stages(self, mock_db):
        engine = PipelineIntelligenceEngine(mock_db)

        fake_leads = [
            Lead(id=uuid.uuid4(), name="Lead 1", pipeline_stage="new", budget_max=1_000_000.0),
            Lead(id=uuid.uuid4(), name="Lead 2", pipeline_stage="qualified", budget_max=2_500_000.0),
            Lead(id=uuid.uuid4(), name="Lead 3", pipeline_stage="negotiation", budget_max=5_000_000.0),
        ]
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = fake_leads
        mock_db.execute.return_value = mock_res

        snapshots = await engine.evaluate_pipeline_health("org_test")
        assert len(snapshots) == 3
        stg_names = [s.stage_id for s in snapshots]
        assert "new" in stg_names
        assert "qualified" in stg_names
        assert "negotiation" in stg_names


class TestAgentWorkload:
    """Test agent capacity utilization and overload detection."""

    @pytest.mark.asyncio
    async def test_agent_overload_detection(self, mock_db):
        engine = WorkloadIntelligenceEngine(mock_db)
        broker_id = str(uuid.uuid4())

        # 50 active leads
        fake_leads = [
            Lead(id=uuid.uuid4(), broker_id=uuid.UUID(broker_id), score="hot" if i < 10 else "warm", pipeline_stage="new")
            for i in range(50)
        ]
        # 6 overdue tasks
        fake_tasks = [
            Task(id=str(uuid.uuid4()), broker_id=broker_id, status="pending", due_at=datetime.now(timezone.utc) - timedelta(days=2))
            for _ in range(6)
        ]

        def execute_side_effect(stmt):
            m = MagicMock()
            sql_str = str(stmt).lower()
            if "from leads" in sql_str:
                m.scalars.return_value.all.return_value = fake_leads
            elif "from tasks" in sql_str:
                m.scalars.return_value.all.return_value = fake_tasks
            elif "count(meetings.id)" in sql_str:
                m.scalar.return_value = 4
            else:
                m.scalars.return_value.all.return_value = []
                m.scalar.return_value = 0
            return m

        mock_db.execute.side_effect = execute_side_effect

        snap = await engine.evaluate_agent_workload(broker_id, "org_test")
        assert snap.workload_status in ("OVERLOADED", "CRITICAL")
        assert snap.rebalancing_recommended is True
        assert snap.capacity_utilization_pct >= 100.0


class TestAnomalyDetection:
    """Test statistical anomaly detection."""

    @pytest.mark.asyncio
    async def test_cancellation_surge_anomaly(self, mock_db):
        engine = AnomalyDetectionEngine(mock_db)

        # 10 meetings, 6 cancelled (60% cancellation rate, surge > 35%)
        fake_mtgs = [
            Meeting(
                id=str(uuid.uuid4()),
                status="cancelled" if i < 6 else "scheduled",
                scheduled_at=datetime.now(timezone.utc) - timedelta(days=2)
            )
            for i in range(10)
        ]

        def execute_side_effect(stmt):
            m = MagicMock()
            m.scalars.return_value.all.return_value = fake_mtgs
            m.scalar.return_value = 10
            return m

        mock_db.execute.side_effect = execute_side_effect

        anomalies = await engine.detect_anomalies("org_test")
        assert len(anomalies) >= 1
        assert anomalies[0].metric_name == "CANCELLATION_SURGE"
        assert anomalies[0].actual_value >= 50.0


class TestNextBestActionAndExecution:
    """Test Next Best Action generation and 1-click execution."""

    @pytest.mark.asyncio
    async def test_generate_and_execute_nba(self, mock_db):
        engine = NextBestActionEngine(mock_db)

        lead_id = str(uuid.uuid4())
        fake_features = {
            "lead_id": lead_id,
            "organization_id": "org_test",
            "broker_id": str(uuid.uuid4()),
            "lead_score": 80.0,
            "score_confidence": 0.9,
            "stage_name": "qualified",
            "days_in_current_stage": 3.0,
            "hours_since_last_activity": 30.0,
            "hours_since_customer_message": 10.0,
            "first_response_time_seconds": 60.0,
            "activity_count": 2,
            "message_count": 2,
            "meeting_count": 0,
            "cancelled_meetings_count": 0,
            "no_show_meetings_count": 0,
            "overdue_tasks_count": 0,
            "budget_max": 2_500_000.0,
            "has_preferred_locations": True,
        }

        with patch.object(engine.aggregator, "extract_lead_features", return_value=fake_features):
            actions = await engine.generate_actions_for_lead(lead_id, "org_test")
            assert len(actions) > 0
            action = actions[0]
            assert action.priority in ("URGENT", "HIGH")

        # Mock action retrieval for execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = action
        mock_db.execute.return_value = mock_result

        execution = await engine.execute_action(action.id, executed_by="BROKER_1CLICK")
        assert execution.execution_status == "SUCCESS"
        assert action.status == "EXECUTED"


class TestInsightsAndDismissal:
    """Test AI Sales Insight generation and dismissal override."""

    @pytest.mark.asyncio
    async def test_generate_insights_and_dismiss(self, mock_db):
        service = InsightEngineService(mock_db)

        # Mock 2 active neglect risks
        fake_risks = [
            LeadRisk(
                id=str(uuid.uuid4()),
                organization_id="org_test",
                lead_id=str(uuid.uuid4()),
                risk_type="NEGLECT",
                severity="HIGH",
                evidence="No activity in 30h",
                recommended_recovery_action="Call lead",
                status="ACTIVE"
            ),
            LeadRisk(
                id=str(uuid.uuid4()),
                organization_id="org_test",
                lead_id=str(uuid.uuid4()),
                risk_type="NEGLECT",
                severity="HIGH",
                evidence="No activity in 40h",
                recommended_recovery_action="Call lead",
                status="ACTIVE"
            )
        ]

        def execute_side_effect(stmt):
            m = MagicMock()
            sql_str = str(stmt).lower()
            if "from lead_risks" in sql_str:
                m.scalars.return_value.all.return_value = fake_risks
            elif "from sla_breaches" in sql_str:
                m.scalars.return_value.all.return_value = []
            elif "from sales_insights" in sql_str:
                m.scalar_one_or_none.return_value = None
            return m

        mock_db.execute.side_effect = execute_side_effect

        insights = await service.generate_insights("org_test")
        assert len(insights) >= 1
        assert "neglected" in insights[0].title.lower()

        # Test dismissal
        insight = insights[0]
        mock_db.execute.side_effect = None
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = insight
        mock_db.execute.return_value = mock_res

        success = await service.dismiss_insight(insight.id, str(uuid.uuid4()))
        assert success is True
        assert insight.is_active is False

    @pytest.mark.asyncio
    async def test_snooze_insight(self, mock_db):
        service = InsightEngineService(mock_db)
        insight = SalesInsight(
            id=str(uuid.uuid4()),
            organization_id="org_test",
            insight_type="LEAD_INSIGHT",
            title="Neglected Leads Alert",
            summary_markdown="Test",
            priority="HIGH",
            impact_level="HIGH",
            confidence=0.9,
            evidence=[],
            recommended_action="Act",
            is_active=True
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = insight
        mock_db.execute.return_value = mock_res

        success = await service.snooze_insight(insight.id, str(uuid.uuid4()), hours=24)
        assert success is True
        assert insight.expires_at is not None


class TestCopilotControlledTools:
    """Test controlled tool invocation for AI Copilot."""

    @pytest.mark.asyncio
    async def test_copilot_tool_daily_brief(self, mock_db):
        tools = CopilotIntelligenceTools(mock_db)

        # Mock counts for daily brief
        def execute_side_effect(stmt):
            m = MagicMock()
            m.scalar.return_value = 5
            m.scalars.return_value.all.return_value = []
            return m

        mock_db.execute.side_effect = execute_side_effect

        brief = await tools.get_daily_brief("org_test", role="manager")
        assert brief["role"] == "manager"
        assert "today_new_leads" in brief
        assert "high_intent_leads" in brief
        assert "executive_summary" in brief

    @pytest.mark.asyncio
    async def test_copilot_tool_lead_health(self, mock_db):
        tools = CopilotIntelligenceTools(mock_db)
        lead_id = str(uuid.uuid4())

        fake_features = {
            "lead_id": lead_id,
            "organization_id": "org_test",
            "broker_id": str(uuid.uuid4()),
            "lead_score": 90.0,
            "score_confidence": 0.95,
            "stage_name": "meeting",
            "days_in_current_stage": 2.0,
            "hours_since_last_activity": 4.0,
            "hours_since_customer_message": 2.0,
            "first_response_time_seconds": 45.0,
            "activity_count": 8,
            "message_count": 10,
            "meeting_count": 2,
            "cancelled_meetings_count": 0,
            "no_show_meetings_count": 0,
            "overdue_tasks_count": 0,
            "budget_max": 5_000_000.0,
            "has_preferred_locations": True,
        }

        with patch("app.modules.crm_intelligence.lead_health.lead_health_engine.FeatureAggregator.extract_lead_features", return_value=fake_features):
            res = await tools.get_lead_health(lead_id, "org_test")
            assert res["lead_id"] == lead_id
            assert res["health_state"] in ("HOT", "HEALTHY")
            assert res["health_score"] >= 80.0
