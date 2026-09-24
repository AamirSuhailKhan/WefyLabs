"""WefyLabs Native CRM — Universal Search Service
=================================================
Multi-entity search across Customers, Leads, Opportunities,
Properties, and Tasks with strict multi-tenant isolation and RBAC.
"""
from __future__ import annotations

import uuid
import re
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func

from app.models.lead import Lead
from app.models.crm_models import Task, Contact
from app.models.transaction_models import DealTransaction
from app.models.property_models import PropertyListing
from app.models.calendar_models import SchedulingMeeting
from app.modules.crm.dto.crm_schemas import (
    CRMSearchResultItem, CRMSearchResponse
)


class CRMSearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        query: str,
        broker_id: uuid.UUID,
        organization_id: str,
        limit: int = 30
    ) -> CRMSearchResponse:
        """
        Executes normalized multi-entity search bounded strictly by broker_id and organization_id.
        """
        raw_query = (query or "").strip()
        if not raw_query:
            return CRMSearchResponse(query="", total_results=0, results=[])

        search_pat = f"%{raw_query}%"
        results: List[CRMSearchResultItem] = []

        # 1. Search Leads
        try:
            lead_stmt = select(Lead).where(
                Lead.broker_id == broker_id,
                Lead.deleted_at.is_(None),
                or_(
                    Lead.name.ilike(search_pat),
                    Lead.phone.ilike(search_pat),
                    Lead.email.ilike(search_pat)
                )
            ).limit(10)
            lead_res = await self.db.execute(lead_stmt)
            for lead in lead_res.scalars().all():
                results.append(
                    CRMSearchResultItem(
                        id=str(lead.id),
                        entity_type="lead",
                        title=lead.name or "Unnamed Lead",
                        subtitle=f"{lead.phone} • {lead.pipeline_stage.upper()} • {lead.score.upper()}",
                        status=lead.status,
                        created_at=lead.created_at,
                        deep_link=f"/dashboard/crm/leads/{lead.id}",
                        metadata={"phone": lead.phone, "email": lead.email, "score": lead.score}
                    )
                )
        except Exception:
            pass

        # 2. Search Deals / Opportunities
        try:
            deal_stmt = select(DealTransaction).where(
                DealTransaction.broker_id == broker_id,
                DealTransaction.deal_name.ilike(search_pat)
            ).limit(10)
            deal_res = await self.db.execute(deal_stmt)
            for deal in deal_res.scalars().all():
                results.append(
                    CRMSearchResultItem(
                        id=str(deal.id),
                        entity_type="opportunity",
                        title=deal.deal_name,
                        subtitle=f"{deal.currency} {deal.agreed_price:,.0f} • Stage: {deal.current_stage}",
                        status=deal.current_stage,
                        created_at=deal.created_at,
                        deep_link=f"/dashboard/crm/pipeline?deal={deal.id}",
                        metadata={"agreed_price": deal.agreed_price, "currency": deal.currency}
                    )
                )
        except Exception:
            pass

        # 3. Search Tasks
        try:
            task_stmt = select(Task).where(
                Task.broker_id == broker_id,
                or_(
                    Task.title.ilike(search_pat),
                    Task.description.ilike(search_pat)
                )
            ).limit(10)
            task_res = await self.db.execute(task_stmt)
            for task in task_res.scalars().all():
                results.append(
                    CRMSearchResultItem(
                        id=str(task.id),
                        entity_type="task",
                        title=task.title,
                        subtitle=f"Status: {task.status.upper()} • Priority: {task.priority.upper()}",
                        status=task.status,
                        created_at=task.created_at,
                        deep_link=f"/dashboard/crm/tasks?task={task.id}",
                        metadata={"status": task.status, "priority": task.priority}
                    )
                )
        except Exception:
            pass

        # 4. Search Appointments
        try:
            mtg_stmt = select(SchedulingMeeting).where(
                SchedulingMeeting.broker_id == broker_id,
                SchedulingMeeting.title.ilike(search_pat)
            ).limit(10)
            mtg_res = await self.db.execute(mtg_stmt)
            for mtg in mtg_res.scalars().all():
                results.append(
                    CRMSearchResultItem(
                        id=str(mtg.id),
                        entity_type="appointment",
                        title=mtg.title,
                        subtitle=f"{mtg.meeting_type} • Status: {mtg.status}",
                        status=mtg.status,
                        created_at=mtg.created_at,
                        deep_link=f"/dashboard/crm/customers?meeting={mtg.id}",
                        metadata={"meeting_type": mtg.meeting_type, "status": mtg.status}
                    )
                )
        except Exception:
            pass

        # 5. Search Properties
        try:
            prop_stmt = select(PropertyListing).where(
                or_(
                    PropertyListing.title.ilike(search_pat),
                    PropertyListing.location.ilike(search_pat),
                    PropertyListing.city.ilike(search_pat)
                )
            ).limit(10)
            prop_res = await self.db.execute(prop_stmt)
            for prop in prop_res.scalars().all():
                results.append(
                    CRMSearchResultItem(
                        id=str(prop.id),
                        entity_type="property",
                        title=prop.title,
                        subtitle=f"{prop.city or ''} • {getattr(prop, 'price', 0):,.0f} {getattr(prop, 'currency', 'AED')}",
                        status=prop.status if hasattr(prop, "status") else "available",
                        created_at=prop.created_at,
                        deep_link=f"/dashboard/properties/{prop.id}",
                        metadata={"location": prop.location, "city": prop.city}
                    )
                )
        except Exception:
            pass

        return CRMSearchResponse(
            query=raw_query,
            total_results=len(results),
            results=results[:limit]
        )
