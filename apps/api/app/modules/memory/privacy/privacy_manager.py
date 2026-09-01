"""
Privacy, PII Protection & GDPR Right to Delete Manager
======================================================
Manages privacy compliance, PII masking, and deletion requests with complete audit logs.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete, update

from app.models.memory_models import (
    MemoryRecord, MemoryVersion, MemoryEvidence,
    MemoryAuditLog, MemoryDeletionRequest
)

logger = logging.getLogger(__name__)

class PrivacyManager:
    """
    Executes customer memory deletion requests and creates privacy audit records.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_lead_deletion_request(
        self,
        organization_id: str,
        lead_id: str,
        requested_by: str
    ) -> MemoryDeletionRequest:
        """
        Purges memory records for a lead in accordance with GDPR/CCPA.
        """
        now = datetime.now(timezone.utc)

        # 1. Count records to delete
        stmt = select(MemoryRecord).where(
            and_(
                MemoryRecord.organization_id == organization_id,
                MemoryRecord.lead_id == lead_id
            )
        )
        res = await self.db.execute(stmt)
        records = list(res.scalars().all())
        del_count = len(records)

        # 2. Hard delete or mark DELETED
        await self.db.execute(
            delete(MemoryRecord).where(
                and_(
                    MemoryRecord.organization_id == organization_id,
                    MemoryRecord.lead_id == lead_id
                )
            )
        )

        # 3. Create Deletion Request & Audit Log
        req = MemoryDeletionRequest(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            requested_by=requested_by,
            status="COMPLETED",
            records_deleted_count=del_count,
            completed_at=now
        )
        self.db.add(req)

        audit = MemoryAuditLog(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            action="DELETED",
            actor=requested_by,
            reason="GDPR/CCPA Lead Memory Purge Request",
            changes_json={"purged_records_count": del_count}
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(req)

        logger.info(f"[PRIVACY] Purged {del_count} memory record(s) for lead '{lead_id}' (Org: {organization_id}).")
        return req
