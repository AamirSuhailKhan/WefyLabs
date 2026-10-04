"""
Part 30 — AI Real-Estate Agent Daily Command Center Orchestration Service
==========================================================================
High-performance, action-first operational command center service.
Aggregates Leads, Tasks, Meetings, Site Visits, Matches, and Inventory
with strict tenant isolation, bounded DB execution, and explainable priorities.
"""
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Activity
from app.models.property_models import PropertyListing, LeadPropertyInterest
from app.models.command_center_models import CommandCenterDismissal
from app.models.audit_log import AuditLog
from app.modules.command_center.dto import (
    PriorityItemDTO,
    FirstContactSlaItemDTO,
    OverdueFollowupItemDTO,
    TodayScheduleItemDTO,
    HotLeadItemDTO,
    StaleLeadSummaryDTO,
    InventoryOpportunityDTO,
    InventoryGapItemDTO,
    DemandHeatmapDTO,
    DailyBriefingDTO,
    CommandCenterSummaryDTO,
    CommandCenterResponseDTO,
    DismissItemRequestDTO,
    StartMyDayStepDTO,
    StartMyDayResponseDTO
)
from app.modules.command_center.priority_engine import CommandCenterPriorityEngine
from app.modules.command_center.inventory_intelligence import InventoryIntelligenceEngine
from app.modules.command_center.briefing_service import CommandCenterBriefingService

logger = logging.getLogger("wefylabs.command_center.service")


