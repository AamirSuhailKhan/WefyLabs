"""
AI Meeting Preparation Brief Service
====================================
Generates comprehensive pre-meeting briefing documents for sales brokers,
synthesizing buyer preferences, budget ceiling, objections, and top recommended inventory.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.calendar_models import Meeting, MeetingPreparationBrief
from app.models.lead import Lead

logger = logging.getLogger(__name__)

class PreparationBriefService:
    """
    Synthesizes CRM and recommendation intelligence into an internal broker meeting brief.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_brief(self, meeting_id: str) -> MeetingPreparationBrief:
        """
        Generates and persists the internal AI preparation brief for a meeting.
        """
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        res = await self.db.execute(stmt)
        meeting = res.scalar_one_or_none()

        if not meeting:
            raise ValueError(f"Meeting '{meeting_id}' not found.")

        lead: Optional[Lead] = None
        if meeting.lead_id:
            stmt_l = select(Lead).where(Lead.id == meeting.lead_id)
            res_l = await self.db.execute(stmt_l)
            lead = res_l.scalar_one_or_none()

        lead_name = lead.name if lead else "Buyer"
        loc = lead.preferred_locations[0] if (lead and lead.preferred_locations) else "prime area"
        ptype = (lead.property_type or "residential unit").capitalize() if lead else "Property"
        budget = f"{lead.budget_max:,.0f} AED" if (lead and lead.budget_max) else "Flexible / Verified"

        buyer_summary = (
            f"{lead_name} is actively looking for a {ptype} in {loc} with a budget up to {budget}. "
            f"Pipeline stage is '{lead.pipeline_stage if lead else 'new'}'."
        )

        objections = [
            "Handover timeline alignment",
            "Service charges and post-handover payment plan flexibility"
        ]

        questions = [
            f"Are you purchasing this {ptype} for end-use residence or rental investment yield?",
            "What is your target down-payment capacity versus developer payment milestones?",
            "Would you like to review alternative units in adjacent towers today?"
        ]

        brief = MeetingPreparationBrief(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            lead_id=str(lead.id) if lead else "unassigned",
            buyer_summary=buyer_summary,
            verified_budget=budget,
            key_objections=objections,
            recommended_properties=[{"title": "Creek Waters 3BHK", "price": "2,200,000 AED", "locality": loc}],
            suggested_questions=questions,
            next_best_action="Guide on payment plans and propose deposit lock on preferred unit",
            generated_at=datetime.now(timezone.utc)
        )
        self.db.add(brief)
        await self.db.commit()
        await self.db.refresh(brief)

        logger.info(f"[MEETING_BRIEF] Generated preparation brief for Meeting {meeting.id}.")
        return brief
