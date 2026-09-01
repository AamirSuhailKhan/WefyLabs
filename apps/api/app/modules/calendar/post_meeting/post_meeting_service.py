"""
Post-Meeting Intelligence & Outcome Service
===========================================
Captures structured post-meeting feedback, buyer interest level, next steps,
and syncs outcomes to CRM pipeline and recommendation feedback.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.calendar_models import Meeting, MeetingOutcome
from app.models.lead import Lead
from app.modules.calendar.dto.calendar_schemas import RecordOutcomeRequestDTO, MeetingOutcomeDTO

logger = logging.getLogger(__name__)

class PostMeetingIntelligenceService:
    """
    Records post-meeting outcomes and synchronizes intelligence to CRM.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_outcome(
        self,
        meeting_id: str,
        dto: RecordOutcomeRequestDTO
    ) -> MeetingOutcomeDTO:
        """
        Persists outcome, updates meeting status, and advances lead pipeline stage.
        """
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        res = await self.db.execute(stmt)
        meeting = res.scalar_one_or_none()

        if not meeting:
            raise ValueError(f"Meeting '{meeting_id}' not found.")

        # Update meeting status
        if dto.outcome_category == "NO_SHOW":
            meeting.status = "NO_SHOW"
        else:
            meeting.status = "COMPLETED"

        # Check existing outcome
        stmt_out = select(MeetingOutcome).where(MeetingOutcome.meeting_id == meeting_id)
        res_out = await self.db.execute(stmt_out)
        outcome = res_out.scalar_one_or_none()

        if outcome:
            outcome.outcome_category = dto.outcome_category
            outcome.buyer_interest_level = dto.buyer_interest_level
            outcome.detailed_feedback = dto.detailed_feedback
            outcome.agreed_next_step = dto.agreed_next_step
            outcome.next_follow_up_date = dto.next_follow_up_date
            outcome.agent_notes = dto.agent_notes
        else:
            outcome = MeetingOutcome(
                id=str(uuid.uuid4()),
                meeting_id=meeting.id,
                outcome_category=dto.outcome_category,
                buyer_interest_level=dto.buyer_interest_level,
                detailed_feedback=dto.detailed_feedback,
                agreed_next_step=dto.agreed_next_step,
                next_follow_up_date=dto.next_follow_up_date,
                agent_notes=dto.agent_notes,
                recorded_at=datetime.now(timezone.utc)
            )
            self.db.add(outcome)

        # Advance Lead Stage
        if meeting.lead_id:
            try:
                import uuid as _uuid
                l_pk = _uuid.UUID(str(meeting.lead_id))
            except Exception:
                l_pk = meeting.lead_id

            stmt_l = select(Lead).where(Lead.id == l_pk)
            res_l = await self.db.execute(stmt_l)
            lead = res_l.scalar_one_or_none()
            if lead:
                if dto.outcome_category in ("VERY_INTERESTED", "NEGOTIATION"):
                    lead.pipeline_stage = "negotiation"
                elif dto.outcome_category == "CONVERTED":
                    lead.pipeline_stage = "converted"
                    lead.status = "converted"
                elif dto.outcome_category == "NOT_INTERESTED":
                    lead.pipeline_stage = "nurture"
                elif dto.outcome_category == "NO_SHOW":
                    lead.pipeline_stage = "unresponsive"
                else:
                    lead.pipeline_stage = "viewing_completed"

        await self.db.commit()
        await self.db.refresh(outcome)

        logger.info(f"[POST_MEETING] Recorded outcome '{dto.outcome_category}' for Meeting {meeting.id}.")
        return MeetingOutcomeDTO.model_validate(outcome)