class CommandCenterService:
    """
    Central orchestration service for the AI Agent Daily Command Center.
    """

    def __init__(self, db: AsyncSession, ai_service: Optional[Any] = None):
        self.db = db
        self.ai_service = ai_service

    async def get_command_center_data(
        self,
        broker: Any,
        timezone_str: str = "Asia/Kolkata"
    ) -> CommandCenterResponseDTO:
        """
        Gathers and synthesizes all operational items for the broker's workspace.
        Enforces tenant isolation across every database query.
        """
        now = datetime.now(timezone.utc)
        if isinstance(broker, (str, uuid.UUID)):
            broker_uuid = uuid.UUID(str(broker))
            broker_obj = await self.db.get(Broker, broker_uuid)
            if broker_obj:
                broker = broker_obj
                broker_name = getattr(broker, "name", "Agent") or "Agent"
                org_id_str = str(getattr(broker, "organization_id", None) or broker.id)
            else:
                broker_name = "Agent"
                org_id_str = str(broker_uuid)
        else:
            broker_uuid = uuid.UUID(str(broker.id))
            org_id_str = str(getattr(broker, "organization_id", None) or broker.id)
            broker_name = getattr(broker, "name", "Agent") or "Agent"

        # 1. Fetch active dismissals and snoozes
        stmt_dismissals = select(CommandCenterDismissal).where(
            and_(
                CommandCenterDismissal.broker_id == broker_uuid,
                or_(
                    CommandCenterDismissal.action_type == "dismissed",
                    and_(
                        CommandCenterDismissal.action_type == "snoozed",
                        CommandCenterDismissal.snoozed_until > now
                    )
                )
            )
        )
        dismissals = list((await self.db.execute(stmt_dismissals)).scalars().all())
        dismissed_keys = {d.item_key for d in dismissals}

        # 2. Fetch Active Leads (bounded to top 200 recent)
        stmt_leads = select(Lead).where(
            and_(
                Lead.broker_id == broker_uuid,
                Lead.deleted_at.is_(None),
                Lead.status.in_(["pending", "active", "qualified", "new"])
            )
        ).order_by(Lead.updated_at.desc()).limit(200)
        leads = list((await self.db.execute(stmt_leads)).scalars().all())

        # 3. Fetch Pending Tasks (bounded to 150)
        stmt_tasks = select(Task).where(
            and_(
                Task.broker_id == broker_uuid,
                Task.status.in_(["pending", "in_progress"])
            )
        ).order_by(Task.due_at.asc()).limit(150)
        tasks = list((await self.db.execute(stmt_tasks)).scalars().all())

        # 4. Fetch Today's Meetings (bounded range +/- 24 hours from UTC now)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        stmt_meetings = select(Meeting).where(
            and_(
                Meeting.broker_id == broker_uuid,
                Meeting.scheduled_at >= day_start,
                Meeting.scheduled_at <= day_end,
                Meeting.status.in_(["scheduled", "in_progress"])
            )
        ).order_by(Meeting.scheduled_at.asc()).limit(50)
        meetings = list((await self.db.execute(stmt_meetings)).scalars().all())

        # 5. Fetch Available Properties (bounded to 150)
        stmt_props = select(PropertyListing).where(
            and_(
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None),
                PropertyListing.status == "available"
            )
        ).order_by(PropertyListing.created_at.desc()).limit(150)
        properties = list((await self.db.execute(stmt_props)).scalars().all())

        # 6. Fetch Strong Property Matches (LeadPropertyInterest match_score >= 85)
        stmt_interests = select(LeadPropertyInterest).where(
            and_(
                LeadPropertyInterest.organization_id == broker_uuid,
                LeadPropertyInterest.match_score >= 85.0,
                LeadPropertyInterest.status.in_(["MATCHED", "SHORTLISTED", "INTERESTED"])
            )
        ).order_by(LeadPropertyInterest.match_score.desc()).limit(50)
        interests = list((await self.db.execute(stmt_interests)).scalars().all())

        # 7. Fetch Recent Activities (bounded to 10)
        stmt_act = select(Activity).where(
            Activity.organization_id == org_id_str
        ).order_by(Activity.created_at.desc()).limit(10)
        activities = list((await self.db.execute(stmt_act)).scalars().all())
        recent_acts = [
            {
                "id": str(a.id),
                "activity_type": a.activity_type,
                "title": a.title,
                "description": a.description,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "lead_id": str(a.lead_id) if a.lead_id else None
            }
            for a in activities
        ]

        # ── Component Processing ──

        lead_map = {l.id: l for l in leads}
        prop_map = {p.id: p for p in properties}

        all_priority_items: List[PriorityItemDTO] = []

        # A. First Contact SLA Processing
        first_contact_items: List[FirstContactSlaItemDTO] = []
        sla_breaches_count = 0

        for l in leads:
            # Check if lead is new/pending and needs first contact
            is_new = (l.status in ("pending", "new") or l.pipeline_stage in ("new", "inbound"))
            if is_new and l.created_at:
                created = l.created_at if l.created_at.tzinfo else l.created_at.replace(tzinfo=timezone.utc)
                # Standard 15 min SLA threshold
                sla_deadline = created + timedelta(minutes=15)
                diff_sec = (now - sla_deadline).total_seconds()
                is_overdue = diff_sec > 0
                overdue_mins = int(diff_sec / 60.0) if is_overdue else None
                mins_left = max(0, int(-diff_sec / 60.0)) if not is_overdue else None

                if is_overdue:
                    sla_breaches_count += 1

                sla_dto = FirstContactSlaItemDTO(
                    lead_id=str(l.id),
                    lead_name=l.name or "New Prospect",
                    lead_phone=l.phone,
                    source=l.source or "manual",
                    created_at=created.isoformat(),
                    sla_deadline=sla_deadline.isoformat(),
                    is_overdue=is_overdue,
                    overdue_minutes=overdue_mins,
                    time_remaining_minutes=mins_left,
                    pipeline_stage=l.pipeline_stage or "new"
                )
                first_contact_items.append(sla_dto)

                # Add to Priority Queue
                p_label, p_score = CommandCenterPriorityEngine.evaluate_item_priority(
                    category="first_contact",
                    overdue_minutes=overdue_mins if is_overdue else -mins_left,
                    is_hot_lead=(l.score == "hot"),
                    now=now
                )
                item_title = f"First contact overdue: {l.name or 'New Lead'}" if is_overdue else f"First contact due: {l.name or 'New Lead'}"
                item_desc = f"Created {int((now - created).total_seconds()/60)}m ago via {l.source or 'web'}. SLA response time is {overdue_mins or 0}m overdue." if is_overdue else f"SLA response deadline expires in {mins_left}m."

                all_priority_items.append(
                    PriorityItemDTO(
                        id=f"fc_{l.id}",
                        item_key=f"lead:{l.id}:first_contact",
                        priority=p_label,
                        priority_score=p_score,
                        category="first_contact",
                        title=item_title,
                        description=item_desc,
                        due_at=sla_deadline.isoformat(),
                        overdue_minutes=overdue_mins,
                        entity_type="lead",
                        entity_id=str(l.id),
                        lead_id=str(l.id),
                        lead_name=l.name or "New Lead",
                        lead_phone=l.phone,
                        recommended_action="CALL",
                        metadata={"source": l.source, "is_overdue": is_overdue}
                    )
                )

        # B. Overdue Follow-ups Processing
        overdue_followups: List[OverdueFollowupItemDTO] = []
        for t in tasks:
            if t.due_at:
                t_due = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)
                if t_due < now:
                    diff_sec = (now - t_due).total_seconds()
                    overdue_days = int(diff_sec // 86400)
                    overdue_hours = int((diff_sec % 86400) // 3600)

                    t_lead = lead_map.get(t.lead_id)
                    lead_name = t_lead.name if t_lead else None

                    overdue_dto = OverdueFollowupItemDTO(
                        task_id=str(t.id),
                        lead_id=str(t.lead_id) if t.lead_id else None,
                        lead_name=lead_name,
                        title=t.title,
                        description=t.description,
                        due_at=t_due.isoformat(),
                        overdue_days=overdue_days,
                        overdue_hours=overdue_hours,
                        priority=t.priority or "normal"
                    )
                    overdue_followups.append(overdue_dto)

                    p_label, p_score = CommandCenterPriorityEngine.evaluate_item_priority(
                        category="overdue_followup",
                        overdue_minutes=int(diff_sec / 60.0),
                        is_hot_lead=(t_lead.score == "hot" if t_lead else False),
                        now=now
                    )

                    all_priority_items.append(
                        PriorityItemDTO(
                            id=f"task_{t.id}",
                            item_key=f"task:{t.id}:overdue",
                            priority=p_label,
                            priority_score=p_score,
                            category="overdue_followup",
                            title=f"Follow-up Overdue: {t.title}",
                            description=f"Overdue by {overdue_days}d {overdue_hours}h for {lead_name or 'Lead'}.",
                            due_at=t_due.isoformat(),
                            overdue_minutes=int(diff_sec / 60.0),
                            entity_type="task",
                            entity_id=str(t.id),
                            lead_id=str(t.lead_id) if t.lead_id else None,
                            lead_name=lead_name,
                            recommended_action="COMPLETE_TASK",
                            metadata={"priority": t.priority}
                        )
                    )

        # C. Today's Meetings & Site Visits
        today_schedule: List[TodayScheduleItemDTO] = []
        site_visits_today = 0

        for m in meetings:
            m_sched = m.scheduled_at if m.scheduled_at.tzinfo else m.scheduled_at.replace(tzinfo=timezone.utc)
            mins_until = (m_sched - now).total_seconds() / 60.0
            is_soon = 0 <= mins_until <= 120
            if m.meeting_type == "site_visit":
                site_visits_today += 1

            m_lead = lead_map.get(m.lead_id)
            lead_name = m_lead.name if m_lead else None

            sched_dto = TodayScheduleItemDTO(
                id=str(m.id),
                meeting_type=m.meeting_type or "meeting",
                title=m.title,
                scheduled_at=m_sched.isoformat(),
                duration_minutes=m.duration_minutes or 60,
                lead_id=str(m.lead_id) if m.lead_id else None,
                lead_name=lead_name,
                location=m.location,
                meeting_url=m.meeting_url,
                status=m.status or "scheduled",
                is_starting_soon=is_soon
            )
            today_schedule.append(sched_dto)

            # Priority Item
            cat = "site_visit" if m.meeting_type == "site_visit" else "meeting"
            p_label, p_score = CommandCenterPriorityEngine.evaluate_item_priority(
                category=cat,
                due_at=m_sched,
                now=now
            )
            directive = "SCHEDULE_VISIT" if cat == "site_visit" else "OPEN_LEAD"
            if is_soon:
                item_title = f"{cat.replace('_', ' ').title()} in {int(mins_until)} mins: {m.title}"
            else:
                item_title = f"{cat.replace('_', ' ').title()}: {m.title}"

            all_priority_items.append(
                PriorityItemDTO(
                    id=f"meet_{m.id}",
                    item_key=f"meeting:{m.id}:schedule",
                    priority=p_label,
                    priority_score=p_score,
                    category=cat,
                    title=item_title,
                    description=f"Scheduled for {m_sched.strftime('%I:%M %p')} with {lead_name or 'Client'} ({m.location or 'Online'}).",
                    due_at=m_sched.isoformat(),
                    entity_type="meeting",
                    entity_id=str(m.id),
                    lead_id=str(m.lead_id) if m.lead_id else None,
                    lead_name=lead_name,
                    recommended_action=directive,
                    metadata={"meeting_type": m.meeting_type, "location": m.location}
                )
            )

        # D. Hot Leads Processing
        hot_leads_list: List[HotLeadItemDTO] = []
        for l in leads:
            if l.score == "hot":
                # Check top match in interests
                top_interest = next((i for i in interests if i.lead_id == l.id), None)
                match_title = None
                match_score = None
                if top_interest:
                    prop = prop_map.get(top_interest.property_id)
                    match_title = prop.title if prop else None
                    match_score = top_interest.match_score

                last_act = l.updated_at or l.created_at
                last_act_dt = last_act if last_act.tzinfo else last_act.replace(tzinfo=timezone.utc)
                uncontacted_days = int((now - last_act_dt).total_seconds() // 86400)

                hot_dto = HotLeadItemDTO(
                    lead_id=str(l.id),
                    name=l.name or "Hot Prospect",
                    phone=l.phone,
                    pipeline_stage=l.pipeline_stage or "contacted",
                    temperature="hot",
                    last_activity_at=last_act_dt.isoformat(),
                    budget_max=l.budget_max,
                    preferred_locations=l.preferred_locations or [],
                    property_type=l.property_type,
                    strongest_property_match=match_title,
                    match_score=match_score,
                    uncontacted_days=uncontacted_days
                )
                hot_leads_list.append(hot_dto)

                if match_score and match_score >= 90.0:
                    p_label, p_score = CommandCenterPriorityEngine.evaluate_item_priority(
                        category="strong_match",
                        match_score=match_score,
                        is_hot_lead=True,
                        now=now
                    )
                    all_priority_items.append(
                        PriorityItemDTO(
                            id=f"hot_match_{l.id}",
                            item_key=f"match:{l.id}:{top_interest.property_id}",
                            priority=p_label,
                            priority_score=p_score,
                            category="strong_match",
                            title=f"90+ Match for {l.name}: {match_title}",
                            description=f"Compatibility score {match_score:.0f}%. High-fit inventory ready to present.",
                            entity_type="match",
                            entity_id=f"{l.id}:{top_interest.property_id}",
                            lead_id=str(l.id),
                            lead_name=l.name,
                            property_id=str(top_interest.property_id),
                            property_title=match_title,
                            match_score=match_score,
                            recommended_action="REVIEW_MATCHES"
                        )
                    )

        # E. Stale Leads Summary (7, 14, 30+ days)
        stale_7 = 0
        stale_14 = 0
        stale_30 = 0
        sample_stale = []

        for l in leads:
            last_dt = l.updated_at or l.created_at
            if last_dt:
                dt_utc = last_dt if last_dt.tzinfo else last_dt.replace(tzinfo=timezone.utc)
                days_idle = (now - dt_utc).total_seconds() / 86400.0
                if days_idle >= 30:
                    stale_30 += 1
                elif days_idle >= 14:
                    stale_14 += 1
                elif days_idle >= 7:
                    stale_7 += 1

                if days_idle >= 7 and len(sample_stale) < 5:
                    sample_stale.append({
                        "lead_id": str(l.id),
                        "name": l.name,
                        "days_inactive": int(days_idle),
                        "stage": l.pipeline_stage,
                        "score": l.score
                    })

        stale_summary = StaleLeadSummaryDTO(
            stale_7_days_count=stale_7,
            stale_14_days_count=stale_14,
            stale_30_plus_days_count=stale_30,
            total_stale_leads=stale_7 + stale_14 + stale_30,
            sample_stale_leads=sample_stale
        )

        # F. Inventory Intelligence & Opportunities
        inventory_opps = InventoryIntelligenceEngine.identify_new_inventory_opportunities(
            properties=properties,
            leads=leads
        )
        inventory_gaps = InventoryIntelligenceEngine.identify_inventory_gaps(
            leads=leads,
            properties=properties
        )
        demand_heatmap = InventoryIntelligenceEngine.compute_demand_heatmap(
            leads=leads,
            properties=properties
        )

        # G. Rank & Filter Priority Items
        ranked_priorities = CommandCenterPriorityEngine.rank_and_filter_priorities(
            items=all_priority_items,
            dismissed_keys=dismissed_keys,
            limit=25
        )

        # Calculate Summary Counters
        critical_count = sum(1 for p in ranked_priorities if p.priority == "CRITICAL")
        high_count = sum(1 for p in ranked_priorities if p.priority == "HIGH")
        medium_count = sum(1 for p in ranked_priorities if p.priority == "MEDIUM")

        top_directive = ranked_priorities[0].title if ranked_priorities else None
        top_gap_str = inventory_gaps[0].segment_label if inventory_gaps else None

        summary_dto = CommandCenterSummaryDTO(
            critical_actions_count=critical_count,
            high_actions_count=high_count,
            medium_actions_count=medium_count,
            total_priority_actions=len(ranked_priorities),
            overdue_followups_count=len(overdue_followups),
            sla_breaches_count=sla_breaches_count,
            meetings_today_count=len(today_schedule),
            site_visits_today_count=site_visits_today,
            hot_leads_count=len(hot_leads_list),
            strong_matches_count=len(interests),
            stale_leads_count=stale_summary.total_stale_leads,
            inventory_gaps_count=len(inventory_gaps)
        )

        # H. Morning Briefing
        briefing_dto = await CommandCenterBriefingService.generate_briefing(
            broker_name=broker_name,
            critical_count=critical_count,
            overdue_count=len(overdue_followups),
            meetings_count=len(today_schedule),
            site_visits_count=site_visits_today,
            hot_leads_count=len(hot_leads_list),
            strong_matches_count=len(interests),
            top_directive=top_directive,
            top_inventory_gap=top_gap_str,
            ai_service=self.ai_service
        )

        return CommandCenterResponseDTO(
            organization_id=org_id_str,
            broker_id=str(broker_uuid),
            broker_name=broker_name,
            timezone=timezone_str,
            summary=summary_dto,
            daily_briefing=briefing_dto,
            priorities=ranked_priorities,
            first_contact_queue=first_contact_items,
            overdue_followups=overdue_followups,
            today_schedule=today_schedule,
            hot_leads=hot_leads_list,
            stale_leads_summary=stale_summary,
            inventory_opportunities=inventory_opps,
            inventory_gaps=inventory_gaps,
            demand_heatmap=demand_heatmap,
            recent_activities=recent_acts
        )

    async def get_priority_queue(
        self,
        broker: Broker,
        limit: int = 25,
        priority_filter: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[PriorityItemDTO]:
        """Returns ordered priority actions queue with optional filters."""
        data = await self.get_command_center_data(broker)
        items = data.priorities
        if priority_filter:
            items = [p for p in items if p.priority.upper() == priority_filter.upper()]
        if entity_type:
            items = [p for p in items if p.entity_type.lower() == entity_type.lower()]
        return items[:limit]

    async def get_start_my_day_sequence(
        self,
        broker: Broker
    ) -> StartMyDayResponseDTO:
        """
        Creates an interactive, sequential step-by-step workflow for the agent's workday.
        """
        data = await self.get_command_center_data(broker)
        top_items = data.priorities[:10]
        steps = [
            StartMyDayStepDTO(
                step_number=idx + 1,
                total_steps=len(top_items),
                item=item
            )
            for idx, item in enumerate(top_items)
        ]
        return StartMyDayResponseDTO(
            total_items=len(top_items),
            steps=steps
        )

    get_start_my_day_queue = get_start_my_day_sequence

    async def dismiss_or_snooze_item(
        self,
        broker: Any,
        dto: DismissItemRequestDTO
    ) -> Dict[str, Any]:
        """
        Records dismissal or snooze state without mutating underlying CRM records.
        """
        if isinstance(broker, (str, uuid.UUID)):
            broker_uuid = uuid.UUID(str(broker))
            broker_obj = await self.db.get(Broker, broker_uuid)
            org_id_str = str(getattr(broker_obj, "organization_id", None) or broker_uuid)
        else:
            broker_uuid = uuid.UUID(str(broker.id))
            org_id_str = str(getattr(broker, "organization_id", None) or broker.id)
        now = datetime.now(timezone.utc)

        snooze_until = None
        if dto.action_type == "snoozed" and dto.snooze_hours:
            snooze_until = now + timedelta(hours=dto.snooze_hours)

        # Check existing dismissal
        stmt = select(CommandCenterDismissal).where(
            and_(
                CommandCenterDismissal.broker_id == broker_uuid,
                CommandCenterDismissal.item_key == dto.item_key
            )
        )
        existing = (await self.db.execute(stmt)).scalars().first()

        if existing:
            existing.action_type = dto.action_type
            existing.snoozed_until = snooze_until
            existing.updated_at = now
        else:
            record = CommandCenterDismissal(
                id=str(uuid.uuid4()),
                organization_id=org_id_str,
                broker_id=broker_uuid,
                item_key=dto.item_key,
                entity_type=dto.entity_type,
                entity_id=dto.entity_id,
                action_type=dto.action_type,
                snoozed_until=snooze_until,
                created_at=now,
                updated_at=now
            )
            self.db.add(record)

        # Audit log entry
        audit = AuditLog(
            organization_id=broker_uuid,
            actor_id=broker_uuid,
            actor_type="user",
            action=f"command_center.{dto.action_type}",
            resource_type="command_center_item",
            resource_id=dto.item_key,
            new_values={
                "action_type": dto.action_type,
                "snooze_hours": dto.snooze_hours,
                "snoozed_until": snooze_until.isoformat() if snooze_until else None
            }
        )
        self.db.add(audit)
        await self.db.commit()

        # ── Sprint 1E: Revenue Learning OS wiring for NBA feedback ────────────
        try:
            from app.modules.intelligence.outcome_recorder import OutcomeRecorder
            from app.models.intelligence_models import OutcomeEventType, OutcomeEntityType, OutcomeSource, LearningSignalType

            evt_type = (
                OutcomeEventType.AI_ACTION_ACCEPTED if dto.action_type in ("executed", "accepted")
                else OutcomeEventType.AI_ACTION_REJECTED if dto.action_type in ("dismissed", "rejected")
                else OutcomeEventType.AI_ACTION_IGNORED
            )
            sig_type = (
                LearningSignalType.HUMAN_ACCEPT if dto.action_type in ("executed", "accepted")
                else LearningSignalType.HUMAN_DISMISS if dto.action_type in ("dismissed", "rejected")
                else LearningSignalType.HUMAN_SNOOZE
            )
            lead_id_val = str(dto.entity_id) if dto.entity_type == "lead" else None
            await OutcomeRecorder.safe_record(
                db=self.db,
                org_id=org_id_str,
                event_type=evt_type,
                entity_type=OutcomeEntityType.AI_ACTION,
                entity_id=dto.item_key,
                source_table="command_center_dismissals",
                source_event_id=dto.item_key,
                occurred_at=now,
                lead_id=lead_id_val,
                agent_id=str(broker_uuid),
                actor_type="HUMAN",
                outcome_source=OutcomeSource.HUMAN,
                metadata={
                    "item_key": dto.item_key,
                    "action_type": dto.action_type,
                    "signal_type": sig_type.value,
                    "snooze_hours": dto.snooze_hours,
                },
            )
        except Exception as exc:
            logger.warning(f"[CommandCenter] Non-fatal learning layer record error: {exc}")

        return {
            "status": "success",
            "message": f"Item '{dto.item_key}' {dto.action_type} successfully.",
            "item_key": dto.item_key,
            "action_type": dto.action_type,
            "snoozed_until": snooze_until.isoformat() if snooze_until else None
        }

    async def dismiss_item(
        self,
        broker: Any = None,
        item_key: str = "",
        entity_type: str = "lead",
        entity_id: str = "",
        action_type: str = "dismissed",
        snooze_hours: Optional[int] = None,
        broker_id: Any = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Convenience method for programmatic item dismissal."""
        target_broker = broker if broker is not None else broker_id
        action = kwargs.get("action", action_type)
        if action in ("dismiss", "dismissed"):
            resolved_action = "dismissed"
        elif action in ("snooze", "snoozed"):
            resolved_action = "snoozed"
        else:
            resolved_action = action_type
        
        hours = snooze_hours or kwargs.get("snooze_minutes", 60) // 60 or 1
        dto = DismissItemRequestDTO(
            item_key=item_key,
            entity_type=entity_type,
            entity_id=entity_id or str(uuid.uuid4()),
            action_type=resolved_action,
            snooze_hours=hours if resolved_action == "snoozed" else None
        )
        return await self.dismiss_or_snooze_item(target_broker, dto)


    async def get_inventory_intelligence(
        self,
        broker: Any
    ) -> Dict[str, Any]:
        """Aggregates inventory gaps and demand heatmap for broker's organization."""
        broker_uuid = uuid.UUID(str(broker.id)) if hasattr(broker, "id") else uuid.UUID(str(broker))


        stmt_leads = select(Lead).where(
            and_(
                Lead.broker_id == broker_uuid,
                Lead.deleted_at.is_(None),
                Lead.status.in_(["pending", "active", "qualified"])
            )
        ).limit(250)
        leads = list((await self.db.execute(stmt_leads)).scalars().all())

        stmt_props = select(PropertyListing).where(
            and_(
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None)
            )
        ).limit(250)
        properties = list((await self.db.execute(stmt_props)).scalars().all())

        heatmap = InventoryIntelligenceEngine.compute_demand_heatmap(leads, properties)
        gaps = InventoryIntelligenceEngine.identify_inventory_gaps(leads, properties)
        opps = InventoryIntelligenceEngine.identify_new_inventory_opportunities(properties, leads)

        return {
            "demand_heatmap": heatmap.model_dump(),
            "inventory_gaps": [g.model_dump() for g in gaps],
            "inventory_opportunities": [o.model_dump() for o in opps]
        }
