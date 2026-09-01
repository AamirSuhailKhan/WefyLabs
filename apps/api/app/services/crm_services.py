import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead
from app.models.organization import Organization
from app.models.property_models import PropertyListing
from app.models.crm_models import Task, Meeting, Contact, Activity
from app.infrastructure.repositories.tenant_repository import TenantRepository
from app.infrastructure.events.event_bus import event_bus, DomainEvent

class LeadService:
    """
    Service Interface for Lead lifecycle operations.
    Exposes clean interfaces for AI OS modules, emitting Domain Events.
    """
    @classmethod
    async def create_lead(
        cls,
        db: AsyncSession,
        name: str,
        phone: str,
        email: Optional[str] = None,
        organization_id: Optional[str] = "org-default",
        workspace_id: Optional[str] = "ws-default",
        broker_id: Optional[uuid.UUID] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        preferred_locations: Optional[List[str]] = None
    ) -> Lead:
        repo = TenantRepository(Lead, db)
        lead = Lead(
            name=name,
            phone=phone,
            email=email,
            organization_id=organization_id,
            workspace_id=workspace_id,
            broker_id=broker_id,
            budget_min=budget_min,
            budget_max=budget_max,
            preferred_locations=preferred_locations or []
        )
        saved = await repo.create(lead)
        await db.commit()

        # Emit LeadCreated Event
        await event_bus.publish(DomainEvent(
            event_type="LeadCreated",
            organization_id=organization_id or "global",
            workspace_id=workspace_id or "default",
            payload={"lead_id": str(saved.id), "name": saved.name, "phone": saved.phone}
        ))
        return saved

    @classmethod
    async def list_leads(
        cls,
        db: AsyncSession,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Lead]:
        repo = TenantRepository(Lead, db)
        return await repo.list_all(organization_id=organization_id, limit=limit, offset=offset)


class TaskService:
    """Service Interface for Task management."""
    @classmethod
    async def create_task(
        cls,
        db: AsyncSession,
        title: str,
        due_in_hours: int = 24,
        organization_id: Optional[str] = "org-default",
        workspace_id: Optional[str] = "ws-default",
        lead_id: Optional[uuid.UUID] = None,
        assigned_broker_id: Optional[uuid.UUID] = None
    ) -> Task:
        repo = TenantRepository(Task, db)
        task = Task(
            title=title,
            organization_id=organization_id,
            workspace_id=workspace_id,
            lead_id=lead_id,
            assigned_broker_id=assigned_broker_id
        )
        saved = await repo.create(task)
        await db.commit()

        await event_bus.publish(DomainEvent(
            event_type="TaskCreated",
            organization_id=organization_id or "global",
            workspace_id=workspace_id or "default",
            payload={"task_id": str(saved.id), "title": saved.title}
        ))
        return saved


class PropertyService:
    """Service Interface for Property Inventory Management."""
    @classmethod
    async def list_properties(
        cls,
        db: AsyncSession,
        organization_id: Optional[str] = None,
        limit: int = 50
    ) -> List[PropertyListing]:
        repo = TenantRepository(PropertyListing, db)
        return await repo.list_all(organization_id=organization_id, limit=limit)


class OrganizationService:
    """Service Interface for Enterprise Organization & Tenant Profile Management."""
    @classmethod
    async def get_organization(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID
    ) -> Optional[Organization]:
        stmt = select(Organization).where(Organization.id == org_id)
        res = await db.execute(stmt)
        return res.scalars().first()
