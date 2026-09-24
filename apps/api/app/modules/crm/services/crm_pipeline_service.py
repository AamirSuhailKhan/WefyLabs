"""WefyLabs Native CRM — Sales Pipeline Kanban Service
======================================================
Provides authoritative pipeline stage aggregation, deal valuation,
stagnation detection, and Kanban board organization for real-estate sales.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.transaction_models import DealTransaction
from app.models.revenue_autopilot_models import RevenueOpportunity
from app.modules.crm.dto.crm_schemas import (
    PipelineKanbanResponse, PipelineColumnDTO, PipelineCardDTO
)

STANDARD_PIPELINE_STAGES = [
    {"key": "new", "name": "New Leads", "color": "#64748B", "order": 0},
    {"key": "contacted", "name": "Contacted", "color": "#3B82F6", "order": 1},
    {"key": "qualified", "name": "Qualified", "color": "#8B5CF6", "order": 2},
    {"key": "matched", "name": "Property Matched", "color": "#EC4899", "order": 3},
    {"key": "appointment", "name": "Appointment Booked", "color": "#F59E0B", "order": 4},
    {"key": "site_visit", "name": "Site Visit Completed", "color": "#10B981", "order": 5},
    {"key": "opportunity", "name": "Opportunity / Deal", "color": "#06B6D4", "order": 6},
    {"key": "negotiation", "name": "Negotiation", "color": "#F97316", "order": 7},
    {"key": "booking", "name": "Booking / Under Contract", "color": "#14B8A6", "order": 8},
    {"key": "won", "name": "Closed Won", "color": "#22C55E", "order": 9},
    {"key": "lost", "name": "Closed Lost", "color": "#EF4444", "order": 10},
]


class CRMPipelineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_pipeline_kanban(
        self,
        broker_id: uuid.UUID,
        organization_id: str,
        assigned_to: Optional[str] = None
    ) -> PipelineKanbanResponse:
        """
        Builds the canonical Kanban pipeline board with columns and cards.
        Computes stage totals and detects revenue risks/stagnation.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch all active deals for broker
        deals_stmt = select(DealTransaction).where(
            DealTransaction.broker_id == broker_id
        )
        deals_res = await self.db.execute(deals_stmt)
        deals = deals_res.scalars().all()
        deal_by_lead: Dict[uuid.UUID, DealTransaction] = {d.lead_id: d for d in deals}

        # 2. Fetch revenue opportunities to mark cards with alerts
        rev_stmt = select(RevenueOpportunity.lead_id).where(
            RevenueOpportunity.broker_id == broker_id,
            RevenueOpportunity.status == "OPEN"
        )
        rev_res = await self.db.execute(rev_stmt)
        leads_with_rev_alerts = set(rev_res.scalars().all())

        # 3. Fetch broker details for name mapping
        broker_res = await self.db.execute(select(Broker).where(Broker.id == broker_id))
        broker = broker_res.scalars().first()
        broker_name = broker.name if broker else "Assigned Agent"

        # 4. Fetch leads
        leads_stmt = select(Lead).where(
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        if assigned_to:
            try:
                target_uuid = uuid.UUID(assigned_to)
                leads_stmt = leads_stmt.where(Lead.broker_id == target_uuid)
            except ValueError:
                pass

        leads_res = await self.db.execute(leads_stmt)
        leads = leads_res.scalars().all()

        # Group cards by stage key
        cards_by_stage: Dict[str, List[PipelineCardDTO]] = {s["key"]: [] for s in STANDARD_PIPELINE_STAGES}
        total_pipeline_value: float = 0.0
        total_active_deals: int = 0

        for lead in leads:
            stage_key = (lead.pipeline_stage or "new").lower()
            if stage_key not in cards_by_stage:
                stage_key = "new"

            deal = deal_by_lead.get(lead.id)
            deal_val: Optional[float] = None
            if deal:
                deal_val = float(deal.agreed_price)
            elif lead.budget_max:
                deal_val = float(lead.budget_max)
            elif lead.budget_min:
                deal_val = float(lead.budget_min)

            if deal_val and stage_key not in ("won", "lost"):
                total_pipeline_value += deal_val
                total_active_deals += 1

            created_at = lead.created_at
            if created_at and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_days = (now - created_at).days if created_at else 0
            has_alert = lead.id in leads_with_rev_alerts

            card = PipelineCardDTO(
                id=str(deal.id) if deal else str(lead.id),
                lead_id=str(lead.id),
                deal_id=str(deal.id) if deal else None,
                customer_name=lead.name or "Unnamed Lead",
                phone=lead.phone,
                email=lead.email,
                stage=stage_key,
                score=lead.score or "pending",
                property_interest=lead.property_type,
                owner_id=str(lead.broker_id),
                owner_name=broker_name,
                deal_value=deal_val,
                currency=lead.budget_currency or "AED",
                age_days=age_days,
                last_activity_at=lead.updated_at,
                next_action=None,
                has_revenue_alert=has_alert
            )
            cards_by_stage[stage_key].append(card)

        # Build column DTOs
        columns: List[PipelineColumnDTO] = []
        for s in STANDARD_PIPELINE_STAGES:
            st_cards = cards_by_stage[s["key"]]
            col_val = sum(c.deal_value for c in st_cards if c.deal_value is not None)
            columns.append(
                PipelineColumnDTO(
                    stage_key=s["key"],
                    stage_name=s["name"],
                    order_index=s["order"],
                    color=s["color"],
                    total_cards=len(st_cards),
                    total_pipeline_value=col_val,
                    cards=st_cards
                )
            )

        return PipelineKanbanResponse(
            total_pipeline_value=total_pipeline_value,
            total_active_deals=total_active_deals,
            columns=columns
        )
