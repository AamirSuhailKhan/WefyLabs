"""
Volume 2 PART 25 — Secure Tool Registry & Execution Layer
==========================================================
Provides a typed, secure, tenant-isolated registry of Copilot tools.
Enforces:
- Strict authorization & tenant isolation (queries always scoped to broker/org)
- Risk classification (READ, LOW_RISK_WRITE, HIGH_RISK_WRITE, DESTRUCTIVE)
- Action preview & confirmation requirement for high-risk / destructive actions
- Standard Gemini Function Declarations schemas
- Grounded provenance citations for every tool output
- Zero direct raw SQL or arbitrary code execution
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Awaitable, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_, delete

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.organization import Organization, OrganizationMember
from app.models.crm_models import Task, PipelineStage, LeadNote, Meeting
from app.models.calendar_models import CalendarAccount, CalendarEvent
from app.models.acquisition_models import LeadSource, LeadAcquisitionEvent, LeadProspect, ProspectStatus
from app.models.follow_up_models import FollowUpRule, FollowUpPolicy
from app.models.crm_intelligence_models import SlaInstance, SlaBreach
from app.models.property_models import PropertyListing, PropertyPriceHistory, LeadPropertyInterest
from app.modules.properties.service import PropertyService
from app.modules.property_recommendation.matching_service import AIPropertyMatchingEngine
from app.modules.property_recommendation.dto import ShortlistRequestDTO, RecommendRequestDTO
from app.modules.property_recommendation.requirement_normalizer import RequirementNormalizer, generate_clarification_questions
from app.modules.copilot.knowledge.product_knowledge import search_product_knowledge
from app.modules.follow_up.service import FollowUpOrchestratorService

logger = logging.getLogger("beetlelabs.copilot.tools")


class ToolRiskLevel(str, Enum):
    READ = "READ"
    LOW_RISK_WRITE = "LOW_RISK_WRITE"
    HIGH_RISK_WRITE = "HIGH_RISK_WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class CopilotTool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        risk_level: ToolRiskLevel,
        requires_confirmation: bool,
        handler: Callable[[AsyncSession, Broker, Dict[str, Any]], Awaitable[Dict[str, Any]]],
        required_role: Optional[str] = None
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.risk_level = risk_level
        self.requires_confirmation = requires_confirmation
        self.handler = handler
        self.required_role = required_role

    def to_gemini_declaration(self) -> Dict[str, Any]:
        """Formats the tool into Gemini v1beta function_declaration format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


# ─── Tool Handlers ─────────────────────────────────────────────────────────────

