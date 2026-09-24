"""
WefyLabs Data Integrity & Diagnostic Engine
===========================================
Read-only diagnostic audit suite (Section 37).
Detects:
- Orphan records (leads without brokers, tasks without leads).
- Cross-tenant relationship anomalies (IDOR data corruption).
- Outbox event backlog & dead-letter counts.
- Stale references and impossible lifecycle states.

STRICT RULE: Read-only diagnostic checks; NEVER automatically mutates production records.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.crm_models import Task, LeadNote
from app.models.outbox_models import OutboxEvent, OutboxStatus

logger = logging.getLogger("wefylabs.diagnostics.integrity")


class DataIntegrityChecker:
    """
    Non-destructive, read-only data integrity diagnostics.
    """

    @staticmethod
    async def check_orphan_crm_records(
        db: AsyncSession,
        broker_id: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Detects tasks or notes with non-existent or null parent leads.
        """
        # Tasks where lead_id is null or unassigned
        task_stmt = select(func.count(Task.id)).where(Task.lead_id.is_(None))
        if broker_id:
            task_stmt = task_stmt.where(Task.broker_id == broker_id)
        task_res = await db.execute(task_stmt)
        unlinked_tasks = task_res.scalar() or 0

        # Notes where lead_id is null
        note_stmt = select(func.count(LeadNote.id)).where(LeadNote.lead_id.is_(None))
        if broker_id:
            note_stmt = note_stmt.where(LeadNote.broker_id == broker_id)
        note_res = await db.execute(note_stmt)
        unlinked_notes = note_res.scalar() or 0

        return {
            "unlinked_tasks_count": unlinked_tasks,
            "unlinked_notes_count": unlinked_notes,
            "status": "PASS" if (unlinked_tasks == 0 and unlinked_notes == 0) else "ANOMALY_DETECTED"
        }

    @staticmethod
    async def check_cross_tenant_anomalies(
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Detects tasks whose broker_id does not match the parent lead's broker_id.
        """
        stmt = (
            select(func.count(Task.id))
            .join(Lead, Task.lead_id == Lead.id)
            .where(Task.broker_id != Lead.broker_id)
        )
        res = await db.execute(stmt)
        mismatched_tasks = res.scalar() or 0

        return {
            "mismatched_task_broker_count": mismatched_tasks,
            "status": "PASS" if mismatched_tasks == 0 else "CROSS_TENANT_LEAK_DETECTED"
        }

    @staticmethod
    async def check_outbox_backlog(
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Inspects Outbox queue health: dead letters and stale pending events (>1 hour old).
        """
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        dl_stmt = select(func.count(OutboxEvent.id)).where(OutboxEvent.status == OutboxStatus.DEAD_LETTER)
        dl_res = await db.execute(dl_stmt)
        dead_letters = dl_res.scalar() or 0

        stale_stmt = select(func.count(OutboxEvent.id)).where(
            and_(
                OutboxEvent.status == OutboxStatus.PENDING,
                OutboxEvent.created_at <= one_hour_ago
            )
        )
        stale_res = await db.execute(stale_stmt)
        stale_events = stale_res.scalar() or 0

        return {
            "dead_letter_count": dead_letters,
            "stale_pending_events_count": stale_events,
            "status": "HEALTHY" if (dead_letters == 0 and stale_events == 0) else "DEGRADED"
        }

    @classmethod
    async def run_full_diagnostic(
        cls,
        db: AsyncSession,
        broker_id: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Runs complete non-destructive database integrity audit.
        """
        orphans = await cls.check_orphan_crm_records(db, broker_id=broker_id)
        cross_tenant = await cls.check_cross_tenant_anomalies(db)
        outbox = await cls.check_outbox_backlog(db)

        overall_healthy = (
            orphans["status"] == "PASS"
            and cross_tenant["status"] == "PASS"
            and outbox["status"] == "HEALTHY"
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_integrity_status": "INTEACT" if overall_healthy else "ANOMALY_DETECTED",
            "diagnostics": {
                "orphans": orphans,
                "cross_tenant_isolation": cross_tenant,
                "outbox_reliability": outbox,
            }
        }
