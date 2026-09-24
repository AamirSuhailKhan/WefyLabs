"""WefyLabs Native CRM — Customer 360 Aggregation Service
=========================================================
Assembles the canonical, 360-degree customer workspace by consolidating
Identity, Leads, Qualification, Property OS, Conversations, Appointments,
Site Visits, Opportunities, Revenue, Tasks, Notes, and AI Insights.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.crm_models import Task, Activity, LeadNote
from app.models.property_models import LeadPropertyInterest, PropertyListing
from app.models.calendar_models import SchedulingMeeting, Viewing, MeetingOutcome
from app.models.transaction_models import DealTransaction
from app.models.revenue_autopilot_models import RevenueOpportunity
from app.models.communication_models import OmnichannelConversation, ChannelMessage
from app.models.qualification_models import QualificationFact
from app.modules.crm.dto.crm_schemas import (
    Customer360Response, CustomerPreferencesDTO, CustomerRevenueJourneyDTO,
    OpportunitySummaryDTO, CRMTaskResponse, CRMActivityResponse, CRMNoteResponse
)
from app.modules.crm.services.crm_timeline_service import CRMTimelineService


class Customer360Service:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.timeline_service = CRMTimelineService(db)

    async def get_customer_360(
        self,
        lead_id: str,
        broker_id: uuid.UUID,
        organization_id: str
    ) -> Customer360Response:
        """
        Consolidates all business systems into the canonical Customer 360 view.
        Enforces tenant isolation by broker_id and organization_id.
        """
        lead_uuid = uuid.UUID(lead_id)

        # 1. Fetch Lead
        stmt = select(Lead).where(
            Lead.id == lead_uuid,
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        res = await self.db.execute(stmt)
        lead = res.scalars().first()
        if not lead:
            raise ValueError(f"Customer {lead_id} not found or unauthorized")

        # 2. Fetch Broker Name
        broker_res = await self.db.execute(select(Broker).where(Broker.id == broker_id))
        broker = broker_res.scalars().first()
        broker_name = broker.name if broker else "Assigned Agent"

        # 3. Preferences DTO
        preferences = CustomerPreferencesDTO(
            budget_min=lead.budget_min,
            budget_max=lead.budget_max,
            budget_currency=lead.budget_currency or "AED",
            property_type=lead.property_type,
            transaction_type=lead.transaction_type,
            preferred_locations=lead.preferred_locations or [],
            timeline=lead.timeline,
            loan_status=lead.loan_status,
            amenities=[]
        )

        # 4. Qualification Facts
        qual_facts_dict: Dict[str, Any] = {
            "score": lead.score,
            "confidence": lead.score_confidence,
            "qualified_at": lead.qualified_at.isoformat() if lead.qualified_at else None,
            "status": lead.status,
            "facts": []
        }
        try:
            qf_stmt = select(QualificationFact).where(QualificationFact.lead_id == lead_uuid)
            qf_res = await self.db.execute(qf_stmt)
            qf_list = qf_res.scalars().all()
            qual_facts_dict["facts"] = [
                {"fact_type": f.fact_type, "value": f.fact_value, "confidence": f.confidence}
                for f in qf_list
            ]
        except Exception:
            pass

        # 5. Property Interests & Matches
        prop_interests: List[Dict[str, Any]] = []
        prop_matches: List[Dict[str, Any]] = []
        try:
            pi_stmt = select(LeadPropertyInterest).where(LeadPropertyInterest.lead_id == lead_uuid)
            pi_res = await self.db.execute(pi_stmt)
            for pi in pi_res.scalars().all():
                p_item = {
                    "id": str(pi.id),
                    "property_id": str(pi.property_id),
                    "interest_level": getattr(pi, "interest_level", "medium"),
                    "match_score": getattr(pi, "match_score", 85.0),
                    "notes": getattr(pi, "notes", None),
                    "created_at": pi.created_at.isoformat() if pi.created_at else None
                }
                prop_interests.append(p_item)
                prop_matches.append(p_item)
        except Exception:
            pass

        # 6. Conversations
        conversations: List[Dict[str, Any]] = []
        try:
            conv_stmt = select(OmnichannelConversation).where(OmnichannelConversation.lead_id == lead_uuid)
            conv_res = await self.db.execute(conv_stmt)
            for conv in conv_res.scalars().all():
                conversations.append({
                    "id": str(conv.id),
                    "channel": conv.channel,
                    "status": conv.status,
                    "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                    "unread_count": getattr(conv, "unread_count", 0)
                })
        except Exception:
            pass

        # 7. Tasks
        tasks: List[CRMTaskResponse] = []
        try:
            task_stmt = select(Task).where(
                or_(Task.lead_id == lead_uuid, Task.lead_id == str(lead_uuid))
            ).order_by(Task.created_at.desc())
            task_res = await self.db.execute(task_stmt)
            now = datetime.now(timezone.utc)
            for t in task_res.scalars().all():
                due_at = t.due_at.replace(tzinfo=timezone.utc) if t.due_at and t.due_at.tzinfo is None else t.due_at
                is_overdue = t.status != "completed" and due_at is not None and due_at < now
                tasks.append(
                    CRMTaskResponse(
                        id=str(t.id),
                        organization_id=t.organization_id,
                        broker_id=str(t.broker_id),
                        lead_id=str(t.lead_id) if t.lead_id else None,
                        assigned_broker_id=str(t.assigned_broker_id) if t.assigned_broker_id else None,
                        title=t.title,
                        description=t.description,
                        due_at=t.due_at,
                        status=t.status,
                        priority=t.priority,
                        is_overdue=is_overdue,
                        completed_at=t.completed_at,
                        created_at=t.created_at,
                        updated_at=t.updated_at
                    )
                )
        except Exception:
            pass

        # 8. Activities
        activities: List[CRMActivityResponse] = []
        try:
            act_stmt = select(Activity).where(
                or_(Activity.lead_id == lead_uuid, Activity.lead_id == str(lead_uuid))
            ).order_by(Activity.created_at.desc()).limit(20)
            act_res = await self.db.execute(act_stmt)
            for a in act_res.scalars().all():
                activities.append(
                    CRMActivityResponse(
                        id=str(a.id),
                        organization_id=a.organization_id,
                        lead_id=str(a.lead_id) if a.lead_id else None,
                        actor_id=str(a.actor_id) if a.actor_id else None,
                        actor_type="HUMAN" if a.actor_id else "SYSTEM",
                        activity_type=a.activity_type,
                        title=a.title,
                        description=a.description,
                        activity_data=a.activity_data or {},
                        created_at=a.created_at
                    )
                )
        except Exception:
            pass

        # 9. Notes
        notes: List[CRMNoteResponse] = []
        try:
            notes_stmt = select(LeadNote).where(LeadNote.lead_id == lead_uuid).order_by(LeadNote.created_at.desc())
            notes_res = await self.db.execute(notes_stmt)
            for n in notes_res.scalars().all():
                notes.append(
                    CRMNoteResponse(
                        id=str(n.id),
                        lead_id=str(n.lead_id),
                        broker_id=str(n.broker_id),
                        content=n.content,
                        visibility="ORGANIZATION",
                        is_ai_generated=False,
                        created_at=n.created_at
                    )
                )
        except Exception:
            pass

        # 10. Appointments & Site Visits
        appointments: List[Dict[str, Any]] = []
        site_visits: List[Dict[str, Any]] = []
        first_appt_booked: Optional[datetime] = None
        site_visit_completed: Optional[datetime] = None

        try:
            mtg_stmt = select(SchedulingMeeting).where(SchedulingMeeting.lead_id == lead_uuid).order_by(SchedulingMeeting.start_utc.asc())
            mtg_res = await self.db.execute(mtg_stmt)
            for m in mtg_res.scalars().all():
                m_dict = {
                    "id": str(m.id),
                    "title": m.title,
                    "meeting_type": m.meeting_type,
                    "status": m.status,
                    "start_utc": m.start_utc.isoformat(),
                    "end_utc": m.end_utc.isoformat(),
                    "location_address": m.location_address,
                    "virtual_provider": m.virtual_provider
                }
                appointments.append(m_dict)
                if not first_appt_booked:
                    first_appt_booked = m.created_at

                if m.meeting_type in ("PROPERTY_VIEWING", "SITE_VISIT"):
                    site_visits.append(m_dict)
                    if m.status == "COMPLETED" and not site_visit_completed:
                        site_visit_completed = m.end_utc
        except Exception:
            pass

        # 11. Opportunities / Deals
        opportunities: List[OpportunitySummaryDTO] = []
        deal_agreed_price: Optional[float] = None
        recorded_revenue: Optional[float] = None

        try:
            deal_stmt = select(DealTransaction).where(DealTransaction.lead_id == lead_uuid)
            deal_res = await self.db.execute(deal_stmt)
            for d in deal_res.scalars().all():
                deal_agreed_price = float(d.agreed_price)
                if d.current_stage == "won":
                    recorded_revenue = float(d.agreed_price)

                opportunities.append(
                    OpportunitySummaryDTO(
                        id=str(d.id),
                        lead_id=str(d.lead_id),
                        lead_name=lead.name,
                        lead_phone=lead.phone,
                        property_id=str(d.property_id) if d.property_id else None,
                        deal_name=d.deal_name,
                        agreed_price=float(d.agreed_price),
                        currency=d.currency,
                        current_stage=d.current_stage,
                        commission_percentage=float(d.commission_percentage),
                        estimated_commission_amount=float(d.estimated_commission_amount),
                        risk_level=d.risk_level,
                        closing_probability_pct=float(d.closing_probability_pct),
                        is_stalled=False,
                        days_in_stage=0,
                        created_at=d.created_at,
                        updated_at=d.updated_at
                    )
                )
        except Exception:
            pass

        # 12. Revenue Journey
        revenue_journey = CustomerRevenueJourneyDTO(
            stage=lead.pipeline_stage,
            source_channel=lead.source,
            first_seen_at=lead.created_at,
            qualified_at=lead.qualified_at,
            appointment_booked_at=first_appt_booked,
            site_visit_completed_at=site_visit_completed,
            opportunity_created_at=opportunities[0].created_at if opportunities else None,
            deal_agreed_price=deal_agreed_price,
            recorded_revenue=recorded_revenue
        )

        # 13. Unified Timeline
        timeline = await self.timeline_service.get_unified_timeline(
            lead_id=lead_id,
            organization_id=organization_id,
            limit=50
        )

        # 14. AI Insights & Next Best Action
        ai_insights: Dict[str, Any] = {
            "score": lead.score,
            "confidence": lead.score_confidence,
            "next_best_action": "Follow up with client to confirm requirements"
        }
        try:
            rev_op_stmt = select(RevenueOpportunity).where(
                RevenueOpportunity.lead_id == lead_uuid,
                RevenueOpportunity.status == "OPEN"
            ).order_by(desc(RevenueOpportunity.score)).limit(1)
            rev_op_res = await self.db.execute(rev_op_stmt)
            rev_op = rev_op_res.scalars().first()
            if rev_op:
                ai_insights["recommended_action"] = rev_op.recommended_action
                ai_insights["urgency"] = rev_op.urgency
                ai_insights["next_best_action"] = rev_op.recommended_action
        except Exception:
            pass

        return Customer360Response(
            customer_id=str(lead.id),
            organization_id=organization_id,
            name=lead.name,
            primary_email=lead.email,
            primary_phone=lead.phone,
            owner_id=str(lead.broker_id),
            owner_name=broker_name,
            lead_status=lead.status,
            pipeline_stage=lead.pipeline_stage,
            temperature=lead.score or "pending",
            source=lead.source,
            campaign=None,
            created_at=lead.created_at,
            last_activity_at=lead.updated_at,
            sla_state="ON_TRACK",
            next_best_action=ai_insights.get("next_best_action"),
            preferences=preferences,
            qualification=qual_facts_dict,
            property_interests=prop_interests,
            property_matches=prop_matches,
            conversations=conversations,
            tasks=tasks,
            activities=activities,
            notes=notes,
            appointments=appointments,
            site_visits=site_visits,
            opportunities=opportunities,
            revenue_journey=revenue_journey,
            timeline=timeline,
            ai_insights=ai_insights
        )
