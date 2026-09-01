"""
Durable Wait State & Timer Management Engine
============================================
Manages durable pauses for workflow instances waiting for durations, specific dates,
or asynchronous domain events (e.g. CustomerResponse, PropertyViewed).
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.workflow_models import WorkflowWaitState, WorkflowInstance

logger = logging.getLogger(__name__)

class WaitManager:
    """
    Creates and resolves durable wait records.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_wait_state(
        self,
        instance_id: str,
        node_id: str,
        wait_type: str,  # DURATION | DATE | EVENT_WAIT
        duration_minutes: Optional[int] = None,
        deadline_utc: Optional[datetime] = None,
        expected_event: Optional[str] = None
    ) -> WorkflowWaitState:
        """
        Creates a persisted wait record and transitions WorkflowInstance status to 'WAITING'.
        """
        now = datetime.now(timezone.utc)
        if duration_minutes:
            resume_time = now + timedelta(minutes=duration_minutes)
        elif deadline_utc:
            resume_time = deadline_utc
        else:
            resume_time = now + timedelta(hours=24)  # Default 24h fallback

        wait_state = WorkflowWaitState(
            id=str(uuid.uuid4()),
            workflow_instance_id=instance_id,
            node_id=node_id,
            wait_type=wait_type,
            expected_event=expected_event,
            resume_deadline_utc=resume_time,
            is_resumed=False
        )
        self.db.add(wait_state)

        # Update instance state to WAITING
        await self.db.execute(
            update(WorkflowInstance)
            .where(WorkflowInstance.id == instance_id)
            .values(status="WAITING", current_node_id=node_id)
        )
        await self.db.commit()
        await self.db.refresh(wait_state)
        logger.info(f"[WAIT_MANAGER] WorkflowInstance {instance_id} paused at node {node_id} (Resume at {resume_time.isoformat()}).")
        return wait_state

    async def resolve_due_waits(self) -> List[WorkflowWaitState]:
        """
        Queries all expired timer wait records and marks them as resumed.
        """
        now = datetime.now(timezone.utc)
        stmt = select(WorkflowWaitState).where(
            and_(
                WorkflowWaitState.is_resumed == False,
                WorkflowWaitState.resume_deadline_utc <= now
            )
        )
        res = await self.db.execute(stmt)
        due_waits = list(res.scalars().all())

        for w in due_waits:
            w.is_resumed = True
            w.resumed_at = now
            # Transition instance back to RUNNING
            await self.db.execute(
                update(WorkflowInstance)
                .where(WorkflowInstance.id == w.workflow_instance_id)
                .values(status="RUNNING")
            )

        if due_waits:
            await self.db.commit()
            logger.info(f"[WAIT_MANAGER] Resumed {len(due_waits)} due workflow wait state(s).")
        return due_waits
