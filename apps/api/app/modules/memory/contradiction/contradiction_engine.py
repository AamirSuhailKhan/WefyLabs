"""
Contradiction Detection & Versioning Engine
===========================================
Detects conflicting facts for a customer key (e.g. Budget AED 2M -> AED 2.5M).
Enforces hierarchy rules and archives superseded states into immutable MemoryVersion records.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.memory_models import MemoryRecord, MemoryVersion, MemoryAuditLog
from app.modules.memory.provenance.provenance_tracker import ProvenanceTracker

logger = logging.getLogger(__name__)

class ContradictionResolutionResult:
    def __init__(
        self,
        action_taken: str,  # CREATED | SUPERSEDED | REJECTED_LOW_RANK | MERGED
        active_record: MemoryRecord,
        archived_version: Optional[MemoryVersion] = None,
        reason: Optional[str] = None
    ):
        self.action_taken = action_taken
        self.active_record = active_record
        self.archived_version = archived_version
        self.reason = reason


class ContradictionEngine:
    """
    Handles contradiction resolution, version archiving, and priority enforcement.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconcile_memory(
        self,
        organization_id: str,
        lead_id: str,
        memory_type: str,
        key: str,
        new_value_json: Dict[str, Any],
        new_value_text: Optional[str] = None,
        source_type: str = "CUSTOMER_STATED",
        source_id: Optional[str] = None,
        confidence: Optional[float] = None,
        importance: float = 0.80,
        is_customer_safe: bool = True,
        actor: str = "system"
    ) -> ContradictionResolutionResult:
        """
        Reconciles incoming memory with existing active memory for (lead_id, key).
        """
        calc_confidence = confidence or ProvenanceTracker.get_default_confidence(source_type)

        # 1. Fetch active record if exists
        stmt = select(MemoryRecord).where(
            and_(
                MemoryRecord.organization_id == organization_id,
                MemoryRecord.lead_id == lead_id,
                MemoryRecord.key == key,
                MemoryRecord.status == "ACTIVE"
            )
        )
        res = await self.db.execute(stmt)
        existing: Optional[MemoryRecord] = res.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if not existing:
            # Create new master memory record
            rec = MemoryRecord(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                lead_id=lead_id,
                memory_type=memory_type,
                key=key,
                value_json=new_value_json,
                value_text=new_value_text,
                source_type=source_type,
                source_id=source_id,
                confidence=calc_confidence,
                importance=importance,
                status="ACTIVE",
                version_number=1,
                is_customer_safe=is_customer_safe,
                valid_from=now
            )
            self.db.add(rec)

            audit = MemoryAuditLog(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                lead_id=lead_id,
                memory_record_id=rec.id,
                action="CREATED",
                actor=actor,
                reason=f"Initial memory record created for key '{key}' from {source_type}",
                changes_json={"new_value": new_value_json}
            )
            self.db.add(audit)
            await self.db.commit()
            await self.db.refresh(rec)
            return ContradictionResolutionResult("CREATED", rec)

        # 2. Check identical value (Deduplication / Confirmation)
        if existing.value_json == new_value_json:
            existing.last_confirmed_at = now
            existing.confidence = min(1.0, existing.confidence + 0.02)
            await self.db.commit()
            await self.db.refresh(existing)
            return ContradictionResolutionResult("MERGED", existing, reason="Value matched existing memory; confirmed and boosted confidence.")

        # 3. Check Rank Override Permission
        can_override = ProvenanceTracker.can_source_override(source_type, existing.source_type)
        if not can_override:
            logger.info(f"[CONTRADICTION] Rejected lower-rank source '{source_type}' from overriding '{existing.source_type}' for key '{key}'.")
            return ContradictionResolutionResult(
                "REJECTED_LOW_RANK",
                existing,
                reason=f"Source '{source_type}' (Rank {ProvenanceTracker.get_source_rank(source_type)}) cannot override existing '{existing.source_type}' (Rank {ProvenanceTracker.get_source_rank(existing.source_type)})."
            )

        # 4. Supersede and Archive Old Version
        archived_ver = MemoryVersion(
            id=str(uuid.uuid4()),
            memory_record_id=existing.id,
            version_number=existing.version_number,
            value_json=existing.value_json,
            value_text=existing.value_text,
            source_type=existing.source_type,
            source_id=existing.source_id,
            confidence=existing.confidence,
            status="CONTRADICTED",
            reason_for_change=f"Superseded by {source_type} update: {new_value_text or new_value_json}",
            superseded_at=now
        )
        self.db.add(archived_ver)

        # Update Master Record to New State
        existing.value_json = new_value_json
        existing.value_text = new_value_text
        existing.source_type = source_type
        existing.source_id = source_id
        existing.confidence = calc_confidence
        existing.importance = importance
        existing.version_number += 1
        existing.is_customer_safe = is_customer_safe
        existing.updated_at = now

        audit = MemoryAuditLog(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            memory_record_id=existing.id,
            action="CONTRADICTED",
            actor=actor,
            reason=f"Memory updated to v{existing.version_number} via {source_type}",
            changes_json={
                "old_version": archived_ver.version_number,
                "old_value": archived_ver.value_json,
                "new_version": existing.version_number,
                "new_value": new_value_json
            }
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(existing)
        logger.info(f"[CONTRADICTION] Superseded key '{key}' for lead '{lead_id}' (v{existing.version_number}).")
        return ContradictionResolutionResult("SUPERSEDED", existing, archived_ver)
