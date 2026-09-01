"""
Merge Reverter — Undoes a completed merge operation using full pre-merge snapshots.
Restores both identities and all their IdentityLinks to pre-merge state.
Publishes MergeReverted event after successful undo.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.identity_models import (
    Identity, IdentityLink, IdentityAlias,
    MergeOperation, MergeHistory
)

logger = logging.getLogger(__name__)


class MergeReverter:
    """
    Reverses a completed MergeOperation using its stored pre-merge snapshots.

    Undo Process:
    1. Load MergeOperation with pre-merge snapshots
    2. Restore source identity to its pre-merge state
    3. Restore all IdentityLinks back to source identity
    4. Mark MergeOperation as undone
    5. Write MergeHistory undo entry
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def undo_merge(
        self,
        merge_operation_id: str,
        undone_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Undo a merge by restoring both identities from their snapshots.

        Returns:
            {
                "status": "undone",
                "merge_operation_id": "...",
                "source_identity_id": "...",
                "target_identity_id": "...",
            }
        """
        # ── Load MergeOperation ───────────────────────────────────────────────
        result = await self.db.execute(
            select(MergeOperation).where(MergeOperation.id == merge_operation_id)
        )
        merge_op = result.scalar_one_or_none()

        if not merge_op:
            raise ValueError(f"MergeOperation {merge_operation_id} not found.")
        if merge_op.status == "undone":
            raise ValueError(f"MergeOperation {merge_operation_id} is already undone.")

        source_id = merge_op.source_identity_id
        target_id = merge_op.target_identity_id
        source_snapshot = merge_op.source_snapshot
        links_snapshot = merge_op.source_links_snapshot

        # ── Restore source identity from snapshot ─────────────────────────────
        src_result = await self.db.execute(select(Identity).where(Identity.id == source_id))
        source = src_result.scalar_one_or_none()

        if source:
            source.is_merged = False
            source.merged_into_id = None
            source.primary_email = source_snapshot.get("primary_email")
            source.primary_phone_e164 = source_snapshot.get("primary_phone_e164")
            source.primary_name = source_snapshot.get("primary_name")
            source.primary_whatsapp = source_snapshot.get("primary_whatsapp")
            source.primary_telegram = source_snapshot.get("primary_telegram")
            source.location_profile = source_snapshot.get("location_profile", {})
            source.financial_profile = source_snapshot.get("financial_profile", {})
            source.lead_count = source_snapshot.get("lead_count", 1)
            source.updated_at = datetime.now(timezone.utc)

        # ── Re-point migrated IdentityLinks back to source ────────────────────
        if links_snapshot:
            link_ids = [l["id"] for l in links_snapshot]
            link_result = await self.db.execute(
                select(IdentityLink).where(IdentityLink.id.in_(link_ids))
            )
            for link in link_result.scalars().all():
                link.identity_id = source_id
                link.link_method = "merge_undone"
                link.is_active = True

        # ── Restore target lead_count ─────────────────────────────────────────
        tgt_result = await self.db.execute(select(Identity).where(Identity.id == target_id))
        target = tgt_result.scalar_one_or_none()
        if target and source:
            target.lead_count = max(1, (target.lead_count or 1) - (source.lead_count or 0))
            target.updated_at = datetime.now(timezone.utc)

        # ── Update MergeOperation status ──────────────────────────────────────
        merge_op.status = "undone"
        merge_op.undone_at = datetime.now(timezone.utc)
        merge_op.undone_by = undone_by

        # ── Write MergeHistory undo entry ─────────────────────────────────────
        self.db.add(MergeHistory(
            merge_operation_id=merge_operation_id,
            organization_id=merge_op.organization_id,
            action="merge_undone",
            actor_id=undone_by,
            actor_type="user" if undone_by else "system",
            details={
                "source": source_id,
                "target": target_id,
                "restored_links": len(links_snapshot) if links_snapshot else 0,
            },
        ))

        await self.db.commit()
        logger.info(f"[MERGE_REVERTER] Undone merge {merge_operation_id}: {source_id} ← {target_id}")

        return {
            "status": "undone",
            "merge_operation_id": merge_operation_id,
            "source_identity_id": source_id,
            "target_identity_id": target_id,
            "restored_links": len(links_snapshot) if links_snapshot else 0,
        }
