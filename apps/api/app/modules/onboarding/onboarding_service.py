"""
PART 31 — Progressive Onboarding State Machine Service
======================================================
Manages resilient, resumable, skippable, and idempotent workspace onboarding.
Generates live-synchronized checklists and coordinates business profile updates.
Enforces multi-tenant isolation and records immutable audit logs for compliance.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.onboarding_models import OnboardingState
from app.modules.onboarding.dto import (
    BusinessProfileSetupDTO,
    OnboardingStepUpdateDTO,
    ChecklistItemDTO,
    OnboardingStatusResponseDTO,
)
from app.modules.onboarding.activation_service import TenantActivationService
from app.services.audit_service import AuditLogService

logger = logging.getLogger("beetlelabs.onboarding.service")

STEPS_ORDER = [
    "ORGANIZATION_SETUP",
    "DATA_SOURCE",
    "PROPERTY_SETUP",
    "LEAD_SETUP",
    "MATCH_SHOWCASE",
    "FOLLOWUP_SETUP",
    "TEAM_INVITE",
    "CALENDAR_CONNECT",
    "COPILOT_INTRO",
    "ACTIVATED",
]

CORE_CHECKLIST_DEFINITIONS = [
    {
        "id": "ORGANIZATION_SETUP",
        "title": "Set Up Workspace Profile",
        "description": "Configure business name, operating city, timezone, and currency.",
        "action_route": "/onboarding?step=ORGANIZATION_SETUP",
        "action_label": "Configure Profile",
        "order": 1,
    },
    {
        "id": "PROPERTY_SETUP",
        "title": "Add Your First Property",
        "description": "Add an inventory unit manually or import sample listings.",
        "action_route": "/properties/new",
        "action_label": "Add Property",
        "order": 2,
    },
    {
        "id": "LEAD_SETUP",
        "title": "Ingest Your First Lead",
        "description": "Capture a buyer inquiry with budget and preferred configuration.",
        "action_route": "/leads/new",
        "action_label": "Add Lead",
        "order": 3,
    },
    {
        "id": "MATCH_SHOWCASE",
        "title": "Generate AI Property Matches",
        "description": "Match buyer intent with available properties using explainable AI.",
        "action_route": "/matches",
        "action_label": "View Matches",
        "order": 4,
    },
    {
        "id": "FOLLOWUP_SETUP",
        "title": "Schedule First Follow-Up / Task",
        "description": "Create a client cadence or site visit appointment.",
        "action_route": "/tasks",
        "action_label": "Schedule Task",
        "order": 5,
    },
    {
        "id": "TEAM_INVITE",
        "title": "Invite Team Member",
        "description": "Add agents or managers with secure role-based permissions.",
        "action_route": "/settings/team",
        "action_label": "Invite Team",
        "order": 6,
    },
    {
        "id": "CALENDAR_CONNECT",
        "title": "Connect Google Calendar (Optional)",
        "description": "Sync site visits and customer calls automatically.",
        "action_route": "/settings/integrations",
        "action_label": "Connect Calendar",
        "order": 7,
    },
    {
        "id": "COPILOT_INTRO",
        "title": "Explore AI Copilot",
        "description": "Ask Copilot to summarize inventory gaps or hot leads.",
        "action_route": "/copilot",
        "action_label": "Open Copilot",
        "order": 8,
    },
]


class OnboardingService:
    """
    Manages tenant onboarding lifecycle, step completion, checklist sync, and resume logic.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.activation_service = TenantActivationService(db)

    async def get_or_create_state(
        self,
        broker: Broker,
        organization_id: Optional[uuid.UUID] = None
    ) -> OnboardingState:
        """
        Retrieves or initializes the onboarding state for the tenant.
        Idempotent and resilient across browser sessions and re-logins.
        """
        org_id = organization_id or await self.activation_service._resolve_org_id(broker)

        stmt = select(OnboardingState).where(OnboardingState.organization_id == org_id)
        result = await self.db.execute(stmt)
        state = result.scalars().first()

        if not state:
            state = OnboardingState(
                organization_id=org_id,
                broker_id=broker.id,
                current_step=STEPS_ORDER[0],
                completed_steps=[],
                skipped_steps=[],
                is_completed=False,
                step_data={}
            )
            self.db.add(state)
            await self.db.flush()

        return state

    async def get_status(
        self,
        broker: Broker,
        organization_id: Optional[uuid.UUID] = None
    ) -> OnboardingStatusResponseDTO:
        """
        Calculates comprehensive status, synchronizing with live CRM entity state.
        Ensures existing users with properties/leads automatically reflect completed steps.
        """
        org_id = organization_id or await self.activation_service._resolve_org_id(broker)
        state = await self.get_or_create_state(broker, org_id)
        activation_dto = await self.activation_service.get_or_calculate_activation(broker, org_id)

        # Synchronize live milestones into completed_steps
        completed = set(state.completed_steps or [])
        skipped = set(state.skipped_steps or [])

        # Live entity sync: if milestone is achieved, mark corresponding onboarding step complete
        for milestone in activation_dto.completed_milestones:
            if milestone == "ORGANIZATION_CREATED":
                completed.add("ORGANIZATION_SETUP")
            elif milestone == "FIRST_PROPERTY_CREATED":
                completed.add("PROPERTY_SETUP")
            elif milestone == "FIRST_LEAD_CREATED":
                completed.add("LEAD_SETUP")
            elif milestone == "FIRST_MATCH_GENERATED":
                completed.add("MATCH_SHOWCASE")
            elif milestone == "FIRST_FOLLOWUP_CREATED":
                completed.add("FOLLOWUP_SETUP")

        # Persist updated completed_steps if changed
        if set(state.completed_steps or []) != completed:
            state.completed_steps = sorted(list(completed))
            await self.db.flush()

        # Build dynamic checklist
        checklist: List[ChecklistItemDTO] = []
        for defn in CORE_CHECKLIST_DEFINITIONS:
            step_id = defn["id"]
            is_done = step_id in completed
            is_skip = step_id in skipped and not is_done
            checklist.append(
                ChecklistItemDTO(
                    id=step_id,
                    title=defn["title"],
                    description=defn["description"],
                    is_completed=is_done,
                    is_skipped=is_skip,
                    action_route=defn["action_route"],
                    action_label=defn["action_label"],
                    order=defn["order"],
                )
            )

        # Calculate progress percentage against core 8 checklist items
        core_steps = [d["id"] for d in CORE_CHECKLIST_DEFINITIONS]
        done_core = [s for s in core_steps if s in completed or s in skipped]
        progress_pct = min(100, int((len(done_core) / len(core_steps)) * 100))

        # Check if fully completed
        is_completed = state.is_completed or activation_dto.is_activated or progress_pct >= 80
        if is_completed and not state.is_completed:
            state.is_completed = True
            state.completed_at = datetime.now(timezone.utc)
            if broker.onboarding_status != "ONBOARDED":
                broker.onboarding_status = "ONBOARDED"
            await self.db.flush()

        return OnboardingStatusResponseDTO(
            organization_id=str(org_id),
            broker_id=str(broker.id),
            current_step=state.current_step,
            completed_steps=state.completed_steps or [],
            skipped_steps=state.skipped_steps or [],
            is_completed=state.is_completed,
            progress_percentage=progress_pct,
            completed_at=state.completed_at.isoformat() if state.completed_at else None,
            checklist=checklist,
            is_activated=activation_dto.is_activated,
            activation_score=activation_dto.activation_score,
            is_demo=broker.is_demo,
        )

    async def update_business_profile(
        self,
        broker: Broker,
        dto: BusinessProfileSetupDTO,
        organization_id: Optional[uuid.UUID] = None
    ) -> OnboardingStatusResponseDTO:
        """
        Saves agency branding and operational defaults to Organization.
        Marks ORGANIZATION_SETUP step as completed.
        """
        org_id = organization_id or await self.activation_service._resolve_org_id(broker)
        org = await self.db.get(Organization, org_id)
        if not org:
            org = Organization(
                id=org_id,
                name=dto.agency_name,
                slug=f"org-{str(org_id)[:8]}",
                plan="pro",
                is_demo=broker.is_demo
            )
            self.db.add(org)

        # Apply profile configuration
        org.name = dto.agency_name
        org.business_type = dto.business_type
        org.country_code = dto.country_code
        org.currency_code = dto.currency_code
        org.reporting_currency_code = dto.currency_code
        org.default_timezone = dto.timezone
        org.team_size = dto.team_size
        if not org.settings:
            org.settings = {}
        org.settings.update({
            "city": dto.city,
            "primary_business_model": dto.primary_business_model,
            "website": dto.website
        })

        # Update broker agency name and city
        broker.agency_name = dto.agency_name
        broker.city = dto.city

        # Mark step as complete
        await self.update_step(
            broker=broker,
            step_dto=OnboardingStepUpdateDTO(
                step="ORGANIZATION_SETUP",
                action="complete",
                payload=dto.model_dump()
            ),
            organization_id=org_id
        )

        # Recalculate activation
        await self.activation_service.get_or_calculate_activation(broker, org_id, force_refresh=True)

        await AuditLogService.record(
            db=self.db,
            action="organization.business_profile_updated",
            resource_type="organization",
            actor_id=broker.id,
            organization_id=org_id,
            resource_id=str(org_id),
            changes=dto.model_dump()
        )

        return await self.get_status(broker, org_id)

    async def update_step(
        self,
        broker: Broker,
        step_dto: OnboardingStepUpdateDTO,
        organization_id: Optional[uuid.UUID] = None
    ) -> OnboardingStatusResponseDTO:
        """
        Updates an onboarding step (complete or skip).
        Advances current_step pointer and saves auxiliary payload.
        """
        org_id = organization_id or await self.activation_service._resolve_org_id(broker)
        state = await self.get_or_create_state(broker, org_id)

        step = step_dto.step
        completed = set(state.completed_steps or [])
        skipped = set(state.skipped_steps or [])
        step_data = dict(state.step_data or {})

        if step_dto.action == "complete":
            completed.add(step)
            skipped.discard(step)
            if step_dto.payload:
                step_data[step] = step_dto.payload
        elif step_dto.action == "skip":
            if step not in completed:
                skipped.add(step)

        state.completed_steps = sorted(list(completed))
        state.skipped_steps = sorted(list(skipped))
        state.step_data = step_data

        # Advance current step to next incomplete step
        try:
            current_idx = STEPS_ORDER.index(step)
            next_idx = current_idx + 1
            if next_idx < len(STEPS_ORDER):
                state.current_step = STEPS_ORDER[next_idx]
            else:
                state.current_step = "ACTIVATED"
        except ValueError:
            state.current_step = STEPS_ORDER[0]

        # Update broker onboarding status if in progress
        if broker.onboarding_status == "AUTHENTICATED_NOT_ONBOARDED":
            broker.onboarding_status = "ONBOARDING_IN_PROGRESS"

        await self.db.flush()

        await AuditLogService.record(
            db=self.db,
            action=f"onboarding.step_{step_dto.action}",
            resource_type="onboarding_state",
            actor_id=broker.id,
            organization_id=org_id,
            resource_id=str(state.id),
            changes={"step": step, "action": step_dto.action}
        )

        return await self.get_status(broker, org_id)
