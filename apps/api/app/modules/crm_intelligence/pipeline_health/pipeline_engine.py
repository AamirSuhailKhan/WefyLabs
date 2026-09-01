"""
Pipeline Stagnation & Opportunity Risk Engine
=============================================
Calculates stage velocity, drop-off rates, stagnation excess days,
and pipeline revenue at risk across all deals.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.lead import Lead
from app.models.crm_models import PipelineStage, Task, Meeting
from app.models.crm_intelligence_models import PipelineHealthSnapshot, OpportunityHealthSnapshot

logger = logging.getLogger(__name__)

# Configurable expected stage dwell times in days
DEFAULT_STAGE_DURATION_DAYS: Dict[str, int] = {
    "new": 2,
    "contacted": 3,
    "qualified": 5,
    "meeting": 7,
    "viewing": 7,
    "negotiation": 14,
    "offer": 10,
    "closed_won": 0,
    "closed_lost": 0,
}

class PipelineIntelligenceEngine:
    """
    Evaluates pipeline health, velocity, stage stagnation, and opportunity closing risks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_pipeline_health(self, organization_id: str) -> List[PipelineHealthSnapshot]:
        """
        Computes aggregate metrics for each pipeline stage and detects stagnation.
        """
        now = datetime.now(timezone.utc)

        # 1. Query leads
        stmt_leads = select(Lead).where(
            and_(
                Lead.deleted_at == None,
            )
        )
        res_leads = await self.db.execute(stmt_leads)
        leads = res_leads.scalars().all()

        stages: Dict[str, List[Lead]] = {}
        for l in leads:
            stg = (l.pipeline_stage or "new").lower()
            if stg not in stages:
                stages[stg] = []
            stages[stg].append(l)

        snapshots: List[PipelineHealthSnapshot] = []

        for stg_name, stage_leads in stages.items():
            expected_days = DEFAULT_STAGE_DURATION_DAYS.get(stg_name, 7)
            lead_count = len(stage_leads)

            total_val = 0.0
            weighted_val = 0.0
            stagnant_count = 0
            rev_at_risk = 0.0
            total_dwell_days = 0.0

            # Conversion weight proxy based on stage maturity
            stage_weight = (
                0.10 if stg_name == "new" else
                0.25 if stg_name in ("contacted", "qualified") else
                0.50 if stg_name in ("meeting", "viewing") else
                0.75 if stg_name in ("negotiation", "offer") else
                1.0 if stg_name == "closed_won" else 0.0
            )

            for l in stage_leads:
                l_val = float(l.budget_max or 2_000_000.0)
                total_val += l_val
                weighted_val += (l_val * stage_weight)

                updated_t = l.updated_at if l.updated_at else l.created_at
                if updated_t:
                    t_clean = updated_t if updated_t.tzinfo else updated_t.replace(tzinfo=timezone.utc)
                    dwell = max(0.1, (now - t_clean).total_seconds() / 86400.0)
                else:
                    dwell = 1.0
                total_dwell_days += dwell

                if expected_days > 0 and dwell > expected_days:
                    stagnant_count += 1
                    rev_at_risk += l_val

            avg_dwell = (total_dwell_days / lead_count) if lead_count > 0 else 0.0
            drop_off_rate = (stagnant_count / lead_count * 100.0) if lead_count > 0 else 0.0
            conversion_rate = stage_weight * 100.0

            snap = PipelineHealthSnapshot(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                stage_id=stg_name,
                stage_name=stg_name.replace("_", " ").title(),
                lead_count=lead_count,
                total_pipeline_value_aed=round(total_val, 2),
                weighted_pipeline_value_aed=round(weighted_val, 2),
                avg_stage_duration_days=round(avg_dwell, 1),
                stagnant_leads_count=stagnant_count,
                conversion_rate_pct=round(conversion_rate, 1),
                drop_off_rate_pct=round(drop_off_rate, 1),
                revenue_at_risk_aed=round(rev_at_risk, 2),
                snapshot_date=now
            )
            self.db.add(snap)
            snapshots.append(snap)

        await self.db.commit()
        logger.info(f"[PIPELINE] Generated health snapshot for {len(snapshots)} stages.")
        return snapshots

    async def evaluate_opportunity_health(self, lead_id: str, organization_id: str) -> OpportunityHealthSnapshot:
        """
        Assesses deal risk, stagnation, and recommended recovery action for an individual opportunity.
        """
        import uuid as _uuid
        try:
            l_pk = _uuid.UUID(str(lead_id))
        except Exception:
            l_pk = lead_id

        stmt = select(Lead).where(Lead.id == l_pk)
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        now = datetime.now(timezone.utc)
        updated_t = lead.updated_at if lead.updated_at else lead.created_at
        t_clean = updated_t if updated_t.tzinfo else updated_t.replace(tzinfo=timezone.utc) if updated_t else now
        stagnation_days = int((now - t_clean).total_seconds() // 86400)

        stg = (lead.pipeline_stage or "new").lower()
        expected = DEFAULT_STAGE_DURATION_DAYS.get(stg, 7)

        val = float(lead.budget_max or 1_500_000.0)

        if stagnation_days > (expected * 2):
            deal_health = "CRITICAL"
            momentum = 20.0
            closing_prob = 0.15
            rev_at_risk = val
            action = "Urgent manager review: schedule decision-maker alignment call."
        elif stagnation_days > expected:
            deal_health = "AT_RISK"
            momentum = 50.0
            closing_prob = 0.35
            rev_at_risk = val * 0.5
            action = "Dispatch refreshed property comparisons with attractive payment terms."
        else:
            deal_health = "STRONG"
            momentum = 85.0
            closing_prob = 0.70
            rev_at_risk = 0.0
            action = "Maintain scheduled follow-up cadence."

        opp = OpportunityHealthSnapshot(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=str(lead.id),
            deal_health=deal_health,
            momentum_score=momentum,
            closing_probability=closing_prob,
            stagnation_days=stagnation_days,
            competitor_threat_detected=False,
            revenue_at_risk_aed=rev_at_risk,
            recommended_recovery_action=action
        )
        self.db.add(opp)
        await self.db.commit()
        await self.db.refresh(opp)
        return opp
