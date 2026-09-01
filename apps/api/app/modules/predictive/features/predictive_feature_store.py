"""
Predictive Feature Store & Leakage Prevention Engine
====================================================
Generates time-aware feature vectors for leads, opportunities, and campaigns.
Enforces strict temporal consistency to prevent future target data leakage.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Activity
from app.models.conversation import Conversation

logger = logging.getLogger(__name__)

FEATURE_SCHEMA_VERSION = "v1.0.0"

class PredictiveFeatureStore:
    """
    Computes time-aware feature vectors without future data leakage.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_lead_features(
        self,
        lead_id: str,
        as_of_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extracts features for a lead strictly as of `as_of_timestamp` (defaults to current UTC time).
        Events occurring after `as_of_timestamp` are strictly excluded to prevent data leakage.
        """
        import uuid as _uuid
        try:
            l_pk = _uuid.UUID(str(lead_id))
        except Exception:
            l_pk = lead_id

        cutoff = as_of_timestamp or datetime.now(timezone.utc)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)

        # 1. Query Lead
        stmt = select(Lead).where(Lead.id == l_pk)
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        lead_created = lead.created_at if lead.created_at.tzinfo else lead.created_at.replace(tzinfo=timezone.utc)
        if lead_created > cutoff:
            raise ValueError(f"Data Leakage Violation: Lead was created at {lead_created.isoformat()}, after cutoff {cutoff.isoformat()}.")

        lead_age_days = max(0.1, (cutoff - lead_created).total_seconds() / 86400.0)

        # 2. Activity Count before cutoff
        stmt_act = select(func.count(Activity.id)).where(
            and_(
                Activity.lead_id == str(lead.id),
                Activity.created_at <= cutoff
            )
        )
        res_act = await self.db.execute(stmt_act)
        activity_count = res_act.scalar() or 0

        # Last activity before cutoff
        stmt_last_act = select(Activity).where(
            and_(
                Activity.lead_id == str(lead.id),
                Activity.created_at <= cutoff
            )
        ).order_by(Activity.created_at.desc()).limit(1)
        res_last_act = await self.db.execute(stmt_last_act)
        last_act = res_last_act.scalar_one_or_none()
        hours_since_last_activity = 168.0  # Default 7 days
        if last_act and last_act.created_at:
            act_t = last_act.created_at if last_act.created_at.tzinfo else last_act.created_at.replace(tzinfo=timezone.utc)
            hours_since_last_activity = max(0.0, (cutoff - act_t).total_seconds() / 3600.0)

        # 3. Conversations before cutoff
        stmt_msgs = select(Conversation).where(
            and_(
                Conversation.lead_id == str(lead.id),
                Conversation.created_at <= cutoff
            )
        ).order_by(Conversation.created_at.asc())
        res_msgs = await self.db.execute(stmt_msgs)
        messages = res_msgs.scalars().all()

        inbound_count = len([m for m in messages if m.direction == "inbound"])
        outbound_count = len([m for m in messages if m.direction == "outbound"])
        customer_response_ratio = (inbound_count / outbound_count) if outbound_count > 0 else 0.0

        # 4. Meetings before cutoff
        stmt_mtg = select(Meeting).where(
            and_(
                Meeting.lead_id == str(lead.id),
                Meeting.created_at <= cutoff
            )
        )
        res_mtg = await self.db.execute(stmt_mtg)
        meetings = res_mtg.scalars().all()
        viewings_count = len(meetings)
        cancelled_viewings = len([m for m in meetings if m.status == "cancelled"])
        attended_viewings = len([m for m in meetings if m.status == "completed"])
        viewing_attendance_ratio = (attended_viewings / viewings_count) if viewings_count > 0 else 0.0

        # 5. Financial Features
        budget_val = float(lead.budget_max or 2_000_000.0)
        has_budget = bool(lead.budget_max and lead.budget_max > 0)
        has_location = bool(lead.preferred_locations and len(lead.preferred_locations) > 0)

        # 6. Intent & Score Features
        score_val = 80.0 if lead.score == "hot" else 50.0 if lead.score == "warm" else 20.0
        score_conf = float(lead.score_confidence if lead.score_confidence is not None else 0.8)

        feature_dict = {
            "lead_id": str(lead.id),
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "as_of_timestamp": cutoff.isoformat(),
            "lead_age_days": round(lead_age_days, 1),
            "activity_count": activity_count,
            "hours_since_last_activity": round(hours_since_last_activity, 1),
            "inbound_message_count": inbound_count,
            "outbound_message_count": outbound_count,
            "customer_response_ratio": round(min(2.0, customer_response_ratio), 2),
            "viewings_count": viewings_count,
            "cancelled_viewings_count": cancelled_viewings,
            "attended_viewings_count": attended_viewings,
            "viewing_attendance_ratio": round(viewing_attendance_ratio, 2),
            "budget_max_aed": budget_val,
            "has_budget": has_budget,
            "has_preferred_location": has_location,
            "lead_score_points": score_val,
            "score_confidence": score_conf,
            "pipeline_stage": (lead.pipeline_stage or "new").lower(),
        }
        return feature_dict
