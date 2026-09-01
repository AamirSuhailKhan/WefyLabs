"""
Next Best Action (NBA) & Autonomous Sales Operations Engine
===========================================================
Generates prioritized operational recommendations, evaluates automation
governance policies, and executes 1-click or automated CRM tasks.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.lead import Lead
from app.models.crm_models import Task, Activity
from app.models.crm_intelligence_models import (
    OperationalNextBestAction, ActionExecution, LeadHealthSnapshot
)
from app.modules.crm_intelligence.feature_store.feature_aggregator import FeatureAggregator

logger = logging.getLogger(__name__)

class NextBestActionEngine:
    """
    Generates and executes prioritized Next Best Actions for sales operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.aggregator = FeatureAggregator(db)

    async def generate_actions_for_lead(self, lead_id: str, organization_id: str) -> List[OperationalNextBestAction]:
        """
        Synthesizes prioritized operational actions based on lead health, SLA status, and stage progress.
        """
        feats = await self.aggregator.extract_lead_features(lead_id, organization_id)
        actions_to_create: List[Dict[str, Any]] = []

        val = float(feats["budget_max"] or 2_000_000.0)

        # Rule 1: High-value neglected lead -> Immediate Call
        if feats["lead_score"] >= 75.0 and feats["hours_since_last_activity"] >= 24.0:
            actions_to_create.append({
                "action_type": "CALL_LEAD",
                "title": "Priority Broker Call: Rekindle High-Intent Buyer",
                "description": f"Lead has not received broker contact for {feats['hours_since_last_activity']:.0f}h. Immediate call recommended.",
                "priority": "URGENT",
                "urgency_hours": 2,
                "revenue_impact": val * 0.05,
                "governance": "APPROVAL_REQUIRED"
            })

        # Rule 2: Viewing cancelled without reschedule -> Reschedule Viewing
        if feats["cancelled_meetings_count"] > 0:
            actions_to_create.append({
                "action_type": "RESCHEDULE_MEETING",
                "title": "Reschedule Cancelled Property Viewing",
                "description": "Viewing was cancelled. Provide client with 3 candidate slots in prime hours.",
                "priority": "HIGH",
                "urgency_hours": 6,
                "revenue_impact": val * 0.03,
                "governance": "RECOMMENDATION_ONLY"
            })

        # Rule 3: Qualified lead with no viewing -> Propose Site Visit
        if feats["stage_name"] in ("qualified", "contacted") and feats["meeting_count"] == 0:
            actions_to_create.append({
                "action_type": "SCHEDULE_VIEWING",
                "title": "Propose Property Site Visit",
                "description": "Buyer preferences identified. Recommend 2 curated matching properties and offer viewing itinerary.",
                "priority": "HIGH",
                "urgency_hours": 12,
                "revenue_impact": val * 0.02,
                "governance": "RECOMMENDATION_ONLY"
            })

        # Rule 4: Overdue tasks -> Rebalance or Escalate
        if feats["overdue_tasks_count"] > 0:
            actions_to_create.append({
                "action_type": "CREATE_TASK",
                "title": "Resolve Overdue Action Item",
                "description": f"Lead has {feats['overdue_tasks_count']} overdue task(s). Reassign or complete immediately.",
                "priority": "HIGH",
                "urgency_hours": 4,
                "revenue_impact": val * 0.01,
                "governance": "FULLY_AUTOMATIC"
            })

        persisted: List[OperationalNextBestAction] = []
        for a in actions_to_create:
            nba = OperationalNextBestAction(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                lead_id=str(feats["lead_id"]),
                broker_id=feats["broker_id"],
                action_type=a["action_type"],
                title=a["title"],
                description=a["description"],
                priority=a["priority"],
                urgency_hours=a["urgency_hours"],
                potential_revenue_impact_aed=round(a["revenue_impact"], 2),
                governance_policy=a["governance"],
                status="PENDING"
            )
            self.db.add(nba)
            persisted.append(nba)

        if persisted:
            await self.db.commit()
            logger.info(f"[NBA] Generated {len(persisted)} actions for Lead {lead_id}.")

        return persisted

    async def execute_action(
        self,
        action_id: str,
        executed_by: str = "BROKER_1CLICK",
        override_payload: Optional[Dict[str, Any]] = None
    ) -> ActionExecution:
        """
        Executes an action, creates appropriate CRM tasks or activities, and records ActionExecution audit.
        """
        stmt = select(OperationalNextBestAction).where(OperationalNextBestAction.id == action_id)
        res = await self.db.execute(stmt)
        action = res.scalar_one_or_none()
        if not action:
            raise ValueError(f"NextBestAction '{action_id}' not found.")

        # 1. Execute CRM Side Effects
        result_payload = override_payload or {}
        if action.action_type in ("CALL_LEAD", "CREATE_TASK", "SCHEDULE_VIEWING"):
            new_task = Task(
                id=str(uuid.uuid4()),
                broker_id=str(action.broker_id or uuid.uuid4()),
                lead_id=str(action.lead_id),
                organization_id=action.organization_id,
                title=action.title,
                description=action.description,
                due_at=datetime.now(timezone.utc) + timedelta(hours=action.urgency_hours),
                status="pending",
                priority="urgent" if action.priority == "URGENT" else "high"
            )
            self.db.add(new_task)
            result_payload["task_id"] = new_task.id

        # 2. Record Activity
        act = Activity(
            id=str(uuid.uuid4()),
            organization_id=action.organization_id,
            actor_id=action.broker_id,
            lead_id=str(action.lead_id),
            activity_type="next_best_action_executed",
            title=f"Executed Action: {action.title}",
            description=action.description,
            activity_data={"action_id": action.id, "executed_by": executed_by}
        )
        self.db.add(act)

        # 3. Update Action status
        action.status = "EXECUTED"

        # 4. Record ActionExecution
        execution = ActionExecution(
            id=str(uuid.uuid4()),
            action_id=action.id,
            executed_by=executed_by,
            execution_status="SUCCESS",
            result_payload=result_payload,
            executed_at=datetime.now(timezone.utc)
        )
        self.db.add(execution)

        await self.db.commit()
        await self.db.refresh(execution)
        logger.info(f"[NBA] Successfully executed action {action_id} by {executed_by}.")
        return execution
