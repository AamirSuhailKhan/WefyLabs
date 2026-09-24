"""WefyLabs Native CRM — Lead Lifecycle & Operator Service
=========================================================
Implements operator filtering, safe stage transitions, manual/auto
reassignment, and secure bulk operations with audit and event emission.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc, func

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.crm_models import Activity, Task
from app.models.audit_log import AuditLog
from app.infrastructure.events.event_bus import event_bus, DomainEvent
from app.modules.crm.dto.crm_schemas import (
    LeadCRMListItem, LeadCRMFilterParams, BulkLeadOperationRequest, BulkOperationResult
)


class CRMLeadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_leads(
        self,
        broker_id: uuid.UUID,
        organization_id: str,
        params: LeadCRMFilterParams
    ) -> Tuple[List[LeadCRMListItem], int]:
        """
        Operator table query with multi-faceted filtering, sorting, and pagination.
        """
        stmt = select(Lead).where(
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )

        # Filters
        if params.stage:
            stmt = stmt.where(Lead.pipeline_stage == params.stage.lower())
        if params.status:
            stmt = stmt.where(Lead.status == params.status.lower())
        if params.score:
            stmt = stmt.where(Lead.score == params.score.lower())
        if params.source:
            stmt = stmt.where(Lead.source == params.source)
        if params.property_type:
            stmt = stmt.where(Lead.property_type.ilike(f"%{params.property_type}%"))
        if params.budget_min is not None:
            stmt = stmt.where(Lead.budget_min >= params.budget_min)
        if params.budget_max is not None:
            stmt = stmt.where(Lead.budget_max <= params.budget_max)
        if params.search:
            pat = f"%{params.search.strip()}%"
            stmt = stmt.where(
                or_(
                    Lead.name.ilike(pat),
                    Lead.phone.ilike(pat),
                    Lead.email.ilike(pat)
                )
            )

        # Total count query
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.db.execute(count_stmt)
        total_count = count_res.scalar() or 0

        # Sorting
        sort_col = getattr(Lead, params.sort_by, Lead.created_at)
        if params.sort_order == "asc":
            stmt = stmt.order_by(asc(sort_col))
        else:
            stmt = stmt.order_by(desc(sort_col))

        # Pagination
        stmt = stmt.offset(params.offset).limit(params.limit)
        res = await self.db.execute(stmt)
        leads = res.scalars().all()

        broker_res = await self.db.execute(select(Broker).where(Broker.id == broker_id))
        broker = broker_res.scalars().first()
        broker_name = broker.name if broker else "Assigned Agent"

        items = [
            LeadCRMListItem(
                id=str(l.id),
                name=l.name,
                phone=l.phone,
                email=l.email,
                source=l.source,
                campaign=None,
                score=l.score,
                status=l.status,
                pipeline_stage=l.pipeline_stage,
                budget_min=l.budget_min,
                budget_max=l.budget_max,
                budget_currency=l.budget_currency or "AED",
                preferred_locations=l.preferred_locations or [],
                property_type=l.property_type,
                owner_id=str(l.broker_id),
                owner_name=broker_name,
                sla_status="ON_TRACK",
                last_activity_at=l.updated_at,
                next_action=None,
                created_at=l.created_at,
                updated_at=l.updated_at
            )
            for l in leads
        ]

        return items, total_count

    async def transition_stage(
        self,
        lead_id: str,
        new_stage: str,
        reason: Optional[str],
        broker_id: uuid.UUID,
        organization_id: str
    ) -> Lead:
        """
        Executes a controlled stage transition, updates lead lifecycle, records activity & audit,
        and emits canonical domain event for Revenue Intelligence.
        """
        lead_uuid = uuid.UUID(lead_id)
        stmt = select(Lead).where(
            Lead.id == lead_uuid,
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        res = await self.db.execute(stmt)
        lead = res.scalars().first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found or unauthorized")

        old_stage = lead.pipeline_stage
        clean_new_stage = new_stage.lower()

        # Update stage
        lead.pipeline_stage = clean_new_stage
        lead.updated_at = datetime.now(timezone.utc)

        # Map to high-level status if reached milestone stages
        if clean_new_stage in ("qualified", "matched"):
            lead.status = "qualified"
            if not lead.qualified_at:
                lead.qualified_at = datetime.now(timezone.utc)
        elif clean_new_stage == "won":
            lead.status = "converted"
        elif clean_new_stage == "lost":
            lead.status = "lost"

        # Record activity
        activity = Activity(
            organization_id=organization_id,
            actor_id=broker_id,
            lead_id=lead_uuid,
            activity_type="stage_changed",
            title=f"Stage Changed: {old_stage.upper()} → {clean_new_stage.upper()}",
            description=reason or f"Pipeline progression to {clean_new_stage}",
            activity_data={
                "old_stage": old_stage,
                "new_stage": clean_new_stage,
                "reason": reason
            }
        )
        self.db.add(activity)

        # Record AuditLog
        audit = AuditLog(
            actor_id=broker_id,
            actor_type="user",
            action="lead.stage_changed",
            resource_type="lead",
            resource_id=str(lead.id),
            changes={
                "old_stage": old_stage,
                "new_stage": clean_new_stage,
                "reason": reason
            }
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(lead)

        # Emit canonical domain event for Revenue Intelligence & Autopilot
        try:
            event = DomainEvent(
                event_name="lead.stage_changed",
                payload={
                    "lead_id": str(lead.id),
                    "organization_id": organization_id,
                    "broker_id": str(broker_id),
                    "old_stage": old_stage,
                    "new_stage": clean_new_stage,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            await event_bus.publish(event)
        except Exception:
            pass

        return lead

    async def reassign_lead(
        self,
        lead_id: str,
        target_broker_id: str,
        reason: Optional[str],
        current_broker_id: uuid.UUID,
        organization_id: str
    ) -> Lead:
        """
        Reassigns a lead to a new broker/team, preserves assignment history, audits, and emits event.
        """
        lead_uuid = uuid.UUID(lead_id)
        target_uuid = uuid.UUID(target_broker_id)

        # Verify target broker exists
        tb_res = await self.db.execute(select(Broker).where(Broker.id == target_uuid))
        target_broker = tb_res.scalars().first()
        if not target_broker:
            raise ValueError("Target broker does not exist")

        stmt = select(Lead).where(
            Lead.id == lead_uuid,
            Lead.broker_id == current_broker_id,
            Lead.deleted_at.is_(None)
        )
        res = await self.db.execute(stmt)
        lead = res.scalars().first()
        if not lead:
            raise ValueError("Lead not found or unauthorized")

        old_broker_id = str(lead.broker_id)
        lead.broker_id = target_uuid
        lead.updated_at = datetime.now(timezone.utc)

        activity = Activity(
            organization_id=organization_id,
            actor_id=current_broker_id,
            lead_id=lead_uuid,
            activity_type="lead_reassigned",
            title=f"Lead Reassigned to {target_broker.name}",
            description=reason or "Manual CRM reassignment",
            activity_data={
                "old_broker_id": old_broker_id,
                "new_broker_id": str(target_uuid),
                "reason": reason
            }
        )
        self.db.add(activity)

        audit = AuditLog(
            actor_id=current_broker_id,
            actor_type="user",
            action="lead.reassigned",
            resource_type="lead",
            resource_id=str(lead.id),
            changes={
                "old_broker_id": old_broker_id,
                "new_broker_id": str(target_uuid),
                "reason": reason
            }
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(lead)

        try:
            event = DomainEvent(
                event_name="lead.assigned",
                payload={
                    "lead_id": str(lead.id),
                    "old_broker_id": old_broker_id,
                    "new_broker_id": str(target_uuid),
                    "organization_id": organization_id,
                    "reason": reason
                }
            )
            await event_bus.publish(event)
        except Exception:
            pass

        return lead

    async def execute_bulk_operation(
        self,
        req: BulkLeadOperationRequest,
        broker_id: uuid.UUID,
        organization_id: str
    ) -> BulkOperationResult:
        """
        Executes bounded bulk operations. Verifies ownership of every targeted lead.
        """
        successful: int = 0
        failed: List[Dict[str, Any]] = []

        for lid in req.lead_ids:
            try:
                l_uuid = uuid.UUID(lid)
                lead_res = await self.db.execute(
                    select(Lead).where(Lead.id == l_uuid, Lead.broker_id == broker_id, Lead.deleted_at.is_(None))
                )
                lead = lead_res.scalars().first()
                if not lead:
                    failed.append({"lead_id": lid, "reason": "Record not found or access denied"})
                    continue

                if req.operation == "change_stage":
                    new_stage = req.params.get("stage", "contacted")
                    lead.pipeline_stage = str(new_stage).lower()
                    lead.updated_at = datetime.now(timezone.utc)
                elif req.operation == "change_priority":
                    new_score = req.params.get("score", "warm")
                    lead.score = str(new_score).lower()
                    lead.updated_at = datetime.now(timezone.utc)
                elif req.operation == "create_task":
                    task_title = req.params.get("title", "Bulk Task")
                    task = Task(
                        broker_id=broker_id,
                        lead_id=l_uuid,
                        organization_id=organization_id,
                        title=task_title,
                        due_at=datetime.now(timezone.utc)
                    )
                    self.db.add(task)
                elif req.operation == "assign":
                    target_id = req.params.get("target_broker_id")
                    if target_id:
                        lead.broker_id = uuid.UUID(target_id)
                        lead.updated_at = datetime.now(timezone.utc)

                successful += 1
            except Exception as e:
                failed.append({"lead_id": lid, "reason": str(e)})

        await self.db.commit()

        # Audit bulk execution
        audit = AuditLog(
            actor_id=broker_id,
            actor_type="user",
            action=f"lead.bulk_{req.operation}",
            resource_type="lead_bulk",
            resource_id=f"bulk_{len(req.lead_ids)}",
            changes={
                "operation": req.operation,
                "target_count": len(req.lead_ids),
                "successful": successful,
                "failed": len(failed)
            }
        )
        self.db.add(audit)
        await self.db.commit()

        return BulkOperationResult(
            operation=req.operation,
            total_requested=len(req.lead_ids),
            successful_count=successful,
            failed_count=len(failed),
            failed_items=failed,
            audit_id=str(audit.id) if hasattr(audit, "id") else None
        )