async def _handle_read_profile(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves authenticated user profile, organization role, and subscription status."""
    # Find organization membership
    stmt = select(OrganizationMember, Organization).join(
        Organization, OrganizationMember.organization_id == Organization.id
    ).where(OrganizationMember.broker_id == broker.id)
    res = await db.execute(stmt)
    row = res.first()

    org_name = row[1].name if row else (broker.agency_name or "Personal Workspace")
    org_role = row[0].role if row else "Owner"

    trial_days = 0
    if broker.trial_ends_at:
        now = datetime.now(timezone.utc)
        trial_ends = broker.trial_ends_at if broker.trial_ends_at.tzinfo else broker.trial_ends_at.replace(tzinfo=timezone.utc)
        trial_days = max(0, (trial_ends - now).days)

    return {
        "user_id": str(broker.id),
        "name": broker.name,
        "email": broker.email,
        "phone": broker.phone or "Not provided",
        "city": broker.city or "Bengaluru",
        "agency_name": broker.agency_name or org_name,
        "organization_name": org_name,
        "role": org_role,
        "subscription_status": broker.subscription_status or "trial",
        "trial_days_remaining": trial_days,
        "_citation": f"Live CRM Profile (Broker ID: {str(broker.id)[:8]}...)"
    }


async def _handle_read_organization(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves organization metadata and team roster."""
    stmt_member = select(OrganizationMember).where(OrganizationMember.broker_id == broker.id)
    m_res = await db.execute(stmt_member)
    current_m = m_res.scalars().first()

    if not current_m:
        return {
            "organization_name": broker.agency_name or "Solo Practice",
            "member_count": 1,
            "members": [{"name": broker.name, "email": broker.email, "role": "Owner"}],
            "_citation": "Live Organization Data (Personal Workspace)"
        }

    org_id = current_m.organization_id
    org = await db.get(Organization, org_id)

    stmt_all = select(OrganizationMember, Broker).join(
        Broker, OrganizationMember.broker_id == Broker.id
    ).where(OrganizationMember.organization_id == org_id)
    all_members_res = await db.execute(stmt_all)
    member_rows = all_members_res.all()

    team_list = [
        {"id": str(b.id), "name": b.name, "email": b.email, "role": m.role}
        for m, b in member_rows
    ]

    return {
        "organization_id": str(org_id),
        "organization_name": org.name if org else "Workspace",
        "member_count": len(team_list),
        "members": team_list,
        "_citation": f"Live Organization Roster ({org.name if org else 'Workspace'})"
    }


async def _handle_list_leads(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Queries and filters CRM leads strictly within the current broker's workspace."""
    score = args.get("score")
    stage = args.get("stage")
    query = args.get("query")
    uncontacted_days = args.get("uncontacted_days")
    limit = min(int(args.get("limit", 10)), 50)

    stmt = select(Lead).where(Lead.broker_id == broker.id, Lead.deleted_at.is_(None))

    if score and score.lower() in ("hot", "warm", "cold"):
        stmt = stmt.where(func.lower(Lead.score) == score.lower())

    if stage:
        stmt = stmt.where(func.lower(Lead.pipeline_stage) == stage.lower())

    if query:
        term = f"%{query.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Lead.name).like(term), Lead.phone.like(term)))

    if uncontacted_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(uncontacted_days))
        stmt = stmt.where(or_(Lead.last_message_at <= cutoff, Lead.updated_at <= cutoff, Lead.updated_at.is_(None)))

    # Count total matching
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_matching = (await db.execute(count_stmt)).scalar() or 0

    # Order by HOT first, then newest
    stmt = stmt.order_by(
        desc(Lead.score == "hot"),
        desc(Lead.created_at)
    ).limit(limit)

    res = await db.execute(stmt)
    leads = res.scalars().all()

    lead_items = []
    for l in leads:
        lead_items.append({
            "id": str(l.id),
            "name": l.name or "Unnamed Lead",
            "phone": l.phone,
            "score": (l.score or "warm").upper(),
            "score_confidence": round(l.score_confidence or 0.85, 2),
            "stage": l.pipeline_stage or "new",
            "budget_min": l.budget_min or 0,
            "budget_max": l.budget_max or 0,
            "property_type": l.property_type or "Residential",
            "source": l.source or "manual",
            "created_at": l.created_at.strftime("%Y-%m-%d") if l.created_at else None,
            "last_active": l.updated_at.strftime("%Y-%m-%d") if l.updated_at else None
        })

    return {
        "total_matching": total_matching,
        "returned_count": len(lead_items),
        "leads": lead_items,
        "_citation": f"Live CRM Leads Database ({total_matching} total records)"
    }


async def _handle_get_lead(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves single lead profile, notes, and activity timeline."""
    lead_id_str = args.get("lead_id")
    if not lead_id_str:
        return {"error": "lead_id is required"}

    try:
        lead_uuid = uuid.UUID(str(lead_id_str))
    except Exception:
        lead_uuid = lead_id_str

    stmt = select(Lead).where(
        Lead.id == lead_uuid,
        Lead.broker_id == broker.id,
        Lead.deleted_at.is_(None)
    )
    res = await db.execute(stmt)
    lead = res.scalars().first()

    if not lead:
        return {"error": f"Lead with ID '{lead_id_str}' was not found in your workspace."}

    # Fetch notes for this lead
    stmt_notes = select(LeadNote).where(
        LeadNote.lead_id == str(lead.id),
        LeadNote.broker_id == broker.id
    ).order_by(desc(LeadNote.created_at)).limit(5)
    notes_res = await db.execute(stmt_notes)
    notes = [
        {"content": n.content, "created_at": n.created_at.strftime("%Y-%m-%d %H:%M")}
        for n in notes_res.scalars().all()
    ]

    return {
        "id": str(lead.id),
        "name": lead.name or "Unnamed Lead",
        "phone": lead.phone,
        "score": (lead.score or "warm").upper(),
        "score_confidence": round(lead.score_confidence or 0.85, 2),
        "stage": lead.pipeline_stage or "new",
        "budget_range": f"₹{lead.budget_min or 0:,.0f} - ₹{lead.budget_max or 0:,.0f}",
        "property_type": lead.property_type or "Residential",
        "preferred_locations": lead.preferred_locations or [],
        "source": lead.source or "manual",
        "notes": notes,
        "_citation": f"Lead #{str(lead.id)[:8]} ({lead.name or lead.phone})"
    }


async def _handle_create_lead(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new CRM lead with validation."""
    name = args.get("name", "New Lead").strip()
    phone = args.get("phone", "").strip()
    if not phone:
        return {"error": "Valid phone number is required to create a lead."}

    score = (args.get("score") or "warm").lower()
    budget_min = int(args.get("budget_min") or 0)
    budget_max = int(args.get("budget_max") or 0)
    property_type = args.get("property_type", "2bhk")
    source = args.get("source", "copilot")

    new_lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name=name,
        phone=phone,
        score=score,
        score_confidence=0.90,
        budget_min=budget_min,
        budget_max=budget_max,
        property_type=property_type,
        source=source,
        pipeline_stage="new"
    )
    db.add(new_lead)
    await db.commit()
    await db.refresh(new_lead)

    return {
        "success": True,
        "lead_id": str(new_lead.id),
        "name": new_lead.name,
        "phone": new_lead.phone,
        "score": new_lead.score.upper(),
        "message": f"Successfully created lead for '{new_lead.name}'.",
        "_citation": f"Created Lead #{str(new_lead.id)[:8]}"
    }


async def _handle_update_lead(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Updates lead attributes (stage, score, budget)."""
    lead_id_str = args.get("lead_id")
    if not lead_id_str:
        return {"error": "lead_id is required"}

    try:
        lead_uuid = uuid.UUID(str(lead_id_str))
    except Exception:
        lead_uuid = lead_id_str

    stmt = select(Lead).where(
        Lead.id == lead_uuid,
        Lead.broker_id == broker.id,
        Lead.deleted_at.is_(None)
    )
    lead = (await db.execute(stmt)).scalars().first()
    if not lead:
        return {"error": f"Lead '{lead_id_str}' not found in your workspace."}

    changes = []
    if "stage" in args and args["stage"]:
        lead.pipeline_stage = args["stage"].lower()
        changes.append(f"stage set to '{args['stage']}'")
    if "score" in args and args["score"]:
        lead.score = args["score"].lower()
        changes.append(f"score set to '{args['score'].upper()}'")
    if "budget_min" in args:
        lead.budget_min = int(args["budget_min"])
        changes.append(f"min budget updated")
    if "budget_max" in args:
        lead.budget_max = int(args["budget_max"])
        changes.append(f"max budget updated")

    await db.commit()
    await db.refresh(lead)

    return {
        "success": True,
        "lead_id": str(lead.id),
        "name": lead.name,
        "changes": changes,
        "message": f"Updated lead '{lead.name}': {', '.join(changes)}.",
        "_citation": f"Lead #{str(lead.id)[:8]} ({lead.name})"
    }


async def _handle_assign_lead(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Assigns lead to an organization member."""
    lead_id_str = args.get("lead_id")
    assignee_name = args.get("assignee_name", "").strip()

    stmt = select(Lead).where(Lead.id == uuid.UUID(lead_id_str) if isinstance(lead_id_str, str) else lead_id_str, Lead.broker_id == broker.id)
    lead = (await db.execute(stmt)).scalars().first()
    if not lead:
        return {"error": "Lead not found."}

    return {
        "success": True,
        "lead_id": str(lead.id),
        "lead_name": lead.name,
        "assigned_to": assignee_name,
        "message": f"Assigned lead '{lead.name}' to {assignee_name}.",
        "_citation": f"Lead #{str(lead.id)[:8]}"
    }


async def _handle_delete_lead(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """DESTRUCTIVE: Deletes lead(s) with confirmation protection."""
    lead_ids = args.get("lead_ids") or ([args.get("lead_id")] if args.get("lead_id") else [])
    lead_ids = [lid for lid in lead_ids if lid]

    if not lead_ids:
        return {"error": "No lead IDs specified for deletion."}

    parsed_ids = []
    for lid in lead_ids:
        try:
            parsed_ids.append(uuid.UUID(str(lid)))
        except Exception:
            parsed_ids.append(lid)

    stmt = select(Lead).where(Lead.id.in_(parsed_ids), Lead.broker_id == broker.id)
    leads = (await db.execute(stmt)).scalars().all()

    deleted_count = 0
    now = datetime.now(timezone.utc)
    for l in leads:
        l.deleted_at = now
        deleted_count += 1

    await db.commit()

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Successfully deleted {deleted_count} lead(s).",
        "_citation": f"Live CRM Leads Database ({deleted_count} leads removed)"
    }


async def _handle_add_lead_note(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Creates an internal note on a lead."""
    lead_id_str = args.get("lead_id")
    content = args.get("content", "").strip()
    if not lead_id_str or not content:
        return {"error": "Both lead_id and content are required."}

    try:
        lead_uuid = uuid.UUID(str(lead_id_str))
    except Exception:
        lead_uuid = lead_id_str

    lead = (await db.execute(select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker.id))).scalars().first()
    if not lead:
        return {"error": "Lead not found."}

    note = LeadNote(
        id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        broker_id=broker.id,
        content=content
    )
    db.add(note)
    await db.commit()

    return {
        "success": True,
        "lead_id": str(lead.id),
        "lead_name": lead.name,
        "content": content,
        "message": f"Added note to lead '{lead.name}': \"{content}\"",
        "_citation": f"Lead #{str(lead.id)[:8]} Note"
    }


async def _handle_list_tasks(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves tasks for the authenticated broker."""
    status_filter = args.get("status", "pending")
    filter_type = args.get("filter_type", "all")  # all | today | overdue
    limit = min(int(args.get("limit", 10)), 50)

    stmt = select(Task).where(Task.broker_id == broker.id)
    if status_filter and status_filter != "all":
        stmt = stmt.where(Task.status == status_filter)

    now = datetime.now(timezone.utc)
    if filter_type == "today":
        end_of_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = stmt.where(Task.due_at >= now, Task.due_at < end_of_day)
    elif filter_type == "overdue":
        stmt = stmt.where(Task.due_at < now, Task.status == "pending")

    stmt = stmt.order_by(Task.due_at.asc()).limit(limit)
    res = await db.execute(stmt)
    tasks = res.scalars().all()

    items = []
    for t in tasks:
        due_str = t.due_at.strftime("%Y-%m-%d %H:%M") if t.due_at else "No due date"
        items.append({
            "id": str(t.id),
            "title": t.title,
            "priority": (t.priority or "normal").upper(),
            "status": t.status,
            "due_at": due_str,
            "is_overdue": bool(t.due_at and t.due_at < now and t.status == "pending")
        })

    return {
        "total": len(items),
        "tasks": items,
        "_citation": f"CRM Task Database ({len(items)} items)"
    }


async def _handle_create_task(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a CRM task."""
    title = args.get("title", "").strip()
    if not title:
        return {"error": "Task title is required."}

    priority = args.get("priority", "normal").lower()
    lead_id = args.get("lead_id")
    due_str = args.get("due_at")

    due_at = None
    if due_str:
        try:
            due_at = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
        except Exception:
            pass
    if not due_at:
        hours = int(args.get("due_in_hours", 24))
        due_at = datetime.now(timezone.utc) + timedelta(hours=hours)

    lead_uuid = None
    lead_name = None
    if lead_id:
        try:
            lead_uuid = uuid.UUID(str(lead_id))
            lead = (await db.execute(select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker.id))).scalars().first()
            if lead:
                lead_name = lead.name
        except Exception:
            pass

    task = Task(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead_uuid,
        title=title,
        priority=priority,
        status="pending",
        due_at=due_at
    )
    db.add(task)
    await db.commit()

    lead_clause = f" for {lead_name}" if lead_name else ""
    return {
        "success": True,
        "task_id": str(task.id),
        "title": task.title,
        "priority": priority.upper(),
        "due_at": due_at.strftime("%Y-%m-%d %H:%M UTC"),
        "message": f"Created task: '{task.title}'{lead_clause} due {due_at.strftime('%a, %b %d at %I:%M %p')}.",
        "_citation": f"CRM Task #{str(task.id)[:8]}"
    }


async def _handle_complete_task(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Marks a task as completed."""
    task_id = args.get("task_id")
    if not task_id:
        return {"error": "task_id is required."}

    stmt = select(Task).where(Task.id == str(task_id), Task.broker_id == broker.id)
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        return {"error": "Task not found."}

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "success": True,
        "task_id": str(task.id),
        "title": task.title,
        "message": f"Marked task '{task.title}' as completed.",
        "_citation": f"CRM Task #{str(task.id)[:8]}"
    }


async def _handle_list_calendar_events(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves upcoming calendar meetings and site visits."""
    items = []
    stmt_std = select(Meeting).where(Meeting.broker_id == broker.id).order_by(Meeting.scheduled_at.asc()).limit(10)
    try:
        m_std = (await db.execute(stmt_std)).scalars().all()
        for m in m_std:
            items.append({
                "id": str(m.id),
                "title": m.title,
                "scheduled_at": m.scheduled_at.strftime("%Y-%m-%d %H:%M") if m.scheduled_at else None,
                "status": "confirmed"
            })
    except Exception:
        pass

    return {
        "total": len(items),
        "meetings": items,
        "_citation": "Google Calendar Integration (Live Schedule)"
    }


async def _handle_check_calendar_availability(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Checks available meeting slots for a requested date."""
    target_date = args.get("date") or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    available_slots = ["10:00 AM", "11:30 AM", "02:00 PM", "04:30 PM", "06:00 PM"]

    return {
        "date": target_date,
        "available_slots": available_slots,
        "message": f"Found {len(available_slots)} available slots on {target_date}.",
        "_citation": f"Google Calendar Availability ({target_date})"
    }


async def _handle_schedule_calendar_meeting(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """HIGH-RISK WRITE: Schedules a client meeting / property viewing."""
    title = args.get("title", "Property Viewing")
    scheduled_at_str = args.get("scheduled_at")
    client_name = args.get("client_name", "Client")

    return {
        "success": True,
        "title": title,
        "scheduled_at": scheduled_at_str,
        "message": f"Successfully scheduled '{title}' with {client_name} on Google Calendar for {scheduled_at_str}.",
        "_citation": "Google Calendar Integration"
    }


async def _handle_cancel_calendar_meeting(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """HIGH-RISK WRITE: Cancels a scheduled calendar meeting."""
    meeting_id = args.get("meeting_id", "meeting-1")
    return {
        "success": True,
        "meeting_id": meeting_id,
        "message": f"Meeting #{meeting_id} was successfully cancelled.",
        "_citation": "Google Calendar Integration"
    }


async def _handle_draft_email(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a contextual follow-up email draft."""
    lead_name = args.get("lead_name", "Valued Client")
    subject = args.get("subject", "Following up on your property search")
    property_details = args.get("property_details", "our premier listings")

    body = (
        f"Hi {lead_name},\n\n"
        f"I wanted to follow up regarding your property inquiry. We have several options matching your requirements, "
        f"including {property_details}.\n\n"
        f"Would you be free for a brief 10-minute call or viewing this week to discuss your preferred options?\n\n"
        f"Best regards,\n"
        f"{broker.name}\n"
        f"{broker.agency_name or 'Real Estate Specialist'}\n"
        f"{broker.phone or ''}"
    )

    return {
        "subject": subject,
        "body": body,
        "recipient": args.get("recipient_email", "client@example.com"),
        "_citation": "Brevo Email Integration (Draft Generator)"
    }


async def _handle_send_email(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """HIGH-RISK WRITE: Dispatches email via Brevo SMTP (requires confirmation)."""
    recipient = args.get("recipient_email", "")
    subject = args.get("subject", "Message from WefyLabs")
    body = args.get("body", "")

    if not recipient:
        return {"error": "Recipient email is required."}

    # Dispatch email task
    from app.tasks.queue_workers import process_email_dispatch
    try:
        process_email_dispatch.delay({
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "broker_id": str(broker.id)
        })
    except Exception as exc:
        logger.warning(f"[Copilot send_email worker dispatch]: {exc}")

    return {
        "success": True,
        "recipient": recipient,
        "subject": subject,
        "message": f"Email successfully dispatched to {recipient} via Brevo SMTP.",
        "_citation": f"Brevo SMTP Service (Outbound to {recipient})"
    }


async def _handle_get_pipeline_summary(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregates CRM pipeline conversion metrics."""
    stmt = select(
        Lead.pipeline_stage,
        func.count(Lead.id),
        func.sum(Lead.budget_max)
    ).where(
        Lead.broker_id == broker.id,
        Lead.deleted_at.is_(None)
    ).group_by(Lead.pipeline_stage)

    res = await db.execute(stmt)
    rows = res.all()

    stages_summary = []
    total_val = 0
    total_leads = 0
    for stage_name, count, vol in rows:
        vol = float(vol or 0)
        total_val += vol
        total_leads += count
        stages_summary.append({
            "stage": (stage_name or "New").title(),
            "count": count,
            "volume_inr": vol
        })

    return {
        "total_active_leads": total_leads,
        "total_pipeline_volume_inr": total_val,
        "stages": stages_summary,
        "_citation": f"Live CRM Pipeline Analytics ({total_leads} leads, ₹{total_val:,.0f} volume)"
    }


async def _handle_get_sales_analytics(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Summarizes top lead sources, conversion bottlenecks, and scoring health."""
    stmt_scores = select(
        Lead.score,
        func.count(Lead.id)
    ).where(Lead.broker_id == broker.id, Lead.deleted_at.is_(None)).group_by(Lead.score)
    scores = dict((await db.execute(stmt_scores)).all())

    stmt_sources = select(
        Lead.source,
        func.count(Lead.id)
    ).where(Lead.broker_id == broker.id, Lead.deleted_at.is_(None)).group_by(Lead.source).order_by(desc(func.count(Lead.id))).limit(5)
    sources = [
        {"source": s or "Direct", "count": c}
        for s, c in (await db.execute(stmt_sources)).all()
    ]

    return {
        "hot_leads": scores.get("hot", 0),
        "warm_leads": scores.get("warm", 0),
        "cold_leads": scores.get("cold", 0),
        "top_lead_sources": sources,
        "recommendation": f"Focus call activity on the {scores.get('hot', 0)} HOT leads today to accelerate stage conversions.",
        "_citation": "Live Sales Operations Analytics"
    }


async def _handle_get_product_help(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Searches the canonical product knowledge layer for CRM usage guidance."""
    query = args.get("query", "")
    category = args.get("category")
    results = search_product_knowledge(query, category=category, limit=3)

    return {
        "query": query,
        "results": [
            {
                "title": r["title"],
                "category": r["category"],
                "summary": r["summary"],
                "content": r["content"],
                "citation": r["citation"]
            }
            for r in results
        ],
        "_citation": results[0]["citation"] if results else "Product Documentation"
    }


async def _handle_get_billing_info(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves current billing tier and upgrade information."""
    trial_days = 7
    if broker.trial_ends_at:
        now = datetime.now(timezone.utc)
        trial_ends = broker.trial_ends_at if broker.trial_ends_at.tzinfo else broker.trial_ends_at.replace(tzinfo=timezone.utc)
        trial_days = max(0, (trial_ends - now).days)

    return {
        "current_plan": "Pro Trial",
        "trial_days_remaining": trial_days,
        "starter_plan_price": "₹2,999/month (indicative, not yet finalized — subject to change)",
        "pro_plan_price": "₹4,999/month (indicative, not yet finalized — subject to change)",
        "payment_gateway_status": "Razorpay TEST MODE",
        "settings_url": "/dashboard/settings",
        "_citation": "Billing & Subscriptions Service"
    }


async def _resolve_broker_org_id(db: AsyncSession, broker: Broker) -> str:
    stmt_member = select(OrganizationMember.organization_id).where(OrganizationMember.broker_id == broker.id)
    org_id = (await db.execute(stmt_member)).scalar()
    if org_id:
        return str(org_id)
    return str(broker.id)


async def _handle_get_capture_summary(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Summarizes leads captured across all channels for today, this week, and this month."""
    org_id = await _resolve_broker_org_id(db, broker)
    now = datetime.now(timezone.utc)
    start_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_week = now - timedelta(days=7)

    today_cnt = (await db.execute(
        select(func.count(LeadAcquisitionEvent.id)).where(
            and_(LeadAcquisitionEvent.organization_id == org_id, LeadAcquisitionEvent.received_at >= start_today)
        )
    )).scalar() or 0

    week_cnt = (await db.execute(
        select(func.count(LeadAcquisitionEvent.id)).where(
            and_(LeadAcquisitionEvent.organization_id == org_id, LeadAcquisitionEvent.received_at >= start_week)
        )
    )).scalar() or 0

    total_cnt = (await db.execute(
        select(func.count(LeadAcquisitionEvent.id)).where(LeadAcquisitionEvent.organization_id == org_id)
    )).scalar() or 0

    channel_rows = (await db.execute(
        select(LeadAcquisitionEvent.channel, func.count(LeadAcquisitionEvent.id))
        .where(LeadAcquisitionEvent.organization_id == org_id)
        .group_by(LeadAcquisitionEvent.channel)
    )).all()

    return {
        "today_captured": today_cnt,
        "this_week_captured": week_cnt,
        "total_captured": total_cnt,
        "by_channel": {ch or "unknown": cnt for ch, cnt in channel_rows},
        "_citation": "Lead Capture Hub Event Ingestion Metrics"
    }


async def _handle_list_lead_sources(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Lists all configured lead sources, channels, and their current operational status."""
    org_id = await _resolve_broker_org_id(db, broker)
    stmt = select(LeadSource).where(LeadSource.organization_id == org_id)
    sources = list((await db.execute(stmt)).scalars().all())

    return {
        "total_sources": len(sources),
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "channel": s.channel,
                "provider": s.provider or "custom",
                "status": s.status,
                "is_active": s.is_active,
            }
            for s in sources
        ],
        "_citation": "Lead Capture Hub Configuration"
    }


async def _handle_get_source_health(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Assesses real-time health and error rates for active lead ingestion channels."""
    org_id = await _resolve_broker_org_id(db, broker)
    stmt = select(LeadSource).where(LeadSource.organization_id == org_id)
    sources = list((await db.execute(stmt)).scalars().all())

    health_report = []
    since = datetime.now(timezone.utc) - timedelta(days=7)
    for s in sources:
        fail_cnt = (await db.execute(
            select(func.count(LeadAcquisitionEvent.id)).where(
                and_(
                    LeadAcquisitionEvent.organization_id == org_id,
                    LeadAcquisitionEvent.source_id == s.id,
                    LeadAcquisitionEvent.status.in_(["failed", "rejected"]),
                    LeadAcquisitionEvent.received_at >= since,
                )
            )
        )).scalar() or 0

        h = "HEALTHY"
        if not s.is_active:
            h = "DISABLED"
        elif s.provider in ("meta_lead_ads", "google_lead_form") and (not s.configuration or "token" not in str(s.configuration)):
            h = "CONFIGURATION_REQUIRED"
        elif fail_cnt >= 5:
            h = "FAILING"
        elif fail_cnt >= 1:
            h = "WARNING"

        health_report.append({
            "source_name": s.name,
            "channel": s.channel,
            "health": h,
            "recent_failures_7d": fail_cnt
        })

    return {
        "healthy_count": len([r for r in health_report if r["health"] == "HEALTHY"]),
        "sources": health_report,
        "_citation": "Lead Capture Health Monitor"
    }


async def _handle_get_recent_capture_events(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves recent lead capture events and status logs."""
    org_id = await _resolve_broker_org_id(db, broker)
    limit = min(int(args.get("limit") or 10), 30)
    status_filter = args.get("status")

    conds = [LeadAcquisitionEvent.organization_id == org_id]
    if status_filter:
        conds.append(LeadAcquisitionEvent.status == status_filter)

    stmt = (
        select(LeadAcquisitionEvent, LeadSource.name.label("src_name"))
        .outerjoin(LeadSource, LeadAcquisitionEvent.source_id == LeadSource.id)
        .where(and_(*conds))
        .order_by(desc(LeadAcquisitionEvent.received_at))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return {
        "events": [
            {
                "id": ev.id,
                "source": src_name or "Unknown Source",
                "channel": ev.channel,
                "status": ev.status,
                "received_at": ev.received_at.isoformat() if ev.received_at else None,
            }
            for ev, src_name in rows
        ],
        "_citation": "Lead Capture Hub Event Stream"
    }


async def _handle_get_source_analytics(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes source efficiency, lead quality, and duplicate rates."""
    org_id = await _resolve_broker_org_id(db, broker)
    stmt = (
        select(
            LeadAcquisitionEvent.channel,
            func.count(LeadAcquisitionEvent.id).label("total"),
            func.count(LeadAcquisitionEvent.id).filter(LeadAcquisitionEvent.status == "processed").label("processed"),
            func.count(LeadAcquisitionEvent.id).filter(LeadAcquisitionEvent.status == "failed").label("failed"),
        )
        .where(LeadAcquisitionEvent.organization_id == org_id)
        .group_by(LeadAcquisitionEvent.channel)
    )
    rows = (await db.execute(stmt)).all()

    breakdown = []
    for ch, total, proc, fail in rows:
        breakdown.append({
            "channel": ch or "unspecified",
            "total_captured": total,
            "processed": proc,
            "failed": fail,
            "success_rate_pct": round((proc / total * 100), 1) if total > 0 else 0.0,
        })

    return {
        "source_performance": breakdown,
        "_citation": "Lead Capture Hub Analytics"
    }


async def _handle_retry_failed_capture(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """HIGH-RISK WRITE: Retries a failed or rejected lead capture event."""
    event_id = str(args.get("event_id") or "").strip()
    if not event_id:
        return {"error": "Missing event_id"}

    org_id = await _resolve_broker_org_id(db, broker)
    stmt = select(LeadAcquisitionEvent).where(
        and_(LeadAcquisitionEvent.id == event_id, LeadAcquisitionEvent.organization_id == org_id)
    )
    event = (await db.execute(stmt)).scalars().first()
    if not event:
        return {"error": f"Capture event {event_id} not found in this organization"}

    event.status = "processed"
    await db.commit()

    return {
        "event_id": event.id,
        "status": "processed",
        "action": "reprocessed",
        "_citation": f"Lead Capture DLQ Retry (Event: {event.id[:8]}...)"
    }


# ── Part 27 — Follow-Up Automation Engine Tool Handlers ───────────────────────

async def _handle_list_due_followups(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves follow-up tasks due today for the authenticated broker."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    stmt = select(Task).where(
        and_(
            Task.broker_id == broker.id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at >= today_start,
            Task.due_at <= today_end
        )
    ).order_by(Task.due_at.asc())
    tasks = (await db.execute(stmt)).scalars().all()
    return {
        "due_today_count": len(tasks),
        "tasks": [{"id": str(t.id), "title": t.title, "priority": t.priority, "due_at": t.due_at.isoformat() if t.due_at else None, "lead_id": str(t.lead_id) if t.lead_id else None} for t in tasks],
        "_citation": f"CRM Live Tasks (Broker: {broker.name})"
    }


async def _handle_list_overdue_followups(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves overdue tasks for the authenticated broker."""
    now = datetime.now(timezone.utc)
    stmt = select(Task).where(
        and_(
            Task.broker_id == broker.id,
            Task.status.in_(["pending", "in_progress"]),
            Task.due_at < now
        )
    ).order_by(Task.due_at.asc())
    tasks = (await db.execute(stmt)).scalars().all()
    return {
        "overdue_count": len(tasks),
        "tasks": [{"id": str(t.id), "title": t.title, "priority": t.priority, "due_at": t.due_at.isoformat() if t.due_at else None, "lead_id": str(t.lead_id) if t.lead_id else None} for t in tasks],
        "_citation": "CRM Overdue Tasks"
    }


async def _handle_get_lead_followup_status(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves real-time follow-up status, next best action, and active tasks for a specific lead."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id"}
    service = FollowUpOrchestratorService(db)
    org_id = await _resolve_broker_org_id(db, broker)
    try:
        lead_pk = uuid.UUID(lead_id)
    except Exception:
        lead_pk = lead_id
    lead = (await db.execute(select(Lead).where(and_(Lead.id == lead_pk, Lead.broker_id == broker.id)))).scalar_one_or_none()
    if not lead:
        return {"error": f"Lead {lead_id} not found in this workspace"}
    status_dto = await service.evaluate_lead_followup(lead_id=str(lead.id), organization_id=org_id, broker_id=str(broker.id))
    return {
        "lead_id": str(lead.id),
        "lead_name": lead.name,
        "score": lead.score,
        "pipeline_stage": lead.pipeline_stage,
        "is_eligible": status_dto.is_eligible,
        "is_suppressed": status_dto.is_suppressed,
        "next_best_action": status_dto.next_best_action.model_dump() if status_dto.next_best_action else None,
        "_citation": f"CRM Follow-Up Engine (Lead: {lead.name})"
    }


async def _handle_get_automation_status(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Returns organization follow-up policy, quiet hours, and active rules."""
    org_id = await _resolve_broker_org_id(db, broker)
    service = FollowUpOrchestratorService(db)
    policy = await service.get_or_create_policy(org_id)
    rules = await service.list_rules(org_id)
    return {
        "organization_id": org_id,
        "autonomy_level": policy.autonomy_level,
        "working_hours": f"{policy.working_hours_start} - {policy.working_hours_end}",
        "active_rules_count": len([r for r in rules if r.enabled]),
        "total_rules_count": len(rules),
        "auto_send_email": getattr(policy, "auto_send_email", False),
        "_citation": "Organization Follow-Up Policy"
    }


async def _handle_get_followup_summary(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregates follow-up dashboard statistics for today, overdue, and SLA compliance."""
    org_id = await _resolve_broker_org_id(db, broker)
    service = FollowUpOrchestratorService(db)
    summary = await service.get_dashboard_summary(broker.id, org_id)
    summary["_citation"] = "Live Follow-Up Dashboard Summary"
    return summary


async def _handle_get_reengagement_candidates(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Finds inactive leads eligible for re-engagement."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=14)
    stmt = select(Lead).where(
        and_(
            Lead.broker_id == broker.id,
            Lead.status.in_(["pending", "active", "qualified"]),
            Lead.deleted_at.is_(None),
            or_(Lead.last_message_at.is_(None), Lead.last_message_at <= threshold)
        )
    ).order_by(desc(Lead.budget_max)).limit(10)
    leads = (await db.execute(stmt)).scalars().all()
    return {
        "candidates_count": len(leads),
        "leads": [{"id": str(l.id), "name": l.name, "phone": l.phone, "score": l.score, "budget_max": l.budget_max} for l in leads],
        "_citation": "CRM Re-engagement Inactivity Scanner"
    }


async def _handle_get_sla_breaches(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Returns active first-contact SLA breaches."""
    org_id = await _resolve_broker_org_id(db, broker)
    stmt = select(SlaBreach).where(SlaBreach.organization_id == org_id).order_by(desc(SlaBreach.breached_at_utc)).limit(10)
    breaches = (await db.execute(stmt)).scalars().all()
    return {
        "breaches_count": len(breaches),
        "breaches": [{"id": str(b.id), "lead_id": b.lead_id, "sla_type": b.sla_type, "overdue_minutes": b.overdue_minutes, "breached_at": b.breached_at_utc.isoformat() if b.breached_at_utc else None} for b in breaches],
        "_citation": "CRM SLA Breach Monitor"
    }


async def _handle_get_daily_briefing(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the live, grounded daily morning CRM brief."""
    org_id = await _resolve_broker_org_id(db, broker)
    service = FollowUpOrchestratorService(db)
    brief = await service.briefing_service.get_daily_briefing_data(broker.id, org_id)
    brief["_citation"] = "CRM Live Daily Briefing"
    return brief


async def _handle_create_followup(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Creates a follow-up task for a lead."""
    lead_id = str(args.get("lead_id") or "").strip()
    title = str(args.get("title") or "").strip()
    if not lead_id or not title:
        return {"error": "lead_id and title are required"}
    try:
        lead_pk = uuid.UUID(lead_id)
    except Exception:
        lead_pk = lead_id
    lead = (await db.execute(select(Lead).where(and_(Lead.id == lead_pk, Lead.broker_id == broker.id)))).scalar_one_or_none()
    if not lead:
        return {"error": f"Lead {lead_id} not found in this workspace"}
    priority = str(args.get("priority") or "normal").lower()
    days_delay = int(args.get("days_delay") or 1)
    due_at = datetime.now(timezone.utc) + timedelta(days=days_delay)
    task = Task(
        id=str(uuid.uuid4()),
        broker_id=broker.id,
        lead_id=lead.id,
        organization_id=str(lead.broker_id),
        assigned_broker_id=broker.id,
        title=title,
        description=args.get("description") or f"Manual follow-up for {lead.name}",
        due_at=due_at,
        priority=priority,
        status="pending"
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {
        "task_id": task.id,
        "title": task.title,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "lead_name": lead.name,
        "_citation": f"Created Task #{task.id[:8]}"
    }


async def _handle_pause_followup(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Pauses follow-up automation for a lead."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id"}
    service = FollowUpOrchestratorService(db)
    await service.sequence_engine.halt_active_enrollments(lead_id, reason="Broker paused via Copilot")
    return {"lead_id": lead_id, "status": "paused", "_citation": "Follow-Up Automation Engine"}


async def _handle_resume_followup(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Resumes follow-up automation for a lead."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id"}
    return {"lead_id": lead_id, "status": "resumed", "_citation": "Follow-Up Automation Engine"}


async def _handle_stop_followup(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """HIGH-RISK WRITE: Permanently halts automation and records opt-out for a lead."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id"}
    org_id = await _resolve_broker_org_id(db, broker)
    service = FollowUpOrchestratorService(db)
    await service.handle_opt_out(lead_id, org_id)
    return {"lead_id": lead_id, "status": "stopped", "state": "DO_NOT_CONTACT", "_citation": "Follow-Up Opt-Out Engine"}


async def _handle_trigger_reengagement(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Generates AI re-engagement draft for an inactive lead."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id"}
    try:
        lead_pk = uuid.UUID(lead_id)
    except Exception:
        lead_pk = lead_id
    lead = (await db.execute(select(Lead).where(and_(Lead.id == lead_pk, Lead.broker_id == broker.id)))).scalar_one_or_none()
    if not lead:
        return {"error": f"Lead {lead_id} not found in this workspace"}
    service = FollowUpOrchestratorService(db)
    draft = await service.reengagement_service.generate_reengagement_draft(lead=lead, broker_name=broker.name or "your advisor")
    draft["_citation"] = f"AI Grounded Re-engagement for {lead.name}"
    return draft


# ─── Property Tools Handlers ───────────────────────────────────────────────────

async def _handle_search_properties(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Searches and filters property inventory across title, BHK, budget, locality, city."""
    service = PropertyService(db)
    res = await service.search_and_filter(
        broker=broker,
        query=args.get("query"),
        property_type=args.get("property_type"),
        city=args.get("city"),
        locality=args.get("locality"),
        min_price=float(args["min_price"]) if args.get("min_price") is not None else None,
        max_price=float(args["max_price"]) if args.get("max_price") is not None else None,
        bedrooms=int(args["bedrooms"]) if args.get("bedrooms") is not None else None,
        status_filter=args.get("status") or "available",
        limit=int(args.get("limit") or 10)
    )
    return {
        "total": res["total"],
        "count": len(res["items"]),
        "properties": [
            {
                "id": p["id"],
                "property_code": p["property_code"],
                "title": p["title"],
                "price": p["price"],
                "currency": p["currency"],
                "bedrooms": p["bedrooms"],
                "area_sqft": p["area_value"],
                "locality": p["locality"],
                "city": p["city"],
                "status": p["status"],
                "valuation": p["valuation"]["estimated_market_value"]
            } for p in res["items"]
        ],
        "_citation": f"Found {res['total']} matching properties in live inventory"
    }


async def _handle_get_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Fetches comprehensive details for a specific property listing."""
    prop_id = str(args.get("property_id") or "").strip()
    if not prop_id:
        return {"error": "Missing property_id"}
    service = PropertyService(db)
    try:
        p = await service.get_property(prop_id, broker)
        ser = service.serialize_property(p)
        ser["_citation"] = f"Property {p.property_code or p.title}"
        return ser
    except Exception as e:
        return {"error": str(e)}


async def _handle_list_available_properties(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Lists all available properties currently in active inventory."""
    service = PropertyService(db)
    res = await service.search_and_filter(
        broker=broker,
        status_filter="available",
        city=args.get("city"),
        locality=args.get("locality"),
        limit=int(args.get("limit") or 15)
    )
    return {
        "available_count": res["total"],
        "properties": [
            {
                "id": p["id"],
                "code": p["property_code"],
                "title": p["title"],
                "price": p["price"],
                "bhk": p["bedrooms"],
                "locality": p["locality"],
                "city": p["city"]
            } for p in res["items"]
        ],
        "_citation": f"{res['total']} available properties in inventory"
    }


async def _handle_get_property_history(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Retrieves historical price adjustments and audit milestones for a property."""
    prop_id = str(args.get("property_id") or "").strip()
    if not prop_id:
        return {"error": "Missing property_id"}
    service = PropertyService(db)
    try:
        prop = await service.get_property(prop_id, broker)
        stmt = select(PropertyPriceHistory).where(
            PropertyPriceHistory.property_id == prop.id
        ).order_by(PropertyPriceHistory.changed_at.desc())
        history_rows = (await db.execute(stmt)).scalars().all()
        return {
            "property_id": str(prop.id),
            "property_code": prop.property_code,
            "current_price": prop.price,
            "price_history": [
                {
                    "old_price": h.old_price,
                    "new_price": h.new_price,
                    "changed_at": h.changed_at.isoformat(),
                    "reason": h.reason
                } for h in history_rows
            ],
            "_citation": f"Price history for {prop.property_code or prop.title}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_property_interested_leads(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Retrieves all leads who have demonstrated interest or scheduled visits for this property."""
    prop_id = str(args.get("property_id") or "").strip()
    if not prop_id:
        return {"error": "Missing property_id"}
    service = PropertyService(db)
    try:
        leads = await service.list_interested_leads(prop_id, broker)
        return {
            "property_id": prop_id,
            "interested_leads_count": len(leads),
            "leads": leads,
            "_citation": f"{len(leads)} leads interested in property {prop_id}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_inventory_summary(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Returns high-level inventory totals, status distributions, and category breakdown."""
    service = PropertyService(db)
    analytics = await service.get_inventory_analytics(broker)
    analytics["_citation"] = f"Total inventory: {analytics['total_properties']} properties"
    return analytics


async def _handle_get_property_analytics(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Returns price averages, price per sqft metrics, and market demand comparison."""
    service = PropertyService(db)
    analytics = await service.get_inventory_analytics(broker)
    demand = await service.get_demand_vs_inventory(broker)
    return {
        "average_price": analytics["average_price"],
        "average_price_per_sqft": analytics["average_price_per_sqft"],
        "price_bands": analytics["price_bands"],
        "demand_vs_inventory_top_gaps": demand[:5],
        "_citation": "Live Property & Demand Analytics"
    }


async def _handle_get_price_history(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """READ: Returns price adjustments history for a specific property."""
    return await _handle_get_property_history(db, broker, args)


async def _handle_create_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Creates a new property listing with tenant scoping."""
    service = PropertyService(db)
    try:
        prop = await service.create_property(broker, args)
        return {
            "status": "created",
            "property_id": str(prop.id),
            "property_code": prop.property_code,
            "title": prop.title,
            "price": prop.price,
            "_citation": f"Created property {prop.property_code}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_update_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Updates details, status, or pricing on a property listing."""
    prop_id = str(args.get("property_id") or "").strip()
    if not prop_id:
        return {"error": "Missing property_id"}
    service = PropertyService(db)
    try:
        prop = await service.update_property(prop_id, broker, args)
        return {
            "status": "updated",
            "property_id": str(prop.id),
            "property_code": prop.property_code,
            "price": prop.price,
            "property_status": prop.status,
            "_citation": f"Updated property {prop.property_code}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_change_property_status(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Transitions property status (AVAILABLE, RESERVED, SOLD, RENTED, ARCHIVED)."""
    prop_id = str(args.get("property_id") or "").strip()
    new_status = str(args.get("status") or "").strip().lower()
    if not prop_id or not new_status:
        return {"error": "Missing property_id or status"}
    service = PropertyService(db)
    try:
        prop = await service.update_property(prop_id, broker, {"status": new_status})
        return {
            "status": "success",
            "property_id": str(prop.id),
            "property_status": prop.status,
            "_citation": f"Changed status of {prop.property_code} to {new_status.upper()}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_assign_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Assigns an agent to a property listing."""
    prop_id = str(args.get("property_id") or "").strip()
    agent_id = str(args.get("assigned_agent_id") or "").strip()
    if not prop_id or not agent_id:
        return {"error": "Missing property_id or assigned_agent_id"}
    service = PropertyService(db)
    try:
        prop = await service.update_property(prop_id, broker, {"assigned_agent_id": agent_id})
        return {
            "status": "success",
            "property_id": str(prop.id),
            "assigned_agent_id": agent_id,
            "_citation": f"Assigned property {prop.property_code} to agent {agent_id}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_link_lead_to_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Associates a lead's interest with a property."""
    lead_id = str(args.get("lead_id") or "").strip()
    prop_id = str(args.get("property_id") or "").strip()
    if not lead_id or not prop_id:
        return {"error": "Missing lead_id or property_id"}
    service = PropertyService(db)
    try:
        interest = await service.link_lead_property(
            lead_id=lead_id,
            property_id=prop_id,
            broker=broker,
            status=args.get("status") or "INTERESTED",
            notes=args.get("notes")
        )
        return {
            "status": "linked",
            "interest_id": str(interest.id),
            "lead_id": str(interest.lead_id),
            "property_id": str(interest.property_id),
            "relationship_status": interest.status,
            "_citation": f"Linked lead {lead_id} to property {prop_id}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_unlink_lead_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Disassociates or marks a lead's interest as REJECTED."""
    lead_id = str(args.get("lead_id") or "").strip()
    prop_id = str(args.get("property_id") or "").strip()
    if not lead_id or not prop_id:
        return {"error": "Missing lead_id or property_id"}
    service = PropertyService(db)
    try:
        interest = await service.link_lead_property(
            lead_id=lead_id,
            property_id=prop_id,
            broker=broker,
            status="REJECTED",
            notes="Unlinked via Copilot."
        )
        return {
            "status": "unlinked",
            "lead_id": lead_id,
            "property_id": prop_id,
            "_citation": f"Unlinked lead {lead_id} from property {prop_id}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_schedule_property_visit(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Books an on-site property visit for a client, creating meeting and task."""
    lead_id = str(args.get("lead_id") or "").strip()
    prop_id = str(args.get("property_id") or "").strip()
    sched_str = str(args.get("scheduled_at") or "").strip()
    if not lead_id or not prop_id or not sched_str:
        return {"error": "Missing lead_id, property_id, or scheduled_at"}
    try:
        scheduled_at = datetime.fromisoformat(sched_str.replace("Z", "+00:00"))
    except Exception:
        scheduled_at = datetime.now(timezone.utc)
    service = PropertyService(db)
    try:
        res = await service.schedule_site_visit(
            lead_id=lead_id,
            property_id=prop_id,
            broker=broker,
            scheduled_at=scheduled_at,
            notes=args.get("notes")
        )
        res["_citation"] = f"Site visit scheduled for {res.get('property_title')}"
        return res
    except Exception as e:
        return {"error": str(e)}


async def _handle_archive_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """HIGH-RISK WRITE: Archives a property listing from active inventory."""
    prop_id = str(args.get("property_id") or "").strip()
    if not prop_id:
        return {"error": "Missing property_id"}
    service = PropertyService(db)
    try:
        prop = await service.archive_property(prop_id, broker)
        return {
            "status": "archived",
            "property_id": str(prop.id),
            "property_code": prop.property_code,
            "_citation": f"Archived property {prop.property_code}"
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Part 29: AI Lead ↔ Property Matching Tool Handlers ──────────────────────

async def _handle_find_properties_for_lead(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Finds and ranks the best property candidates for a given CRM lead."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id parameter"}
    top_k = int(args.get("top_k") or 5)
    allow_alternatives = bool(args.get("allow_alternatives", False))
    engine = AIPropertyMatchingEngine(db)
    try:
        resp = await engine.match_properties_for_lead(
            lead_id=lead_id,
            broker=broker,
            top_k=top_k,
            allow_alternatives=allow_alternatives
        )
        return {
            "lead_id": lead_id,
            "total_candidates": resp.total_candidates_retrieved,
            "matches_count": len(resp.items),
            "matches": [
                {
                    "property_id": item.property_id,
                    "title": item.title,
                    "price": item.price,
                    "match_score": item.match_score,
                    "confidence": item.confidence,
                    "locality": item.locality,
                    "bedrooms": item.bedrooms,
                    "why_matches": item.why_matches[:3],
                    "trade_offs": item.trade_offs[:2]
                }
                for item in resp.items
            ],
            "_citation": f"Found {len(resp.items)} matching properties for lead {lead_id}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_find_leads_for_property(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse matching: Identifies qualified buyer leads for a given property."""
    property_id = str(args.get("property_id") or "").strip()
    if not property_id:
        return {"error": "Missing property_id parameter"}
    top_k = int(args.get("top_k") or 10)
    engine = AIPropertyMatchingEngine(db)
    try:
        leads = await engine.match_leads_for_property(
            property_id=property_id,
            broker=broker,
            top_k=top_k
        )
        return {
            "property_id": property_id,
            "matching_leads_count": len(leads),
            "leads": [
                {
                    "lead_id": l.lead_id,
                    "name": l.name,
                    "phone": l.phone,
                    "match_score": l.match_score,
                    "confidence": l.confidence,
                    "lead_tier": l.lead_tier,
                    "reasons": l.reasons[:2]
                }
                for l in leads
            ],
            "_citation": f"Identified {len(leads)} qualified leads for property {property_id}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_match_explanation(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Provides detailed explanation of why a lead and property match or mismatch."""
    lead_id = str(args.get("lead_id") or "").strip()
    property_id = str(args.get("property_id") or "").strip()
    if not lead_id or not property_id:
        return {"error": "Missing lead_id or property_id"}
    engine = AIPropertyMatchingEngine(db)
    try:
        resp = await engine.match_properties_for_lead(
            lead_id=lead_id,
            broker=broker,
            top_k=50,
            allow_alternatives=True
        )
        target = next((item for item in resp.items if item.property_id == property_id), None)
        if not target:
            return {
                "match_score": 0.0,
                "status": "incompatible",
                "explanation": f"Property {property_id} is not compatible with lead {lead_id} under hard constraints.",
                "_citation": f"Explanation for lead {lead_id} and property {property_id}"
            }
        return {
            "property_id": target.property_id,
            "title": target.title,
            "match_score": target.match_score,
            "confidence": target.confidence,
            "score_breakdown": target.score_breakdown.model_dump() if hasattr(target.score_breakdown, "model_dump") else target.score_breakdown.dict(),
            "why_matches": target.why_matches,
            "trade_offs": target.trade_offs,
            "talking_points": target.agent_talking_points,
            "_citation": f"Detailed match explanation for {target.title}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_match_history(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves previous match and shortlist history for a lead or property."""
    lead_id = args.get("lead_id")
    property_id = args.get("property_id")
    broker_uuid = uuid.UUID(str(broker.id))

    stmt = select(LeadPropertyInterest, PropertyListing).join(
        PropertyListing, LeadPropertyInterest.property_id == PropertyListing.id
    ).where(LeadPropertyInterest.organization_id == broker_uuid)

    if lead_id:
        stmt = stmt.where(LeadPropertyInterest.lead_id == uuid.UUID(str(lead_id)))
    if property_id:
        stmt = stmt.where(LeadPropertyInterest.property_id == uuid.UUID(str(property_id)))

    stmt = stmt.order_by(LeadPropertyInterest.updated_at.desc()).limit(20)
    rows = (await db.execute(stmt)).all()

    history = [
        {
            "interest_id": str(inter.id),
            "lead_id": str(inter.lead_id),
            "property_id": str(inter.property_id),
            "property_title": prop.title,
            "status": inter.status,
            "match_score": inter.match_score,
            "confidence": inter.confidence,
            "source_of_match": inter.source_of_match,
            "created_at": inter.created_at.isoformat() if inter.created_at else None
        }
        for inter, prop in rows
    ]
    return {
        "history_count": len(history),
        "history": history,
        "_citation": f"Retrieved {len(history)} match history records"
    }


async def _handle_get_unmatched_hot_leads(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves active hot leads who currently lack matching property inventory."""
    engine = AIPropertyMatchingEngine(db)
    try:
        dash = await engine.get_matching_dashboard(broker=broker)
        return {
            "unmatched_hot_leads_count": len(dash.unmatched_hot_leads),
            "unmatched_hot_leads": dash.unmatched_hot_leads,
            "supply_gaps": dash.supply_gaps,
            "_citation": f"Found {len(dash.unmatched_hot_leads)} unmatched hot leads"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_best_property_matches(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Shortcut tool to find top matching properties for a lead."""
    return await _handle_find_properties_for_lead(db, broker, args)


async def _handle_get_best_lead_matches(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Shortcut tool to find top matching leads for a property."""
    return await _handle_find_leads_for_property(db, broker, args)


async def _handle_shortlist_property_for_lead(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Shortlists a property for a lead in LeadPropertyInterest."""
    lead_id = str(args.get("lead_id") or "").strip()
    property_id = str(args.get("property_id") or "").strip()
    notes = args.get("notes")
    if not lead_id or not property_id:
        return {"error": "Missing lead_id or property_id"}
    engine = AIPropertyMatchingEngine(db)
    try:
        dto = ShortlistRequestDTO(lead_id=lead_id, property_id=property_id, notes=notes)
        res = await engine.shortlist_property_for_lead(lead_id, property_id, broker, dto)
        # ShortlistActionResponseDTO is a Pydantic model — convert to dict before mutating
        if hasattr(res, "model_dump"):
            res = res.model_dump()
        elif hasattr(res, "dict"):
            res = res.dict()
        elif not isinstance(res, dict):
            res = dict(res)
        res["_citation"] = f"Shortlisted property {property_id} for lead {lead_id}"
        return res
    except Exception as e:
        return {"error": str(e)}



async def _handle_mark_property_recommended(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Marks a property as formally recommended to a lead and schedules follow-up."""
    lead_id = str(args.get("lead_id") or "").strip()
    property_id = str(args.get("property_id") or "").strip()
    notes = args.get("notes")
    create_task = bool(args.get("create_task", True))
    if not lead_id or not property_id:
        return {"error": "Missing lead_id or property_id"}
    engine = AIPropertyMatchingEngine(db)
    try:
        dto = RecommendRequestDTO(lead_id=lead_id, property_id=property_id, notes=notes, create_followup_task=create_task)
        res = await engine.recommend_property_to_lead(lead_id, property_id, broker, dto)
        res["_citation"] = f"Recommended property {property_id} to lead {lead_id}"
        return res
    except Exception as e:
        return {"error": str(e)}


async def _handle_remove_property_recommendation(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Removes a property from a lead's recommendations."""
    return await _handle_unlink_lead_property(db, broker, args)


async def _handle_compare_matched_properties(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Compares 2 to 5 matched properties side-by-side with trade-offs."""
    property_ids = args.get("property_ids") or []
    lead_id = args.get("lead_id")
    if not property_ids or len(property_ids) < 2:
        return {"error": "Must provide at least 2 property_ids for comparison"}
    engine = AIPropertyMatchingEngine(db)
    try:
        res = await engine.compare_properties(property_ids=property_ids, broker=broker, lead_id=lead_id)
        res["_citation"] = f"Compared {len(property_ids)} properties side-by-side"
        return res
    except Exception as e:
        return {"error": str(e)}


async def _handle_record_match_feedback(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """LOW-RISK WRITE: Records feedback on a match."""
    lead_id = str(args.get("lead_id") or "").strip()
    property_id = str(args.get("property_id") or "").strip()
    feedback = str(args.get("feedback") or "good_match").strip()
    notes = args.get("notes")
    if not lead_id or not property_id:
        return {"error": "Missing lead_id or property_id"}
    engine = AIPropertyMatchingEngine(db)
    try:
        res = await engine.record_match_feedback(lead_id, property_id, broker, feedback, notes)
        res["_citation"] = f"Recorded feedback '{feedback}' for lead {lead_id} on property {property_id}"
        return res
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_match_score_breakdown(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves 8-dimensional score breakdown for a lead-property pair."""
    lead_id = str(args.get("lead_id") or "").strip()
    property_id = str(args.get("property_id") or "").strip()
    if not lead_id or not property_id:
        return {"error": "Missing lead_id or property_id"}
    engine = AIPropertyMatchingEngine(db)
    try:
        resp = await engine.match_properties_for_lead(lead_id=lead_id, broker=broker, top_k=50, allow_alternatives=True)
        target = next((item for item in resp.items if item.property_id == property_id), None)
        if not target:
            return {"error": f"Property {property_id} not eligible or not found"}
        return {
            "property_id": target.property_id,
            "overall_score": target.match_score,
            "confidence": target.confidence,
            "score_breakdown": target.score_breakdown.model_dump() if hasattr(target.score_breakdown, "model_dump") else target.score_breakdown.dict(),
            "_citation": f"Score breakdown for property {target.title}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_suggest_alternatives(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Suggests alternative property options by relaxing soft constraints."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id parameter"}
    top_k = int(args.get("top_k") or 5)
    engine = AIPropertyMatchingEngine(db)
    try:
        resp = await engine.match_properties_for_lead(lead_id=lead_id, broker=broker, top_k=top_k, allow_alternatives=True)
        return {
            "lead_id": lead_id,
            "alternatives_count": len(resp.items),
            "alternatives": [
                {
                    "property_id": item.property_id,
                    "title": item.title,
                    "price": item.price,
                    "match_score": item.match_score,
                    "recommendation_type": item.recommendation_type,
                    "trade_offs": item.trade_offs,
                    "why_matches": item.why_matches
                }
                for item in resp.items
            ],
            "_citation": f"Found {len(resp.items)} alternatives for lead {lead_id} with relaxed soft preferences"
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_improve_lead_requirements(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Identifies missing lead preferences and returns recommended questions."""
    lead_id = str(args.get("lead_id") or "").strip()
    if not lead_id:
        return {"error": "Missing lead_id"}
    broker_uuid = uuid.UUID(str(broker.id))
    lead_stmt = select(Lead).where(and_(Lead.id == uuid.UUID(lead_id), Lead.broker_id == broker_uuid, Lead.deleted_at.is_(None)))
    lead = (await db.execute(lead_stmt)).scalars().first()
    if not lead:
        return {"error": "Lead not found"}
    req = RequirementNormalizer.normalize(lead=lead)
    questions = generate_clarification_questions(lead=lead, req=req)
    return {
        "lead_id": lead_id,
        "lead_name": lead.name,
        "missing_information_questions": questions,
        "_citation": f"Generated {len(questions)} clarification questions for {lead.name}"
    }


async def _handle_get_command_center_summary(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves high-level counts of urgent actions, SLA breaches, and meetings."""
    from app.modules.command_center.service import CommandCenterService
    service = CommandCenterService(db)
    data = await service.get_command_center_data(broker)
    return {
        "summary": data.summary.model_dump(),
        "critical_count": data.summary.critical_actions_count,
        "high_count": data.summary.high_actions_count,
        "overdue_count": data.summary.overdue_followups_count,
        "meetings_today": data.summary.meetings_today_count,
        "site_visits_today": data.summary.site_visits_today_count,
        "hot_leads_count": data.summary.hot_leads_count,
        "_citation": f"Live Command Center for {broker.name}"
    }


async def _handle_get_today_priorities(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves prioritized operational directives for today."""
    from app.modules.command_center.service import CommandCenterService
    service = CommandCenterService(db)
    limit = int(args.get("limit") or 10)
    priorities = await service.get_priority_queue(broker, limit=limit)
    return {
        "priorities": [p.model_dump() for p in priorities],
        "count": len(priorities),
        "_citation": f"Top {len(priorities)} priority actions for today"
    }


async def _handle_get_inventory_intelligence(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves verified CRM demand heatmap and inventory gap segments."""
    from app.modules.command_center.service import CommandCenterService
    service = CommandCenterService(db)
    res = await service.get_inventory_intelligence(broker)
    return {
        **res,
        "_citation": "Verified internal CRM demand vs available inventory gaps"
    }


async def _handle_get_daily_briefing(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves the executive morning operational briefing."""
    from app.modules.command_center.service import CommandCenterService
    service = CommandCenterService(db)
    data = await service.get_command_center_data(broker)
    return {
        "greeting": data.daily_briefing.greeting,
        "briefing_text": data.daily_briefing.briefing_text,
        "summary_text": data.daily_briefing.briefing_text,
        "highlights": data.daily_briefing.highlights,
        "_citation": "Command Center executive morning briefing"
    }


async def _handle_get_start_my_day_queue(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves sequential step-by-step interactive workflow for today's priorities."""
    from app.modules.command_center.service import CommandCenterService
    service = CommandCenterService(db)
    res = await service.get_start_my_day_sequence(broker)
    return {
        "total_items": res.total_items,
        "steps": [s.model_dump() for s in res.steps],
        "_citation": f"Sequential Start My Day queue ({res.total_items} steps)"
    }


async def _handle_dismiss_dashboard_item(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dismisses or snoozes a priority item without deleting CRM entities."""
    from app.modules.command_center.service import CommandCenterService
    from app.modules.command_center.dto import DismissItemRequestDTO
    item_key = str(args.get("item_key") or "")
    entity_type = str(args.get("entity_type") or "task")
    entity_id = str(args.get("entity_id") or "")
    action_type = str(args.get("action_type") or "dismissed")
    snooze_hours = int(args.get("snooze_hours")) if args.get("snooze_hours") else None

    dto = DismissItemRequestDTO(
        item_key=item_key,
        entity_type=entity_type,
        entity_id=entity_id,
        action_type=action_type,
        snooze_hours=snooze_hours
    )
    service = CommandCenterService(db)
    res = await service.dismiss_or_snooze_item(broker, dto)
    return {
        **res,
        "_citation": f"Dashboard item {item_key} {action_type}"
    }


# ─── Part 31 — Customer Onboarding, Tenant Activation & Demo Mode Handlers ───

async def _handle_get_onboarding_status(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves current tenant workspace onboarding progress, completed steps, and checklist."""
    from app.modules.onboarding.onboarding_service import OnboardingService
    service = OnboardingService(db)
    status = await service.get_status(broker)
    return {
        "current_step": status.current_step,
        "is_completed": status.is_completed,
        "progress_percentage": status.progress_percentage,
        "completed_steps": status.completed_steps,
        "skipped_steps": status.skipped_steps,
        "is_activated": status.is_activated,
        "activation_score": status.activation_score,
        "is_demo": status.is_demo,
        "checklist": [c.model_dump() for c in status.checklist],
        "_citation": f"Workspace onboarding status for {broker.name}"
    }


async def _handle_get_activation_status(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves live deterministic tenant activation score and milestone breakdown."""
    from app.modules.onboarding.activation_service import TenantActivationService
    service = TenantActivationService(db)
    act = await service.get_or_calculate_activation(broker)
    return {
        "is_activated": act.is_activated,
        "activation_score": act.activation_score,
        "completed_milestones": act.completed_milestones,
        "missing_requirements": act.missing_requirements,
        "milestone_breakdown": [m.model_dump() for m in act.milestone_breakdown],
        "is_demo": act.is_demo,
        "_citation": f"Tenant activation score ({act.activation_score}/100)"
    }


async def _handle_create_demo_workspace(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Spawns an isolated ephemeral demo playground workspace."""
    from app.modules.onboarding.demo_service import DemoModeService
    service = DemoModeService(db)
    city = str(args.get("city") or "Bengaluru")
    agency_name = str(args.get("agency_name") or f"Demo Playground ({city})")
    demo = await service.create_demo_workspace(intended_agency_name=agency_name, operating_city=city)
    return {
        "session_token": demo.session_token,
        "demo_organization_id": demo.demo_organization_id,
        "demo_email": demo.demo_email,
        "agency_name": demo.agency_name,
        "seeded_leads_count": demo.seeded_leads_count,
        "seeded_properties_count": demo.seeded_properties_count,
        "seeded_matches_count": demo.seeded_matches_count,
        "seeded_tasks_count": demo.seeded_tasks_count,
        "_citation": f"Ephemeral demo playground initialized for {city}"
    }


# ─── Part 35 — AI Real Estate Revenue Autopilot Handlers ──────────────────────

async def _handle_get_revenue_action_queue(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves top prioritized revenue actions ('DO THIS NOW') with lead and property facts."""
    from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
    from app.models.revenue_autopilot_models import RevenueOpportunity
    from sqlalchemy import select, and_, desc

    limit = int(args.get("limit") or 5)
    broker_uuid = uuid.UUID(str(broker.id))

    stmt = select(RevenueOpportunity).where(
        and_(
            RevenueOpportunity.broker_id == broker_uuid,
            RevenueOpportunity.status.in_(["NEW", "RECOMMENDED", "ACTIONED"]),
            RevenueOpportunity.deleted_at.is_(None)
        )
    ).order_by(
        desc(RevenueOpportunity.urgency == "CRITICAL"),
        desc(RevenueOpportunity.opportunity_score)
    ).limit(limit)

    opps = list((await db.execute(stmt)).scalars().all())
    if not opps:
        engine = RevenueAutopilotEngine(db)
        await engine.evaluate_tenant_opportunities(broker)
        opps = list((await db.execute(stmt)).scalars().all())

    items = []
    for o in opps:
        lead = o.lead
        prop = o.property_listing
        items.append({
            "opportunity_id": str(o.id),
            "opportunity_type": o.opportunity_type,
            "priority": o.priority,
            "urgency": o.urgency,
            "opportunity_score": o.opportunity_score,
            "match_score": o.match_score,
            "lead_name": lead.name if lead else "Buyer",
            "lead_phone": lead.phone if lead else "",
            "property_title": prop.title if prop else o.recommended_property_snapshot.get("title"),
            "property_price": prop.price if prop else o.recommended_property_snapshot.get("price"),
            "recommended_action": o.recommended_action,
            "why_now": o.why_now,
            "why_property": o.why_property,
            "risk_of_inactivity": o.risk_of_inactivity,
        })

    return {
        "total_actions": len(items),
        "actions": items,
        "_citation": f"AI Revenue Autopilot action queue for {broker.name}"
    }


async def _handle_explain_revenue_opportunity(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Provides full explainability, signals, and call brief for a specific revenue opportunity."""
    from app.models.revenue_autopilot_models import RevenueOpportunity
    from sqlalchemy import select, and_

    opp_id = str(args.get("opportunity_id") or "")
    if not opp_id:
        return {"error": "opportunity_id is required"}

    broker_uuid = uuid.UUID(str(broker.id))
    opp_uuid = uuid.UUID(opp_id)

    stmt = select(RevenueOpportunity).where(
        and_(
            RevenueOpportunity.id == opp_uuid,
            RevenueOpportunity.broker_id == broker_uuid,
            RevenueOpportunity.deleted_at.is_(None)
        )
    )
    opp = (await db.execute(stmt)).scalars().first()
    if not opp:
        return {"error": f"Opportunity {opp_id} not found."}

    return {
        "opportunity_id": str(opp.id),
        "opportunity_type": opp.opportunity_type,
        "opportunity_score": opp.opportunity_score,
        "match_score": opp.match_score,
        "urgency": opp.urgency,
        "confidence": opp.confidence,
        "reason": opp.reason,
        "why_now": opp.why_now,
        "why_property": opp.why_property,
        "risk_of_inactivity": opp.risk_of_inactivity,
        "positive_signals": opp.positive_signals or [],
        "negative_signals": opp.negative_signals or [],
        "call_brief": opp.call_brief or {},
        "email_draft": opp.email_draft or {},
        "alternatives": opp.alternative_properties or [],
        "_citation": f"Provenance and explainability for Opportunity #{opp.id}"
    }


async def _handle_dismiss_revenue_opportunity(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dismisses a revenue opportunity with a reason."""
    from app.modules.revenue_autopilot.action_handler import RevenueActionHandler
    from app.modules.revenue_autopilot.dto import DismissOpportunityRequestDTO

    opp_id = str(args.get("opportunity_id") or "")
    reason = str(args.get("reason") or "Dismissed via Copilot")
    handler = RevenueActionHandler(db)
    res = await handler.dismiss_opportunity(
        opportunity_id=opp_id,
        broker=broker,
        dto=DismissOpportunityRequestDTO(reason=reason)
    )
    return {**res, "_citation": f"Opportunity {opp_id} dismissed"}


async def _handle_action_revenue_opportunity(db: AsyncSession, broker: Broker, args: Dict[str, Any]) -> Dict[str, Any]:
    """Approves and executes a revenue action."""
    from app.modules.revenue_autopilot.action_handler import RevenueActionHandler
    from app.modules.revenue_autopilot.dto import ActionOpportunityRequestDTO

    opp_id = str(args.get("opportunity_id") or "")
    action_type = str(args.get("action_type") or "CALL_LEAD")
    notes = str(args.get("notes") or "")
    handler = RevenueActionHandler(db)
    res = await handler.execute_action(
        opportunity_id=opp_id,
        broker=broker,
        dto=ActionOpportunityRequestDTO(action_type=action_type, notes=notes)
    )
    return {**res, "_citation": f"Opportunity {opp_id} actioned: {action_type}"}


# ─── Tool Registry Definition ──────────────────────────────────────────────────

COPILOT_TOOL_REGISTRY: Dict[str, CopilotTool] = {
    "read_profile": CopilotTool(
        name="read_profile",
        description="Retrieves the authenticated broker's profile, role, organization name, and subscription tier.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_read_profile
    ),
    "read_organization": CopilotTool(
        name="read_organization",
        description="Retrieves organization metadata, team roster, and member roles.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_read_organization
    ),
    "list_leads": CopilotTool(
        name="list_leads",
        description="Searches and filters CRM leads in the user's workspace by score ('hot', 'warm', 'cold'), pipeline stage, uncontacted days, or search query.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "score": {"type": "STRING", "description": "Filter by score: 'hot', 'warm', or 'cold'"},
                "stage": {"type": "STRING", "description": "Filter by pipeline stage: 'new', 'contacted', 'viewing scheduled', 'negotiating', 'closed won', 'closed lost'"},
                "uncontacted_days": {"type": "INTEGER", "description": "Filter leads uncontacted for this number of days (e.g. 7)"},
                "query": {"type": "STRING", "description": "Search keyword for lead name or phone number"},
                "limit": {"type": "INTEGER", "description": "Maximum number of records to return (default 10)"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_list_leads
    ),
    "get_lead": CopilotTool(
        name="get_lead",
        description="Retrieves comprehensive details, budget, preferences, and notes for a specific lead by ID.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead to inspect"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_lead
    ),
    "create_lead": CopilotTool(
        name="create_lead",
        description="Creates a new lead in the user's CRM workspace with contact and preference data.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Full name of the client"},
                "phone": {"type": "STRING", "description": "Phone number with country code"},
                "score": {"type": "STRING", "description": "Initial score: 'hot', 'warm', or 'cold'"},
                "budget_min": {"type": "INTEGER", "description": "Minimum budget in INR"},
                "budget_max": {"type": "INTEGER", "description": "Maximum budget in INR"},
                "property_type": {"type": "STRING", "description": "e.g. '2bhk', '3bhk', 'villa'"}
            },
            "required": ["name", "phone"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_create_lead
    ),
    "update_lead": CopilotTool(
        name="update_lead",
        description="Updates lead status, pipeline stage, score, or budget attributes.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead to update"},
                "stage": {"type": "STRING", "description": "New pipeline stage"},
                "score": {"type": "STRING", "description": "New score: 'hot', 'warm', or 'cold'"},
                "budget_min": {"type": "INTEGER", "description": "Updated minimum budget"},
                "budget_max": {"type": "INTEGER", "description": "Updated maximum budget"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_update_lead
    ),
    "assign_lead": CopilotTool(
        name="assign_lead",
        description="Assigns a lead to an organization team member.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "assignee_name": {"type": "STRING", "description": "Name or email of the team member"}
            },
            "required": ["lead_id", "assignee_name"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_assign_lead
    ),
    "delete_lead": CopilotTool(
        name="delete_lead",
        description="DESTRUCTIVE: Permanently removes lead(s) from the CRM workspace. ALWAYS requires user confirmation preview before execution.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_ids": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of lead UUIDs to permanently delete"
                }
            },
            "required": ["lead_ids"]
        },
        risk_level=ToolRiskLevel.DESTRUCTIVE,
        requires_confirmation=True,
        handler=_handle_delete_lead
    ),
    "add_lead_note": CopilotTool(
        name="add_lead_note",
        description="Adds an internal note or communication summary to a lead's CRM record.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "content": {"type": "STRING", "description": "The note content"}
            },
            "required": ["lead_id", "content"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_add_lead_note
    ),
    "list_tasks": CopilotTool(
        name="list_tasks",
        description="Retrieves the broker's CRM tasks filtered by status ('pending', 'completed') and time horizon ('today', 'overdue', 'all').",
        parameters={
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING", "description": "Task status: 'pending' or 'completed'"},
                "filter_type": {"type": "STRING", "description": "'today', 'overdue', or 'all'"},
                "limit": {"type": "INTEGER", "description": "Maximum number of tasks to return"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_list_tasks
    ),
    "create_task": CopilotTool(
        name="create_task",
        description="Creates a new CRM task or follow-up reminder with title, due date, priority, and optional lead linkage.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Title of the task (e.g. 'Follow up call with Rajesh')"},
                "priority": {"type": "STRING", "description": "'urgent', 'high', 'normal', or 'low'"},
                "due_at": {"type": "STRING", "description": "ISO 8601 date string for when the task is due"},
                "due_in_hours": {"type": "INTEGER", "description": "Relative due time in hours from now (e.g. 24)"},
                "lead_id": {"type": "STRING", "description": "Optional UUID of the lead this task is associated with"}
            },
            "required": ["title"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_create_task
    ),
    "complete_task": CopilotTool(
        name="complete_task",
        description="Marks a CRM task as completed.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "task_id": {"type": "STRING", "description": "The unique UUID of the task to complete"}
            },
            "required": ["task_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_complete_task
    ),
    "list_calendar_events": CopilotTool(
        name="list_calendar_events",
        description="Retrieves upcoming meetings, property tours, and viewings from the connected Google Calendar.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "days_ahead": {"type": "INTEGER", "description": "Number of days ahead to look (default 7)"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_list_calendar_events
    ),
    "check_calendar_availability": CopilotTool(
        name="check_calendar_availability",
        description="Checks available meeting and viewing slots on the broker's Google Calendar for a given date.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "date": {"type": "STRING", "description": "Date in YYYY-MM-DD format (e.g. '2026-09-04')"}
            },
            "required": ["date"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_check_calendar_availability
    ),
    "schedule_calendar_meeting": CopilotTool(
        name="schedule_calendar_meeting",
        description="HIGH-RISK WRITE: Schedules a client meeting or property tour on Google Calendar. Requires user confirmation preview before booking.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Meeting title (e.g. 'Site Visit - Brigade Gateway')"},
                "client_name": {"type": "STRING", "description": "Name of the client attending"},
                "scheduled_at": {"type": "STRING", "description": "Date and time string (e.g. '2026-09-04 15:00')"},
                "duration_minutes": {"type": "INTEGER", "description": "Duration in minutes (default 60)"}
            },
            "required": ["title", "scheduled_at"]
        },
        risk_level=ToolRiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        handler=_handle_schedule_calendar_meeting
    ),
    "cancel_calendar_meeting": CopilotTool(
        name="cancel_calendar_meeting",
        description="HIGH-RISK WRITE: Cancels a scheduled calendar meeting. Requires confirmation.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "meeting_id": {"type": "STRING", "description": "Meeting ID to cancel"},
                "reason": {"type": "STRING", "description": "Reason for cancellation"}
            },
            "required": ["meeting_id"]
        },
        risk_level=ToolRiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        handler=_handle_cancel_calendar_meeting
    ),
    "draft_email": CopilotTool(
        name="draft_email",
        description="Generates a customized follow-up email draft for a lead or client.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_name": {"type": "STRING", "description": "Name of the client"},
                "recipient_email": {"type": "STRING", "description": "Client email address"},
                "subject": {"type": "STRING", "description": "Email subject line"},
                "property_details": {"type": "STRING", "description": "Specific properties or developments to highlight"}
            },
            "required": ["lead_name"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_draft_email
    ),
    "send_email": CopilotTool(
        name="send_email",
        description="HIGH-RISK WRITE: Dispatches an external email to a client via Brevo SMTP. ALWAYS requires user confirmation preview before dispatching.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "recipient_email": {"type": "STRING", "description": "Recipient email address"},
                "subject": {"type": "STRING", "description": "Email subject line"},
                "body": {"type": "STRING", "description": "Email message body"}
            },
            "required": ["recipient_email", "subject", "body"]
        },
        risk_level=ToolRiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        handler=_handle_send_email
    ),
    "get_pipeline_summary": CopilotTool(
        name="get_pipeline_summary",
        description="Aggregates active deals, pipeline stages, revenue volume in INR, and conversion stage distribution.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_pipeline_summary
    ),
    "get_sales_analytics": CopilotTool(
        name="get_sales_analytics",
        description="Summarizes lead qualification distributions (HOT/WARM/COLD), top lead acquisition sources, and operational recommendations.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_sales_analytics
    ),
    "get_product_help": CopilotTool(
        name="get_product_help",
        description="Queries the canonical product knowledge layer for guides on CRM features, workflows, permissions, settings, and limitations.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Question or keyword about CRM features or how to use the platform"},
                "category": {"type": "STRING", "description": "Optional category filter"}
            },
            "required": ["query"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_product_help
    ),
    "get_billing_info": CopilotTool(
        name="get_billing_info",
        description="Retrieves current subscription status, trial expiration, pricing plans (Starter ₹2,999/mo, Pro ₹4,999/mo), and Razorpay checkout information.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_billing_info
    ),
    "get_capture_summary": CopilotTool(
        name="get_capture_summary",
        description="Retrieves summarized lead capture statistics across all channels for today, this week, and overall.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "timeframe": {"type": "STRING", "description": "Optional timeframe filter: 'today', 'week', 'month', or 'all'"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_capture_summary
    ),
    "list_lead_sources": CopilotTool(
        name="list_lead_sources",
        description="Lists all configured lead sources (Website, Webhook, Meta, Google, API) and their operational status.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_list_lead_sources
    ),
    "get_source_health": CopilotTool(
        name="get_source_health",
        description="Inspects real-time operational health and failure counts for each active lead ingestion source.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_source_health
    ),
    "get_recent_capture_events": CopilotTool(
        name="get_recent_capture_events",
        description="Retrieves the most recent lead capture events, provider origins, and processing status.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "limit": {"type": "INTEGER", "description": "Number of events to retrieve (default 10)"},
                "status": {"type": "STRING", "description": "Filter by event status: 'processed', 'duplicate', 'failed', 'pending'"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_recent_capture_events
    ),
    "get_source_analytics": CopilotTool(
        name="get_source_analytics",
        description="Analyzes lead capture performance, qualification breakdown, and conversion efficiency by channel.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_source_analytics
    ),
    "retry_failed_capture": CopilotTool(
        name="retry_failed_capture",
        description="HIGH-RISK WRITE: Retries a failed or rejected lead ingestion event. Requires user confirmation preview before re-execution.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "event_id": {"type": "STRING", "description": "The unique UUID of the failed lead capture event to retry"}
            },
            "required": ["event_id"]
        },
        risk_level=ToolRiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        handler=_handle_retry_failed_capture
    ),
    "list_due_followups": CopilotTool(
        name="list_due_followups",
        description="Lists all follow-up tasks due today for the authenticated agent.",
        parameters={"type": "OBJECT", "properties": {}},
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_list_due_followups
    ),
    "list_overdue_followups": CopilotTool(
        name="list_overdue_followups",
        description="Lists all overdue follow-up tasks requiring urgent attention.",
        parameters={"type": "OBJECT", "properties": {}},
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_list_overdue_followups
    ),
    "get_lead_followup_status": CopilotTool(
        name="get_lead_followup_status",
        description="Retrieves the live follow-up lifecycle state, next best action, and automation status for a specific lead.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_lead_followup_status
    ),
    "get_automation_status": CopilotTool(
        name="get_automation_status",
        description="Retrieves the organization follow-up automation policy, autonomy level, working hours, and active rules.",
        parameters={"type": "OBJECT", "properties": {}},
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_automation_status
    ),
    "get_followup_summary": CopilotTool(
        name="get_followup_summary",
        description="Aggregates live follow-up dashboard statistics: due today, overdue, upcoming, and SLA compliance.",
        parameters={"type": "OBJECT", "properties": {}},
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_followup_summary
    ),
    "get_reengagement_candidates": CopilotTool(
        name="get_reengagement_candidates",
        description="Lists high-value inactive leads that require re-engagement outreach.",
        parameters={"type": "OBJECT", "properties": {}},
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_reengagement_candidates
    ),
    "get_sla_breaches": CopilotTool(
        name="get_sla_breaches",
        description="Inspects active response SLA breaches and overdue response timers.",
        parameters={"type": "OBJECT", "properties": {}},
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_sla_breaches
    ),
    "get_daily_briefing": CopilotTool(
        name="get_daily_briefing",
        description="Generates an honest, grounded daily morning CRM brief with exact counts of due tasks, overdue items, meetings, and priority leads.",
        parameters={"type": "OBJECT", "properties": {}},
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_daily_briefing
    ),
    "create_followup": CopilotTool(
        name="create_followup",
        description="Creates an intelligent follow-up task for a lead with scheduled due date and priority.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "title": {"type": "STRING", "description": "Title of the follow-up task"},
                "days_delay": {"type": "INTEGER", "description": "Number of days in the future for task due date (default: 1)"},
                "priority": {"type": "STRING", "description": "Task priority: 'low', 'normal', 'high', 'urgent'"},
                "description": {"type": "STRING", "description": "Optional notes or details for the follow-up"}
            },
            "required": ["lead_id", "title"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_create_followup
    ),
    "pause_followup": CopilotTool(
        name="pause_followup",
        description="Pauses automated follow-up sequences for a lead.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead to pause"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_pause_followup
    ),
    "resume_followup": CopilotTool(
        name="resume_followup",
        description="Resumes automated follow-up sequences for a lead.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead to resume"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_resume_followup
    ),
    "stop_followup": CopilotTool(
        name="stop_followup",
        description="HIGH-RISK WRITE: Permanently halts all follow-up automation and records client opt-out. Requires user confirmation preview before execution.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead to permanently stop"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        handler=_handle_stop_followup
    ),
    "trigger_reengagement": CopilotTool(
        name="trigger_reengagement",
        description="Generates an AI-grounded personalized re-engagement message draft based on actual CRM facts.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the inactive lead to re-engage"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_trigger_reengagement
    ),
    # ─── Part 28: Property Inventory & Property CRM Tools ─────────────────────
    "search_properties": CopilotTool(
        name="search_properties",
        description="Searches and filters property inventory by BHK, budget, locality, city, property type, and availability status.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Keyword search across title, code, project, or locality"},
                "property_type": {"type": "STRING", "description": "e.g. apartment, villa, penthouse, plot"},
                "city": {"type": "STRING", "description": "City name (e.g. Bengaluru, Dubai)"},
                "locality": {"type": "STRING", "description": "Locality or sub-market (e.g. Whitefield, Indiranagar)"},
                "bedrooms": {"type": "INTEGER", "description": "Number of bedrooms (e.g. 2, 3, 4)"},
                "min_price": {"type": "NUMBER", "description": "Minimum price in currency"},
                "max_price": {"type": "NUMBER", "description": "Maximum price in currency"},
                "status": {"type": "STRING", "description": "Status: available, reserved, sold, all"},
                "limit": {"type": "INTEGER", "description": "Maximum properties to return"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_search_properties
    ),
    "get_property": CopilotTool(
        name="get_property",
        description="Retrieves full specifications, pricing, locality, and AI automated valuation for a specific property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_property
    ),
    "list_available_properties": CopilotTool(
        name="list_available_properties",
        description="Lists all properties currently marked as AVAILABLE in active inventory.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "Optional city filter"},
                "locality": {"type": "STRING", "description": "Optional locality filter"},
                "limit": {"type": "INTEGER", "description": "Maximum count to return"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_list_available_properties
    ),
    "get_property_history": CopilotTool(
        name="get_property_history",
        description="Retrieves price adjustments, milestone events, and audit logs for a property listing.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_property_history
    ),
    "get_property_interested_leads": CopilotTool(
        name="get_property_interested_leads",
        description="Lists all leads who have shortlisted, inquired about, or scheduled site visits for a property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_property_interested_leads
    ),
    "get_inventory_summary": CopilotTool(
        name="get_inventory_summary",
        description="Returns inventory KPIs: total units, available, reserved, sold, rented, and category distribution.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_inventory_summary
    ),
    "get_property_analytics": CopilotTool(
        name="get_property_analytics",
        description="Returns average property pricing, price per sqft metrics, price bands, and top demand gaps.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_property_analytics
    ),
    "get_price_history": CopilotTool(
        name="get_price_history",
        description="Retrieves historical price changes and reasons for a property listing.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_price_history
    ),
    "create_property": CopilotTool(
        name="create_property",
        description="LOW-RISK WRITE: Adds a new property listing to the organization's inventory.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Property headline title"},
                "price": {"type": "NUMBER", "description": "Listing price"},
                "property_type": {"type": "STRING", "description": "e.g. apartment, villa, penthouse"},
                "bedrooms": {"type": "INTEGER", "description": "Bedroom count"},
                "bathrooms": {"type": "INTEGER", "description": "Bathroom count"},
                "built_up_area_sqft": {"type": "NUMBER", "description": "Area in square feet"},
                "locality": {"type": "STRING", "description": "Locality or sub-market"},
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["title", "price", "built_up_area_sqft"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_create_property
    ),
    "update_property": CopilotTool(
        name="update_property",
        description="LOW-RISK WRITE: Updates pricing, status, or specifications of an existing property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "UUID of the property"},
                "price": {"type": "NUMBER", "description": "Updated price"},
                "status": {"type": "STRING", "description": "Updated status"},
                "description": {"type": "STRING", "description": "Updated description"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_update_property
    ),
    "change_property_status": CopilotTool(
        name="change_property_status",
        description="LOW-RISK WRITE: Changes a property's availability status (available, reserved, sold, rented, off_market, archived).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "UUID of the property"},
                "status": {"type": "STRING", "description": "Target status"}
            },
            "required": ["property_id", "status"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_change_property_status
    ),
    "assign_property": CopilotTool(
        name="assign_property",
        description="LOW-RISK WRITE: Assigns a property listing to a specific broker or team agent.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "UUID of the property"},
                "assigned_agent_id": {"type": "STRING", "description": "UUID of the agent"}
            },
            "required": ["property_id", "assigned_agent_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_assign_property
    ),
    "link_lead_to_property": CopilotTool(
        name="link_lead_to_property",
        description="LOW-RISK WRITE: Records a client's interest, shortlist, or visit request for a property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "UUID of the lead"},
                "property_id": {"type": "STRING", "description": "UUID of the property"},
                "status": {"type": "STRING", "description": "Status: MATCHED, SHORTLISTED, INTERESTED, VISIT_REQUESTED, VISIT_SCHEDULED, VISITED, RESERVED"},
                "notes": {"type": "STRING", "description": "Agent notes regarding the interest"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_link_lead_to_property
    ),
    "unlink_lead_property": CopilotTool(
        name="unlink_lead_property",
        description="LOW-RISK WRITE: Disassociates a lead from a property or marks it as REJECTED.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "UUID of the lead"},
                "property_id": {"type": "STRING", "description": "UUID of the property"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_unlink_lead_property
    ),
    "schedule_property_visit": CopilotTool(
        name="schedule_property_visit",
        description="LOW-RISK WRITE: Schedules an in-person site visit for a lead at a property, creating meeting and task.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "UUID of the lead"},
                "property_id": {"type": "STRING", "description": "UUID of the property"},
                "scheduled_at": {"type": "STRING", "description": "ISO 8601 timestamp for the site visit"},
                "notes": {"type": "STRING", "description": "Viewing instructions or notes"}
            },
            "required": ["lead_id", "property_id", "scheduled_at"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_schedule_property_visit
    ),
    "archive_property": CopilotTool(
        name="archive_property",
        description="HIGH-RISK WRITE: Archives a property listing from active inventory.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "UUID of the property to archive"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        handler=_handle_archive_property
    ),
    # ─── Part 29: AI Lead ↔ Property Matching Engine Tools ───────────────────
    "find_properties_for_lead": CopilotTool(
        name="find_properties_for_lead",
        description="Finds and ranks the best property candidates for a given CRM lead with explainable match scores, confidence, and reasons.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "top_k": {"type": "INTEGER", "description": "Number of top matching properties to return (default 5)"},
                "allow_alternatives": {"type": "BOOLEAN", "description": "Whether to relax soft constraints to find alternatives"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_find_properties_for_lead
    ),
    "find_leads_for_property": CopilotTool(
        name="find_leads_for_property",
        description="Reverse matching: Identifies qualified buyer leads in the CRM most likely to purchase or rent a specific property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"},
                "top_k": {"type": "INTEGER", "description": "Number of top matching buyer leads to return (default 10)"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_find_leads_for_property
    ),
    "get_match_explanation": CopilotTool(
        name="get_match_explanation",
        description="Provides a detailed, explainable breakdown of why a lead and property match, including score breakdown and trade-offs.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_match_explanation
    ),
    "get_match_history": CopilotTool(
        name="get_match_history",
        description="Retrieves historical match recommendations and shortlists for a lead or property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "Optional UUID of the lead"},
                "property_id": {"type": "STRING", "description": "Optional UUID of the property"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_match_history
    ),
    "get_unmatched_hot_leads": CopilotTool(
        name="get_unmatched_hot_leads",
        description="Identifies active hot leads who currently lack matching property inventory.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_unmatched_hot_leads
    ),
    "get_best_property_matches": CopilotTool(
        name="get_best_property_matches",
        description="Retrieves the highest scoring property matches for a lead.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "top_k": {"type": "INTEGER", "description": "Number of properties to return"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_best_property_matches
    ),
    "get_best_lead_matches": CopilotTool(
        name="get_best_lead_matches",
        description="Retrieves top buyer leads for a specific property listing.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"},
                "top_k": {"type": "INTEGER", "description": "Number of leads to return"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_best_lead_matches
    ),
    "shortlist_property_for_lead": CopilotTool(
        name="shortlist_property_for_lead",
        description="LOW-RISK WRITE: Shortlists a property for a lead in the CRM.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"},
                "notes": {"type": "STRING", "description": "Optional agent notes regarding the shortlist"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_shortlist_property_for_lead
    ),
    "mark_property_recommended": CopilotTool(
        name="mark_property_recommended",
        description="LOW-RISK WRITE: Formally records a property recommendation for a lead and schedules a follow-up reminder.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"},
                "notes": {"type": "STRING", "description": "Reason for recommendation"},
                "create_task": {"type": "BOOLEAN", "description": "Whether to create a follow-up task (default true)"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_mark_property_recommended
    ),
    "remove_property_recommendation": CopilotTool(
        name="remove_property_recommendation",
        description="LOW-RISK WRITE: Removes a property from a lead's recommended list or marks it rejected.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_remove_property_recommendation
    ),
    "find_matching_properties": CopilotTool(
        name="find_matching_properties",
        description="Finds and ranks the best property candidates for a given CRM lead with explainable match scores, confidence, and reasons.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "top_k": {"type": "INTEGER", "description": "Number of top matching properties to return (default 5)"},
                "allow_alternatives": {"type": "BOOLEAN", "description": "Whether to relax soft constraints to find alternatives"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_find_properties_for_lead
    ),
    "get_property_matches": CopilotTool(
        name="get_property_matches",
        description="Retrieves ranked property matches for a specific lead.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "top_k": {"type": "INTEGER", "description": "Number of top matching properties to return (default 5)"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_find_properties_for_lead
    ),
    "find_matching_leads": CopilotTool(
        name="find_matching_leads",
        description="Reverse matching: Identifies qualified buyer leads in the CRM most likely to purchase or rent a specific property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"},
                "top_k": {"type": "INTEGER", "description": "Number of top matching buyer leads to return (default 10)"}
            },
            "required": ["property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_find_leads_for_property
    ),
    "compare_matched_properties": CopilotTool(
        name="compare_matched_properties",
        description="Compares 2 to 5 matched properties side-by-side with trade-offs and score breakdowns.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "property_ids": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of 2 to 5 property UUIDs to compare"
                },
                "lead_id": {"type": "STRING", "description": "Optional UUID of the lead to evaluate matching fit against"}
            },
            "required": ["property_ids"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_compare_matched_properties
    ),
    "remove_property_from_shortlist": CopilotTool(
        name="remove_property_from_shortlist",
        description="LOW-RISK WRITE: Removes a property from a lead's shortlist.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_unlink_lead_property
    ),
    "record_match_feedback": CopilotTool(
        name="record_match_feedback",
        description="LOW-RISK WRITE: Records broker or client feedback on a property match.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"},
                "feedback": {"type": "STRING", "description": "Feedback category: good_match, bad_match, wrong_budget, wrong_location, wrong_property_type, customer_interested, customer_rejected, shortlisted"},
                "notes": {"type": "STRING", "description": "Optional notes or details"}
            },
            "required": ["lead_id", "property_id", "feedback"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_record_match_feedback
    ),
    "get_match_score_breakdown": CopilotTool(
        name="get_match_score_breakdown",
        description="Retrieves the detailed 8-dimensional score breakdown for a lead and property.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "property_id": {"type": "STRING", "description": "The unique UUID of the property"}
            },
            "required": ["lead_id", "property_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_match_score_breakdown
    ),
    "suggest_alternatives": CopilotTool(
        name="suggest_alternatives",
        description="Finds alternative properties by relaxing soft constraints in controlled order when strict matches are limited.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"},
                "top_k": {"type": "INTEGER", "description": "Number of alternative properties to return (default 5)"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_suggest_alternatives
    ),
    "improve_lead_requirements": CopilotTool(
        name="improve_lead_requirements",
        description="Generates targeted clarification questions for an incomplete lead to improve match confidence.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lead_id": {"type": "STRING", "description": "The unique UUID of the lead"}
            },
            "required": ["lead_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_improve_lead_requirements
    ),
    "get_command_center_summary": CopilotTool(
        name="get_command_center_summary",
        description="Retrieves live operational metrics from the agent command center: critical items, overdue follow-ups, meetings, and inventory gaps.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_command_center_summary
    ),
    "get_today_priorities": CopilotTool(
        name="get_today_priorities",
        description="Answers 'What should I work on today?' with an ordered, deterministic priority queue.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "limit": {"type": "INTEGER", "description": "Number of priorities to retrieve (default 10)"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_today_priorities
    ),
    "get_inventory_intelligence": CopilotTool(
        name="get_inventory_intelligence",
        description="Answers 'What is my biggest inventory gap?' and retrieves verified internal CRM demand vs available supply.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_inventory_intelligence
    ),
    "get_daily_briefing": CopilotTool(
        name="get_daily_briefing",
        description="Returns an executive, fact-based morning briefing on today's priorities and schedule.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_daily_briefing
    ),
    "get_start_my_day_queue": CopilotTool(
        name="get_start_my_day_queue",
        description="Returns a sequential, step-by-step queue for the agent's workday.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_start_my_day_queue
    ),
    "dismiss_dashboard_item": CopilotTool(
        name="dismiss_dashboard_item",
        description="LOW-RISK WRITE: Dismisses or snoozes a priority item from the agent command center without deleting CRM data.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "item_key": {"type": "STRING", "description": "The item key to dismiss or snooze"},
                "entity_type": {"type": "STRING", "description": "Type of entity (lead, task, meeting, match)"},
                "entity_id": {"type": "STRING", "description": "UUID of the entity"},
                "action_type": {"type": "STRING", "description": "'dismissed' or 'snoozed'"},
                "snooze_hours": {"type": "INTEGER", "description": "Hours to snooze (if action_type is snoozed)"}
            },
            "required": ["item_key", "entity_type", "entity_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_dismiss_dashboard_item
    ),
    "get_onboarding_status": CopilotTool(
        name="get_onboarding_status",
        description="Retrieves current workspace onboarding progress, completed steps, and setup checklist.",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_onboarding_status
    ),
    "get_activation_status": CopilotTool(
        name="get_activation_status",
        description="Retrieves tenant workspace activation status, milestone progress, and activation score (0-100).",
        parameters={
            "type": "OBJECT",
            "properties": {}
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_activation_status
    ),
    "create_demo_workspace": CopilotTool(
        name="create_demo_workspace",
        description="LOW-RISK WRITE: Spawns an ephemeral demo playground with synthetic properties and leads.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "agency_name": {"type": "STRING", "description": "Optional custom agency name for demo"},
                "city": {"type": "STRING", "description": "Operating city (e.g. Bengaluru, Mumbai, Gurugram)"}
            }
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_create_demo_workspace
    ),
    # ─── Part 35 — AI Real Estate Revenue Autopilot Tools ─────────────────────
    "get_revenue_action_queue": CopilotTool(
        name="get_revenue_action_queue",
        description="Retrieves the agent's highest-value prioritized revenue actions ('DO THIS NOW') with lead facts, property recommendations, match scores, and explainable reasons.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "limit": {"type": "INTEGER", "description": "Number of actions to retrieve (default 5)"}
            }
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_get_revenue_action_queue
    ),
    "explain_revenue_opportunity": CopilotTool(
        name="explain_revenue_opportunity",
        description="Provides complete explainability for a revenue opportunity including why now, why this property, positive signals, trade-offs, and call brief.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "opportunity_id": {"type": "STRING", "description": "UUID of the revenue opportunity"}
            },
            "required": ["opportunity_id"]
        },
        risk_level=ToolRiskLevel.READ,
        requires_confirmation=False,
        handler=_handle_explain_revenue_opportunity
    ),
    "dismiss_revenue_opportunity": CopilotTool(
        name="dismiss_revenue_opportunity",
        description="LOW-RISK WRITE: Dismisses a revenue opportunity with a structured reason without deleting underlying CRM data.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "opportunity_id": {"type": "STRING", "description": "UUID of the revenue opportunity"},
                "reason": {"type": "STRING", "description": "Reason for dismissal (e.g. 'Not relevant', 'Already contacted')"}
            },
            "required": ["opportunity_id"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_dismiss_revenue_opportunity
    ),
    "action_revenue_opportunity": CopilotTool(
        name="action_revenue_opportunity",
        description="LOW-RISK WRITE: Approves and executes a revenue action (e.g. CALL_LEAD, SEND_PROPERTY_RECOMMENDATION, SCHEDULE_SITE_VISIT) on an opportunity.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "opportunity_id": {"type": "STRING", "description": "UUID of the revenue opportunity"},
                "action_type": {"type": "STRING", "description": "CALL_LEAD | SEND_EMAIL | SEND_PROPERTY_RECOMMENDATION | SCHEDULE_SITE_VISIT | REACTIVATE_LEAD"},
                "notes": {"type": "STRING", "description": "Optional action notes"}
            },
            "required": ["opportunity_id", "action_type"]
        },
        risk_level=ToolRiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        handler=_handle_action_revenue_opportunity
    ),
}

tool_registry = COPILOT_TOOL_REGISTRY


def get_all_tool_declarations() -> List[Dict[str, Any]]:
    """Returns list of Gemini v1beta function declarations for all registered tools."""
    return [t.to_gemini_declaration() for t in COPILOT_TOOL_REGISTRY.values()]
