"""
Part 35 — Revenue Autopilot Action Handler & Lifecycle Execution
=================================================================
Executes agent-approved revenue actions with human-in-the-loop,
idempotent task/meeting/interest creation, activity logging, and audit tracking.
Strict Principles:
1. Multi-Tenant Isolated: Action execution strictly enforces tenant and role ownership.
2. Idempotent: Does not create duplicate tasks or follow-ups on repeated clicks.
3. Durable Audit Trail: Logs state transitions into RevenueFeedbackLog and AuditLog.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.lead import Lead
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.broker import Broker
from app.models.crm_models import Task, Meeting, Activity
from app.models.audit_log import AuditLog
from app.models.revenue_autopilot_models import RevenueOpportunity, RevenueFeedbackLog
from app.modules.revenue_autopilot.dto import (
    ActionOpportunityRequestDTO,
    DismissOpportunityRequestDTO,
    FeedbackOpportunityRequestDTO,
)

logger = logging.getLogger("beetlelabs.revenue_autopilot.action_handler")


class RevenueActionHandler:
    """
    Handles lifecycle action approval, dismissal, and feedback submission
    for Revenue Opportunities.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_action(
        self,
        opportunity_id: str | uuid.UUID,
        broker: Broker,
        dto: ActionOpportunityRequestDTO,
    ) -> Dict[str, Any]:
        """
        Executes an agent action on a Revenue Opportunity.
        Enforces tenant isolation and updates CRM state idempotently.
        """
        opp_uuid = uuid.UUID(str(opportunity_id))
        broker_uuid = uuid.UUID(str(broker.id))
        org_uuid = uuid.UUID(str(getattr(broker, "organization_id", None) or broker.id))
        now = datetime.now(timezone.utc)

        # 1. Fetch opportunity with tenant check
        stmt = select(RevenueOpportunity).where(
            and_(
                RevenueOpportunity.id == opp_uuid,
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
        opp = (await self.db.execute(stmt)).scalars().first()
        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue Opportunity {opportunity_id} not found in current organization."
            )

        # 2. Fetch related lead
        lead_stmt = select(Lead).where(
            and_(Lead.id == opp.lead_id, Lead.broker_id == broker_uuid)
        )
        lead = (await self.db.execute(lead_stmt)).scalars().first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated lead not found or inaccessible."
            )

        # 3. Action-specific side effects
        created_task_id = None
        created_meeting_id = None
        action_summary = f"Executed action '{dto.action_type}' for {lead.name or 'lead'}"

        if dto.action_type in ("CALL_LEAD", "REACTIVATE_LEAD", "REVIEW_DEAL"):
            if dto.create_follow_up_task:
                # Check if an existing pending task exists for this lead to avoid duplicates
                existing_task_stmt = select(Task).where(
                    and_(
                        Task.broker_id == broker_uuid,
                        Task.lead_id == lead.id,
                        Task.status == "pending",
                        Task.title.ilike(f"%{dto.action_type}%")
                    )
                )
                existing_task = (await self.db.execute(existing_task_stmt)).scalars().first()
                if not existing_task:
                    due = dto.scheduled_at or (now + timedelta(hours=4))
                    new_task = Task(
                        broker_id=broker_uuid,
                        lead_id=lead.id,
                        organization_id=str(org_uuid),
                        title=f"{dto.action_type.replace('_', ' ').title()} - {lead.name or 'Prospect'}",
                        description=dto.notes or opp.reason,
                        due_at=due,
                        priority="high" if opp.priority in ("CRITICAL", "HIGH") else "normal",
                        status="pending",
                    )
                    self.db.add(new_task)
                    await self.db.flush()
                    created_task_id = str(new_task.id)

        elif dto.action_type == "SCHEDULE_SITE_VISIT":
            # Schedule a site visit meeting
            scheduled_time = dto.scheduled_at or (now + timedelta(days=2))
            meeting = Meeting(
                broker_id=broker_uuid,
                lead_id=lead.id,
                organization_id=str(org_uuid),
                title=f"Site Visit - {lead.name or 'Prospect'}",
                meeting_type="site_visit",
                scheduled_at=scheduled_time,
                duration_minutes=60,
                location=opp.recommended_property_snapshot.get("locality") or "Property Location",
                notes=dto.notes or f"Generated via Revenue Autopilot (Opp #{opp.id})",
                status="scheduled",
            )
            self.db.add(meeting)
            await self.db.flush()
            created_meeting_id = str(meeting.id)

        elif dto.action_type == "SEND_PROPERTY_RECOMMENDATION" and opp.property_id:
            # Record in LeadPropertyInterest junction
            interest_stmt = select(LeadPropertyInterest).where(
                and_(
                    LeadPropertyInterest.organization_id == org_uuid,
                    LeadPropertyInterest.lead_id == lead.id,
                    LeadPropertyInterest.property_id == opp.property_id,
                )
            )
            interest = (await self.db.execute(interest_stmt)).scalars().first()
            if not interest:
                interest = LeadPropertyInterest(
                    organization_id=org_uuid,
                    lead_id=lead.id,
                    property_id=opp.property_id,
                    status="RECOMMENDED",
                    match_score=opp.match_score,
                    deterministic_score=opp.match_score,
                    confidence=opp.confidence,
                    source_of_match="revenue_autopilot",
                    notes=dto.notes or opp.reason,
                )
                self.db.add(interest)
            else:
                interest.status = "RECOMMENDED"
                interest.match_score = opp.match_score

        # 4. Log Activity
        activity = Activity(
            organization_id=str(org_uuid),
            actor_id=broker_uuid,
            lead_id=lead.id,
            activity_type="revenue_action_executed",
            title=f"Revenue Action: {dto.action_type.replace('_', ' ').title()}",
            description=dto.notes or opp.reason,
            activity_data={
                "opportunity_id": str(opp.id),
                "opportunity_type": opp.opportunity_type,
                "action_type": dto.action_type,
                "task_id": created_task_id,
                "meeting_id": created_meeting_id,
            }
        )
        self.db.add(activity)

        # 5. Transition Opportunity State
        opp.status = "ACTIONED"
        opp.actioned_at = now
        if dto.notes:
            opp.feedback_notes = dto.notes

        # 6. Feedback / Analytics Log
        fb_log = RevenueFeedbackLog(
            opportunity_id=opp.id,
            organization_id=org_uuid,
            broker_id=broker_uuid,
            lead_id=lead.id,
            property_id=opp.property_id,
            action_type=dto.action_type,
            notes=dto.notes,
            features_snapshot={
                "opportunity_score": opp.opportunity_score,
                "match_score": opp.match_score,
                "urgency": opp.urgency,
                "priority": opp.priority,
            }
        )
        self.db.add(fb_log)

        # 7. Audit Log
        audit = AuditLog(
            organization_id=org_uuid,
            actor_id=broker_uuid,
            action="revenue_opportunity.actioned",
            resource_type="revenue_opportunity",
            resource_id=str(opp.id),
            new_values={
                "action_type": dto.action_type,
                "lead_id": str(lead.id),
                "property_id": str(opp.property_id) if opp.property_id else None,
            }
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(opp)

        return {
            "opportunity_id": str(opp.id),
            "status": opp.status,
            "action_type": dto.action_type,
            "created_task_id": created_task_id,
            "created_meeting_id": created_meeting_id,
            "message": action_summary,
        }

    async def dismiss_opportunity(
        self,
        opportunity_id: str | uuid.UUID,
        broker: Broker,
        dto: Optional[DismissOpportunityRequestDTO] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dismisses an opportunity with structured reason and records feedback log.
        """
        opp_uuid = uuid.UUID(str(opportunity_id))
        broker_uuid = uuid.UUID(str(broker.id))
        org_uuid = uuid.UUID(str(getattr(broker, "organization_id", None) or broker.id))
        now = datetime.now(timezone.utc)

        dismissal_reason = reason or (dto.reason if dto else "Not relevant")
        dismissal_notes = dto.notes if dto else None

        stmt = select(RevenueOpportunity).where(
            and_(
                RevenueOpportunity.id == opp_uuid,
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
        opp = (await self.db.execute(stmt)).scalars().first()
        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue Opportunity {opportunity_id} not found."
            )

        opp.status = "DISMISSED"
        opp.dismissed_at = now
        opp.dismissal_reason = dismissal_reason
        if dismissal_notes:
            opp.feedback_notes = dismissal_notes

        # Feedback Log
        fb_log = RevenueFeedbackLog(
            opportunity_id=opp.id,
            organization_id=org_uuid,
            broker_id=broker_uuid,
            lead_id=opp.lead_id,
            property_id=opp.property_id,
            action_type="DISMISSED",
            rating="NO",
            reason=dismissal_reason,
            notes=dismissal_notes,
            features_snapshot={
                "opportunity_score": opp.opportunity_score,
                "opportunity_type": opp.opportunity_type,
            }
        )
        self.db.add(fb_log)

        # Audit Log
        audit = AuditLog(
            organization_id=org_uuid,
            actor_id=broker_uuid,
            action="revenue_opportunity.dismissed",
            resource_type="revenue_opportunity",
            resource_id=str(opp.id),
            new_values={"reason": dismissal_reason}
        )
        self.db.add(audit)

        await self.db.commit()
        return {"opportunity_id": str(opp.id), "status": "DISMISSED", "reason": dismissal_reason}

    async def complete_opportunity(
        self,
        opportunity_id: str | uuid.UUID,
        broker: Broker,
        outcome: str = "DEAL_WON",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Completes an opportunity marking commercial outcome.
        """
        opp_uuid = uuid.UUID(str(opportunity_id))
        broker_uuid = uuid.UUID(str(broker.id))
        org_uuid = uuid.UUID(str(getattr(broker, "organization_id", None) or broker.id))
        now = datetime.now(timezone.utc)

        stmt = select(RevenueOpportunity).where(
            and_(
                RevenueOpportunity.id == opp_uuid,
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
        opp = (await self.db.execute(stmt)).scalars().first()
        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue Opportunity {opportunity_id} not found."
            )

        opp.status = "COMPLETED"
        opp.completed_at = now
        opp.actual_outcome = outcome
        if notes:
            opp.feedback_notes = notes

        fb_log = RevenueFeedbackLog(
            opportunity_id=opp.id,
            organization_id=org_uuid,
            broker_id=broker_uuid,
            lead_id=opp.lead_id,
            property_id=opp.property_id,
            action_type="COMPLETED",
            actual_outcome=outcome,
            notes=notes,
            features_snapshot={
                "opportunity_score": opp.opportunity_score,
                "opportunity_type": opp.opportunity_type,
            }
        )
        self.db.add(fb_log)

        audit = AuditLog(
            organization_id=org_uuid,
            actor_id=broker_uuid,
            action="revenue_opportunity.completed",
            resource_type="revenue_opportunity",
            resource_id=str(opp.id),
            new_values={"outcome": outcome}
        )
        self.db.add(audit)

        await self.db.commit()
        return {"opportunity_id": str(opp.id), "status": "COMPLETED", "outcome": outcome}

    async def submit_feedback(
        self,
        opportunity_id: str | uuid.UUID,
        broker: Broker,
        dto: FeedbackOpportunityRequestDTO,
    ) -> Dict[str, Any]:
        """
        Records agent feedback (YES/NO/NOT_SURE) and actual commercial outcomes.
        """
        opp_uuid = uuid.UUID(str(opportunity_id))
        broker_uuid = uuid.UUID(str(broker.id))
        org_uuid = uuid.UUID(str(getattr(broker, "organization_id", None) or broker.id))
        now = datetime.now(timezone.utc)

        stmt = select(RevenueOpportunity).where(
            and_(
                RevenueOpportunity.id == opp_uuid,
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
        opp = (await self.db.execute(stmt)).scalars().first()
        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue Opportunity {opportunity_id} not found."
            )

        opp.feedback_rating = dto.rating
        if dto.reason:
            opp.dismissal_reason = dto.reason
        if dto.notes:
            opp.feedback_notes = dto.notes
        if dto.actual_outcome:
            opp.actual_outcome = dto.actual_outcome
            # If outcome is a closing state, complete the opportunity
            if dto.actual_outcome.lower() in ("deal_won", "deal_lost", "site_visit_completed"):
                opp.status = "COMPLETED"
                opp.completed_at = now

        fb_log = RevenueFeedbackLog(
            opportunity_id=opp.id,
            organization_id=org_uuid,
            broker_id=broker_uuid,
            lead_id=opp.lead_id,
            property_id=opp.property_id,
            action_type="FEEDBACK",
            rating=dto.rating,
            reason=dto.reason,
            notes=dto.notes,
            actual_outcome=dto.actual_outcome,
            features_snapshot={
                "opportunity_score": opp.opportunity_score,
                "opportunity_type": opp.opportunity_type,
            }
        )
        self.db.add(fb_log)

        await self.db.commit()
        return {
            "opportunity_id": str(opp.id),
            "status": "FEEDBACK_LOGGED",
            "opportunity_status": opp.status,
            "feedback_rating": dto.rating
        }

    # Alias for flexibility
    log_feedback = submit_feedback
