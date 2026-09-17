"""
PART 31 — Centralized Tenant Activation Service
=================================================
Evaluates tenant workspace activation milestones deterministically:
1. Organization Created (20 pts)
2. First Property Listed (20 pts)
3. First Lead Ingested (20 pts)
4. First AI Lead <-> Property Match Generated (20 pts)
5. First Follow-Up / Task Scheduled (20 pts)

Authoritative activation requires >= 80 points including org, property, and lead.
Existing tenants with prior data are automatically recognized as activated.
All evaluations are strictly tenant-isolated.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.property_models import PropertyListing
from app.models.lead import Lead
from app.models.recommendation_models import Recommendation
from app.models.crm_models import Task
from app.models.follow_up import FollowUp
from app.models.onboarding_models import TenantActivation
from app.modules.onboarding.dto import (
    TenantActivationResponseDTO,
    MilestoneProgressDTO,
)
from app.services.audit_service import AuditLogService

logger = logging.getLogger("beetlelabs.onboarding.activation")

MILESTONES = [
    {
        "code": "ORGANIZATION_CREATED",
        "label": "Workspace Profile Setup",
        "weight": 20,
        "description": "Configured agency business profile, timezone, and operating parameters."
    },
    {
        "code": "FIRST_PROPERTY_CREATED",
        "label": "First Property Added",
        "weight": 20,
        "description": "At least one active or available property listing in inventory."
    },
    {
        "code": "FIRST_LEAD_CREATED",
        "label": "First Lead Added",
        "weight": 20,
        "description": "At least one client lead captured or imported into CRM."
    },
    {
        "code": "FIRST_MATCH_GENERATED",
        "label": "Lead ↔ Property AI Match",
        "weight": 20,
        "description": "AI matching engine generated property recommendations for a lead."
    },
    {
        "code": "FIRST_FOLLOWUP_CREATED",
        "label": "First Follow-Up / Task Scheduled",
        "weight": 20,
        "description": "At least one follow-up cadence or CRM task created."
    },
]


class TenantActivationService:
    """
    Evaluates and persists tenant activation state against real database entities.
    Idempotent, robust against concurrent updates, and tenant-scoped.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_calculate_activation(
        self,
        broker: Broker,
        organization_id: Optional[uuid.UUID] = None,
        force_refresh: bool = False
    ) -> TenantActivationResponseDTO:
        """
        Retrieves or evaluates live tenant activation score and milestone checklist.
        Synchronizes live entity counts to ensure existing users appear activated immediately.
        """
        org_id = organization_id or await self._resolve_org_id(broker)
        
        # Check existing activation record
        stmt = select(TenantActivation).where(TenantActivation.organization_id == org_id)
        result = await self.db.execute(stmt)
        record = result.scalars().first()

        # If already activated and no forced recalculation, return cached with breakdown
        if record and record.is_activated and not force_refresh:
            return self._build_dto(record, broker.is_demo)

        # Evaluate live counts across isolated CRM entities
        milestone_status, score, counts, dates = await self._evaluate_live_milestones(broker, org_id)

        is_activated = score >= 80 and (
            "ORGANIZATION_CREATED" in milestone_status and
            "FIRST_PROPERTY_CREATED" in milestone_status and
            "FIRST_LEAD_CREATED" in milestone_status
        )

        now = datetime.now(timezone.utc)
        if not record:
            record = TenantActivation(
                organization_id=org_id,
                is_activated=is_activated,
                activation_score=score,
                completed_milestones=list(milestone_status.keys()),
                activated_at=now if is_activated else None,
                first_property_at=dates.get("property"),
                first_lead_at=dates.get("lead"),
                first_match_at=dates.get("match"),
                first_followup_at=dates.get("followup"),
            )
            self.db.add(record)
        else:
            prev_activated = record.is_activated
            record.activation_score = score
            record.completed_milestones = list(milestone_status.keys())
            if dates.get("property") and not record.first_property_at:
                record.first_property_at = dates.get("property")
            if dates.get("lead") and not record.first_lead_at:
                record.first_lead_at = dates.get("lead")
            if dates.get("match") and not record.first_match_at:
                record.first_match_at = dates.get("match")
            if dates.get("followup") and not record.first_followup_at:
                record.first_followup_at = dates.get("followup")

            if is_activated and not prev_activated:
                record.is_activated = True
                record.activated_at = now
                # Audit log activation achievement
                await AuditLogService.record(
                    db=self.db,
                    action="tenant.activated",
                    resource_type="organization",
                    actor_id=broker.id,
                    organization_id=org_id,
                    resource_id=str(org_id),
                    changes={"activation_score": score, "milestones": list(milestone_status.keys())}
                )

        await self.db.flush()
        return self._build_dto(record, broker.is_demo)

    async def _evaluate_live_milestones(
        self,
        broker: Broker,
        org_id: uuid.UUID
    ) -> Tuple[Dict[str, datetime], int, Dict[str, int], Dict[str, Optional[datetime]]]:
        """Queries live tables to determine milestone completion."""
        milestone_status: Dict[str, datetime] = {}
        dates: Dict[str, Optional[datetime]] = {}
        counts: Dict[str, int] = {}
        now = datetime.now(timezone.utc)

        # 1. Organization Check
        org = await self.db.get(Organization, org_id)
        if org:
            milestone_status["ORGANIZATION_CREATED"] = org.created_at or now
            dates["org"] = org.created_at or now

        # 2. Properties count for this broker / org
        # Find brokers in this organization
        broker_ids_stmt = select(OrganizationMember.broker_id).where(OrganizationMember.organization_id == org_id)
        broker_ids_res = await self.db.execute(broker_ids_stmt)
        org_broker_ids = set(broker_ids_res.scalars().all())
        org_broker_ids.add(broker.id)

        prop_stmt = (
            select(func.count(PropertyListing.id), func.min(PropertyListing.created_at))
            .where(
                and_(
                    PropertyListing.broker_id.in_(org_broker_ids),
                    PropertyListing.deleted_at.is_(None)
                )
            )
        )
        prop_res = await self.db.execute(prop_stmt)
        prop_count, first_prop_date = prop_res.first() or (0, None)
        counts["properties"] = prop_count or 0
        if (prop_count or 0) > 0:
            milestone_status["FIRST_PROPERTY_CREATED"] = first_prop_date or now
            dates["property"] = first_prop_date or now

        # 3. Leads count for this broker / org
        lead_stmt = (
            select(func.count(Lead.id), func.min(Lead.created_at))
            .where(
                and_(
                    Lead.broker_id.in_(org_broker_ids),
                    Lead.deleted_at.is_(None)
                )
            )
        )
        lead_res = await self.db.execute(lead_stmt)
        lead_count, first_lead_date = lead_res.first() or (0, None)
        counts["leads"] = lead_count or 0
        if (lead_count or 0) > 0:
            milestone_status["FIRST_LEAD_CREATED"] = first_lead_date or now
            dates["lead"] = first_lead_date or now

        # 4. Recommendation / Match count (Part 29)
        org_str_ids = [str(org_id)] + [str(b) for b in org_broker_ids]
        rec_stmt = (
            select(func.count(Recommendation.id), func.min(Recommendation.created_at))
            .where(
                or_(
                    Recommendation.organization_id.in_(org_str_ids),
                    Recommendation.broker_id.in_(org_str_ids)
                )
            )
        )
        rec_res = await self.db.execute(rec_stmt)
        rec_count, first_rec_date = rec_res.first() or (0, None)
        counts["matches"] = rec_count or 0
        if (rec_count or 0) > 0:
            milestone_status["FIRST_MATCH_GENERATED"] = first_rec_date or now
            dates["match"] = first_rec_date or now

        # 5. Tasks or Follow-ups count (Part 27 & CRM)
        task_stmt = (
            select(func.count(Task.id), func.min(Task.created_at))
            .where(
                or_(
                    Task.organization_id.in_(org_str_ids),
                    Task.broker_id.in_(org_broker_ids)
                )
            )
        )
        task_res = await self.db.execute(task_stmt)
        task_count, first_task_date = task_res.first() or (0, None)

        # Also check follow-up table
        followup_stmt = (
            select(func.count(FollowUp.id), func.min(FollowUp.created_at))
            .join(Lead, Lead.id == FollowUp.lead_id)
            .where(Lead.broker_id.in_(org_broker_ids))
        )
        fu_res = await self.db.execute(followup_stmt)
        fu_count, first_fu_date = fu_res.first() or (0, None)

        total_followup_tasks = (task_count or 0) + (fu_count or 0)
        counts["followups_and_tasks"] = total_followup_tasks
        if total_followup_tasks > 0:
            earliest_fu = min(
                [d for d in [first_task_date, first_fu_date] if d is not None],
                default=now
            )
            milestone_status["FIRST_FOLLOWUP_CREATED"] = earliest_fu
            dates["followup"] = earliest_fu

        # Score calculation
        score = sum(
            m["weight"] for m in MILESTONES if m["code"] in milestone_status
        )

        return milestone_status, score, counts, dates

    async def _resolve_org_id(self, broker: Broker) -> uuid.UUID:
        """Determines the primary organization UUID for the broker."""
        b_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        stmt = select(OrganizationMember.organization_id).where(OrganizationMember.broker_id == b_id)
        res = await self.db.execute(stmt)
        org_id = res.scalars().first()
        if org_id:
            return org_id if isinstance(org_id, uuid.UUID) else uuid.UUID(str(org_id))

        # Check if organization exists with ID == broker.id (legacy solo tenant)
        org = await self.db.get(Organization, b_id)
        if org:
            return org.id

        # Auto-create fallback solo organization if not exists
        new_org = Organization(
            id=b_id,
            name=broker.agency_name or f"{broker.name}'s Agency",
            slug=f"org-{str(b_id)[:8]}",
            plan="pro",
            country_code="IN",
            currency_code="INR",
            default_timezone="Asia/Kolkata",
            business_type="agency",
            is_demo=broker.is_demo
        )
        self.db.add(new_org)
        member = OrganizationMember(
            organization_id=b_id,
            broker_id=b_id,
            role="owner"
        )
        self.db.add(member)
        await self.db.flush()
        return b_id

    def _build_dto(self, record: TenantActivation, is_demo: bool = False) -> TenantActivationResponseDTO:
        completed = record.completed_milestones or []
        breakdown: List[MilestoneProgressDTO] = []
        missing: List[str] = []

        for m in MILESTONES:
            achieved = m["code"] in completed
            if not achieved:
                missing.append(m["label"])
            breakdown.append(
                MilestoneProgressDTO(
                    code=m["code"],
                    label=m["label"],
                    achieved=achieved,
                    achieved_at=record.activated_at.isoformat() if (achieved and record.activated_at) else None,
                    weight=m["weight"],
                    description=m["description"]
                )
            )

        return TenantActivationResponseDTO(
            organization_id=str(record.organization_id),
            is_activated=record.is_activated,
            activation_score=record.activation_score,
            completed_milestones=completed,
            missing_requirements=missing,
            milestone_breakdown=breakdown,
            activated_at=record.activated_at.isoformat() if record.activated_at else None,
            time_to_activate_seconds=record.time_to_activate_seconds,
            is_demo=is_demo
        )
