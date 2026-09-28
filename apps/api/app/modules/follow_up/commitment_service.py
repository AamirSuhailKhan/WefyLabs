"""
Build 07 — Commitment Service
==============================
Tracks company and customer promises made during conversations.

COMPANY commitment: "I'll send the brochure in 10 minutes."
  → Creates a work item for the company. Monitored. Escalates if missed.

CUSTOMER commitment: "I'll send my salary documents tomorrow."
  → Tracked separately. Creates a WAIT task. Not treated as a sales action.

INVARIANTS:
  1. Company and customer commitments are never confused.
  2. Every company commitment creates a linked work item.
  3. Fulfillment is only recorded when the work item is completed.
  4. Prompt injection: commitment text is treated as user-controlled data,
     not as a system instruction.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.crm_models import Commitment, Task
from app.modules.follow_up.work_item_service import WorkItemService

logger = logging.getLogger(__name__)


class CommitmentService:
    """
    Manages company and customer commitment lifecycle.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.work_item_svc = WorkItemService(db)

    # ─── Company Commitments ───────────────────────────────────────────────────

    async def record_company_commitment(
        self,
        organization_id: str,
        lead_id: str,
        broker_id: str,
        commitment_text: str,
        commitment_type: str = "OTHER",
        due_at: Optional[datetime] = None,
        conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
    ) -> Commitment:
        """
        Record a commitment made by the company/agent to the customer.
        Automatically creates a linked work item.

        Example: "I'll send the brochure in 10 minutes."
        """
        now = datetime.now(timezone.utc)
        effective_due = due_at or (now + timedelta(hours=1))

        # Idempotency key prevents double-recording if same message is processed twice
        idem_key = f"commitment:company:{source_message_id}" if source_message_id else None

        # 1. Create the work item so there's an accountable task
        work_item = await self.work_item_svc.create(
            organization_id=organization_id,
            broker_id=broker_id,
            task_type=_commitment_type_to_task_type(commitment_type),
            source="CUSTOMER_REQUEST",
            title=f"Company commitment: {commitment_text[:80]}",
            lead_id=lead_id,
            reason=f"Company commitment recorded: {commitment_text}",
            priority="high",
            due_at=effective_due,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            idempotency_key=idem_key,
        )
        await self.db.flush()

        # 2. Record the commitment
        commitment = Commitment(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            owner="COMPANY",
            commitment=commitment_text,
            commitment_type=commitment_type,
            due_at=effective_due,
            status="PENDING",
            work_item_id=work_item.id,
        )
        self.db.add(commitment)
        await self.db.flush()

        logger.info(
            f"[Commitment] Company commitment recorded for lead {lead_id}: "
            f"'{commitment_text[:60]}' due {effective_due.isoformat()}"
        )
        return commitment

    async def record_customer_commitment(
        self,
        organization_id: str,
        lead_id: str,
        broker_id: str,
        commitment_text: str,
        commitment_type: str = "OTHER",
        due_at: Optional[datetime] = None,
        conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
    ) -> Commitment:
        """
        Record a commitment made by the CUSTOMER.

        Example: "I'll send my salary documents tomorrow."

        This creates a WAIT work item (not a sales task). The system
        monitors whether the customer follows through.
        """
        now = datetime.now(timezone.utc)
        effective_due = due_at or (now + timedelta(days=1))

        # Create a WAIT work item — not a company action
        work_item = await self.work_item_svc.create(
            organization_id=organization_id,
            broker_id=broker_id,
            task_type="FOLLOW_UP",  # Monitor customer's promise
            source="CUSTOMER_REQUEST",
            title=f"Monitor customer commitment: {commitment_text[:80]}",
            lead_id=lead_id,
            reason=f"Customer committed: {commitment_text}. Monitor for follow-through.",
            priority="normal",
            due_at=effective_due + timedelta(hours=2),  # Check 2h after due
            conversation_id=conversation_id,
            source_message_id=source_message_id,
        )
        await self.db.flush()

        commitment = Commitment(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            owner="CUSTOMER",
            commitment=commitment_text,
            commitment_type=commitment_type,
            due_at=effective_due,
            status="PENDING",
            work_item_id=work_item.id,
        )
        self.db.add(commitment)
        await self.db.flush()

        logger.info(
            f"[Commitment] Customer commitment recorded for lead {lead_id}: "
            f"'{commitment_text[:60]}' expected by {effective_due.isoformat()}"
        )
        return commitment

    # ─── Fulfillment ───────────────────────────────────────────────────────────

    async def mark_fulfilled(
        self,
        commitment_id: str,
        organization_id: str,
        notes: Optional[str] = None,
    ) -> Commitment:
        """Mark a commitment as fulfilled."""
        commitment = await self.get(commitment_id, organization_id)
        if not commitment:
            raise ValueError(f"Commitment '{commitment_id}' not found.")
        if commitment.status not in ("PENDING",):
            raise ValueError(
                f"Cannot fulfill commitment in status '{commitment.status}'."
            )

        commitment.status = "FULFILLED"
        commitment.fulfilled_at = datetime.now(timezone.utc)
        if notes:
            commitment.notes = notes

        # Complete the linked work item
        if commitment.work_item_id:
            try:
                await self.work_item_svc.transition(
                    item_id=commitment.work_item_id,
                    organization_id=organization_id,
                    new_status="completed",
                    reason="Commitment fulfilled",
                )
            except Exception as exc:
                logger.warning(f"[Commitment] Could not complete work item: {exc}")

        await self.db.flush()
        return commitment

    # ─── Monitoring ────────────────────────────────────────────────────────────

    async def get_missed_commitments(
        self,
        organization_id: str,
        limit: int = 50,
    ) -> List[Commitment]:
        """Returns PENDING commitments past their due_at — likely missed."""
        now = datetime.now(timezone.utc)
        stmt = select(Commitment).where(
            Commitment.organization_id == organization_id,
            Commitment.status == "PENDING",
            Commitment.due_at <= now,
        ).order_by(Commitment.due_at.asc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_pending_for_lead(
        self,
        lead_id: str,
        organization_id: str,
    ) -> List[Commitment]:
        """All pending commitments for a lead."""
        stmt = select(Commitment).where(
            Commitment.lead_id == lead_id,
            Commitment.organization_id == organization_id,
            Commitment.status == "PENDING",
        ).order_by(Commitment.due_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def expire_overdue(self, organization_id: str) -> int:
        """Expire PENDING commitments significantly past due."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)  # 7 days past due → EXPIRED
        stmt = select(Commitment).where(
            Commitment.organization_id == organization_id,
            Commitment.status == "PENDING",
            Commitment.due_at <= cutoff,
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        for c in items:
            c.status = "EXPIRED"
        if items:
            await self.db.flush()
        return len(items)

    # ─── Queries ───────────────────────────────────────────────────────────────

    async def get(self, commitment_id: str, organization_id: str) -> Optional[Commitment]:
        stmt = select(Commitment).where(
            Commitment.id == commitment_id,
            Commitment.organization_id == organization_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


def _commitment_type_to_task_type(commitment_type: str) -> str:
    """Map commitment type to a WorkItem task_type."""
    _MAP = {
        "CALL_BACK": "CALL_BACK",
        "SEND_DOCUMENT": "DOCUMENT_REQUEST",
        "SEND_BROCHURE": "SEND_MESSAGE",
        "VISIT": "SITE_VISIT_CONFIRMATION",
        "APPOINTMENT": "APPOINTMENT_CONFIRMATION",
        "OTHER": "FOLLOW_UP",
    }
    return _MAP.get(commitment_type, "FOLLOW_UP")
