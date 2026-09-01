"""
Human-in-the-Loop Approval & Escalation Service
===============================================
Creates, manages, and resolves human approval gates during workflow execution.
Handles decision timeouts and automated manager escalations.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.workflow_models import WorkflowApproval, WorkflowInstance

logger = logging.getLogger(__name__)

class ApprovalService:
    """
    Manages human approval nodes, decisions, and escalation paths.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_approval_ticket(
        self,
        instance_id: str,
        node_id: str,
        organization_id: str,
        title: str,
        description: str,
        context_summary: Dict[str, Any],
        assigned_role: str = "manager",
        deadline_hours: int = 24
    ) -> WorkflowApproval:
        """
        Creates a pending approval ticket and places the WorkflowInstance into WAITING status.
        """
        deadline = datetime.now(timezone.utc) + timedelta(hours=deadline_hours)
        ticket = WorkflowApproval(
            id=str(uuid.uuid4()),
            workflow_instance_id=instance_id,
            node_id=node_id,
            organization_id=organization_id,
            title=title,
            description=description,
            context_summary=context_summary,
            status="PENDING",
            assigned_role=assigned_role,
            deadline_utc=deadline
        )
        self.db.add(ticket)

        await self.db.execute(
            update(WorkflowInstance)
            .where(WorkflowInstance.id == instance_id)
            .values(status="WAITING", current_node_id=node_id)
        )
        await self.db.commit()
        await self.db.refresh(ticket)
        logger.info(f"[APPROVAL] Created Approval Ticket {ticket.id} for Instance {instance_id} at Node {node_id}.")
        return ticket

    async def decide_approval(
        self,
        approval_id: str,
        decision: str,  # APPROVED | REJECTED
        decided_by: str,
        reason: Optional[str] = None
    ) -> WorkflowApproval:
        """
        Records the human decision and transitions the instance back to RUNNING.
        """
        stmt = select(WorkflowApproval).where(WorkflowApproval.id == approval_id)
        res = await self.db.execute(stmt)
        ticket = res.scalar_one_or_none()
        if not ticket:
            raise ValueError(f"WorkflowApproval '{approval_id}' not found.")

        ticket.status = decision.upper()
        ticket.decision_by = decided_by
        ticket.decision_reason = reason or f"Decided as {decision} by {decided_by}"
        ticket.decision_at = datetime.now(timezone.utc)

        # Transition instance back to RUNNING
        await self.db.execute(
            update(WorkflowInstance)
            .where(WorkflowInstance.id == ticket.workflow_instance_id)
            .values(status="RUNNING")
        )
        await self.db.commit()
        await self.db.refresh(ticket)
        logger.info(f"[APPROVAL] Approval Ticket {approval_id} resolved as {decision} by {decided_by}.")
        return ticket
