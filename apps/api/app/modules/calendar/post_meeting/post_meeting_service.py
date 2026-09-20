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
        l_pk = None
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

        # Update Customer-Property Interaction (visited)
        from app.models.calendar_models import Viewing
        from app.models.property_models import LeadPropertyInterest
        viewing = None
        try:
            stmt_viewing = select(Viewing).where(Viewing.meeting_id == meeting.id)
            res_viewing = await self.db.execute(stmt_viewing)
            viewing = res_viewing.scalar_one_or_none()
            if viewing and l_pk:
                p_uuid = uuid.UUID(str(viewing.property_id)) if viewing.property_id else None
                if p_uuid:
                    stmt_int = select(LeadPropertyInterest).where(
                        LeadPropertyInterest.lead_id == l_pk,
                        LeadPropertyInterest.property_id == p_uuid
                    )
                    res_int = await self.db.execute(stmt_int)
                    interest = res_int.scalar_one_or_none()
                    org_val = getattr(lead, "organization_id", None) or getattr(lead, "broker_id", None) or getattr(meeting, "organization_id", None)
                    org_uuid = None
                    if org_val:
                        try:
                            org_uuid = uuid.UUID(str(org_val))
                        except Exception:
                            org_uuid = None

                    notes_append = f"Outcome: {dto.outcome_category} (Rating: {dto.buyer_interest_level}/5). {dto.detailed_feedback or ''}"
                    if interest:
                        interest.status = "visited"
                        interest.notes = (interest.notes or "") + f"\n{notes_append}"
                    else:
                        new_interest = LeadPropertyInterest(
                            organization_id=org_uuid or l_pk,
                            lead_id=l_pk,
                            property_id=p_uuid,
                            status="visited",
                            source_of_match="site_visit",
                            notes=notes_append
                        )
                        self.db.add(new_interest)
        except Exception as exc:
            logger.debug(f"[POST_MEETING] LeadPropertyInterest update skipped: {exc}")

        # Record Customer Timeline Activity
        from app.models.crm_models import Activity
        try:
            b_uuid = uuid.UUID(str(meeting.broker_id)) if meeting.broker_id else None
            l_uuid = l_pk if isinstance(l_pk, uuid.UUID) else (uuid.UUID(str(l_pk)) if l_pk else None)
            interest_label = "VERY_HIGH" if dto.buyer_interest_level >= 5 else ("HIGH" if dto.buyer_interest_level == 4 else ("MEDIUM" if dto.buyer_interest_level == 3 else "LOW"))
            desc_text = dto.detailed_feedback or dto.agent_notes or f"Buyer interest: {interest_label}"
            if interest_label not in desc_text:
                desc_text += f" (Interest: {interest_label})"

            activity = Activity(
                organization_id=meeting.organization_id,
                actor_id=b_uuid,
                lead_id=l_uuid,
                activity_type="site_visit_completed" if dto.outcome_category != "NO_SHOW" else "site_visit_no_show",
                title=f"Site Visit Outcome: {dto.outcome_category.replace('_', ' ').title()}",
                description=desc_text,
                activity_data={
                    "meeting_id": meeting.id,
                    "property_id": viewing.property_id if viewing else None,
                    "outcome_category": dto.outcome_category,
                    "buyer_interest_level": dto.buyer_interest_level,
                    "buyer_interest_rating": interest_label,
                    "agreed_next_step": dto.agreed_next_step,
                }
            )
            self.db.add(activity)
        except Exception as exc:
            logger.debug(f"[POST_MEETING] Activity feed update skipped: {exc}")

        await self.db.commit()
        await self.db.refresh(outcome)

        # Dispatch Celery task for asynchronous Revenue Autopilot & Follow-up evaluation
        if dto.outcome_category != "NO_SHOW":
            try:
                from app.modules.revenue_autopilot.tasks import process_site_visit_completed_task
                process_site_visit_completed_task.delay(str(meeting.id))
            except Exception as exc:
                logger.debug(f"[POST_MEETING] Celery task dispatch skipped: {exc}")

        logger.info(f"[POST_MEETING] Recorded outcome '{dto.outcome_category}' for Meeting {meeting.id}.")
        return MeetingOutcomeDTO.model_validate(outcome)
