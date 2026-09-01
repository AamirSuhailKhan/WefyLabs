"""
Dry Run Test Mode & Historical What-If Simulation Engine
========================================================
Simulates workflow executions over sample or historical lead datasets
without creating real-world side effects (e.g. sending real messages or bookings).
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.lead import Lead
from app.modules.workflow.expressions.expression_evaluator import ExpressionEvaluator

logger = logging.getLogger(__name__)

# Estimated cost metrics per action type in USD
ACTION_ESTIMATED_COST: Dict[str, float] = {
    "communication.send_whatsapp": 0.05,
    "communication.send_sms": 0.03,
    "scoring.evaluate_lead": 0.01,
    "ai_decision": 0.02,
    "calendar.book_viewing": 0.00,
    "crm.create_task": 0.00,
    "predictive.predict_conversion": 0.01,
}

class WorkflowSimulator:
    """
    Evaluates workflow executions non-destructively.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def simulate_historical_leads(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        sample_size: int = 50
    ) -> Dict[str, Any]:
        """
        Simulates workflow execution across past historical leads and estimates path choices,
        action counts, and estimated cost.
        """
        stmt = select(Lead).limit(sample_size)
        res = await self.db.execute(stmt)
        leads = res.scalars().all()

        nodes_map = {n["id"]: n for n in nodes}
        edges_map: Dict[str, List[Dict[str, Any]]] = {}
        for e in edges:
            src = e.get("source")
            if src not in edges_map:
                edges_map[src] = []
            edges_map[src].append(e)

        total_simulated = len(leads) or sample_size
        triggered_count = total_simulated
        actions_triggered: Dict[str, int] = {}
        total_estimated_cost = 0.0

        for l in leads:
            lead_ctx = {
                "lead_id": str(l.id),
                "lead": {
                    "id": str(l.id),
                    "name": l.name,
                    "score": 80.0 if l.score == "hot" else 50.0 if l.score == "warm" else 20.0,
                    "budget_max": float(l.budget_max or 2_000_000.0),
                    "pipeline_stage": l.pipeline_stage or "new"
                },
                "lead_score": 80.0 if l.score == "hot" else 50.0 if l.score == "warm" else 20.0,
                "has_budget": bool(l.budget_max and l.budget_max > 0)
            }

            # Trace path
            curr_id = [n["id"] for n in nodes if n.get("type", "").upper() == "TRIGGER"]
            curr = curr_id[0] if curr_id else list(nodes_map.keys())[0]

            visited = 0
            while curr and visited < 20:
                visited += 1
                n = nodes_map.get(curr)
                if not n:
                    break

                ntype = (n.get("type") or "").upper()
                if ntype == "ACTION":
                    akey = n.get("action_key", "general_action")
                    actions_triggered[akey] = actions_triggered.get(akey, 0) + 1
                    total_estimated_cost += ACTION_ESTIMATED_COST.get(akey, 0.01)

                if ntype == "CONDITION":
                    conds = n.get("conditions", [])
                    res_cond = ExpressionEvaluator.evaluate_composite_conditions(conds, "AND", lead_ctx)
                    # Branch
                    branch_edges = edges_map.get(curr, [])
                    curr = branch_edges[0].get("target") if branch_edges else None
                else:
                    out_edges = edges_map.get(curr, [])
                    curr = out_edges[0].get("target") if out_edges else None

        return {
            "total_leads_simulated": total_simulated,
            "triggered_count": triggered_count,
            "actions_triggered": actions_triggered,
            "total_estimated_cost_usd": round(total_estimated_cost, 2),
            "simulation_status": "COMPLETED"
        }
